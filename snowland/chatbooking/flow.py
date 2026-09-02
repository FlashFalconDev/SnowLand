from copy import deepcopy
from datetime import datetime


ABILITY_LEVELS = [
    {"value": "no_exp", "label": "等級 0／從未滑過"},
    {"value": "level1", "label": "等級 1"},
    {"value": "level2", "label": "等級 2"},
    {"value": "level3", "label": "等級 3"},
    {"value": "level4", "label": "等級 4"},
    {"value": "level5", "label": "等級 5"},
    {"value": "level6", "label": "等級 6"},
]
LANGUAGES = [
    {"value": "zh", "label": "中文"},
    {"value": "en", "label": "English"},
    {"value": "ja", "label": "日本語"},
    {"value": "yue", "label": "粵語"},
]
EQUIPMENT_OPTIONS = [
    {"value": "self_rent", "label": "自行租借"},
    {"value": "own_equipment", "label": "自備裝備"},
    {"value": "class_time_help", "label": "課程時間內協助"},
    {"value": "extra_time_help", "label": "加購協助時段"},
]

ALLOWED_FIELDS = {
    "service_type",
    "category_id",
    "resort",
    "course_type_id",
    "people_count",
    "has_under_6",
    "under_7_can_self_ski",
    "ability_level_counts",
    "ability_level",
    "coach_id",
    "language",
    "template_id",
    "course_dates",
    "session_id",
    "equipment_option",
    "equipment_assistance_time_slot_id",
    "contact_name",
    "contact_email",
    "contact_phone",
    "referral_source",
    "discount_code",
    "policy_accepted",
}

CHECKOUT_FIELDS = {
    "contact_phone",
    "policy_accepted",
}

DEPENDENT_FIELDS = {
    "service_type": {
        "category_id", "resort", "course_type_id", "people_count", "has_under_6",
        "under_7_can_self_ski", "ability_level_counts", "ability_level", "coach_id",
        "language", "template_id", "course_dates", "session_id", "equipment_option",
        "equipment_assistance_time_slot_id",
    },
    "category_id": {
        "resort", "course_type_id", "template_id", "course_dates", "session_id",
        "coach_id", "equipment_assistance_time_slot_id",
    },
    "resort": {
        "course_type_id", "template_id", "course_dates", "session_id", "coach_id",
        "equipment_assistance_time_slot_id",
    },
    "course_type_id": {"template_id", "course_dates", "session_id", "coach_id"},
    "people_count": {"ability_level_counts", "ability_level", "coach_id"},
    "ability_level": {"coach_id"},
    "ability_level_counts": {"coach_id"},
    "template_id": {"course_dates", "session_id", "coach_id", "equipment_assistance_time_slot_id"},
    "course_dates": {"session_id", "coach_id", "equipment_assistance_time_slot_id"},
    "session_id": {"coach_id", "equipment_assistance_time_slot_id"},
    "equipment_option": {"equipment_assistance_time_slot_id"},
}


