import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import Q
from django.http import QueryDict
from django.utils import timezone

from Coach.models import Coach
from Coursekit.models import CourseCategory, CourseSession, CourseTemplate, CourseType
from Resorts.models import EquipmentAssistanceTimeSlot, Resorts
from booking.api_views import (
    CoachListAPI,
    CourseAvailableDatesAPI,
    CourseSessionListAPI,
    CreateReservationAPI,
    calculate_cart_discount_summary,
    compute_cart_item_pricing_authoritative,
    get_category_frontend_resorts,
)
from booking.models import Payment, ReservationGroup

from .flow import (
    checkout_missing_fields,
    item_missing_fields,
    missing_fields,
    validate_business_answers,
)
from .models import ChatBookingDraft, ChatBookingSession, ChatBookingToolInvocation


@dataclass
class ConfirmBookingResult:
    ok: bool
    output: dict
    status_code: int = 200
    error: str = ""
    replayed: bool = False


class RequestProxy:
    def __init__(self, *, data=None, query=None, user=None):
        self.data = data or {}
        self.user = user or AnonymousUser()
        self.GET = QueryDict("", mutable=True)
        for key, value in (query or {}).items():
            if isinstance(value, (list, tuple)):
                self.GET.setlist(key, [str(item) for item in value])
            elif value is not None:
                self.GET[key] = str(value)


def public_user(request):
    user = getattr(request, "user", None)
    return user if user and user.is_authenticated else None


def highest_ability_level(counts):
    order = ["no_exp", "level1", "level2", "level3", "level4", "level5", "level6"]
    selected = [level for level in order if int((counts or {}).get(level, 0) or 0) > 0]
    return selected[-1] if selected else "no_exp"


def _available_date_payload(template_id, month):
    response = CourseAvailableDatesAPI().get(
        RequestProxy(query={"month": month}),
        template_id=template_id,
    )
    if response.status_code >= 400:
        raise ValueError(response.data.get("error") or "無法查詢可預約日期")
    return response.data


def _session_payload(template_id, selected_date):
    response = CourseSessionListAPI().get(
        RequestProxy(query={"template_id": template_id, "date": selected_date}),
    )
    if response.status_code >= 400:
        raise ValueError(response.data.get("error") or "無法查詢課程時段")
    return response.data


def available_dates_for_values(client, values, month=None):
    template_id = values.get("template_id")
    if not template_id:
        raise ValueError("請先選擇課程方案")
    if not CourseTemplate.objects.filter(
        id=template_id,
        course_type__category__client=client,
        is_active=True,
    ).exists():
        raise ValueError("找不到此客戶的課程方案")
    if not month:
        first_date = (values.get("course_dates") or [None])[0]
        month = str(first_date)[:7] if first_date else timezone.localdate().strftime("%Y-%m")
    return _available_date_payload(template_id, month)


def course_catalog_payload(
    client,
    *,
    service_type=None,
    category_id=None,
    resort=None,
):
    if service_type not in (None, "", "ski", "photo"):
        raise ValueError("不支援的服務類型")

    categories = CourseCategory.objects.filter(client=client)
    if service_type:
        categories = categories.filter(service_type=service_type)
    if category_id is not None:
        categories = categories.filter(id=category_id)
    if resort:
        categories = categories.filter(
            types__templates__is_active=True,
            types__templates__resorts__name=resort,
        )

    catalog = []
    template_count = 0
    for category in categories.distinct().order_by("display_order", "id"):
        course_types = CourseType.objects.filter(
            category=category,
            templates__is_active=True,
            templates__resorts__isnull=False,
        )
        if resort:
            course_types = course_types.filter(templates__resorts__name=resort)

        type_items = []
        category_resorts = set()
        for course_type in course_types.distinct().order_by("display_order", "id"):
            templates = CourseTemplate.objects.filter(
                course_type=course_type,
                is_active=True,
                resorts__isnull=False,
            ).prefetch_related("resorts")
            if resort:
                templates = templates.filter(resorts__name=resort)

            template_items = []
            for template in templates.distinct().order_by(
                "display_order",
                "duration_hours",
                "id",
            ):
                resorts = sorted({
                    item.display_name
                    for item in template.resorts.all()
                    if not resort or item.name == resort
                })
                if not resorts:
                    continue
                category_resorts.update(resorts)
                template_items.append({
                    "id": template.id,
                    "name": template.name,
                    "duration_hours": template.duration_hours,
                    "max_capacity": template.max_capacity,
                    "resorts": resorts,
                })

            if template_items:
                template_count += len(template_items)
                type_items.append({
                    "id": course_type.id,
                    "name": course_type.name,
                    "templates": template_items,
                })

        if type_items:
            catalog.append({
                "id": category.id,
                "name": category.name,
                "service_type": category.service_type,
                "service_label": category.get_service_type_display(),
                "resorts": sorted(category_resorts),
                "course_types": type_items,
            })

    return {
        "filters": {
            "service_type": service_type or None,
            "category_id": category_id,
            "resort": resort or None,
        },
        "category_count": len(catalog),
        "template_count": template_count,
        "categories": catalog,
    }


