from Client.models import SiteContent

from .models import MemberDetail
from .pre_course_questions import (
    EXPERIENCE_AREAS, EXPERIENCE_BOARD_CHOICES, EXPERIENCE_KIND_CHOICES, EXPERIENCE_RECENT_CHOICES,
)


COACH_SUMMARY_LOCATION = 'coach.pre_course_summary'
MAX_LABEL_LENGTH = 60
STATUS_LABELS = {'empty': '未填', 'incomplete': '未完成', 'filled': '已填'}
DEFAULT_FIELDS = {
    'status': '完成狀態',
    'kind': '新／舊生',
    'recent': '近期經驗',
    'boards': '板種',
    'notes': '滑行困難',
    'skills': '技能',
    'age_range': '年齡',
}


def default_summary_fields():
    return [
        {'key': key, 'label': label, 'order': order, 'visible': key != 'notes'}
        for order, (key, label) in enumerate(DEFAULT_FIELDS.items(), 1)
    ]


def validate_summary_fields(fields):
    if not isinstance(fields, list) or len(fields) > len(DEFAULT_FIELDS):
        raise ValueError('請提供有效的課前摘要欄位清單')
    seen = set()
    cleaned = []
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError('課前摘要欄位格式不正確')
        key, label, order, visible = (field.get(name) for name in ('key', 'label', 'order', 'visible'))
        if not isinstance(key, str) or key not in DEFAULT_FIELDS or key in seen:
            raise ValueError('課前摘要欄位不支援或重複')
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= MAX_LABEL_LENGTH:
            raise ValueError(f'課前摘要標籤須為 1 至 {MAX_LABEL_LENGTH} 字')
        if type(order) is not int or type(visible) is not bool:
            raise ValueError('課前摘要順序須為整數，顯示設定須為布林值')
        seen.add(key)
        cleaned.append({'key': key, 'label': label.strip(), 'order': order, 'visible': visible})
    return sorted(cleaned, key=lambda field: field['order'])


def summary_settings(client_id):
    return SiteContent.objects.filter(client_id=client_id, content_type='setting', location_key=COACH_SUMMARY_LOCATION)


def configured_summary_fields(setting):
    if setting and isinstance(setting.metadata, dict):
        try:
            return validate_summary_fields(setting.metadata.get('fields'))
        except ValueError:
            pass
    return default_summary_fields()


def experience_assessment_enabled(client):
    return client.internal_code == 'snowland' or summary_settings(client.pk).exists()


def _choice_label(choices, value):
    return dict(choices).get(value) if isinstance(value, str) else None


def _selected_labels(choices, values):
    return [label for key, label in choices if key in values] if isinstance(values, (list, tuple)) else []


def member_pre_course_summary(member, fields):
    answers = member.pre_course_answers
    experience = answers.get('experience') if isinstance(answers, dict) else None
    if not isinstance(experience, dict):
        experience = {}

    kind = _choice_label(EXPERIENCE_KIND_CHOICES, experience.get('kind'))
    recent = _choice_label(EXPERIENCE_RECENT_CHOICES, experience.get('recent'))
    boards = _selected_labels(EXPERIENCE_BOARD_CHOICES.items(), experience.get('boards'))
    age = _choice_label(MemberDetail.AGE_CHOICES, member.age_range)
    skills = []
    for board, values, choices in (
        ('snowboard', member.snowboard_skills, MemberDetail.SNOWBOARD_CHOICES),
        ('ski', member.ski_skills, MemberDetail.SKI_CHOICES),
    ):
        labels = _selected_labels(choices, values)
        if labels:
            skills.append(f'{EXPERIENCE_BOARD_CHOICES[board]}：{"、".join(labels)}')

    has_partial_experience = bool(_selected_labels(
        ((area, area) for area in EXPERIENCE_AREAS), experience.get('areas'),
    )) or any(isinstance(experience.get(key), str) and experience[key].strip() for key in ('notes', 'resort'))
    if experience.get('finished') is True:
        status = 'filled'
    elif any((kind, recent, boards, skills, age, has_partial_experience)):
        status = 'incomplete'
    else:
        status = 'empty'

    values = {
        'status': STATUS_LABELS[status],
        'kind': kind,
        'recent': recent,
        'boards': '、'.join(boards) or None,
        'notes': None,  # The stored answer is free text and has no safe option labels.
        'skills': '；'.join(skills) or None,
        'age_range': age,
    }
    return {
        'status': status,
        'status_label': STATUS_LABELS[status],
        'empty_label': STATUS_LABELS['empty'],
        'items': [
            {'key': field['key'], 'label': field['label'], 'value': values[field['key']],
             'filled': values[field['key']] is not None}
            for field in fields if field['visible']
        ],
    }
