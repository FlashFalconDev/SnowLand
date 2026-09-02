"""
重構後的 API Views - RESTful 架構

從原本的 API(request, tunnel) 拆分成獨立的 ViewSet
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import connection, transaction
from django.db.utils import OperationalError, ProgrammingError
from django.db.models import F, Q
from django.utils import timezone
from datetime import datetime, timedelta

from Client.models import SiteContent
from Coach.models import (
    Coach, CoachResort, CoachCourseLevel, CoachLeaveRequest,
    ABILITY_LEVEL_CHOICES, normalize_ability_level, normalize_ability_levels,
)
from Resorts.models import Resorts, ResortFee, EquipmentAssistanceTimeSlot
from Coursekit.models import CourseType, CourseTemplate, SeasonSetting, CourseCategory, CourseSession, CoursePricing, DiscountCode
from .models import Booking, ReservationGroup, Payment, Reservation
from Control.views import login_required_control
from .funcNewebpay import neweb_pay_request
from snowland.settings import RUN_HOST


class PriceCalculationError(Exception):
    """價格計算失敗（缺設定、人數超過上限、找不到雪場/模板等）"""
    pass


class TenantResolutionError(Exception):
    """租戶解析失敗:URL 沒給 client_code 且系統內有 0 或多於 1 個 active client"""
    pass


SCHEDULED_RESERVATION_STATUSES = [
    'auto_assigned',
    'manually_assigned',
    'pending_coach_confirmation',
    'form_filled',
    'completed',
]

PENDING_COACH_CONFIRMATION_MESSAGE = '訂單已建立，但部分課程需要教練確認接課，確認前暫不開放付款。'
SCHEDULING_FAILED_PAYMENT_MESSAGE = '訂單已建立但自動排課失敗，確認排課前暫不開放付款。'


def has_pending_coach_confirmation(reservations):
    return any(
        getattr(reservation, 'status', None) == 'pending_coach_confirmation'
        for reservation in reservations
    )


def group_has_pending_coach_confirmation(group):
    return group.reservations.filter(status='pending_coach_confirmation').exists()


def get_group_payment_hold(group):
    if group.reservations.filter(status='pending_coach_confirmation').exists():
        return PENDING_COACH_CONFIRMATION_MESSAGE, 'pending_coach_approval'
    if group.reservations.filter(status='auto_assignment_failed').exists():
        return SCHEDULING_FAILED_PAYMENT_MESSAGE, 'scheduling_failed'
    return None, None


def model_table_has_column(model, column_name):
    try:
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(cursor, model._meta.db_table)
        return any(column.name == column_name for column in columns)
    except (OperationalError, ProgrammingError):
        return False


def infer_legacy_category_service_type(category_name):
    name = f"{category_name or ''}".lower()
    if any(keyword in name for keyword in ['攝影', '旅拍', 'photography', 'photo']):
        return 'photo'
    return 'ski'


PHOTO_SERVICE_KEYWORDS = ('攝影', '旅拍', 'photography', 'photo')


def looks_like_photo_service(*values):
    text = ' '.join(str(value or '') for value in values).lower()
    return any(keyword.lower() in text for keyword in PHOTO_SERVICE_KEYWORDS)


def infer_cart_item_service_type(item, course_type=None):
    names = [
        item.get('serviceType'),
        item.get('service_type'),
        item.get('category'),
        item.get('courseCategory'),
        item.get('courseCategoryName'),
    ]
    for course in item.get('courses') or []:
        names.extend([
            course.get('courseTypeName'),
            course.get('courseTemplateName'),
        ])

    category_service_type = None
    if course_type:
        category = getattr(course_type, 'category', None)
        category_service_type = getattr(category, 'service_type', None)
        names.extend([
            getattr(course_type, 'name', ''),
            getattr(category, 'name', ''),
        ])

    if looks_like_photo_service(*names):
        return 'photo'
    if category_service_type in ('ski', 'photo'):
        return category_service_type
    return 'ski'


def resolve_tenant_client(client_code):
    """
    解析下單請求所屬的 Client。永不回 None — 解析失敗會 raise,避免訂單被 silent 寫成
    client=NULL 之後在後台消失。

    規則:
    1. 有 client_code:嚴格用它查;查不到 → 報錯(不要 silent pass)
    2. 沒 client_code:若 DB 只有 1 個 active client → 自動綁(單客戶情境的便利)
                      若有 0 或多於 1 個 → 報錯要求帶 client_code(防止未來多客戶時綁錯)

    Why: 原本若沒帶 client_code 或抓不到 client,tenant_client 會是 None,
         ReservationGroup.client 寫成 NULL,後台用 filter(client=tenant) 撈不到 → 訂單消失。
    """
    from Client.models import Client

    if client_code:
        try:
            return Client.objects.get(internal_code=client_code, is_active=True)
        except Client.DoesNotExist:
            raise TenantResolutionError(f'找不到客戶代碼:{client_code}(或該客戶已停用)')

    active_clients = list(Client.objects.filter(is_active=True))
    if len(active_clients) == 1:
        return active_clients[0]
    if len(active_clients) == 0:
        raise TenantResolutionError('系統內沒有任何 active client,無法建立訂單')
    raise TenantResolutionError(
        f'URL 未指定 client_code,但系統內有 {len(active_clients)} 個 active client,'
        f'無法自動判斷;請確認前端有帶 client_code'
    )


def compute_course_price_authoritative(*, template_id, resort_name, people_count, course_date):
    """
    後端權威算價:絕對不接受前端傳來的 price / totalPrice,一律用模板+雪場+日期+人數
    在後端重算,避免使用者竄改 payload 用 1 元下單。

    Why: 前端送來的價只能拿來「對帳顯示」,寫入訂單的價必須由後端決定。
    """
    if not template_id or not resort_name or not course_date or not people_count:
        raise PriceCalculationError('算價參數不足:需要 template_id / resort / date / people_count')

    try:
        template = CourseTemplate.objects.get(id=template_id)
    except CourseTemplate.DoesNotExist:
        raise PriceCalculationError(f'找不到課程模板: {template_id}')

    try:
        resort = Resorts.objects.get(name=resort_name)
    except Resorts.DoesNotExist:
        raise PriceCalculationError(f'找不到雪場: {resort_name}')

    pricing = CoursePricing.objects.filter(
        templates=template,
        resort=resort,
        is_active=True,
    ).first()
    if not pricing:
        raise PriceCalculationError(
            f'找不到對應的價格設定(template={template_id}, resort={resort_name})'
        )

    if isinstance(course_date, str):
        course_date = datetime.strptime(course_date, '%Y-%m-%d').date()

    season_type = SeasonSetting.get_season_type_for_date(course_date)
    is_peak_season = (season_type == 'peak')

    try:
        price = pricing.calculate_price(int(people_count), is_peak_season)
    except ValueError as e:
        raise PriceCalculationError(str(e))

    return int(price)


def _resolve_coach_price_level(coach, course_type):
    """
    從教練在「該課程類型」的 CoachCourseLevel 取出 price_level。
    沒設定就回 'general'(對應 ResortFee 預設一般教練費)。
    """
    if not coach or not course_type:
        return 'general'
    level_obj = CoachCourseLevel.objects.filter(coach=coach, course_type=course_type).first()
    if not level_obj:
        return 'general'
    return _normalize_coach_fee_price_level(level_obj.price_level)


def _normalize_coach_fee_price_level(price_level):
    # ResortFee.get_coach_fee 只認 director / Lv2,其餘走 general
    return price_level if price_level in ('director', 'Lv2') else 'general'


def _resolve_template_coach_price_level(course_template, course_type):
    """
    課程模板若限制教練等級或設定排課優先教練，即使客人選「不指定教練」也要收對應費用。
    實際教練仍由排課系統從符合等級、雪場、語言與能力條件的教練中安排。
    """
    if not course_template:
        return None

    minimum_level = getattr(course_template, 'minimum_coach_price_level', '') or ''
    if minimum_level:
        return _normalize_coach_fee_price_level(minimum_level)

    allowed_manager = getattr(course_template, 'allowed_coaches', None)
    if not allowed_manager or not allowed_manager.exists():
        return None

    allowed_levels = CoachCourseLevel.objects.filter(
        coach__in=allowed_manager.all(),
        course_type=course_type,
    ).values_list('price_level', flat=True)
    fee_levels = [_normalize_coach_fee_price_level(level) for level in allowed_levels]

    for level in ('general', 'Lv2', 'director'):
        if level in fee_levels:
            return level
    return 'general'


def compute_addon_fees_authoritative(*, resort, coach, course_type, language, equipment_value,
                                     people_count, bookings_count, course_template=None):
    """
    後端權威計算「附加費」(教練指定 / 語言篩選 / 裝備),回 (coach_fee, language_fee, equipment_fee)。
    規則沿用舊版 booking/views.py:
      - 教練費:指定教練時依該教練等級收;若模板有限制教練等級/名單,即使選不指定也收模板限制費
      - 語言只作為教練篩選條件,不另外收費;英文/粵語由前端要求必須指定教練
      - 裝備費:只有 equipment='purchaseAssistanceTime'(加購協助時間)才收;依人數查 ResortFee,整組課程只收一次
    """
    bookings_count = max(int(bookings_count or 1), 1)

    # 教練指定費
    coach_fee = 0
    if coach is not None:
        price_level = _resolve_coach_price_level(coach, course_type)
    else:
        price_level = _resolve_template_coach_price_level(course_template, course_type)

    if price_level:
        coach_fee = int(ResortFee.get_coach_fee(resort, price_level)) * bookings_count

    # 語言只作為篩選條件,不另外收費
    language_fee = 0

    # 裝備費(只在「加購協助時間」收)
    equipment_fee = 0
    if equipment_value == 'purchaseAssistanceTime':
        equipment_fee = int(ResortFee.get_equipment_fee(resort, int(people_count or 1)))

    return coach_fee, language_fee, equipment_fee


EQUIPMENT_OPTION_MAP = {
    'self_rent': 'rentWithoutyourself',
    'own_equipment': 'ownWithoutAssistance',
    'class_time_help': 'assistDuringCourse',
    'extra_time_help': 'purchaseAssistanceTime',
}


COACH_PRICE_LEVEL_RANK = {
    'Lv1': 1,
    'Lv2': 2,
    'Lv3': 3,
    'director': 4,
}


def _coach_price_level_rank(value):
    return COACH_PRICE_LEVEL_RANK.get(value or '', 0)


def select_cart_group_course_template(courses, course_type, resort):
    """
    同一組預約可以包含 1-1、1-2 這種不同模板/時段。
    Reservation 只能存一個 course_template，因此用整組中「教練門檻最高」的模板代表排課條件。
    """
    templates = []
    for course in courses or []:
        template_id = course.get('courseTemplateId')
        course_template = CourseTemplate.objects.select_related('course_type').prefetch_related(
            'resorts',
            'allowed_coaches',
        ).filter(id=template_id).first()
        if not course_template:
            raise ValueError(f"找不到課程模板: {template_id}")
        if course_template.course_type_id != course_type.id:
            raise ValueError('同一組預約內的課程模板與課程類型不一致，請分成不同組別')
        if course_template.resorts.exists() and not course_template.resorts.filter(id=resort.id).exists():
            raise ValueError('此課程模板不適用於選擇的雪場')
        templates.append(course_template)

    if not templates:
        raise ValueError('此組預約沒有課程模板')

    return sorted(
        templates,
        key=lambda template: (
            _coach_price_level_rank(template.minimum_coach_price_level),
            int(getattr(template, 'duration_hours', 0) or 0),
            template.id,
        ),
        reverse=True,
    )[0]


def normalize_discount_code(value):
    return (value or '').strip().upper()


def compute_cart_item_pricing_authoritative(item):
    courses = item.get('courses') or []
    if not courses:
        raise ValueError('購物車項目缺少課程')

    try:
        resort = Resorts.objects.get(name=item['resort'])
    except Resorts.DoesNotExist:
        raise ValueError(f"找不到雪場 {item.get('resort')}")

    first_course = courses[0]
    try:
        course_type = CourseType.objects.select_related('category').get(id=first_course['courseTypeId'])
    except CourseType.DoesNotExist:
        raise ValueError(f"找不到課程類型 {first_course.get('courseTypeId')}")

    coach_instance = None
    coach_id = item.get('coach')
    if coach_id not in ('any', None, ''):
        try:
            coach_instance = Coach.objects.get(id=coach_id)
        except Coach.DoesNotExist:
            coach_instance = None

    people_count = int(item.get('peopleCount', 1) or 1)
    course_fee = 0
    duration_hours_total = 0
    group_course_template = select_cart_group_course_template(courses, course_type, resort)
    for course in courses:
        course_fee += compute_course_price_authoritative(
            template_id=course.get('courseTemplateId'),
            resort_name=item['resort'],
            people_count=people_count,
            course_date=course['date'],
        )
        template = CourseTemplate.objects.filter(id=course.get('courseTemplateId')).first()
        duration_hours_total += int(getattr(template, 'duration_hours', 0) or course.get('durationHours') or 0)

    equipment_value = EQUIPMENT_OPTION_MAP.get(item.get('equipmentOption'))
    language_value = item.get('language', 'zh') or 'zh'
    coach_fee, language_fee, equipment_fee = compute_addon_fees_authoritative(
        resort=resort,
        coach=coach_instance,
        course_type=course_type,
        language=language_value,
        equipment_value=equipment_value,
        people_count=people_count,
        bookings_count=len(courses),
        course_template=group_course_template,
    )

    service_type = infer_cart_item_service_type(item, course_type)
    subtotal = course_fee + coach_fee + language_fee + equipment_fee

    return {
        'resort': resort,
        'course_type': course_type,
        'service_type': service_type,
        'course_fee': int(course_fee),
        'coach_fee': int(coach_fee),
        'language_fee': int(language_fee),
        'equipment_fee': int(equipment_fee),
        'subtotal': int(subtotal),
        'course_count': len(courses),
        'duration_hours_total': duration_hours_total,
    }


def is_new_customer_for_discount(tenant_client, user, contact_info):
    phone = (contact_info or {}).get('phone') or ''
    groups = ReservationGroup.objects.filter(client=tenant_client)

    if user and groups.filter(user=user).exists():
        return False

    if phone:
        try:
            if Payment.objects.filter(
                reservation_group__client=tenant_client,
                DataJSON__contact__phone=phone,
            ).exists():
                return False
        except Exception:
            pass

    return True


def discount_rule_is_active(rule, now):
    if not rule.is_active:
        return False, '折扣碼已停用'
    if rule.start_at and now < rule.start_at:
        return False, '折扣尚未開始'
    if rule.end_at and now > rule.end_at:
        return False, '折扣已過期'
    if rule.usage_limit is not None and rule.used_count >= rule.usage_limit:
        return False, '折扣碼使用次數已滿'
    return True, ''


def get_discount_eligible_indices(rule, cart_items):
    service_types = {item['service_type'] for item in cart_items}
    has_ski = 'ski' in service_types
    has_photo = 'photo' in service_types

    if rule.apply_scope == DiscountCode.APPLY_SCOPE_SKI:
        return [index for index, item in enumerate(cart_items) if item['service_type'] == 'ski'], ''
    if rule.apply_scope == DiscountCode.APPLY_SCOPE_PHOTO:
        return [index for index, item in enumerate(cart_items) if item['service_type'] == 'photo'], ''
    if rule.apply_scope == DiscountCode.APPLY_SCOPE_BUNDLE:
        if not (has_ski and has_photo):
            return [], '此優惠需同時購買滑雪課程與攝影服務'
        return [index for index, item in enumerate(cart_items) if item['service_type'] == 'photo'], ''
    return list(range(len(cart_items))), ''


def get_discount_unit_count(rule, cart_items, eligible_indices):
    mode = getattr(rule, 'amount_apply_mode', DiscountCode.AMOUNT_APPLY_MODE_ORDER)
    if mode == DiscountCode.AMOUNT_APPLY_MODE_ITEM:
        return len(eligible_indices)
    if mode == DiscountCode.AMOUNT_APPLY_MODE_COURSE:
        return sum(cart_items[index].get('course_count', 0) for index in eligible_indices)
    if mode == DiscountCode.AMOUNT_APPLY_MODE_HOUR:
        return sum(cart_items[index].get('duration_hours_total', 0) for index in eligible_indices)
    return 1


def calculate_discount_amount(rule, base_amount, unit_count=1):
    if base_amount <= 0:
        return 0
    if rule.discount_type == DiscountCode.DISCOUNT_TYPE_PERCENT:
        amount = (base_amount * int(rule.discount_value or 0)) // 100
        if rule.max_discount_amount:
            amount = min(amount, int(rule.max_discount_amount))
        return min(amount, base_amount)
    amount = int(rule.discount_value or 0) * max(int(unit_count or 1), 1)
    return min(amount, base_amount)


def allocate_discount_amount(amount, eligible_indices, remaining_by_index):
    allocations = {}
    eligible = [(index, remaining_by_index.get(index, 0)) for index in eligible_indices]
    eligible = [(index, remaining) for index, remaining in eligible if remaining > 0]
    total_remaining = sum(remaining for _, remaining in eligible)
    if amount <= 0 or total_remaining <= 0:
        return allocations

    amount_left = min(amount, total_remaining)
    for position, (index, remaining) in enumerate(eligible):
        if position == len(eligible) - 1:
            share = min(remaining, amount_left)
        else:
            share = min(remaining, (amount * remaining) // total_remaining)
            share = min(share, amount_left)
        if share > 0:
            allocations[index] = share
            amount_left -= share
    return allocations


def evaluate_discount_rule(rule, cart_items, remaining_by_index, subtotal, is_new_customer):
    is_active, reason = discount_rule_is_active(rule, timezone.now())
    if not is_active:
        return None, reason

    if rule.min_order_amount and subtotal < rule.min_order_amount:
        return None, f'訂單需滿 NT$ {rule.min_order_amount}'

    if getattr(rule, 'new_customer_only', False) and not is_new_customer:
        return None, '此折扣僅限新客使用'

    total_course_count = sum(item['course_count'] for item in cart_items)
    if rule.require_multiple_items and len(cart_items) < 2 and total_course_count < 2:
        return None, '此優惠需搭配多項課程或服務'

    eligible_indices, scope_reason = get_discount_eligible_indices(rule, cart_items)
    if not eligible_indices:
        return None, scope_reason or '此折扣不適用於目前購物車'

    eligible_base = sum(remaining_by_index.get(index, 0) for index in eligible_indices)
    unit_count = get_discount_unit_count(rule, cart_items, eligible_indices)
    amount = calculate_discount_amount(rule, eligible_base, unit_count)
    if amount <= 0:
        return None, '目前沒有可折抵金額'

    allocations = allocate_discount_amount(amount, eligible_indices, remaining_by_index)
    allocated_amount = sum(allocations.values())
    if allocated_amount <= 0:
        return None, '目前沒有可折抵金額'

    return {
        'id': rule.id,
        'code': rule.code,
        'name': rule.name or rule.code,
        'amount': allocated_amount,
        'is_auto_apply': getattr(rule, 'is_auto_apply', False),
        'new_customer_only': getattr(rule, 'new_customer_only', False),
        'apply_scope': rule.apply_scope,
        'amount_apply_mode': getattr(rule, 'amount_apply_mode', DiscountCode.AMOUNT_APPLY_MODE_ORDER),
        'can_combine': rule.can_combine,
        'allocations': allocations,
    }, ''


def discount_rule_can_stack(rule, applied_discounts):
    if not applied_discounts:
        return True
    if not rule.can_combine:
        return False

    # Bundle discounts are add-on incentives, e.g. ski course + photo.
    # Let them stack on top of a broad order discount so an early-bird promo
    # does not silently hide the photo per-hour discount.
    if rule.apply_scope == DiscountCode.APPLY_SCOPE_BUNDLE:
        return not any(
            discount.get('apply_scope') == DiscountCode.APPLY_SCOPE_BUNDLE
            for discount in applied_discounts
        )

    return all(discount['can_combine'] for discount in applied_discounts)


def calculate_cart_discount_summary(cart_data, tenant_client, user=None, contact_info=None, discount_code=''):
    cart_items = []
    for item in cart_data:
        cart_items.append(compute_cart_item_pricing_authoritative(item))

    subtotal = sum(item['subtotal'] for item in cart_items)
    remaining_by_index = {index: item['subtotal'] for index, item in enumerate(cart_items)}
    item_discount_amounts = [0 for _ in cart_items]
    applied_discounts = []
    manual_error = ''
    is_new_customer = is_new_customer_for_discount(tenant_client, user, contact_info)
    manual_code = normalize_discount_code(discount_code)

    rules = []
    if manual_code:
        manual_rule = DiscountCode.objects.filter(
            client=tenant_client,
            code__iexact=manual_code,
        ).order_by('-is_active', '-created_at', 'id').first()
        if manual_rule:
            rules.append(manual_rule)
        else:
            manual_error = '找不到此折扣碼'

    auto_rules = DiscountCode.objects.filter(
        client=tenant_client,
        is_auto_apply=True,
    ).order_by('id')
    if manual_code:
        auto_rules = auto_rules.exclude(code__iexact=manual_code)
    rules.extend(list(auto_rules))

    for rule in rules:
        if not discount_rule_can_stack(rule, applied_discounts):
            continue

        result, reason = evaluate_discount_rule(
            rule,
            cart_items,
            remaining_by_index,
            subtotal,
            is_new_customer,
        )
        if not result:
            if manual_code and normalize_discount_code(rule.code) == manual_code:
                manual_error = reason
            continue

        for index, amount in result['allocations'].items():
            remaining_by_index[index] = max(remaining_by_index.get(index, 0) - amount, 0)
            item_discount_amounts[index] += amount
        applied_discounts.append(result)

    discount_total = sum(item_discount_amounts)
    public_discounts = []
    for discount in applied_discounts:
        public_discounts.append({
            'id': discount['id'],
            'code': discount['code'],
            'name': discount['name'],
            'amount': discount['amount'],
            'is_auto_apply': discount['is_auto_apply'],
            'new_customer_only': discount['new_customer_only'],
            'apply_scope': discount['apply_scope'],
            'amount_apply_mode': discount['amount_apply_mode'],
        })

    return {
        'subtotal': subtotal,
        'discount_total': discount_total,
        'total': max(subtotal - discount_total, 0),
        'item_subtotals': [item['subtotal'] for item in cart_items],
        'item_discount_amounts': item_discount_amounts,
        'applied_discounts': public_discounts,
        'applied_discount_details': applied_discounts,
        'discount_code_error': manual_error,
        'is_new_customer': is_new_customer,
    }


def increment_discount_usage(applied_discounts):
    seen_ids = set()
    for discount in applied_discounts:
        discount_id = discount.get('id')
        if not discount_id or discount_id in seen_ids:
            continue
        seen_ids.add(discount_id)
        DiscountCode.objects.filter(id=discount_id).update(used_count=F('used_count') + 1)


def parse_time_value(value):
    if not value:
        return None
    if hasattr(value, 'hour'):
        return value
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(str(value), fmt).time()
        except ValueError:
            continue
    return None


def resolve_equipment_assistance_time_slot(
    resort,
    equipment_value,
    slot_id,
    duration_hours=None,
    session_start_time=None,
    course_template_id=None,
):
    if equipment_value != 'purchaseAssistanceTime':
        return None, ''

    if not slot_id:
        raise ValueError('equipmentAssistanceTimeSlotId is required for purchaseAssistanceTime')

    try:
        slot_id = int(slot_id)
    except (TypeError, ValueError):
        raise ValueError('equipmentAssistanceTimeSlotId must be a number')

    try:
        slot = EquipmentAssistanceTimeSlot.objects.get(
            id=slot_id,
            resort=resort,
            is_active=True,
        )
    except EquipmentAssistanceTimeSlot.DoesNotExist:
        raise ValueError('Selected equipment assistance time slot is not available')

    if slot.equipment_option != equipment_value:
        raise ValueError('Selected equipment assistance time slot does not match equipment option')

    parsed_start_time = parse_time_value(session_start_time)
    if not slot.matches_course(
        duration_hours=duration_hours,
        session_start_time=parsed_start_time,
        course_template_id=course_template_id,
    ):
        raise ValueError('Selected equipment assistance time slot does not match selected course time')

    return slot, slot.display_label()


def get_request_user_or_none(request):
    return request.user if getattr(request, 'user', None) and request.user.is_authenticated else None


def normalize_contact_info(request):
    contact = request.data.get('contact') or {}
    if not isinstance(contact, dict):
        contact = {}

    user = get_request_user_or_none(request)
    name = (contact.get('name') or '').strip()
    email = (contact.get('email') or '').strip()
    phone = (contact.get('phone') or '').strip()
    messenger_type = (
        contact.get('messengerType') or
        contact.get('messenger_type') or
        contact.get('communication_type') or
        ''
    ).strip()
    messenger_id = (
        contact.get('messengerId') or
        contact.get('messenger_id') or
        contact.get('communication_id') or
        ''
    ).strip()
    referral_source = (
        contact.get('referralSource') or
        contact.get('referral_source') or
        contact.get('referrer') or
        ''
    ).strip()

    if user:
        name = name or user.get_full_name() or user.username
        email = email or user.email

    return {
        'name': name,
        'email': email,
        'phone': phone,
        'messenger_type': messenger_type,
        'messenger_id': messenger_id,
        'referral_source': referral_source,
    }


class SiteContentListAPI(APIView):
    """
    GET /booking/<client_code>/api/site-content/

    官網公開內容清單。預設只回傳狀態為進行中、且在顯示期間內的內容。
    """
    permission_classes = []

    def get(self, request, client_code=None):
        try:
            client = resolve_tenant_client(client_code)
        except TenantResolutionError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        qs = SiteContent.objects.filter(client=client)
        content_type = (request.GET.get('content_type') or '').strip()
        location_key = (request.GET.get('location_key') or '').strip()
        tag = (request.GET.get('tag') or '').strip()

        if content_type:
            qs = qs.filter(content_type=content_type)
        if location_key:
            qs = qs.filter(location_key=location_key)
        if tag:
            qs = qs.filter(tags__contains=[tag])

        now = timezone.now()
        include_ended = str(request.GET.get('include_ended') or '').lower() in ('1', 'true', 'yes')
        if include_ended:
            qs = qs.exclude(status__in=['draft', 'hidden']).filter(
                Q(start_at__isnull=True) | Q(start_at__lte=now) | Q(status='ended'),
            )
        else:
            qs = qs.filter(status='active').filter(
                Q(start_at__isnull=True) | Q(start_at__lte=now),
            ).filter(
                Q(end_at__isnull=True) | Q(end_at__gte=now),
            )

        qs = qs.order_by('content_type', 'location_key', '-is_pinned', 'display_order', '-created_at')

        limit = request.GET.get('limit')
        if limit:
            try:
                qs = qs[:max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass

        data = [
            {
                'id': item.id,
                'content_type': item.content_type,
                'location_key': item.location_key,
                'title': item.title,
                'subtitle': item.subtitle,
                'summary': item.summary,
                'body': item.body,
                'image_url': item.image_url,
                'link_url': item.link_url,
                'source': item.source,
                'external_id': item.external_id,
                'tags': item.tags if isinstance(item.tags, list) else [],
                'metadata': item.metadata if isinstance(item.metadata, dict) else {},
                'status': item.computed_status,
                'start_at': item.start_at.isoformat() if item.start_at else None,
                'end_at': item.end_at.isoformat() if item.end_at else None,
                'display_order': item.display_order,
                'is_pinned': item.is_pinned,
                'created_at': item.created_at.isoformat() if item.created_at else None,
                'updated_at': item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in qs
        ]

        return Response(data, status=status.HTTP_200_OK)


class CoachListAPI(APIView):
    """
    GET /api/coaches/
    查詢符合條件的教練列表

    參數：
    - resort: 雪場名稱
    - courseType: 課程類型 ID
    - abilityLevel: 能力等級（可選）
    """

    certification_category_labels = {
        'ski': '雙板',
        'snowboard': '單板',
        'other': '其他',
    }
    price_level_labels = {
        'Lv1': 'Lv1',
        'Lv2': 'Lv2',
        'Lv3': 'Lv3',
        'director': '校長 / 總監',
    }
    availability_status_labels = {
        'active': '可指定',
        'passive': '需確認',
        'unavailable': '不可接課',
    }

    def _format_certification(self, item):
        parts = []
        category = item.get('category')
        if category in self.certification_category_labels:
            parts.append(self.certification_category_labels[category])
        if item.get('certificate'):
            parts.append(str(item.get('certificate')).strip())
        if item.get('level'):
            parts.append(str(item.get('level')).strip())
        if item.get('note'):
            parts.append(str(item.get('note')).strip())
        return ' '.join([part for part in parts if part])

    def _get_booking_certifications(self, coach):
        certifications = coach.certifications if isinstance(coach.certifications, list) else []
        visible_certifications = []
        for item in certifications:
            if not isinstance(item, dict):
                continue
            if item.get('category') == 'photo':
                continue
            if item.get('show_on_website') is False:
                continue
            text = self._format_certification(item)
            if text:
                visible_certifications.append({
                    'category': item.get('category') or 'other',
                    'certificate': item.get('certificate') or '',
                    'level': item.get('level') or '',
                    'note': item.get('note') or '',
                    'text': text,
                })
        return visible_certifications

    def _parse_requested_dates(self, request):
        raw_values = []
        for key in ('courseDates', 'course_dates', 'dates', 'date'):
            raw_values.extend(request.GET.getlist(key))
            raw_values.extend(request.GET.getlist(f'{key}[]'))

        parsed_dates = []
        seen = set()
        for raw_value in raw_values:
            for raw_date in str(raw_value or '').split(','):
                raw_date = raw_date.strip()
                if not raw_date or raw_date in seen:
                    continue
                try:
                    parsed_date = datetime.strptime(raw_date, '%Y-%m-%d').date()
                except ValueError:
                    continue
                seen.add(raw_date)
                parsed_dates.append(parsed_date)
        return parsed_dates

    def _get_requested_session(self, request):
        session_id = (
            request.GET.get('timeSlot') or
            request.GET.get('time_slot') or
            request.GET.get('session_id') or
            ''
        )
        if not session_id:
            return None
        try:
            session_pk = int(session_id)
        except (TypeError, ValueError):
            return None
        return CourseSession.objects.filter(id=session_pk, is_active=True).first()

    def _coach_is_unavailable_for_request(self, coach, requested_dates, session):
        if not requested_dates or not session:
            return False

        leave_ranges = CoachLeaveRequest.objects.filter(
            coach=coach,
            status='approved',
            start_date__lte=max(requested_dates),
            end_date__gte=min(requested_dates),
        ).values_list('start_date', 'end_date')
        for leave_start, leave_end in leave_ranges:
            if any(leave_start <= requested_date <= leave_end for requested_date in requested_dates):
                return True

        return Booking.objects.filter(
            reservation__preferred_coach=coach,
            reservation__is_preferred_coach=True,
            reservation__status__in=SCHEDULED_RESERVATION_STATUSES,
            is_scheduled=True,
            date__in=requested_dates,
            start_time__lt=session.end_time,
            end_time__gt=session.start_time,
        ).exists()

    def get(self, request, client_code=None):
        resort_name = request.GET.get('resort', '')
        course_type = request.GET.get('courseType', '')
        ability_level = request.GET.get('abilityLevel', '')
        requested_dates = self._parse_requested_dates(request)
        requested_session = self._get_requested_session(request)
        course_template_id = (
            request.GET.get('courseTemplate') or
            request.GET.get('courseTemplateId') or
            request.GET.get('template_id') or
            ''
        )
        course_template = None
        if course_template_id:
            course_template = CourseTemplate.objects.select_related('course_type').prefetch_related('allowed_coaches').filter(
                id=course_template_id
            ).first()
            if course_template:
                course_type = str(course_template.course_type_id)

        # 1. 攝影課程不可指定教練
        if course_type == 'Photography':
            return Response({
                'coach_list': [],
                'courses': []
            }, status=status.HTTP_200_OK)

        # 2. 檢查雪場是否啟用自動排課
        try:
            resort_obj = Resorts.objects.get(name=resort_name)
            if not resort_obj.auto_scheduling_enabled:
                return Response({
                    'coach_list': [],
                    'courses': []
                }, status=status.HTTP_200_OK)
        except Resorts.DoesNotExist:
            return Response({
                'coach_list': [],
                'courses': []
            }, status=status.HTTP_404_NOT_FOUND)

        # 3. 查詢符合條件的教練
        coach_ids_resort = CoachResort.objects.filter(
            resort__id=resort_obj.id
        ).values_list('coach_id', flat=True)

        coach_ids_course = CoachCourseLevel.objects.filter(
            course_type=course_type
        ).values_list('coach_id', flat=True)

        # 交集：同時符合雪場和課程類型
        coach_ids = set(coach_ids_resort) & set(coach_ids_course)
        allowed_coach_ids = set()
        if course_template:
            allowed_coach_ids = set(course_template.allowed_coaches.values_list('id', flat=True))

        # 如果有能力等級要求，再過濾
        if ability_level:
            ability_order = [item[0] for item in ABILITY_LEVEL_CHOICES]
            normalized_ability_level = normalize_ability_level(ability_level)
            try:
                desired_ability_index = ability_order.index(normalized_ability_level)
            except ValueError:
                desired_ability_index = -1

            def coach_can_teach_selected_ability(ccl):
                raw_levels = ccl.ability_levels or []
                if isinstance(raw_levels, str):
                    raw_levels = [item.strip() for item in raw_levels.split(',') if item.strip()]
                for raw_level in raw_levels:
                    normalized_raw_level = normalize_ability_level(raw_level)
                    try:
                        if ability_order.index(normalized_raw_level) >= desired_ability_index:
                            return True
                    except ValueError:
                        continue
                return False

            coach_ids_ability = [
                ccl.coach_id
                for ccl in CoachCourseLevel.objects.filter(course_type=course_type)
                if coach_can_teach_selected_ability(ccl)
            ]
            coach_ids = coach_ids & set(coach_ids_ability)

        # 判斷用戶權限（管理員可看所有教練）
        is_manager = False
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_profile = getattr(request.user, 'userprofile', None)
            if user_profile:
                is_manager = user_profile.is_manager

        # 根據權限查詢教練
        if is_manager:
            coaches = Coach.objects.filter(id__in=coach_ids)
        else:
            # 一般用戶顯示主動接課與需確認接課；不可接課仍排除
            coaches = Coach.objects.filter(
                id__in=coach_ids,
                availability_status__in=['active', 'passive']
            )

        # 組裝教練資料
        coach_list = []
        lang_map = {
            "zh": "中文",
            "en": "英文",
            "yue": "粵語",
        }

        for coach in coaches:
            if self._coach_is_unavailable_for_request(coach, requested_dates, requested_session):
                continue

            course_level = CoachCourseLevel.objects.filter(
                coach=coach,
                course_type=course_type,
            ).first()
            if course_template:
                from .scheduler import coach_matches_course_template
                if not coach_matches_course_template(
                    coach,
                    course_template,
                    coach_course_level=course_level,
                    allowed_coach_ids=allowed_coach_ids,
                ):
                    continue
            price_level = course_level.price_level if course_level else 'Lv1'
            ability_levels_raw = course_level.ability_levels if course_level else []
            ability_levels = normalize_ability_levels(ability_levels_raw)
            certifications = self._get_booking_certifications(coach)

            # 處理語言
            languages = coach.languages or ""
            if isinstance(languages, str):
                languages = [l.strip() for l in languages.split(',') if l.strip()]
            elif not isinstance(languages, list):
                languages = ['中文']

            languages = [lang_map.get(l, l) for l in languages]

            # 處理圖片
            image_url = coach.img if coach.img else 'https://host.flashfalcon.info/static/manager/img/logo.png'

            coach_data = {
                'pk': coach.pk,
                'name': f"{coach.name} (僅管理員可見)" if is_manager and coach.availability_status != 'active' else coach.name,
                'description': "",
                'specialties': [],
                'languages': languages,
                'image': image_url,
                'price_level': price_level,
                'price_level_label': self.price_level_labels.get(price_level, price_level),
                'ability_levels': ability_levels,
                'availability_status': coach.availability_status,
                'availability_status_label': self.availability_status_labels.get(
                    coach.availability_status,
                    coach.availability_status
                ),
                'requires_confirmation': coach.availability_status == 'passive',
                'certifications': certifications,
                'certification_text': ' / '.join([item['text'] for item in certifications]),
            }
            coach_list.append(coach_data)

        return Response({
            'coach_list': coach_list,
            'courses': [],
            'template_rule': course_template.get_minimum_coach_price_level_display() if course_template and course_template.minimum_coach_price_level else '',
        }, status=status.HTTP_200_OK)


class WebsiteCoachListAPI(APIView):
    """
    GET /booking/<client_code>/api/website-coaches/
    Public website coach cards controlled by Coach.website_enabled.
    """
    permission_classes = []

    certification_category_labels = {
        'ski': '雙板 Ski',
        'snowboard': '單板 Snowboard',
        'other': '其他',
    }

    def _format_certification(self, item):
        parts = []
        category = item.get('category')
        if category in self.certification_category_labels:
            parts.append(self.certification_category_labels[category])
        if item.get('certificate'):
            parts.append(str(item.get('certificate')).strip())
        if item.get('level'):
            parts.append(str(item.get('level')).strip())
        if item.get('note'):
            parts.append(str(item.get('note')).strip())
        return ' '.join([part for part in parts if part])

    def _get_website_certifications(self, coach):
        certifications = coach.certifications if isinstance(coach.certifications, list) else []
        visible_certifications = []
        for item in certifications:
            if not isinstance(item, dict):
                continue
            if item.get('category') == 'photo':
                continue
            if item.get('show_on_website') is False:
                continue
            text = self._format_certification(item)
            if text:
                visible_certifications.append({
                    'category': item.get('category') or 'other',
                    'certificate': item.get('certificate') or '',
                    'level': item.get('level') or '',
                    'note': item.get('note') or '',
                    'text': text,
                })
        return visible_certifications

    def get(self, request, client_code=None):
        try:
            coaches = Coach.objects.filter(website_enabled=True)

            if client_code:
                client = resolve_tenant_client(client_code)
                coaches = coaches.filter(client=client)

            coaches = coaches.prefetch_related(
                'course_levels__course_type__category',
            ).order_by('website_sort_order', 'id')

            language_labels = {
                'zh': '中文',
                'en': '英文',
                'yue': '粵語',
            }

            data = []
            for coach in coaches:
                language_codes = coach.languages or []
                if isinstance(language_codes, str):
                    language_codes = [item.strip() for item in language_codes.split(',') if item.strip()]
                else:
                    language_codes = list(language_codes)

                course_categories = []
                course_types = []
                for level in coach.course_levels.all():
                    course_type = level.course_type
                    if not course_type:
                        continue

                    category = getattr(course_type, 'category', None)
                    if category and getattr(category, 'service_type', '') == CourseCategory.SERVICE_TYPE_PHOTO:
                        continue

                    course_types.append(course_type.name)
                    if category:
                        course_categories.append(category.name)

                course_categories = list(dict.fromkeys(course_categories))
                course_types = list(dict.fromkeys(course_types))
                image_url = (coach.img or '').strip()
                if image_url.lower() == 'none':
                    image_url = ''

                website_certifications = self._get_website_certifications(coach)

                data.append({
                    'id': coach.id,
                    'name': coach.name or '',
                    'slug': coach.website_slug or '',
                    'image': image_url,
                    'languages': language_codes,
                    'languages_display': [language_labels.get(code, code) for code in language_codes],
                    'languages_text': ' / '.join([language_labels.get(code, code) for code in language_codes]),
                    'course_categories': course_categories,
                    'course_types': course_types,
                    'coach_type': ' / '.join([item['text'] for item in website_certifications] or course_categories or course_types),
                    'certifications': website_certifications,
                    'certification_text': ' / '.join([item['text'] for item in website_certifications]),
                    'card_bio': coach.website_card_bio or '',
                    'availability_status': coach.availability_status,
                    'sort_order': coach.website_sort_order,
                })

            return Response({
                'code': 200,
                'msg': 'OK',
                'data': {'list': data, 'total': len(data)},
            }, status=status.HTTP_200_OK)
        except TenantResolutionError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)


class CoachBookingsAPI(APIView):
    """
    GET /api/coach-bookings/
    查詢教練的已預約時段和請假日期

    參數：
    - coach_id: 教練 ID
    """

    def get(self, request, client_code=None):
        coach_id = request.GET.get('coach_id', '')
        booked_slots = []
        unavailable_dates = []

        if coach_id and coach_id != "any":
            coach_instance = get_object_or_404(Coach, pk=coach_id)

            # 獲取已預約時段
            booked_slots = self._get_booked_slots(coach_instance)

            # 獲取已批准的請假日期
            approved_leaves = CoachLeaveRequest.objects.filter(
                coach=coach_instance,
                status='approved'
            )

            for leave in approved_leaves:
                current_date = leave.start_date
                while current_date <= leave.end_date:
                    unavailable_dates.append(current_date.strftime('%Y-%m-%d'))
                    current_date += timedelta(days=1)

        return Response({
            "coach_id": coach_id,
            "booked_slots": booked_slots,
            "unavailable_dates": unavailable_dates
        }, status=status.HTTP_200_OK)

    def _get_booked_slots(self, coach):
        """獲取教練的已預約時段"""
        from .models import Reservation

        reservations = Reservation.objects.filter(
            preferred_coach=coach,
            status__in=['auto_assigned', 'manually_assigned', 'pending_coach_confirmation']
        ).prefetch_related('bookings')

        booked_slots = []
        for resv in reservations:
            for booking in resv.bookings.all():
                booked_slots.append({
                    'date': booking.date,
                    'start_time': booking.start_time.strftime('%H:%M'),
                    'end_time': booking.end_time.strftime('%H:%M'),
                })

        return booked_slots


class CalculatePriceAPI(APIView):
    """
    GET /api/calculate-price/
    計算課程價格

    參數：
    - template_id: 課程模板 ID
    - people_count: 人數
    - date: 日期 (YYYY-MM-DD)
    - resort: 雪場名稱
    """

    def get(self, request, client_code=None):
        try:
            template_id = request.GET.get('template_id')
            people_count = int(request.GET.get('people_count', 1))
            # 接受 'date' 或 'course_date' 兩種參數名
            date_str = request.GET.get('date') or request.GET.get('course_date')
            resort_name = request.GET.get('resort')

            if not all([template_id, date_str, resort_name]):
                return Response(
                    {'error': '缺少必要參數'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 與下單共用同一條算價路徑,避免「顯示價」與「入帳價」不一致
            price = compute_course_price_authoritative(
                template_id=template_id,
                resort_name=resort_name,
                people_count=people_count,
                course_date=date_str,
            )

            template = CourseTemplate.objects.get(id=template_id)
            resort = Resorts.objects.get(name=resort_name)
            coach = None
            coach_id = request.GET.get('coach') or request.GET.get('coach_id')
            if coach_id and coach_id != 'any':
                try:
                    coach = Coach.objects.get(id=coach_id)
                except Coach.DoesNotExist:
                    coach = None
            if coach:
                from .scheduler import coach_matches_course_template, course_template_restriction_label
                if not coach_matches_course_template(coach, template):
                    rule_label = course_template_restriction_label(template) or '指定教練限制'
                    return Response(
                        {'error': f'此課程模板需要符合教練條件（{rule_label}），請重新選擇教練'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            equipment_mapping = {
                'self_rent': 'rentWithoutyourself',
                'own_equipment': 'ownWithoutAssistance',
                'class_time_help': 'assistDuringCourse',
                'extra_time_help': 'purchaseAssistanceTime',
            }
            equipment_option = request.GET.get('equipment_option') or request.GET.get('equipmentOption')
            equipment_value = equipment_mapping.get(equipment_option) if equipment_option else None
            language_value = request.GET.get('language') or 'zh'
            bookings_count = int(request.GET.get('bookings_count') or 1)
            coach_fee, language_fee, equipment_fee = compute_addon_fees_authoritative(
                resort=resort,
                coach=coach,
                course_type=template.course_type,
                language=language_value,
                equipment_value=equipment_value,
                people_count=people_count,
                bookings_count=bookings_count,
                course_template=template,
            )
            return Response({
                'price': price,
                'course_fee': price,
                'coach_fee': coach_fee,
                'language_fee': language_fee,
                'equipment_rental_fee': equipment_fee,
                'total_price': price + coach_fee + language_fee + equipment_fee,
                'course_type_id': template.course_type.id,
                'course_type_name': template.course_type.name,
                'course_template_name': template.name,
                'duration_hours': template.duration_hours,
            }, status=status.HTTP_200_OK)

        except PriceCalculationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def merge_resort_names(*name_lists):
    names = []
    seen = set()
    for name_list in name_lists:
        for name in name_list:
            if not name:
                continue
            key = str(name)
            if key in seen:
                continue
            seen.add(key)
            names.append(key)
    return names


def get_category_frontend_resorts(category):
    explicit_resorts = list(category.available_resorts.values_list('name', flat=True))
    active_template_resorts = list(CourseTemplate.objects.filter(
        course_type__category=category,
        is_active=True,
    ).exclude(resorts__isnull=True).values_list('resorts__name', flat=True).distinct())
    template_resorts = list(get_frontend_priced_course_templates().filter(
        course_type__category=category,
        resorts=F('pricing_options__resort'),
    ).exclude(resorts__isnull=True).values_list('resorts__name', flat=True).distinct())

    # 前台預約以「實際可預約模板」綁定的雪場為準；若尚未建立模板綁定，再退回大類設定。
    if active_template_resorts:
        return merge_resort_names(template_resorts)
    return merge_resort_names(explicit_resorts)


def get_course_type_frontend_resorts(course_type):
    explicit_resorts = list(course_type.available_resorts.values_list('name', flat=True))
    active_template_resorts = list(course_type.templates.filter(
        is_active=True,
    ).exclude(resorts__isnull=True).values_list('resorts__name', flat=True).distinct())
    template_resorts = list(get_frontend_priced_course_templates().filter(
        course_type=course_type,
        resorts=F('pricing_options__resort'),
    ).exclude(resorts__isnull=True).values_list('resorts__name', flat=True).distinct())

    # 同大類邏輯：有模板雪場時，避免舊的類型雪場設定把不可預約雪場帶到前台。
    if active_template_resorts:
        return merge_resort_names(template_resorts)
    return merge_resort_names(explicit_resorts)


def get_frontend_bookable_course_templates(today=None):
    """
    前台可選課程：已啟用、目前在報名窗口內，且課程季節尚未結束。

    不檢查 course_start_date <= today，因為未來雪季只要已開放報名就應可預約。
    """
    today = today or timezone.localdate()
    return CourseTemplate.objects.filter(
        is_active=True,
    ).filter(
        Q(booking_open_date__isnull=True) | Q(booking_open_date__lte=today),
        Q(booking_close_date__isnull=True) | Q(booking_close_date__gte=today),
        Q(course_end_date__isnull=True) | Q(course_end_date__gte=today),
    )


def get_frontend_priced_course_templates(today=None, resort_name=None):
    templates = get_frontend_bookable_course_templates(today).filter(
        pricing_options__is_active=True,
    )
    if resort_name:
        templates = templates.filter(pricing_options__resort__name=resort_name)
    return templates.distinct()


class CourseCategoryListAPI(APIView):
    """
    GET /api/course-categories/
    獲取指定客戶的課程大類

    返回：課程大類列表（單板/雙板/攝影等）
    """
    permission_classes = []  # 公開 API

    def get(self, request, client_code=None):
        service_type = request.GET.get('service_type')
        has_service_type_column = model_table_has_column(CourseCategory, 'service_type')

        # 根據 client_code 過濾課程大類
        if client_code:
            from Client.models import Client
            try:
                client = Client.objects.get(internal_code=client_code, is_active=True)
                categories = CourseCategory.objects.filter(client=client)
            except Client.DoesNotExist:
                return Response({
                    'error': f'找不到客戶: {client_code}'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # 向後相容：如果沒有 client_code，返回所有
            categories = CourseCategory.objects.all()

        if has_service_type_column and service_type:
            categories = categories.filter(service_type=service_type)

        if not has_service_type_column:
            categories = categories.only('id', 'name', 'display_order')

        categories = categories.order_by('display_order')

        data = []
        for category in categories:
            category_service_type = (
                category.service_type
                if has_service_type_column
                else infer_legacy_category_service_type(category.name)
            )
            if service_type and category_service_type != service_type:
                continue
            data.append({
                'id': category.id,
                'name': category.name,
                'service_type': category_service_type,
                'display_order': category.display_order,
                'available_resorts': get_category_frontend_resorts(category)
            })

        return Response(data, status=status.HTTP_200_OK)


class ResortListAPI(APIView):
    """
    GET /api/resorts/
    獲取所有雪場列表

    返回：雪場列表
    """
    permission_classes = []  # 公開 API

    def get(self, request, client_code=None):
        resorts = Resorts.objects.prefetch_related(
            'equipment_rental_items',
            'equipment_assistance_time_slots',
            'equipment_assistance_time_slots__course_templates',
        ).all()

        data = []
        for resort in resorts:
            data.append({
                'name': resort.name,
                'display_name': resort.display_name,
                'auto_scheduling_enabled': resort.auto_scheduling_enabled,
                'equipment_rental_items': [
                    {
                        'id': item.id,
                        'code': item.code,
                        'name': item.name,
                        'daily_price': item.daily_price,
                        'additional_day_price': item.additional_day_price,
                        'is_active': item.is_active,
                        'display_order': item.display_order,
                        'description': item.description,
                    }
                    for item in resort.equipment_rental_items.all()
                    if item.is_active
                ],
                'equipment_time_slots': [
                    {
                        'id': slot.id,
                        'equipment_option': slot.equipment_option,
                        'lesson_duration': slot.lesson_duration,
                        'session_period': slot.session_period,
                        'day_type': slot.day_type,
                        'course_template_ids': list(slot.course_templates.values_list('id', flat=True)),
                        'course_template_names': [template.name for template in slot.course_templates.all()],
                        'label': slot.display_label(),
                        'start_time': slot.start_time.strftime('%H:%M') if slot.start_time else None,
                        'end_time': slot.end_time.strftime('%H:%M') if slot.end_time else None,
                        'is_active': slot.is_active,
                        'display_order': slot.display_order,
                        'description': slot.description,
                    }
                    for slot in resort.equipment_assistance_time_slots.all()
                    if slot.is_active
                ],
            })

        return Response(data, status=status.HTTP_200_OK)


class CourseTypeListAPI(APIView):
    """
    GET /api/course-types/
    獲取所有課程類型

    可選參數：
    - category_id: 課程大類 ID（篩選用）
    """
    permission_classes = []  # 公開 API

    def get(self, request, client_code=None):
        category_id = request.GET.get('category_id')
        resort_name = request.GET.get('resort')

        course_types = CourseType.objects.prefetch_related('available_resorts')
        priced_templates = get_frontend_priced_course_templates()

        if client_code:
            client = resolve_tenant_client(client_code)
            course_types = course_types.filter(category__client=client)
            priced_templates = priced_templates.filter(course_type__category__client=client)

        if category_id:
            course_types = course_types.filter(category_id=category_id)
            priced_templates = priced_templates.filter(course_type__category_id=category_id)

        priced_type_ids = set(priced_templates.values_list('course_type_id', flat=True))

        if resort_name:
            resort_priced_templates = priced_templates.filter(pricing_options__resort__name=resort_name)
            template_bound_ids = set(resort_priced_templates.filter(
                resorts__name=resort_name,
            ).values_list('course_type_id', flat=True))
            types_with_template_resorts = set(course_types.filter(
                templates__is_active=True,
            ).exclude(
                templates__resorts__isnull=True,
            ).values_list('id', flat=True))
            explicit_fallback_ids = set(course_types.filter(
                id__in=set(resort_priced_templates.values_list('course_type_id', flat=True)),
                available_resorts__name=resort_name,
            ).exclude(
                id__in=types_with_template_resorts,
            ).values_list('id', flat=True))

            course_types = course_types.filter(id__in=template_bound_ids | explicit_fallback_ids)
        else:
            course_types = course_types.filter(id__in=priced_type_ids)

        course_types = course_types.distinct().order_by('display_order', 'id')

        data = []
        for course_type in course_types:
            data.append({
                'id': course_type.id,
                'name': course_type.name,
                'category_id': course_type.category_id,
                'display_order': course_type.display_order,
                'available_resorts': get_course_type_frontend_resorts(course_type)
            })

        return Response(data, status=status.HTTP_200_OK)


class CourseTemplateListAPI(APIView):
    """
    GET /api/course-templates/
    獲取所有課程模板

    可選參數：
    - course_type_id: 課程類型 ID（篩選用）
    - resort: 雪場名稱（篩選用）
    """
    permission_classes = []  # 公開 API

    def get(self, request, client_code=None):
        course_type_id = request.GET.get('course_type_id')
        resort_name = request.GET.get('resort')

        templates = get_frontend_priced_course_templates().select_related('course_type').prefetch_related('resorts', 'allowed_coaches')

        if client_code:
            client = resolve_tenant_client(client_code)
            templates = templates.filter(course_type__category__client=client)

        if course_type_id:
            templates = templates.filter(course_type_id=course_type_id)

        if resort_name:
            templates = templates.filter(
                resorts__name=resort_name,
                pricing_options__resort__name=resort_name,
            )

        templates = templates.annotate(
            course_type_name_value=F('course_type__name'),
            category_name_value=F('course_type__category__name'),
        ).distinct().order_by(
            'course_type__category__display_order',
            'course_type__display_order',
            'display_order',
            'duration_hours',
            'id',
        )

        data = []
        for template in templates:
            data.append({
                'id': template.id,
                'name': template.name,
                'course_type_id': template.course_type_id,
                'course_type_name': template.course_type_name_value,
                'category_name': template.category_name_value,
                'duration_hours': template.duration_hours,
                'max_capacity': template.max_capacity,
                'display_order': template.display_order,
                'is_active': template.is_active,
                'resorts': list(template.resorts.values_list('name', flat=True)),
                'booking_open_date': template.booking_open_date.isoformat() if template.booking_open_date else None,
                'booking_close_date': template.booking_close_date.isoformat() if template.booking_close_date else None,
                'course_start_date': template.course_start_date.isoformat() if template.course_start_date else None,
                'course_end_date': template.course_end_date.isoformat() if template.course_end_date else None,
                'minimum_coach_price_level': template.minimum_coach_price_level,
                'minimum_coach_price_level_label': template.get_minimum_coach_price_level_display(),
                'allowed_coaches': list(template.allowed_coaches.values_list('id', flat=True)),
            })

        return Response(data, status=status.HTTP_200_OK)


class CourseSessionListAPI(APIView):
    """
    GET /api/course-sessions/
    獲取課程時段列表

    可選參數：
    - template_id: 課程模板 ID（篩選用）
    - date: 檢查特定日期是否可預約（YYYY-MM-DD）
            若帶此參數，會檢查 booking 視窗、course 期間、容量
    """
    permission_classes = []  # 公開 API

    def get(self, request, client_code=None):
        from datetime import datetime, date

        template_id = request.GET.get('template_id')
        date_str = request.GET.get('date')

        sessions = CourseSession.objects.filter(is_active=True).select_related('template')

        if template_id:
            sessions = sessions.filter(template_id=template_id)

        sessions = sessions.order_by('start_time')

        # 若帶 date 參數，檢查日期合法性
        check_date = None
        if date_str:
            try:
                check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': '日期格式錯誤'}, status=status.HTTP_400_BAD_REQUEST)

            today = date.today()

            # 不能預約過去
            if check_date < today:
                return Response([], status=status.HTTP_200_OK)

        data = []
        for session in sessions:
            tmpl = session.template

            # 檢查課程期間（雪季）
            if check_date:
                if tmpl.course_start_date and check_date < tmpl.course_start_date:
                    continue
                if tmpl.course_end_date and check_date > tmpl.course_end_date:
                    continue

                # 檢查預約窗口（今天必須在 booking_open_date ~ booking_close_date 之間）
                today = date.today()
                if tmpl.booking_open_date and today < tmpl.booking_open_date:
                    continue
                if tmpl.booking_close_date and today > tmpl.booking_close_date:
                    continue

                # 檢查容量（同模板同日同時段已預約人數）
                booked_count = Reservation.objects.filter(
                    bookings__date=check_date,
                    bookings__start_time=session.start_time,
                    bookings__end_time=session.end_time,
                ).exclude(status__in=['cancelled', 'deleted']).count()
                is_full = booked_count >= (tmpl.max_capacity or 6)
            else:
                is_full = False

            data.append({
                'id': session.id,
                'template_id': session.template.id,
                'start_time': session.start_time.strftime('%H:%M'),
                'end_time': session.end_time.strftime('%H:%M'),
                'is_active': session.is_active,
                'is_full': is_full,
            })

        return Response(data, status=status.HTTP_200_OK)


class CourseAvailableDatesAPI(APIView):
    """
    GET /api/course-templates/<id>/available-dates/?month=YYYY-MM
    回傳指定模板在某月的可預約日期清單

    用於前端日曆禁用不可選日期
    """
    permission_classes = []

    def get(self, request, template_id, client_code=None):
        from datetime import datetime, date, timedelta
        from calendar import monthrange

        try:
            tmpl = CourseTemplate.objects.get(pk=template_id, is_active=True)
        except CourseTemplate.DoesNotExist:
            return Response({'error': '模板不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 解析月份
        month_str = request.GET.get('month')
        today = date.today()
        if month_str:
            try:
                year, month = map(int, month_str.split('-'))
            except (ValueError, AttributeError):
                year, month = today.year, today.month
        else:
            year, month = today.year, today.month

        # 取得月內所有日期
        _, last_day = monthrange(year, month)

        # 預約窗口檢查（看「今天」）
        booking_window_open = True
        if tmpl.booking_open_date and today < tmpl.booking_open_date:
            booking_window_open = False
        if tmpl.booking_close_date and today > tmpl.booking_close_date:
            booking_window_open = False

        # 課程期間
        course_start = tmpl.course_start_date
        course_end = tmpl.course_end_date

        available_dates = []
        for day in range(1, last_day + 1):
            d = date(year, month, day)

            # 不能預約過去
            if d < today:
                continue

            # 預約窗口
            if not booking_window_open:
                continue

            # 課程期間
            if course_start and d < course_start:
                continue
            if course_end and d > course_end:
                continue

            available_dates.append(d.isoformat())

        return Response({
            'template_id': tmpl.id,
            'template_name': tmpl.name,
            'month': f'{year}-{month:02d}',
            'booking_open_date': tmpl.booking_open_date.isoformat() if tmpl.booking_open_date else None,
            'booking_close_date': tmpl.booking_close_date.isoformat() if tmpl.booking_close_date else None,
            'course_start_date': tmpl.course_start_date.isoformat() if tmpl.course_start_date else None,
            'course_end_date': tmpl.course_end_date.isoformat() if tmpl.course_end_date else None,
            'available_dates': available_dates,
        }, status=status.HTTP_200_OK)


class DiscountPreviewAPI(APIView):
    """
    POST /api/discount-preview/
    Preview cart discounts before creating reservations.
    """
    permission_classes = []

    def post(self, request, client_code=None):
        try:
            cart_data = request.data.get('cart', [])
            if not cart_data:
                return Response({
                    'code': 400,
                    'msg': '購物車是空的'
                }, status=status.HTTP_400_BAD_REQUEST)

            tenant_client = resolve_tenant_client(client_code)
            summary = calculate_cart_discount_summary(
                cart_data,
                tenant_client,
                user=get_request_user_or_none(request),
                contact_info=normalize_contact_info(request),
                discount_code=request.data.get('discount_code') or request.data.get('discountCode') or '',
            )
            return Response({
                'code': 200,
                'msg': 'OK',
                'subtotal': summary['subtotal'],
                'discount_total': summary['discount_total'],
                'total': summary['total'],
                'item_subtotals': summary['item_subtotals'],
                'item_discount_amounts': summary['item_discount_amounts'],
                'applied_discounts': summary['applied_discounts'],
                'discount_code_error': summary['discount_code_error'],
                'is_new_customer': summary['is_new_customer'],
            }, status=status.HTTP_200_OK)

        except (PriceCalculationError, ValueError, TenantResolutionError) as e:
            return Response({
                'code': 400,
                'msg': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'code': 500,
                'msg': f'折扣試算失敗: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateReservationAPI(APIView):
    """
    POST /api/create-reservation/
    創建預約（從購物車提交）

    請求格式：
    {
        "cart": [
            {
                "coach": number | "any",
                "peopleCount": number,
                "abilityLevel": string,
                "equipment": boolean,
                "equipmentOption": string | null,
                "language": string | null,
                "resort": string,
                "courseCategory": string,
                "courses": [
                    {
                        "date": "YYYY-MM-DD",
                        "courseTypeId": number,
                        "courseTypeName": string,
                        "courseTemplateId": number,
                        "courseTemplateName": string,
                        "durationHours": number,
                        "timeSlotStart": "HH:MM",
                        "timeSlotEnd": "HH:MM",
                        "price": number
                    }
                ],
                "totalPrice": number
            }
        ]
    }

    返回：
    {
        "code": 200,
        "msg": "預約成功",
        "reservation_group_ids": [1, 2, ...]
    }
    """

    @transaction.atomic
    def post(self, request, client_code=None):
        try:
            request_user = get_request_user_or_none(request)
            contact_info = normalize_contact_info(request)
            cart_data = request.data.get('cart', [])

            if not cart_data:
                return Response({
                    'code': 400,
                    'msg': '購物車為空'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not contact_info.get('phone'):
                return Response({
                    'code': 400,
                    'msg': '請填寫聯絡電話'
                }, status=status.HTTP_400_BAD_REQUEST)
            if not contact_info.get('messenger_type') or not contact_info.get('messenger_id'):
                return Response({
                    'code': 400,
                    'msg': '請選擇通訊軟體並填寫聯繫 ID'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 解析 tenant client(永不回 None;失敗會 raise TenantResolutionError)
            tenant_client = resolve_tenant_client(client_code)
            tenant_client = type(tenant_client).objects.select_for_update().get(pk=tenant_client.pk)
            discount_code = request.data.get('discount_code') or request.data.get('discountCode') or ''
            discount_summary = calculate_cart_discount_summary(
                cart_data,
                tenant_client,
                user=request_user,
                contact_info=contact_info,
                discount_code=discount_code,
            )
            if discount_code and discount_summary.get('discount_code_error'):
                return Response({
                    'code': 400,
                    'msg': discount_summary['discount_code_error']
                }, status=status.HTTP_400_BAD_REQUEST)

            created_group_ids = []
            created_reservations = []
            reservation_groups = []
            item_discounts = discount_summary.get('item_discount_amounts') or []
            applied_discount_details = discount_summary.get('applied_discount_details') or []

            # 為每個購物車項目創建預約組
            for index, item in enumerate(cart_data):
                item_discount_amount = item_discounts[index] if index < len(item_discounts) else 0
                item_applied_discounts = [discount for discount in applied_discount_details if discount.get('allocations', {}).get(index, 0) > 0]
                group_id, reservation, group = self._create_reservation_group(
                    request_user,
                    item,
                    tenant_client,
                    contact_info,
                    discount_amount=item_discount_amount,
                    applied_discounts=item_applied_discounts,
                )
                created_group_ids.append(group_id)
                created_reservations.append(reservation)
                reservation_groups.append(group)

            # 檢查是否需要自動排課
            # 只有當雪場啟用自動排課時才進行（包括指定教練的預約也需要檢查衝突）
            reservations_need_scheduling = []
            for resv in created_reservations:
                if resv.resort and resv.resort.auto_scheduling_enabled:
                    reservations_need_scheduling.append(resv)

            # 如果有需要排課的預約，調用排課系統
            if reservations_need_scheduling:
                from .scheduler import assign_coachs

                success, report = assign_coachs(reservations_to_assign=reservations_need_scheduling)

                if not success:
                    # 自動排課失敗：訂單保留，標記為待人工排課（不刪、不可付款）
                    error_detail = report.get('error', '自動排課失敗')
                    conflict_info = report.get('conflict_details', {})

                    # 將所有相關預約標記為排課失敗（讓後台/課服可介入處理）
                    for resv in created_reservations:
                        resv.status = 'auto_assignment_failed'
                        resv.save(update_fields=['status'])

                    return Response({
                        'code': 200,
                        'msg': '訂單已建立但自動排課失敗，請等待課服聯繫或改選其他日期',
                        'reservation_group_ids': created_group_ids,
                        'scheduling_failed': True,
                        'conflict_details': conflict_info,
                        'requires_payment': False,  # 失敗訂單先不開放付款
                    }, status=status.HTTP_200_OK)

                msg = f'成功創建 {len(created_group_ids)} 個預約並完成教練分配'
            else:
                # 雪場未啟用自動排課
                msg = f'成功創建 {len(created_group_ids)} 個預約（等待手動分配教練）'

            if has_pending_coach_confirmation(created_reservations):
                increment_discount_usage(applied_discount_details)
                return Response({
                    'code': 200,
                    'msg': PENDING_COACH_CONFIRMATION_MESSAGE,
                    'reservation_group_ids': created_group_ids,
                    'scheduling_failed': False,
                    'pending_coach_confirmation': True,
                    'requires_payment': False,
                }, status=status.HTTP_200_OK)

            # 為每個預約組創建付款記錄
            increment_discount_usage(applied_discount_details)

            from .models import Payment
            from snowland.settings import PAYMENT_HOST

            payment_urls = []
            for group in reservation_groups:
                # 創建付款記錄
                payment = Payment.objects.create(
                    reservation_group=group,
                    user=request_user,
                    status='unpaid',
                    payment_method='TT',  # 預設為匯款，用戶可在付款頁面選擇
                    DataJSON={'contact': contact_info}
                )

                # 生成付款URL
                payment_url = PAYMENT_HOST + '?reservation_group=' + str(group.pk)
                payment_urls.append({
                    'reservation_group_id': group.pk,
                    'payment_url': payment_url
                })

            # 根據預約組數量決定返回格式
            response_data = {
                'code': 200,
                'msg': msg,
                'reservation_group_ids': created_group_ids,
                'scheduling_failed': False
            }

            if len(payment_urls) == 1:
                # 單一預約組，直接返回payment_url
                response_data['payment_url'] = payment_urls[0]['payment_url']
                response_data['requires_payment'] = True
            else:
                # 多個預約組，返回所有payment_urls
                response_data['payment_urls'] = payment_urls
                response_data['requires_payment'] = True

            return Response(response_data, status=status.HTTP_200_OK)

        except (PriceCalculationError, ValueError, TenantResolutionError) as e:
            transaction.set_rollback(True)
            # 算價失敗 / 前後端對帳不一致 / 租戶解析失敗 → 拒單,且明確告知前端原因
            return Response({
                'code': 400,
                'msg': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            transaction.set_rollback(True)
            return Response({
                'code': 500,
                'msg': f'預約失敗: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _create_reservation_group(
        self,
        user,
        item,
        tenant_client=None,
        contact_info=None,
        discount_amount=0,
        applied_discounts=None,
    ):
        """創建單個預約組及其相關記錄"""
        from .models import ReservationGroup, Reservation

        # 絕對不能 client=NULL — 否則後台 filter(client=tenant) 撈不到,訂單會消失
        if tenant_client is None:
            raise TenantResolutionError('內部錯誤:tenant_client 為 None,拒絕建單以免訂單消失')

        # 創建 ReservationGroup（綁到對應的 client，後台才能依租戶過濾出來）
        contact_info = contact_info or {}
        group_name = contact_info.get('name') or f"{item['courseCategory']} - {item['resortName']}"
        group = ReservationGroup.objects.create(
            client=tenant_client,
            user=user,
            name=group_name
        )

        # 創建 Reservation
        reservation = self._create_reservation(
            group,
            item,
            discount_amount=discount_amount,
            applied_discounts=applied_discounts or [],
        )

        # 為每個課程日期創建 Booking
        for course in item['courses']:
            self._create_booking(reservation, course)

        return group.id, reservation, group

    def _create_reservation(self, group, item, discount_amount=0, applied_discounts=None):
        """創建單個預約記錄"""
        from .models import Reservation

        # 獲取雪場對象
        try:
            resort = Resorts.objects.get(name=item['resort'])
        except Resorts.DoesNotExist:
            raise ValueError(f"找不到雪場: {item['resort']}")

        # 獲取課程類型（從第一個課程）
        first_course = item['courses'][0]
        try:
            course_type = CourseType.objects.get(id=first_course['courseTypeId'])
        except CourseType.DoesNotExist:
            raise ValueError(f"找不到課程類型: {first_course['courseTypeId']}")

        # 處理教練
        coach_instance = None
        is_preferred = False
        if item['coach'] != 'any' and item['coach'] is not None:
            try:
                coach_instance = Coach.objects.get(id=item['coach'])
                is_preferred = True
            except Coach.DoesNotExist:
                pass

        # 映射裝備選項
        equipment_mapping = {
            'self_rent': 'rentWithoutyourself',
            'own_equipment': 'ownWithoutAssistance',
            'class_time_help': 'assistDuringCourse',
            'extra_time_help': 'purchaseAssistanceTime',
        }
        equipment_value = None
        if item.get('equipmentOption'):
            equipment_value = equipment_mapping.get(item['equipmentOption'])

        course_template = select_cart_group_course_template(item['courses'], course_type, resort)
        if coach_instance:
            from .scheduler import coach_matches_course_template, course_template_restriction_label
            if not coach_matches_course_template(coach_instance, course_template):
                rule_label = course_template_restriction_label(course_template) or '指定教練限制'
                raise ValueError(f'此課程模板需要符合教練條件（{rule_label}），請重新選擇教練')
        selected_session_start = first_course.get('timeSlotStart')
        if not selected_session_start and first_course.get('timeSlotId'):
            session = CourseSession.objects.filter(id=first_course.get('timeSlotId')).first()
            selected_session_start = session.start_time if session else None
        equipment_time_slot, equipment_time_label = resolve_equipment_assistance_time_slot(
            resort,
            equipment_value,
            item.get('equipmentAssistanceTimeSlotId') or item.get('equipment_assistance_time_slot_id'),
            duration_hours=course_template.duration_hours if course_template else None,
            session_start_time=selected_session_start,
            course_template_id=first_course.get('courseTemplateId'),
        )

        # 後端權威算價:逐堂重算課程費,並從 ResortFee 算附加費,完全不採用前端 price / totalPrice
        people_count = int(item.get('peopleCount', 1) or 1)
        course_fee = 0
        for course in item['courses']:
            course_fee += compute_course_price_authoritative(
                template_id=course.get('courseTemplateId'),
                resort_name=item['resort'],
                people_count=people_count,
                course_date=course['date'],
            )

        bookings_count = len(item['courses'])
        language_value = item.get('language', 'zh') or 'zh'
        coach_fee, language_fee, equipment_fee = compute_addon_fees_authoritative(
            resort=resort,
            coach=coach_instance,
            course_type=course_type,
            language=language_value,
            equipment_value=equipment_value,
            people_count=people_count,
            bookings_count=bookings_count,
            course_template=course_template,
        )

        backend_total = course_fee + coach_fee + language_fee + equipment_fee
        applied_discounts = applied_discounts or []
        discount_amount = min(int(discount_amount or 0), backend_total)
        discount_code = ', '.join([discount.get('code', '') for discount in applied_discounts if discount.get('code')])
        discount_name = ', '.join([discount.get('name', '') for discount in applied_discounts if discount.get('name')])

        # 對帳:前端 totalPrice 是使用者「看到要付的最終金額」,所以比的是 backend_total
        client_total = item.get('totalPrice')
        if client_total is not None:
            try:
                client_total_int = int(client_total)
            except (TypeError, ValueError):
                raise ValueError('totalPrice 格式錯誤')
            if client_total_int != backend_total:
                raise ValueError(
                    f'價格不一致(顯示={client_total_int} / 後端={backend_total}),請重新整理頁面'
                )

        # 創建預約(total_fee 會在 Reservation.save() 自動加總)
        reservation = Reservation.objects.create(
            group=group,
            is_preferred_coach=is_preferred,
            preferred_coach=coach_instance,
            need_equipment=item.get('equipment', False),
            equipment=equipment_value,
            language=language_value,
            resort=resort,
            course_type=course_type,
            course_template=course_template,
            max_ability_level=item.get('abilityLevel', 'no_exp'),
            status='created',
            number_of_people=people_count,
            course_fee=course_fee,
            language_fee=language_fee,
            coach_fee=coach_fee,
            equipment_rental_fee=equipment_fee,
            discount_amount=discount_amount,
            discount_code=discount_code[:255],
            discount_name=discount_name[:255],
            equipment_assistance_time_slot=equipment_time_slot,
            equipment_assistance_time_label=equipment_time_label,
        )

        return reservation

    def _create_booking(self, reservation, course):
        """創建單個課程預約記錄"""
        from .models import Booking

        # 解析日期和時間
        booking_date = datetime.strptime(course['date'], '%Y-%m-%d').date()

        # 處理時間格式（可能是 HH:MM 或 HH:MM:SS）
        try:
            start_time = datetime.strptime(course['timeSlotStart'], '%H:%M:%S').time()
        except ValueError:
            start_time = datetime.strptime(course['timeSlotStart'], '%H:%M').time()

        try:
            end_time = datetime.strptime(course['timeSlotEnd'], '%H:%M:%S').time()
        except ValueError:
            end_time = datetime.strptime(course['timeSlotEnd'], '%H:%M').time()

        # 創建預約課程
        booking = Booking.objects.create(
            reservation=reservation,
            course_type=course.get('courseTypeName', ''),
            course_name=course.get('courseTemplateName', ''),
            date=booking_date,
            start_time=start_time,
            end_time=end_time,
            is_scheduled=False
        )

        return booking


class SuperScheduleAPI(APIView):
    """
    POST /api/super-schedule/
    進階排課：將多天課程拆分為單日單元，允許不同教練教不同天

    用於當常規排課失敗時，嘗試更靈活的排課方式
    """

    @transaction.atomic
    def post(self, request, client_code=None):
        try:
            request_user = get_request_user_or_none(request)
            contact_info = normalize_contact_info(request)
            cart_data = request.data.get('cart', [])

            if not cart_data:
                return Response({
                    'code': 400,
                    'msg': '購物車為空'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not contact_info.get('phone'):
                return Response({
                    'code': 400,
                    'msg': '請填寫聯絡電話'
                }, status=status.HTTP_400_BAD_REQUEST)
            if not contact_info.get('messenger_type') or not contact_info.get('messenger_id'):
                return Response({
                    'code': 400,
                    'msg': '請選擇通訊軟體並填寫聯繫 ID'
                }, status=status.HTTP_400_BAD_REQUEST)

            from .models import ReservationGroup, Payment
            from snowland.settings import PAYMENT_HOST

            # 解析 tenant client(永不回 None;失敗會 raise TenantResolutionError)
            tenant_client = resolve_tenant_client(client_code)
            tenant_client = type(tenant_client).objects.select_for_update().get(pk=tenant_client.pk)
            discount_code = request.data.get('discount_code') or request.data.get('discountCode') or ''
            discount_summary = calculate_cart_discount_summary(
                cart_data,
                tenant_client,
                user=request_user,
                contact_info=contact_info,
                discount_code=discount_code,
            )
            if discount_code and discount_summary.get('discount_code_error'):
                return Response({
                    'code': 400,
                    'msg': discount_summary['discount_code_error']
                }, status=status.HTTP_400_BAD_REQUEST)

            # 創建單一ReservationGroup（所有拆分的預約都屬於同一組）
            group = ReservationGroup.objects.create(
                client=tenant_client,
                user=request_user,
                name=contact_info.get('name') or f"進階排課 - {cart_data[0]['resortName']}"
            )

            created_reservations = []
            item_discounts = discount_summary.get('item_discount_amounts') or []
            applied_discount_details = discount_summary.get('applied_discount_details') or []

            # 拆分邏輯：將每個購物車項目的每一天課程都創建為獨立的Reservation
            for item_index, item in enumerate(cart_data):
                courses = item.get('courses') or []
                item_discount_amount = item_discounts[item_index] if item_index < len(item_discounts) else 0
                item_applied_discounts = [
                    discount for discount in applied_discount_details
                    if discount.get('allocations', {}).get(item_index, 0) > 0
                ]
                course_count = max(len(courses), 1)
                per_course_discount = item_discount_amount // course_count
                discount_remainder = item_discount_amount - (per_course_discount * course_count)

                # 對每一天的課程創建獨立的Reservation
                for course_index, course in enumerate(courses):
                    course_discount_amount = per_course_discount + (discount_remainder if course_index == 0 else 0)
                    # 創建單日Reservation（強制不指定教練）
                    reservation = self._create_single_day_reservation(
                        group=group,
                        item=item,
                        course=course,
                        force_no_coach=True,  # 進階排課強制不指定教練
                        discount_amount=course_discount_amount,
                        applied_discounts=item_applied_discounts,
                        charge_equipment_fee=(course_index == 0),
                    )
                    created_reservations.append(reservation)

            # 檢查哪些預約需要排課
            reservations_need_scheduling = []
            for resv in created_reservations:
                if resv.resort and resv.resort.auto_scheduling_enabled:
                    reservations_need_scheduling.append(resv)

            # 調用排課系統
            if reservations_need_scheduling:
                from .scheduler import assign_coachs

                success, report = assign_coachs(reservations_to_assign=reservations_need_scheduling)

                if not success:
                    # 即使進階排課也失敗，刪除已創建的預約記錄
                    error_detail = report.get('error', '進階排課失敗')
                    conflict_info = report.get('conflict_details', {})

                    # 刪除已創建的 ReservationGroup（會級聯刪除所有 Reservation 和 Booking）
                    group.delete()

                    # 返回排課失敗信息和建議，但不保留任何資料庫記錄
                    return Response({
                        'code': 400,
                        'msg': '進階排課失敗，訂單已取消',
                        'scheduling_failed': True,
                        'conflict_details': conflict_info,
                        'requires_payment': False
                    }, status=status.HTTP_400_BAD_REQUEST)

            # 創建付款記錄
            if has_pending_coach_confirmation(created_reservations):
                increment_discount_usage(applied_discount_details)
                return Response({
                    'code': 200,
                    'msg': PENDING_COACH_CONFIRMATION_MESSAGE,
                    'reservation_group_id': group.id,
                    'reservation_group_ids': [group.id],
                    'scheduling_failed': False,
                    'pending_coach_confirmation': True,
                    'requires_payment': False,
                }, status=status.HTTP_200_OK)

            increment_discount_usage(applied_discount_details)

            payment = Payment.objects.create(
                reservation_group=group,
                user=request_user,
                status='unpaid',
                payment_method='TT',
                DataJSON={'contact': contact_info}
            )

            payment_url = PAYMENT_HOST + '?reservation_group=' + str(group.pk)

            return Response({
                'code': 200,
                'msg': f'進階排課成功！已將課程拆分為 {len(created_reservations)} 個獨立預約，由不同教練授課',
                'reservation_group_id': group.id,
                'scheduling_failed': False,
                'payment_url': payment_url,
                'requires_payment': True
            }, status=status.HTTP_200_OK)

        except (PriceCalculationError, ValueError, TenantResolutionError) as e:
            transaction.set_rollback(True)
            return Response({
                'code': 400,
                'msg': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            transaction.set_rollback(True)
            return Response({
                'code': 500,
                'msg': f'進階排課失敗: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _create_single_day_reservation(
        self,
        group,
        item,
        course,
        force_no_coach=False,
        discount_amount=0,
        applied_discounts=None,
        charge_equipment_fee=True,
    ):
        """為單天課程創建Reservation"""
        from .models import Reservation, Booking

        # 獲取雪場和課程類型
        try:
            resort = Resorts.objects.get(name=item['resort'])
            course_type = CourseType.objects.get(id=course['courseTypeId'])
        except (Resorts.DoesNotExist, CourseType.DoesNotExist) as e:
            raise ValueError(f"資料查詢失敗: {str(e)}")

        # 進階排課強制不指定教練
        coach_instance = None
        is_preferred = False

        # 映射裝備選項
        equipment_mapping = {
            'self_rent': 'rentWithoutyourself',
            'own_equipment': 'ownWithoutAssistance',
            'class_time_help': 'assistDuringCourse',
            'extra_time_help': 'purchaseAssistanceTime',
        }
        equipment_value = None
        if item.get('equipmentOption'):
            equipment_value = equipment_mapping.get(item['equipmentOption'])

        # 後端權威算價:單天課 → bookings_count=1。進階排課強制無指定教練,coach_fee 必為 0
        people_count = int(item.get('peopleCount', 1) or 1)
        course_template = CourseTemplate.objects.select_related('course_type').prefetch_related(
            'resorts',
            'allowed_coaches',
        ).filter(id=course.get('courseTemplateId')).first()
        if not course_template:
            raise ValueError(f"找不到課程模板: {course.get('courseTemplateId')}")
        if course_template.course_type_id != course_type.id:
            raise ValueError('課程模板與課程類型不一致，請重新選擇課程')
        if course_template.resorts.exists() and not course_template.resorts.filter(id=resort.id).exists():
            raise ValueError('此課程模板不適用於選擇的雪場')
        selected_session_start = course.get('timeSlotStart')
        if not selected_session_start and course.get('timeSlotId'):
            session = CourseSession.objects.filter(id=course.get('timeSlotId')).first()
            selected_session_start = session.start_time if session else None
        equipment_time_slot = None
        equipment_time_label = ''
        if equipment_value == 'purchaseAssistanceTime' and charge_equipment_fee:
            equipment_time_slot, equipment_time_label = resolve_equipment_assistance_time_slot(
                resort,
                equipment_value,
                item.get('equipmentAssistanceTimeSlotId') or item.get('equipment_assistance_time_slot_id'),
                duration_hours=course_template.duration_hours if course_template else None,
                session_start_time=selected_session_start,
                course_template_id=course.get('courseTemplateId'),
            )
        course_fee = compute_course_price_authoritative(
            template_id=course.get('courseTemplateId'),
            resort_name=item['resort'],
            people_count=people_count,
            course_date=course['date'],
        )

        # 對帳:前端若有送單堂 price,必須一致(這裡只比課程費,因為 course.price 不含附加費)
        client_price = course.get('price')
        if client_price is not None and int(client_price) != course_fee:
            raise ValueError(
                f'價格不一致(顯示={client_price} / 後端={course_fee}),請重新整理頁面'
            )

        language_value = item.get('language', 'zh') or 'zh'
        coach_fee, language_fee, equipment_fee = compute_addon_fees_authoritative(
            resort=resort,
            coach=coach_instance,                    # 進階排課強制 None → coach_fee=0
            course_type=course_type,
            language=language_value,
            equipment_value=equipment_value if charge_equipment_fee else None,
            people_count=people_count,
            bookings_count=1,
        )

        backend_total = course_fee + coach_fee + language_fee + equipment_fee
        applied_discounts = applied_discounts or []
        discount_amount = min(int(discount_amount or 0), backend_total)
        discount_code = ', '.join([discount.get('code', '') for discount in applied_discounts if discount.get('code')])
        discount_name = ', '.join([discount.get('name', '') for discount in applied_discounts if discount.get('name')])

        # 創建預約
        reservation = Reservation.objects.create(
            group=group,
            is_preferred_coach=is_preferred,
            preferred_coach=coach_instance,
            need_equipment=item.get('equipment', False) if charge_equipment_fee else False,
            equipment=equipment_value if charge_equipment_fee else None,
            language=language_value,
            resort=resort,
            course_type=course_type,
            course_template=course_template,
            max_ability_level=item.get('abilityLevel', 'no_exp'),
            status='created',
            number_of_people=people_count,
            course_fee=course_fee,
            language_fee=language_fee,
            coach_fee=coach_fee,
            equipment_rental_fee=equipment_fee,
            discount_amount=discount_amount,
            discount_code=discount_code[:255],
            discount_name=discount_name[:255],
            equipment_assistance_time_slot=equipment_time_slot,
            equipment_assistance_time_label=equipment_time_label,
        )

        # 為這一天創建Booking
        booking_date = datetime.strptime(course['date'], '%Y-%m-%d').date()

        try:
            start_time = datetime.strptime(course['timeSlotStart'], '%H:%M:%S').time()
        except ValueError:
            start_time = datetime.strptime(course['timeSlotStart'], '%H:%M').time()

        try:
            end_time = datetime.strptime(course['timeSlotEnd'], '%H:%M:%S').time()
        except ValueError:
            end_time = datetime.strptime(course['timeSlotEnd'], '%H:%M').time()

        Booking.objects.create(
            reservation=reservation,
            course_type=course.get('courseTypeName', ''),
            course_name=course.get('courseTemplateName', ''),
            date=booking_date,
            start_time=start_time,
            end_time=end_time,
            is_scheduled=False
        )

        return reservation


class PaymentInfoAPI(APIView):
    """
    GET /api/payment-info/
    獲取付款資訊

    參數：
    - reservation_group: 預約群組 ID

    返回：
    {
        "reservation_group_id": number,
        "total_amount": number,
        "payment_status": "unpaid" | "paid" | "pending" | "expired",
        "order_details": [
            {
                "pk": number,
                "course_fee": number,
                "coach_fee": number,
                "equipment_rental_fee": number,
                "language_fee": number,
                "total_fee": number
            }
        ]
    }
    """
    permission_classes = []  # 公開 API（但建議加上權限檢查）

    def get(self, request, client_code=None):
        try:
            reservation_group_id = request.GET.get('reservation_group')

            if not reservation_group_id:
                return Response({
                    'error': '缺少預約群組ID'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 獲取預約群組
            try:
                group = ReservationGroup.objects.get(pk=reservation_group_id)
            except ReservationGroup.DoesNotExist:
                return Response({
                    'error': '找不到預約群組'
                }, status=status.HTTP_404_NOT_FOUND)

            # 獲取付款記錄
            try:
                payment = Payment.objects.get(reservation_group=group)
                payment_status = payment.status
            except Payment.DoesNotExist:
                payment_status = 'unpaid'

            # 獲取有效的預約（排除已刪除的）
            active_reservations = group.reservations.exclude(status='deleted')

            if not active_reservations.exists():
                return Response({
                    'error': '此預約群組沒有有效的預約項目',
                    'payment_status': 'no_active_reservations'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 過濾掉已取消的預約
            reservations_to_pay = active_reservations.exclude(status='cancelled')

            if not reservations_to_pay.exists():
                return Response({
                    'error': '所有預約均已取消',
                    'payment_status': 'all_cancelled'
                }, status=status.HTTP_400_BAD_REQUEST)

            hold_message, hold_status = get_group_payment_hold(group)
            if hold_message:
                return Response({
                    'error': hold_message,
                    'payment_status': hold_status,
                    'requires_payment': False,
                }, status=status.HTTP_400_BAD_REQUEST)

            # 計算訂單詳情和總金額
            order_details = []
            total_amount = 0

            for resv in reservations_to_pay:
                detail = {
                    'pk': resv.pk,
                    'course_fee': resv.course_fee,
                    'coach_fee': resv.coach_fee,
                    'equipment_rental_fee': resv.equipment_rental_fee,
                    'equipment_assistance_time_label': resv.get_equipment_assistance_time_display(),
                    'language_fee': resv.language_fee,
                    'discount_amount': resv.discount_amount,
                    'discount_code': resv.discount_code,
                    'discount_name': resv.discount_name,
                    'original_total_fee': resv.total_fee,
                    'total_fee': resv.payment_amount,
                    'payment_amount': resv.payment_amount,
                }
                order_details.append(detail)
                total_amount += resv.payment_amount

            # 取得收款銀行資訊（從 Client 上）
            bank_info = {'bank_name': '', 'bank_branch': '', 'bank_account_number': '', 'bank_account_holder': ''}
            if client_code:
                try:
                    from Client.models import Client
                    c = Client.objects.get(internal_code=client_code, is_active=True)
                    bank_info = {
                        'bank_name': c.bank_name,
                        'bank_branch': c.bank_branch,
                        'bank_account_number': c.bank_account_number,
                        'bank_account_holder': c.bank_account_holder,
                    }
                except Client.DoesNotExist:
                    pass

            return Response({
                'reservation_group_id': int(reservation_group_id),
                'total_amount': total_amount,
                'payment_status': payment_status,
                'order_details': order_details,
                'bank_info': bank_info,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'獲取付款資訊失敗: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReservationHistoryAPI(APIView):
    """
    GET /api/reservation-history/
    獲取用戶的預約歷史紀錄

    返回：
    {
        "history": [
            {
                "reservation_group_id": number,
                "created_at": "2025-01-15T10:30:00Z",
                "total_amount": number,
                "payment_status": "paid" | "unpaid" | "pending",
                "reservations": [
                    {
                        "id": number,
                        "resort": string,
                        "course_type": string,
                        "language": string,
                        "status": string,
                        "number_of_people": number,
                        "course_fee": number,
                        "coach_fee": number,
                        "equipment_rental_fee": number,
                        "language_fee": number,
                        "total_fee": number,
                        "bookings": [
                            {
                                "course_name": string,
                                "date": "2025-01-20",
                                "start_time": "09:00",
                                "end_time": "12:00"
                            }
                        ]
                    }
                ]
            }
        ]
    }
    """
    permission_classes = []  # 使用 session 認證，不需要 DRF 的 IsAuthenticated

    def get(self, request, client_code=None):
        try:
            # 檢查用戶是否通過 session 登入
            if not request.user.is_authenticated:
                return Response({
                    'detail': '請先登入',
                    'code': 401
                }, status=status.HTTP_401_UNAUTHORIZED)

            user = request.user

            # 獲取用戶的所有預約組（按創建時間倒序）
            reservation_groups = ReservationGroup.objects.filter(
                user=user
            ).order_by('-created_at')

            history_data = []

            for group in reservation_groups:
                # 獲取付款狀態
                try:
                    payment = Payment.objects.get(reservation_group=group)
                    payment_status = payment.status
                except Payment.DoesNotExist:
                    payment_status = 'unpaid'

                # 獲取該組的所有預約
                reservations = group.reservations.all()

                # 計算總金額
                total_amount = sum([
                    resv.payment_amount
                    for resv in reservations
                    if resv.status not in ['deleted', 'cancelled']
                ])

                # 組裝預約詳情
                reservation_details = []
                for resv in reservations:
                    # 獲取該預約的所有課程時段
                    bookings = Booking.objects.filter(reservation=resv).order_by('date', 'start_time')

                    booking_details = []
                    for booking in bookings:
                        booking_details.append({
                            'course_name': booking.course_name,
                            'date': booking.date.strftime('%Y-%m-%d'),
                            'start_time': booking.start_time.strftime('%H:%M'),
                            'end_time': booking.end_time.strftime('%H:%M')
                        })

                    # 狀態映射
                    status_map = {
                        'created': 'created',
                        'auto_assigned': 'auto_assigned',
                        'manually_assigned': 'manually_assigned',
                        'pending_coach_confirmation': 'pending_coach_confirmation',
                        'auto_assignment_failed': 'auto_assignment_failed',
                        'cancelled': 'cancelled',
                        'deleted': 'deleted',
                    }

                    reservation_details.append({
                        'id': resv.id,
                        'resort': resv.resort.display_name if resv.resort else '未指定',
                        'course_type': resv.course_type.name if resv.course_type else '未指定',
                        'language': resv.get_language_display() if resv.language else '中文',
                        'status': status_map.get(resv.status, resv.status),
                        'number_of_people': resv.number_of_people,
                        'course_fee': resv.course_fee,
                        'coach_fee': resv.coach_fee,
                        'equipment_rental_fee': resv.equipment_rental_fee,
                        'equipment_assistance_time_label': resv.get_equipment_assistance_time_display(),
                        'language_fee': resv.language_fee,
                        'discount_amount': resv.discount_amount,
                        'discount_code': resv.discount_code,
                        'discount_name': resv.discount_name,
                        'original_total_fee': resv.total_fee,
                        'total_fee': resv.payment_amount,
                        'payment_amount': resv.payment_amount,
                        'bookings': booking_details
                    })

                history_data.append({
                    'reservation_group_id': group.id,
                    'created_at': group.created_at.isoformat(),
                    'total_amount': total_amount,
                    'payment_status': payment_status,
                    'reservations': reservation_details
                })

            return Response({
                'history': history_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'獲取歷史紀錄失敗: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProcessPaymentAPI(APIView):
    """
    POST /api/process-payment/
    處理付款請求（藍新支付或銀行匯款）

    請求格式：
    {
        "reservation_group_id": number,
        "payment_type": "newebpay" | "bank_transfer",
        "sender_account": string (僅銀行匯款需要，後五碼)
    }

    返回（藍新支付）：
    {
        "payment_type": "newebpay",
        "html": "<form>...</form>"  // 自動提交的 HTML 表單
    }

    返回（銀行匯款）：
    {
        "payment_type": "bank_transfer",
        "message": "匯款資訊已提交"
    }
    """

    def post(self, request, client_code=None):
        try:
            reservation_group_id = request.data.get('reservation_group_id')
            payment_type = request.data.get('payment_type')

            if not reservation_group_id or not payment_type:
                return Response({
                    'error': '缺少必要參數'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 獲取預約群組
            try:
                group = ReservationGroup.objects.get(pk=reservation_group_id)
            except ReservationGroup.DoesNotExist:
                return Response({
                    'error': '找不到預約群組'
                }, status=status.HTTP_404_NOT_FOUND)

            hold_message, hold_status = get_group_payment_hold(group)
            if hold_message:
                return Response({
                    'error': hold_message,
                    'payment_status': hold_status,
                    'requires_payment': False,
                }, status=status.HTTP_400_BAD_REQUEST)

            if payment_type == 'newebpay':
                return self._process_newebpay(request, group)
            elif payment_type == 'bank_transfer':
                return self._process_bank_transfer(request, group)
            else:
                return Response({
                    'error': '不支援的付款方式'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'error': f'處理付款失敗: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _process_newebpay(self, request, group):
        """處理藍新支付"""
        # 獲取所有預約
        bookings = Booking.objects.filter(reservation__in=group.reservations.all())

        # 構建商品名稱
        written_courses = set()
        product_name_parts = ["滑雪預約"]

        for booking in bookings:
            formatted_date = booking.date.strftime("%Y-%m-%d")
            course_key = (formatted_date, booking.course_name)
            if course_key not in written_courses:
                product_name_parts.append(f"{formatted_date} {booking.course_name}")
                written_courses.add(course_key)

        product_name = " / ".join(product_name_parts)

        # 計算總金額
        total_amount = sum([
            resv.payment_amount
            for resv in group.reservations.exclude(status__in=['deleted', 'cancelled'])
        ])

        # 準備藍新支付資料
        user = request.user if request.user.is_authenticated else group.user
        user_id = user.id if user else 0

        data = {
            "store": {
                "MerchantID": 'MS3680822811',
                "HashKey": 'tXnG2aLtEnVzACrJY3CW0SLCLyFYZDEf',
                "HashIV": 'PKmJnNJCcJyXpqcC',
            },
            "body": {
                "img": False,
                "OrderNo": str(group.pk),
                "price": str(total_amount),  # 正式環境用實際金額
                # "price": '1',  # 測試環境用 1 元
                "product": product_name,
                "NotifyURL": f"{RUN_HOST}/call_back/NewebPay/?user_id={user_id}",
                "Email": user.email if user and hasattr(user, 'email') else ''
            },
        }

        # 生成付款表單 HTML
        html_form = neweb_pay_request(data)

        return Response({
            "payment_type": "newebpay",
            "html": html_form
        }, status=status.HTTP_200_OK)

    def _process_bank_transfer(self, request, group):
        """處理銀行匯款"""
        sender_account = request.data.get('sender_account')

        if not sender_account or len(sender_account) != 5:
            return Response({
                'error': '請輸入正確的匯款帳戶後五碼'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 更新付款記錄
        user = request.user if request.user.is_authenticated else group.user

        payment, created = Payment.objects.get_or_create(
            reservation_group=group,
            defaults={'status': 'pending', 'payment_method': 'TT'}
        )

        payment.status = 'pending'
        payment.bank_account = sender_account
        payment.user = user
        payment.payment_method = 'TT'
        payment.save()

        return Response({
            "payment_type": "bank_transfer",
            "message": "匯款資訊已提交，請等待確認"
        }, status=status.HTTP_200_OK)


# 輔助函數：從舊的 views.py 提取
def get_booked_slots(coach_instance):
    """獲取教練的已預約時段（保留向後相容）"""
    from .models import Reservation

    reservations = Reservation.objects.filter(
        preferred_coach=coach_instance,
        status__in=['auto_assigned', 'manually_assigned', 'pending_coach_confirmation']
    ).prefetch_related('bookings')

    booked_slots = []
    for resv in reservations:
        for booking in resv.bookings.all():
            booked_slots.append({
                'date': booking.date,
                'start_time': booking.start_time.strftime('%H:%M'),
                'end_time': booking.end_time.strftime('%H:%M'),
            })

    return booked_slots


class GoogleLoginAPI(APIView):
    """
    POST /booking/<client_code>/api/google-login/
    Google 登入 API - 專門給預約系統前台使用

    與 Control 的 google-login API 不同：
    - 不檢查 is_manager 或 is_coach 權限
    - 允許所有 Google 用戶登入預約系統
    - 自動創建 UserProfile（預設無管理權限）

    請求格式：
    {
        "credential": "Google JWT token"
    }

    返回格式：
    {
        "code": 100,
        "msg": "登入成功",
        "data": {
            "email": "user@example.com",
            "name": "User Name",
            "picture": "https://...",
            "jwt": "token"
        }
    }
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, client_code=None):
        """檢查當前 session 是否有登入（給前端 useAuth 用）"""
        # === 🔍 DEBUG: 印出 cookie / session / user 狀態 ===
        print('=' * 60)
        print(f'[GoogleLoginAPI.GET] client_code={client_code}')
        print(f'  Cookies received: {dict(request.COOKIES)}')
        print(f'  session_key: {request.session.session_key}')
        print(f'  session items: {dict(request.session)}')
        print(f'  user.is_authenticated: {request.user.is_authenticated}')
        print(f'  user: {request.user}')
        print(f'  Origin header: {request.META.get("HTTP_ORIGIN")}')
        print(f'  Referer: {request.META.get("HTTP_REFERER")}')
        print('=' * 60)
        # === END DEBUG ===

        if not request.user.is_authenticated:
            return Response({'code': 401, 'msg': '未登入'}, status=status.HTTP_401_UNAUTHORIZED)

        # 拿 Google profile 圖片（如果有）
        picture = ''
        try:
            from allauth.socialaccount.models import SocialAccount
            sa = SocialAccount.objects.filter(user=request.user, provider='google').first()
            if sa:
                picture = (sa.extra_data or {}).get('picture', '')
        except Exception:
            pass

        return Response({
            'code': 200,
            'msg': 'OK',
            'user': {
                'email': request.user.email,
                'name': request.user.get_full_name() or request.user.username,
                'picture': picture,
            },
        })

    def post(self, request, client_code=None):
        import json
        import time
        from django.contrib.auth.models import User
        from Control.models import UserProfile

        credential = None

        # 從 request body 獲取 credential
        if request.body:
            try:
                body = json.loads(request.body)
                credential = body.get('credential')
            except json.JSONDecodeError:
                pass

        # 方式 1: 前端發送 Google JWT credential
        if credential:
            try:
                from google.oauth2 import id_token
                from google.auth.transport import requests as google_requests

                # 驗證 Google JWT token
                GOOGLE_CLIENT_ID = "754789081671-np8lbocgau68d4rers83v649bnm993vp.apps.googleusercontent.com"

                idinfo = id_token.verify_oauth2_token(
                    credential,
                    google_requests.Request(),
                    GOOGLE_CLIENT_ID
                )

                # 獲取用戶資訊
                email = idinfo.get('email')
                name = idinfo.get('name')
                picture = idinfo.get('picture')

                if not email:
                    return Response({'code': 400, 'msg': 'Google token 中缺少 email'})

                # 獲取或創建 Django User
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': email,
                        'first_name': name.split()[0] if name else '',
                        'last_name': name.split()[-1] if name and len(name.split()) > 1 else '',
                    }
                )

                # 確保 UserProfile 存在（但不檢查權限）
                user_profile, profile_created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'is_manager': False,
                        'is_coach': False,
                    }
                )

                # 設置 session (登入用戶)
                from django.contrib.auth import login
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)

                # === 🔍 DEBUG: 確認 session 真的建起來 ===
                # 強制 save session（避免被 lazy save 跳過）
                request.session.save()
                request.session.modified = True
                print('=' * 60)
                print(f'[GoogleLoginAPI.POST] login() 完成')
                print(f'  user_id={user.id} email={email}')
                print(f'  session_key (login 後): {request.session.session_key}')
                print(f'  session.modified: {request.session.modified}')
                print(f'  session items: {dict(request.session)}')
                print(f'  Origin: {request.META.get("HTTP_ORIGIN")}')
                print(f'  收到的 cookies: {dict(request.COOKIES)}')
                print('=' * 60)
                # === END DEBUG ===

                # 生成 JWT token
                jwt_token = f'1|{email}'

                return Response({
                    'code': 100,
                    'msg': '登入成功',
                    'data': {
                        'email': email,
                        'name': name,
                        'picture': picture,
                        'jwt': jwt_token,
                    },
                    'jwt': jwt_token,
                })

            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response({'code': 400, 'msg': f'Google token 驗證失敗: {str(e)}'})

        # 方式 2: 檢查是否已登入（Django allauth session）
        if request.user.is_authenticated:
            # 確保 UserProfile 存在
            user_profile, created = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={
                    'is_manager': False,
                    'is_coach': False,
                }
            )

            # 獲取用戶資訊
            email = request.user.email
            name = request.user.get_full_name() or request.user.first_name or request.user.email

            # 獲取用戶頭像
            picture = ''
            if request.user.socialaccount_set.exists():
                social_account = request.user.socialaccount_set.first()
                picture = social_account.get_avatar_url()

            # 生成 JWT token
            jwt_token = f'1|{email}'

            return Response({
                'code': 200,
                'msg': '已登入',
                'user': {
                    'email': email,
                    'name': name,
                    'picture': picture,
                    'jwt': jwt_token,
                }
            })

        return Response({'code': 400, 'msg': '請先完成 Google 登入'})


