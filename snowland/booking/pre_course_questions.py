import re


def validate_questions(questions):
    if not isinstance(questions, list) or len(questions) > 24:
        raise ValueError('課前表單最多可設定 24 題')
    keys = set()
    cleaned = []
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError('課前題目格式不正確')
        key = question.get('key')
        title = question.get('title')
        kind = question.get('kind')
        section = question.get('section')
        required = question.get('required')
        if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9-]{1,40}', key) or key in keys:
            raise ValueError('課前題目識別碼不正確或重複')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 250:
            raise ValueError('請填寫題目文字，最多 250 字')
        if kind not in ('text', 'single', 'multiple') or section not in ('insurance', 'waiver') or type(required) is not bool:
            raise ValueError('請設定題型、表單區塊及是否必填')
        options = question.get('options', [])
        if kind == 'text':
            options = []
        else:
            if not isinstance(options, list) or not 1 <= len(options) <= 15 or any(
                not isinstance(option, str) or not 1 <= len(option.strip()) <= 120 for option in options
            ):
                raise ValueError('選擇題須填寫 1 至 15 個選項，每項最多 120 字')
            options = [option.strip() for option in options]
            if len(options) != len(set(options)):
                raise ValueError('同一題不能有重複選項')
        keys.add(key)
        cleaned.append({'key': key, 'title': title.strip(), 'kind': kind, 'section': section,
                        'required': required, 'options': options})
    return cleaned


def validate_experience_assessment(value):
    if not isinstance(value, dict) or set(value) - {'kind', 'recent', 'areas', 'boards', 'resort', 'notes', 'finished'}:
        raise ValueError('程度自評格式不正確')
    kind, recent = value.get('kind', ''), value.get('recent', '')
    areas, boards = value.get('areas', []), value.get('boards', [])
    resort, notes, finished = value.get('resort', ''), value.get('notes', ''), value.get('finished', False)
    if (kind not in ('', 'new', 'returning') or recent not in ('', 'yes', 'no')
            or not isinstance(areas, list) or len(areas) > 5
            or any(area not in ('北海道', '湯澤地區', '白馬地區', '其他日本雪場', '日本以外') for area in areas)
            or not isinstance(boards, list) or len(boards) > 2
            or any(board not in ('snowboard', 'ski') for board in boards)
            or not isinstance(resort, str) or len(resort) > 250 or not isinstance(notes, str) or len(notes) > 500
            or type(finished) is not bool):
        raise ValueError('程度自評格式不正確')
    if finished and (not kind or not recent or (recent == 'yes' and (not areas or not boards))):
        raise ValueError('請先完成程度自評必填項目')
    return {'kind': kind, 'recent': recent, 'finished': finished,
            'areas': list(dict.fromkeys(areas)) if recent == 'yes' else [],
            'boards': list(dict.fromkeys(boards)) if recent == 'yes' else [],
            'resort': resort.strip() if recent == 'yes' else '', 'notes': notes.strip() if recent == 'yes' else ''}


def section_questions(document, section):
    return [question for question in document.get('questions', []) if question['section'] == section]


def validate_answers(questions, answers):
    if not isinstance(answers, dict) or set(answers) - {question['key'] for question in questions}:
        raise ValueError('課前題目已更新，請重新載入後再填寫')
    cleaned = {}
    for question in questions:
        key, kind, options = question['key'], question['kind'], question['options']
        value = answers.get(key, [] if kind == 'multiple' else '')
        if kind == 'multiple':
            if (not isinstance(value, list) or len(value) > len(options)
                    or any(not isinstance(option, str) or option not in options for option in value)):
                raise ValueError('請從表單所列的選項作答')
            value = [option for option in options if option in value]
        elif not isinstance(value, str) or len(value) > 1000 or (kind == 'single' and value and value not in options):
            raise ValueError('課前題目答案格式不正確')
        else:
            value = value.strip()
        if value:
            cleaned[key] = value
    return cleaned


def saved_section_answers(member, document, section):
    snapshot = member.pre_course_answers.get(section, {})
    return snapshot.get('answers', {}) if snapshot.get('questions') == section_questions(document, section) else {}


def required_answers_complete(questions, answers):
    return all(not question['required'] or answers.get(question['key']) for question in questions)


def insurance_questions_need_update(member, document):
    return not required_answers_complete(
        section_questions(document, 'insurance'), saved_section_answers(member, document, 'insurance'),
    )