def format_course_catalog_reply(catalog):
    categories = (catalog or {}).get("categories") or []
    if not categories:
        return "目前沒有符合條件且已開放的課程方案。您可以告訴我想去的雪場，我再替您確認。"

    lines = ["目前 SnowLand 的課程與服務如下："]
    for category in categories:
        lines.append(f"\n• {category['name']}")
        for course_type in category.get("course_types") or []:
            plan_names = []
            for template in course_type.get("templates") or []:
                name = str(template.get("name") or "").replace("_", " ").strip()
                if name and name not in plan_names:
                    plan_names.append(name)
            detail = "、".join(plan_names)
            if detail:
                lines.append(f"  - {course_type['name']}：{detail}")
            else:
                lines.append(f"  - {course_type['name']}")

    lines.extend([
        "",
        "實際可選雪場、日期、時段與價格會依您的需求查詢後台。",
        "您想先了解單板、雙板、山岳滑雪或攝影？也可以直接告訴我雪場。",
    ])
    return "\n".join(lines)


def option_payload(client, values, field, month=None):
    aliases = {
        "service": "service_type",
        "category": "category_id",
        "course_type": "course_type_id",
        "template": "template_id",
        "date": "course_dates",
        "time_slot": "session_id",
        "coach": "coach_id",
    }
    field = aliases.get(field, field)

    if field == "service_type":
        return [{"value": "ski", "label": "滑雪課程"}, {"value": "photo", "label": "滑雪攝影"}]
    if field == "category_id":
        queryset = CourseCategory.objects.filter(client=client).order_by("display_order", "id")
        if values.get("service_type"):
            queryset = queryset.filter(service_type=values["service_type"])
        return [
            {
                "value": item.id,
                "label": item.name,
                "service_type": item.service_type,
                "available_resorts": get_category_frontend_resorts(item),
            }
            for item in queryset
        ]
    if field == "resort":
        queryset = Resorts.objects.filter(Q(client=client) | Q(client__isnull=True))
        if values.get("category_id"):
            category = CourseCategory.objects.filter(client=client, id=values["category_id"]).first()
            if not category:
                raise ValueError("找不到課程大類")
            queryset = queryset.filter(name__in=get_category_frontend_resorts(category))
        return [
            {"value": item.name, "label": item.display_name, "auto_scheduling_enabled": item.auto_scheduling_enabled}
            for item in queryset.order_by("display_name", "id")
        ]
    if field == "course_type_id":
        queryset = CourseType.objects.filter(category__client=client)
        if values.get("category_id"):
            queryset = queryset.filter(category_id=values["category_id"])
        if values.get("resort"):
            queryset = queryset.filter(templates__is_active=True, templates__resorts__name=values["resort"])
        return [
            {"value": item.id, "label": item.name, "category_id": item.category_id}
            for item in queryset.distinct().order_by("display_order", "id")
        ]
    if field == "people_count":
        return [{"value": value, "label": f"{value} 人"} for value in range(1, 7)]
    if field == "ability_level":
        from .flow import ABILITY_LEVELS
        return ABILITY_LEVELS
    if field == "language":
        from .flow import LANGUAGES
        return LANGUAGES
    if field == "equipment_option":
        from .flow import EQUIPMENT_OPTIONS
        return EQUIPMENT_OPTIONS
    if field == "template_id":
        queryset = CourseTemplate.objects.filter(
            course_type__category__client=client,
            is_active=True,
        ).select_related("course_type")
        if values.get("course_type_id"):
            queryset = queryset.filter(course_type_id=values["course_type_id"])
        if values.get("resort"):
            queryset = queryset.filter(resorts__name=values["resort"])
        return [
            {
                "value": item.id,
                "label": item.name,
                "duration_hours": item.duration_hours,
                "max_capacity": item.max_capacity,
                "course_type_id": item.course_type_id,
            }
            for item in queryset.distinct().order_by("display_order", "duration_hours", "id")
        ]
    if field == "course_dates":
        return available_dates_for_values(client, values, month)
    if field == "session_id":
        dates = values.get("course_dates") or []
        if not values.get("template_id") or not dates:
            raise ValueError("請先選擇課程方案與日期")
        if not CourseTemplate.objects.filter(
            id=values["template_id"],
            course_type__category__client=client,
            is_active=True,
        ).exists():
            raise ValueError("找不到此客戶的課程方案")
        sessions_by_date = {selected_date: _session_payload(values["template_id"], selected_date) for selected_date in dates}
        common_ids = None
        for sessions in sessions_by_date.values():
            usable = {item["id"] for item in sessions if not item.get("is_full")}
            common_ids = usable if common_ids is None else common_ids & usable
        first_sessions = next(iter(sessions_by_date.values()), [])
        return [
            {
                "value": item["id"],
                "label": f'{item["start_time"]}–{item["end_time"]}',
                "start_time": item["start_time"],
                "end_time": item["end_time"],
            }
            for item in first_sessions
            if item["id"] in (common_ids or set())
        ]
    if field == "coach_id":
        if values.get("service_type") == "photo":
            return [{"value": "any", "label": "由系統安排"}]
        if not Resorts.objects.filter(
            Q(client=client) | Q(client__isnull=True),
            name=values.get("resort"),
        ).exists():
            raise ValueError("請先選擇此客戶的雪場")
        if not CourseType.objects.filter(
            id=values.get("course_type_id"),
            category__client=client,
        ).exists():
            raise ValueError("請先選擇此客戶的課程類型")
        if not CourseTemplate.objects.filter(
            id=values.get("template_id"),
            course_type__category__client=client,
            is_active=True,
        ).exists():
            raise ValueError("請先選擇此客戶的課程方案")
        query = {
            "resort": values.get("resort"),
            "courseType": values.get("course_type_id"),
            "abilityLevel": highest_ability_level(values.get("ability_level_counts")),
            "courseDates": values.get("course_dates") or [],
            "timeSlot": values.get("session_id"),
            "courseTemplate": values.get("template_id"),
        }
        response = CoachListAPI().get(RequestProxy(query=query))
        if response.status_code >= 400:
            raise ValueError("無法查詢教練")
        tenant_coach_ids = set(
            Coach.objects.filter(Q(client=client) | Q(client__isnull=True)).values_list("id", flat=True)
        )
        coaches = [{"value": "any", "label": "不指定教練"}]
        for item in response.data.get("coach_list", []):
            coach_id = item.get("id") or item.get("pk")
            if coach_id in tenant_coach_ids:
                coaches.append({**item, "value": coach_id, "label": item.get("name")})
        return coaches
    if field == "equipment_assistance_time_slot_id":
        if not values.get("resort"):
            raise ValueError("請先選擇雪場")
        queryset = EquipmentAssistanceTimeSlot.objects.filter(
            Q(resort__client=client) | Q(resort__client__isnull=True),
            resort__name=values["resort"],
            is_active=True,
            equipment_option="purchaseAssistanceTime",
        )
        if values.get("template_id"):
            queryset = queryset.filter(course_templates__id=values["template_id"])
        return [
            {
                "value": item.id,
                "label": item.display_label(),
                "day_type": item.day_type,
                "start_time": item.start_time.strftime("%H:%M") if item.start_time else None,
                "end_time": item.end_time.strftime("%H:%M") if item.end_time else None,
            }
            for item in queryset.distinct()
        ]
    raise ValueError(f"不支援的選項欄位: {field}")