def normalize_updates(updates):
    if not isinstance(updates, dict):
        raise ValueError("updates 必須是物件")
    unknown = sorted(set(updates) - ALLOWED_FIELDS)
    if unknown:
        raise ValueError(f"不支援的欄位: {', '.join(unknown)}")

    normalized = {}
    integer_fields = {
        "category_id", "course_type_id", "people_count", "template_id", "session_id",
        "equipment_assistance_time_slot_id",
    }
    boolean_fields = {"has_under_6", "under_7_can_self_ski", "policy_accepted"}
    string_fields = {
        "service_type", "resort", "ability_level", "language", "equipment_option",
        "contact_name", "contact_email", "contact_phone", "referral_source", "discount_code",
    }

    for key, value in updates.items():
        if value is None:
            normalized[key] = None
        elif key in integer_fields:
            normalized[key] = int(value)
        elif key in boolean_fields:
            if not isinstance(value, bool):
                raise ValueError(f"{key} 必須是布林值")
            normalized[key] = value
        elif key in string_fields:
            text = str(value).strip()
            if len(text) > (500 if key == "referral_source" else 255):
                raise ValueError(f"{key} 過長")
            normalized[key] = text
        elif key == "coach_id":
            normalized[key] = "any" if value in (None, "", "any") else int(value)
        elif key == "course_dates":
            if not isinstance(value, list) or not value or len(value) > 14:
                raise ValueError("course_dates 必須是 1 至 14 個日期的陣列")
            dates = []
            for raw_date in value:
                parsed = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
                dates.append(parsed.isoformat())
            normalized[key] = sorted(set(dates))
        elif key == "ability_level_counts":
            if not isinstance(value, dict):
                raise ValueError("ability_level_counts 必須是物件")
            counts = {}
            for level, count in value.items():
                if level not in {item["value"] for item in ABILITY_LEVELS}:
                    raise ValueError(f"未知能力等級: {level}")
                count = int(count)
                if count < 0:
                    raise ValueError("能力人數不可小於 0")
                if count:
                    counts[level] = count
            normalized[key] = counts
        else:
            normalized[key] = deepcopy(value)
    return normalized


def apply_updates(current, updates):
    state = deepcopy(current or {})
    normalized = normalize_updates(updates)
    for changed_field, value in normalized.items():
        if state.get(changed_field) != value:
            for dependent in DEPENDENT_FIELDS.get(changed_field, set()):
                if dependent not in normalized:
                    state.pop(dependent, None)
        if value is None or value == "":
            state.pop(changed_field, None)
        else:
            state[changed_field] = value
    return state


def required_fields(state):
    service_type = state.get("service_type")
    common = [
        "service_type", "category_id", "resort", "course_type_id", "template_id",
        "course_dates", "session_id",
    ]
    if service_type == "ski":
        common[4:4] = [
            "people_count", "has_under_6", "ability_level_counts", "language",
            "equipment_option",
        ]
        if state.get("has_under_6"):
            common.insert(common.index("ability_level_counts"), "under_7_can_self_ski")
        if state.get("equipment_option") == "extra_time_help":
            common.append("equipment_assistance_time_slot_id")
    common.extend(["contact_phone", "policy_accepted"])
    return common


def item_required_fields(state):
    return [field for field in required_fields(state) if field not in CHECKOUT_FIELDS]


def checkout_required_fields():
    return ["contact_phone", "policy_accepted"]


def _missing_fields_for(state, fields):
    missing = []
    for field in fields:
        value = state.get(field)
        if value is None or value == "" or value == []:
            missing.append(field)
        elif field == "ability_level_counts" and value == {}:
            missing.append(field)
        elif field == "policy_accepted" and value is not True:
            missing.append(field)
    return missing


def item_missing_fields(state):
    return _missing_fields_for(state, item_required_fields(state))


def checkout_missing_fields(state):
    return _missing_fields_for(state, checkout_required_fields())


def missing_fields(state):
    return _missing_fields_for(state, required_fields(state))


def next_field(state):
    missing = missing_fields(state)
    return missing[0] if missing else "confirmation"


def validate_business_answers(state):
    if state.get("service_type") not in {"ski", "photo"}:
        raise ValueError("service_type 必須是 ski 或 photo")
    if state.get("service_type") == "ski":
        people_count = int(state.get("people_count") or 0)
        if people_count < 1 or people_count > 6:
            raise ValueError("滑雪課人數必須是 1 至 6 人")
        counts = state.get("ability_level_counts") or {}
        if sum(int(value) for value in counts.values()) != people_count:
            raise ValueError("各能力等級人數加總必須等於上課人數")
        if state.get("has_under_6") and not state.get("under_7_can_self_ski") and people_count > 1:
            raise ValueError("未滿 7 歲且無法自行滑行時，需安排一對一課程")
        if state.get("language") not in {item["value"] for item in LANGUAGES}:
            raise ValueError("不支援的授課語言")
        if state.get("equipment_option") not in {item["value"] for item in EQUIPMENT_OPTIONS}:
            raise ValueError("不支援的裝備選項")
