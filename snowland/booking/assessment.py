"""Tenant rubric and daily technical assessments on existing learner records."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from Client.models import SiteContent


RUBRIC_LOCATION = 'internal.course-assessment'
TECHNICAL_KEY = 'technical_skills'
DISCIPLINES = ('snowboard', 'ski')
RATINGS = ('1', '2', '3')


def _rows(value, limit):
    if not isinstance(value, list) or len(value) > limit or any(not isinstance(row, dict) for row in value):
        raise ValueError('評量設定清單格式不正確或超過上限')
    return value


def _title(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 100:
        raise ValueError('請填寫名稱，最多 100 字')
    return value.strip()


def _unique_id(value, seen):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9-]{1,50}', value) or value in seen:
        raise ValueError('評量項目代碼不正確或重複')
    seen.add(value)
    return value


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('評分或等級超出範圍')
    return value


def validate_rubric(value):
    if not isinstance(value, dict):
        raise ValueError('評量設定格式不正確')
    raw_ratings = value.get('ratings')
    raw_disciplines = value.get('disciplines')
    if not isinstance(raw_ratings, dict) or set(raw_ratings) != set(RATINGS):
        raise ValueError('請設定三個評分名稱')
    if not isinstance(raw_disciplines, dict) or set(raw_disciplines) != set(DISCIPLINES):
        raise ValueError('請分別設定單板及雙板')
    ratings = {rating: _title(raw_ratings[rating]) for rating in RATINGS}
    if len(set(ratings.values())) != 3:
        raise ValueError('評分名稱不能重複')
    disciplines = {}
    for name in DISCIPLINES:
        item = raw_disciplines[name]
        if not isinstance(item, dict):
            raise ValueError('單板或雙板的設定格式不正確')
        sections, rules, section_ids, skill_ids = [], [], set(), set()
        for section in _rows(item.get('sections'), 12):
            sections.append({
                'id': _unique_id(section.get('id'), section_ids),
                'title': _title(section.get('title')),
                'skills': [
                    {'id': _unique_id(skill.get('id'), skill_ids), 'title': _title(skill.get('title'))}
                    for skill in _rows(section.get('skills'), 50)
                ],
            })
        if not skill_ids or len(skill_ids) > 100:
            raise ValueError('單板及雙板各需設定 1 至 100 個項目')
        for rule in _rows(item.get('rules'), 30):
            conditions = _rows(rule.get('criteria'), 100)
            match = rule.get('match')
            if match not in ('any', 'all') or not conditions:
                raise ValueError('每條升級規則須設定至少一項技術及達成方式')
            criteria, seen = [], set()
            for condition in conditions:
                skill = _unique_id(condition.get('skill'), seen)
                if skill not in skill_ids:
                    raise ValueError('升級規則引用了不存在的技術項目')
                criteria.append({'skill': skill, 'rating': _integer(condition.get('rating'), 1, 3)})
            rules.append({'level': _integer(rule.get('level'), 1, 6), 'match': match, 'criteria': criteria})
        disciplines[name] = {'entry_level': _integer(item.get('entry_level'), 0, 6), 'sections': sections, 'rules': rules}
    return {'ratings': ratings, 'disciplines': disciplines}


@lru_cache(maxsize=1)
def default_rubric():
    path = Path(__file__).parent / 'data' / 'assessment_rubric.json'
    return validate_rubric(json.loads(path.read_text(encoding='utf-8')))


def rubric_revision(rubric):
    return hashlib.sha256(json.dumps(rubric, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def school_rubric(tenant):
    row = SiteContent.objects.filter(client=tenant, content_type='setting', location_key=RUBRIC_LOCATION).first()
    rubric = row.metadata if row else default_rubric()
    return {'revision': rubric_revision(rubric), 'rubric': rubric}


def technical_snapshot(evaluation):
    data = evaluation.coach_assessment if evaluation else {}
    return data.get(TECHNICAL_KEY) if isinstance(data, dict) else None


def validate_review(value, current):
    if not isinstance(value, dict) or value.get('revision') != current['revision']:
        raise ValueError('評量設定已更新，請重新載入後再填寫')
    raw_entries = value.get('entries')
    if not isinstance(raw_entries, dict) or set(raw_entries) - set(DISCIPLINES):
        raise ValueError('請選擇正確的評量類別')
    entries = {}
    for discipline, entry in raw_entries.items():
        skills = {skill['id'] for section in current['rubric']['disciplines'][discipline]['sections'] for skill in section['skills']}
        if not isinstance(entry, dict):
            raise ValueError('評量資料格式不正確')
        scores = entry.get('scores', {})
        next_steps = entry.get('next_steps', [])
        if (not isinstance(scores, dict) or set(scores) - skills or not isinstance(next_steps, list)
                or len(next_steps) > len(skills) or any(not isinstance(key, str) or key not in skills for key in next_steps)):
            raise ValueError('評量包含這份表單沒有的技術項目')
        if scores or next_steps:
            entries[discipline] = {'scores': {key: _integer(score, 1, 3) for key, score in scores.items()},
                                   'next_steps': list(dict.fromkeys(next_steps))}
    return {**current, 'entries': entries}


def achieved_level(discipline, scores):
    matched = [discipline['entry_level']] if scores else [0]
    for rule in discipline['rules']:
        matches = (scores.get(item['skill'], 0) >= item['rating'] for item in rule['criteria'])
        if (all(matches) if rule['match'] == 'all' else any(matches)):
            matched.append(rule['level'])
    return max(matched)


def learning_reports(evaluations):
    results, best = {}, {}
    for evaluation in sorted(evaluations, key=lambda row: (row.booking.date, row.booking.start_time, row.pk)):
        snapshot = technical_snapshot(evaluation)
        if not snapshot or not evaluation.completed_at:
            continue
        rubric = snapshot['rubric']
        for discipline, entry in snapshot['entries'].items():
            config = rubric['disciplines'][discipline]
            items = {item['id']: item['title'] for section in config['sections'] for item in section['skills']}
            scores = best.setdefault((evaluation.member_id, discipline), {})
            for skill, score in entry['scores'].items():
                scores[skill] = max(scores.get(skill, 0), score)
            results.setdefault(evaluation.pk, []).append({
                'discipline': discipline,
                'level': achieved_level(config, {key: score for key, score in scores.items() if key in items}),
                'scores': [{'title': title, 'rating': rubric['ratings'][str(entry['scores'][key])]}
                           for key, title in items.items() if key in entry['scores']],
                'next_steps': [items[key] for key in entry['next_steps']],
            })
    return results