def _validate_relations(client, values):
    category = CourseCategory.objects.filter(
        id=values["category_id"],
        client=client,
        service_type=values["service_type"],
    ).first()
    if not category:
        raise ValueError("課程大類與服務類型不符")

    resort = Resorts.objects.filter(
        Q(client=client) | Q(client__isnull=True),
        name=values["resort"],
    ).first()
    if not resort:
        raise ValueError("找不到此客戶的雪場")
    if values["resort"] not in get_category_frontend_resorts(category):
        raise ValueError("此課程大類不適用所選雪場")

    course_type = CourseType.objects.filter(
        id=values["course_type_id"],
        category=category,
    ).first()
    if not course_type:
        raise ValueError("課程類型與課程大類不符")

    template = CourseTemplate.objects.filter(
        id=values["template_id"],
        course_type=course_type,
        is_active=True,
        resorts=resort,
    ).first()
    if not template:
        raise ValueError("課程方案與課程類型或雪場不符")

    session = CourseSession.objects.filter(
        id=values["session_id"],
        template=template,
        is_active=True,
    ).first()
    if not session:
        raise ValueError("課程時段與課程方案不符")

    for selected_date in values["course_dates"]:
        payload = _available_date_payload(template.id, selected_date[:7])
        if selected_date not in payload["available_dates"]:
            raise ValueError(f"{selected_date} 不在可預約日期內")
        available_sessions = _session_payload(template.id, selected_date)
        match = next((item for item in available_sessions if item["id"] == session.id), None)
        if not match or match.get("is_full"):
            raise ValueError(f"{selected_date} 的所選時段已不可預約")

    coach = None
    coach_id = values.get("coach_id", "any")
    if values["service_type"] == "ski" and coach_id not in (None, "", "any"):
        coach_options = option_payload(client, values, "coach_id")
        if int(coach_id) not in {item["value"] for item in coach_options if item["value"] != "any"}:
            raise ValueError("指定教練不符合目前課程條件或時段")
        coach = Coach.objects.filter(id=coach_id).first()
    return category, resort, course_type, template, session, coach