# ==================== 取消失敗訂單（前台改日期時用）====================

class CancelFailedReservationsAPI(APIView):
    """
    POST /api/cancel-failed-reservations/
    body: { "reservation_group_ids": [int, ...] }

    使用者在排課失敗 modal 選「改其他日期」時呼叫，刪除剛才建立但尚未付款的失敗訂單。
    僅允許刪除：1) 屬於當前 user 的；2) 狀態為 auto_assignment_failed 的。
    """
    def post(self, request, client_code=None):
        if not request.user.is_authenticated:
            return Response({'code': 401, 'msg': '請先登入'}, status=status.HTTP_401_UNAUTHORIZED)

        ids = request.data.get('reservation_group_ids') or []
        if not ids:
            return Response({'code': 400, 'msg': '缺少 reservation_group_ids'}, status=status.HTTP_400_BAD_REQUEST)

        from .models import ReservationGroup
        groups = ReservationGroup.objects.filter(pk__in=ids, user=request.user)

        deleted_count = 0
        for g in groups:
            # 安全條件：必須所有 reservation 都是 auto_assignment_failed
            statuses = list(g.reservations.values_list('status', flat=True))
            if statuses and all(s == 'auto_assignment_failed' for s in statuses):
                g.delete()
                deleted_count += 1

        return Response({
            'code': 200, 'msg': f'已取消 {deleted_count} 筆訂單',
            'deleted_count': deleted_count,
        })