CART_SHARED_FIELDS = {
    "contact_name",
    "contact_email",
    "contact_phone",
    "referral_source",
    "discount_code",
    "policy_accepted",
}


def _shared_checkout_values(values):
    return {
        key: deepcopy(value)
        for key, value in (values or {}).items()
        if key in CART_SHARED_FIELDS
    }


def _booking_source_values(values):
    return {
        key: deepcopy(value)
        for key, value in (values or {}).items()
        if key not in CART_SHARED_FIELDS
    }


def checkout_cart(cart):
    """Remove chat-only metadata before pricing or creating real reservations."""
    sanitized = []
    for raw_item in cart or []:
        if not isinstance(raw_item, dict):
            continue
        sanitized.append({
            key: deepcopy(value)
            for key, value in raw_item.items()
            if not str(key).startswith("_chat_")
        })
    return sanitized


def build_cart_item(session, *, saved=False):
    values = dict(session.slot_values or {})
    missing = item_missing_fields(values)
    if missing:
        raise ValueError(f"尚缺少必要資料: {', '.join(missing)}")
    validate_business_answers(values)
    category, resort, course_type, template, selected_session, coach = _validate_relations(
        session.client,
        values,
    )

    if values["service_type"] == "photo":
        people_count = 1
        ability_level = "no_exp"
        coach_value = "any"
        language = "zh"
        equipment_option = None
    else:
        people_count = int(values["people_count"])
        ability_level = highest_ability_level(values.get("ability_level_counts"))
        coach_value = coach.id if coach else "any"
        language = values["language"]
        equipment_option = values["equipment_option"]

    courses = []
    for selected_date in values["course_dates"]:
        courses.append({
            "date": selected_date,
            "courseTypeId": course_type.id,
            "courseTypeName": course_type.name,
            "courseTemplateId": template.id,
            "courseTemplateName": template.name,
            "durationHours": template.duration_hours,
            "timeSlotId": selected_session.id,
            "timeSlotStart": selected_session.start_time.strftime("%H:%M"),
            "timeSlotEnd": selected_session.end_time.strftime("%H:%M"),
        })

    item = {
        "id": (
            f"chat-{session.pk}-{uuid.uuid4().hex[:12]}"
            if saved
            else f"chat-{session.pk}"
        ),
        "serviceType": values["service_type"],
        "coach": coach_value,
        "coachName": coach.name if coach else "不指定",
        "peopleCount": people_count,
        "abilityLevel": ability_level,
        "abilityLevelCounts": values.get("ability_level_counts") or {},
        "equipment": equipment_option in {"class_time_help", "extra_time_help"},
        "equipmentOption": equipment_option,
        "equipmentAssistanceTimeSlotId": values.get("equipment_assistance_time_slot_id"),
        "language": language,
        "resort": resort.name,
        "resortName": resort.display_name,
        "courseCategory": category.name,
        "courses": courses,
    }
    pricing = compute_cart_item_pricing_authoritative(item)
    item.update({
        "courseFee": pricing["course_fee"],
        "coachFee": pricing["coach_fee"],
        "languageFee": pricing["language_fee"],
        "equipmentRentalFee": pricing["equipment_fee"],
        "totalPrice": pricing["subtotal"],
    })
    if saved:
        item["_chat_saved"] = True
        item["_chat_source_values"] = _booking_source_values(values)
    return item


def build_contact(session):
    values = dict(session.slot_values or {})
    missing = checkout_missing_fields(values)
    if missing:
        raise ValueError(f"結帳尚缺少必要資料: {', '.join(missing)}")

    messenger_id = session.external_user_id or f"chat-session:{session.pk}"
    return {
        "name": values.get("contact_name", ""),
        "email": values.get("contact_email", ""),
        "phone": values["contact_phone"],
        "messengerType": "LINE" if session.channel == "line" else "AI客服",
        "messengerId": messenger_id,
        "referralSource": values.get("referral_source", ""),
    }


def build_cart_and_contact(session):
    values = dict(session.slot_values or {})
    missing = missing_fields(values)
    if missing:
        raise ValueError(f"尚缺少必要資料: {', '.join(missing)}")
    return [build_cart_item(session)], build_contact(session)


def cart_summary(cart):
    result = []
    for index, item in enumerate(checkout_cart(cart), start=1):
        courses = item.get("courses") if isinstance(item.get("courses"), list) else []
        first_course = courses[0] if courses and isinstance(courses[0], dict) else {}
        result.append({
            "index": index,
            "service_type": item.get("serviceType"),
            "resort": item.get("resortName") or item.get("resort"),
            "course_category": item.get("courseCategory"),
            "course_type": first_course.get("courseTypeName"),
            "template": first_course.get("courseTemplateName"),
            "dates": [
                course.get("date")
                for course in courses
                if isinstance(course, dict) and course.get("date")
            ],
            "time": (
                f"{first_course.get('timeSlotStart')}–{first_course.get('timeSlotEnd')}"
                if first_course.get("timeSlotStart") and first_course.get("timeSlotEnd")
                else ""
            ),
            "people_count": item.get("peopleCount"),
            "subtotal": item.get("totalPrice"),
        })
    return result


def _invalidate_cart_quote(draft):
    draft.status = ChatBookingDraft.STATUS_DRAFT
    draft.quote = {}
    draft.quote_hash = ""
    draft.quote_expires_at = None
    draft.payment_snapshot = {}
    draft.last_error = ""


@transaction.atomic
def add_current_booking_to_cart(session):
    locked_session = ChatBookingSession.objects.select_for_update().get(pk=session.pk)
    draft, _ = ChatBookingDraft.objects.select_for_update().get_or_create(
        session=locked_session,
    )
    if draft.status == ChatBookingDraft.STATUS_COMMITTED:
        raise ValueError("這筆訂單已成立，請先建立新的預約購物車")

    cart = list(draft.cart or [])
    if len(cart) >= 10:
        raise ValueError("LINE 購物車最多可加入 10 個預約項目，請先結帳")
    item = build_cart_item(locked_session, saved=True)
    cart.append(item)
    draft.cart = cart
    _invalidate_cart_quote(draft)
    draft.save()

    locked_session.slot_values = _shared_checkout_values(locked_session.slot_values)
    locked_session.state_version += 1
    locked_session.status = ChatBookingSession.STATUS_ACTIVE
    locked_session.current_step = "cart_action"
    locked_session.save(
        update_fields=[
            "slot_values",
            "state_version",
            "status",
            "current_step",
            "updated_at",
        ],
    )
    return locked_session, draft


def _promote_legacy_cart_item(draft, session):
    cart = list(draft.cart or [])
    if len(cart) != 1 or not isinstance(cart[0], dict):
        return cart
    if cart[0].get("_chat_saved"):
        return cart
    item = dict(cart[0])
    item["_chat_saved"] = True
    item["_chat_source_values"] = _booking_source_values(session.slot_values or {})
    cart[0] = item
    return cart


@transaction.atomic
def start_new_cart_item(session):
    locked_session = ChatBookingSession.objects.select_for_update().get(pk=session.pk)
    draft = ChatBookingDraft.objects.select_for_update().get(session=locked_session)
    if draft.status == ChatBookingDraft.STATUS_COMMITTED:
        raise ValueError("這筆訂單已成立，請建立新的預約購物車")
    if not draft.cart:
        raise ValueError("購物車目前沒有項目")

    draft.cart = _promote_legacy_cart_item(draft, locked_session)
    _invalidate_cart_quote(draft)
    draft.save()
    locked_session.slot_values = _shared_checkout_values(locked_session.slot_values)
    locked_session.state_version += 1
    locked_session.status = ChatBookingSession.STATUS_ACTIVE
    locked_session.current_step = "service_type"
    locked_session.save(
        update_fields=[
            "slot_values",
            "state_version",
            "status",
            "current_step",
            "updated_at",
        ],
    )
    return locked_session, draft


@transaction.atomic
def remove_cart_item(session, index):
    locked_session = ChatBookingSession.objects.select_for_update().get(pk=session.pk)
    draft = ChatBookingDraft.objects.select_for_update().get(session=locked_session)
    if draft.status == ChatBookingDraft.STATUS_COMMITTED:
        raise ValueError("已成立的訂單不可從購物車刪除")
    cart = list(draft.cart or [])
    position = int(index) - 1
    if position < 0 or position >= len(cart):
        raise ValueError("找不到指定的購物車項目")
    removed = cart.pop(position)
    draft.cart = cart
    _invalidate_cart_quote(draft)
    draft.save()
    locked_session.state_version += 1
    locked_session.status = ChatBookingSession.STATUS_ACTIVE
    locked_session.current_step = "cart_action" if cart else "service_type"
    locked_session.save(
        update_fields=[
            "state_version",
            "status",
            "current_step",
            "updated_at",
        ],
    )
    return locked_session, draft, removed


@transaction.atomic
def edit_cart_item(session, index):
    locked_session = ChatBookingSession.objects.select_for_update().get(pk=session.pk)
    draft = ChatBookingDraft.objects.select_for_update().get(session=locked_session)
    if draft.status == ChatBookingDraft.STATUS_COMMITTED:
        raise ValueError("已成立的訂單需由真人客服協助修改")
    cart = _promote_legacy_cart_item(draft, locked_session)
    position = int(index) - 1
    if position < 0 or position >= len(cart):
        raise ValueError("找不到指定的購物車項目")
    item = cart.pop(position)
    source_values = item.get("_chat_source_values")
    if not isinstance(source_values, dict) or not source_values:
        raise ValueError("這個舊購物車項目無法直接編輯，請刪除後重新加入")

    shared = _shared_checkout_values(locked_session.slot_values)
    locked_session.slot_values = {**shared, **deepcopy(source_values)}
    locked_session.state_version += 1
    locked_session.status = ChatBookingSession.STATUS_ACTIVE
    locked_session.current_step = "editing_cart_item"
    locked_session.save(
        update_fields=[
            "slot_values",
            "state_version",
            "status",
            "current_step",
            "updated_at",
        ],
    )
    draft.cart = cart
    _invalidate_cart_quote(draft)
    draft.save()
    return locked_session, draft


@transaction.atomic
def clear_booking_cart(session):
    locked_session = ChatBookingSession.objects.select_for_update().get(pk=session.pk)
    draft = ChatBookingDraft.objects.select_for_update().get(session=locked_session)
    if draft.status == ChatBookingDraft.STATUS_COMMITTED:
        raise ValueError("已成立的訂單不可清空")
    removed_count = len(draft.cart or [])
    draft.cart = []
    _invalidate_cart_quote(draft)
    draft.save()
    locked_session.slot_values = _shared_checkout_values(locked_session.slot_values)
    locked_session.state_version += 1
    locked_session.status = ChatBookingSession.STATUS_ACTIVE
    locked_session.current_step = "service_type"
    locked_session.save(
        update_fields=[
            "slot_values",
            "state_version",
            "status",
            "current_step",
            "updated_at",
        ],
    )
    return locked_session, draft, removed_count


def make_quote(session):
    draft, _ = ChatBookingDraft.objects.get_or_create(session=session)
    if draft.cart:
        cart = list(draft.cart)
        contact = build_contact(session)
    else:
        cart, contact = build_cart_and_contact(session)
    pricing_cart = checkout_cart(cart)
    if not pricing_cart:
        raise ValueError("購物車目前沒有項目")
    summary = calculate_cart_discount_summary(
        pricing_cart,
        session.client,
        user=session.user,
        contact_info={
            "name": contact["name"],
            "email": contact["email"],
            "phone": contact["phone"],
            "messenger_type": contact["messengerType"],
            "messenger_id": contact["messengerId"],
            "referral_source": contact["referralSource"],
        },
        discount_code=(session.slot_values or {}).get("discount_code", ""),
    )
    discount_code = (session.slot_values or {}).get("discount_code", "")
    if discount_code and summary.get("discount_code_error"):
        raise ValueError(summary["discount_code_error"])

    public_quote = {
        "subtotal": summary["subtotal"],
        "discount_total": summary["discount_total"],
        "total": summary["total"],
        "item_subtotals": summary["item_subtotals"],
        "item_discount_amounts": summary["item_discount_amounts"],
        "applied_discounts": summary["applied_discounts"],
        "is_new_customer": summary["is_new_customer"],
        "currency": "TWD",
        "expires_in_seconds": 900,
    }
    hash_input = {
        "session_id": str(session.pk),
        "state_version": session.state_version,
        "cart": pricing_cart,
        "contact": contact,
        "discount_code": discount_code,
        "quote": public_quote,
    }
    quote_hash = hashlib.sha256(
        json.dumps(hash_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    expires_at = timezone.now() + timedelta(minutes=15)
    draft.status = ChatBookingDraft.STATUS_QUOTED
    draft.cart = cart
    draft.contact = contact
    draft.discount_code = discount_code
    draft.quote = public_quote
    draft.quote_hash = quote_hash
    draft.quote_expires_at = expires_at
    draft.last_error = ""
    draft.save()
    return draft


def payment_snapshot_for_groups(client, group_ids):
    groups = ReservationGroup.objects.filter(client=client, id__in=group_ids).prefetch_related(
        "reservations",
        "payments",
    )
    by_id = {group.id: group for group in groups}
    if set(int(group_id) for group_id in group_ids) != set(by_id):
        raise ValueError("訂單歸屬驗證失敗")

    order_groups = []
    total_amount = 0
    for group_id in group_ids:
        group = by_id[int(group_id)]
        payment = group.payments.order_by("-created_at").first()
        details = []
        group_total = 0
        for reservation in group.reservations.exclude(status__in=["deleted", "cancelled"]):
            details.append({
                "reservation_id": reservation.id,
                "course_fee": reservation.course_fee,
                "coach_fee": reservation.coach_fee,
                "language_fee": reservation.language_fee,
                "equipment_fee": reservation.equipment_rental_fee,
                "discount_amount": reservation.discount_amount,
                "payment_amount": reservation.payment_amount,
                "status": reservation.status,
            })
            group_total += reservation.payment_amount
        total_amount += group_total
        order_groups.append({
            "reservation_group_id": group.id,
            "payment_status": payment.status if payment else "unpaid",
            "total_amount": group_total,
            "details": details,
        })
    return {
        "reservation_group_ids": [int(group_id) for group_id in group_ids],
        "total_amount": total_amount,
        "currency": "TWD",
        "groups": order_groups,
        "bank_info": {
            "bank_name": client.bank_name,
            "bank_branch": client.bank_branch,
            "bank_account_number": client.bank_account_number,
            "bank_account_holder": client.bank_account_holder,
        },
        "payment_methods": ["bank_transfer", "card"],
        "card_status": "gateway_adapter_required",
    }


@transaction.atomic
def submit_bank_transfer(session, sender_account):
    if not sender_account or not str(sender_account).isdigit() or len(str(sender_account)) != 5:
        raise ValueError("請輸入匯款帳戶後五碼")
    draft = ChatBookingDraft.objects.select_for_update().get(session=session)
    if draft.status != ChatBookingDraft.STATUS_COMMITTED or not draft.reservation_group_ids:
        raise ValueError("尚未建立可付款訂單")
    if draft.payment_snapshot.get("payment_allowed") is not True:
        raise ValueError("此訂單目前不可付款，請等待排課處理")
    groups = ReservationGroup.objects.filter(
        client=session.client,
        id__in=draft.reservation_group_ids,
    )
    if groups.count() != len(draft.reservation_group_ids):
        raise ValueError("訂單歸屬驗證失敗")
    for group in groups:
        payment, _ = Payment.objects.get_or_create(
            reservation_group=group,
            defaults={"user": session.user, "status": "pending", "payment_method": "TT"},
        )
        payment.user = session.user
        payment.status = "pending"
        payment.payment_method = "TT"
        payment.bank_account = str(sender_account)
        payment.save(update_fields=["user", "status", "payment_method", "bank_account", "updated_at"])
    draft.payment_snapshot = payment_snapshot_for_groups(session.client, draft.reservation_group_ids)
    draft.payment_snapshot["payment_allowed"] = True
    draft.save(update_fields=["payment_snapshot", "updated_at"])
    return draft.payment_snapshot


@transaction.atomic
def commit_draft(session, request_user):
    draft = ChatBookingDraft.objects.select_for_update().get(session=session)
    if draft.status != ChatBookingDraft.STATUS_QUOTED:
        raise ValueError("請先重新取得報價")
    if not draft.quote_expires_at or draft.quote_expires_at <= timezone.now():
        raise ValueError("報價已過期，請重新取得報價")
    proxy = RequestProxy(
        data={
            "cart": checkout_cart(draft.cart),
            "contact": draft.contact,
            "discount_code": draft.discount_code,
        },
        user=request_user,
    )
    class CommitRejected(Exception):
        pass

    try:
        # The legacy view turns exceptions into Response objects. A nested savepoint
        # guarantees that a failed response cannot leave a partial order behind.
        with transaction.atomic():
            response = CreateReservationAPI().post(proxy, client_code=session.client.internal_code)
            if response.status_code >= 400 or response.data.get("code") != 200:
                raise CommitRejected(response.data.get("msg") or "建立預約失敗")
    except CommitRejected as exc:
        raise ValueError(str(exc)) from exc

    group_ids = response.data.get("reservation_group_ids") or []
    if response.data.get("reservation_group_id"):
        group_ids.append(response.data["reservation_group_id"])
    group_ids = list(dict.fromkeys(int(group_id) for group_id in group_ids))
    if not group_ids:
        raise ValueError("建立預約後未取得訂單編號")

    snapshot = payment_snapshot_for_groups(session.client, group_ids)
    payment_allowed = bool(response.data.get("requires_payment")) and not response.data.get("scheduling_failed")
    snapshot["payment_allowed"] = payment_allowed
    if not payment_allowed:
        snapshot["payment_methods"] = []
        snapshot["card_status"] = "unavailable_until_scheduled"

    draft.status = ChatBookingDraft.STATUS_COMMITTED
    draft.reservation_group_ids = group_ids
    draft.payment_snapshot = snapshot
    draft.last_error = ""
    draft.save()
    return {
        "code": 200,
        "message": response.data.get("msg", "預約已建立"),
        "scheduling_failed": bool(response.data.get("scheduling_failed")),
        "requires_payment": bool(response.data.get("requires_payment")),
        "reservation_group_ids": group_ids,
        "payment": draft.payment_snapshot,
    }


@transaction.atomic
def confirm_quoted_session(
    session,
    request_user,
    *,
    idempotency_key,
    expected_state_version=None,
    expected_quote_hash=None,
    input_data=None,
):
    """Commit a quoted draft once and preserve both successful and failed replays."""
    if not idempotency_key or len(idempotency_key) > 128:
        return ConfirmBookingResult(False, {}, 400, "Idempotency-Key 必須是 1 至 128 字元")

    locked_session = ChatBookingSession.objects.select_for_update().select_related("client").get(
        pk=session.pk,
    )
    invocation, created = ChatBookingToolInvocation.objects.select_for_update().get_or_create(
        session=locked_session,
        tool_key="confirm_booking",
        idempotency_key=idempotency_key,
        defaults={"input_data": input_data or {}},
    )
    if not created:
        if invocation.status == ChatBookingToolInvocation.STATUS_SUCCEEDED:
            return ConfirmBookingResult(True, invocation.output_data, replayed=True)
        if invocation.status == ChatBookingToolInvocation.STATUS_FAILED:
            saved_status = int((invocation.output_data or {}).get("status_code") or 400)
            return ConfirmBookingResult(
                False,
                {},
                saved_status,
                invocation.error or "前次建立訂單失敗",
                replayed=True,
            )
        return ConfirmBookingResult(False, {}, 409, "訂單正在建立中，請勿重複送出", replayed=True)

    def reject(message, status_code):
        invocation.status = ChatBookingToolInvocation.STATUS_FAILED
        invocation.output_data = {"status_code": status_code}
        invocation.error = message
        invocation.save(update_fields=["status", "output_data", "error", "updated_at"])
        return ConfirmBookingResult(False, {}, status_code, message)

    if expected_state_version is None:
        return reject("缺少預約狀態版本", 400)
    try:
        expected_state_version = int(expected_state_version)
    except (TypeError, ValueError):
        return reject("預約狀態版本格式錯誤", 400)
    if expected_state_version != locked_session.state_version:
        return reject("預約資料已變更，請重新取得報價", 409)

    draft = ChatBookingDraft.objects.select_for_update().filter(session=locked_session).first()
    if not draft or not draft.quote_hash:
        return reject("請先取得有效報價", 409)
    if not expected_quote_hash:
        return reject("缺少報價識別碼", 400)
    if expected_quote_hash != draft.quote_hash:
        return reject("報價內容已變更，請重新確認", 409)
    if (locked_session.slot_values or {}).get("policy_accepted") is not True:
        return reject("客人尚未明確同意預約與取消政策", 400)

    try:
        # Serialize tenant booking writes before entering the legacy scheduling pipeline.
        from Client.models import Client

        Client.objects.select_for_update().get(pk=locked_session.client_id)
        output = commit_draft(locked_session, request_user)
    except ValueError as exc:
        return reject(str(exc), 400)

    invocation.status = ChatBookingToolInvocation.STATUS_SUCCEEDED
    invocation.output_data = output
    invocation.error = ""
    invocation.save(update_fields=["status", "output_data", "error", "updated_at"])
    locked_session.status = ChatBookingSession.STATUS_CONFIRMED
    locked_session.current_step = (
        "payment" if output.get("requires_payment") else "scheduling_support"
    )
    locked_session.save(update_fields=["status", "current_step", "updated_at"])
    return ConfirmBookingResult(True, output)
