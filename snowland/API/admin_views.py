"""
後台管理 API
所有後台用 ViewSet 都在這裡
URL 格式：/api/admin/<client_code>/<resource>/
"""
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q, Prefetch
from django.utils import timezone
from datetime import timedelta, datetime
from collections import defaultdict

from Client.models import SiteContent
from Coach.models import Coach, CoachLeaveRequest
from Resorts.models import Resorts
from Coursekit.models import CourseCategory, CourseType, CourseTemplate, CourseSession, CoursePricing, SeasonSetting, DiscountCode
from booking.models import ReservationGroup, Reservation, Booking, MemberDetail, Payment

from .admin_serializers import (
    SiteContentAdminSerializer,
    CoachAdminSerializer,
    CoachLeaveRequestAdminSerializer,
    ResortAdminSerializer,
    CourseCategoryAdminSerializer,
    CourseTypeAdminSerializer,
    CourseTemplateAdminSerializer,
    CoursePricingAdminSerializer,
    DiscountCodeAdminSerializer,
    SeasonSettingAdminSerializer,
    OrderAdminSerializer,
    CustomerAdminSerializer,
    BookingScheduleAdminSerializer,
)
from .admin_permissions import (
    ADMIN_PERMISSION_DEFINITIONS,
    get_user_admin_permissions,
    normalize_admin_permissions,
    user_has_admin_permission,
)


# ==================== 權限 ====================

def _resolve_tenant(request, view):
    """
    從 URL kwargs 或 resolver_match 取出 client_code，查 Client 物件並掛到 request.tenant
    （這個 project 沒有 TenantMiddleware，所以要自己處理）
    """
    if getattr(request, 'tenant', None):
        return request.tenant

    # 1. ViewSet：從 view.kwargs 拿
    client_code = None
    if hasattr(view, 'kwargs') and view.kwargs:
        client_code = view.kwargs.get('client_code')

    # 2. FBV：從 request.resolver_match.kwargs 拿
    if not client_code and hasattr(request, 'resolver_match') and request.resolver_match:
        client_code = request.resolver_match.kwargs.get('client_code')

    if not client_code:
        return None

    try:
        from Client.models import Client
        tenant = Client.objects.get(internal_code=client_code, is_active=True)
        request.tenant = tenant
        return tenant
    except Exception:
        return None


class IsTenantManager(IsAuthenticated):
    """後台管理 API 權限：必須登入 + 是 manager（或 superuser） + 有 tenant"""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        tenant = _resolve_tenant(request, view)
        if not tenant:
            return False

        # superuser 直接放行
        if request.user.is_superuser:
            return True

        # 一般 user 必須有 UserProfile.is_manager
        try:
            profile = request.user.userprofile
            if not profile.is_manager:
                return False
        except Exception:
            return False

        permission_key = getattr(view, 'permission_key', None)
        if permission_key and not user_has_admin_permission(request.user, permission_key):
            return False

        return True


class IsTenantCoach(IsAuthenticated):
    """
    教練視角 API 權限：必須登入 + 是 coach + 有 tenant
    用於 /coach/my-* 等個人視角端點
    """
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        tenant = _resolve_tenant(request, view)
        if not tenant:
            return False

        # superuser 也視為可進（方便 demo）
        if request.user.is_superuser:
            return True

        # 必須有 UserProfile.is_coach 並且有對應的 Coach 紀錄
        try:
            profile = request.user.userprofile
            if not profile.is_coach:
                return False
        except Exception:
            return False

        # 確認此 user 真的有 Coach 紀錄關聯
        if not Coach.objects.filter(user=request.user, client=tenant).exists():
            return False

        return True


# ==================== 標準回應包裝 ====================

def wrap_list(queryset, serializer_class, request, context=None):
    serializer = serializer_class(queryset, many=True, context=context or {'request': request})
    return Response({
        'code': 200, 'msg': 'OK',
        'data': {'list': serializer.data, 'total': len(serializer.data)},
    })


def _permission_forbidden(permission_key):
    return Response({
        'code': 403,
        'msg': '沒有此功能權限',
        'data': {'permission': permission_key},
    }, status=403)


def _require_admin_permission(request, permission_key):
    if user_has_admin_permission(request.user, permission_key):
        return None
    return _permission_forbidden(permission_key)


def _parse_date_query(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _format_calendar_time(value):
    if not value:
        return ''
    return value.strftime('%H:%M:%S') if hasattr(value, 'strftime') else str(value)


def _reservation_user_name(reservation):
    try:
        user = reservation.group.user
        return user.username if user else (reservation.group.name or '訪客')
    except Exception:
        return ''


def _equipment_assistance_calendar_item(reservation, booking, include_coach=True):
    slot = reservation.equipment_assistance_time_slot
    if not slot or not slot.start_time or not slot.end_time:
        return None

    event_date = booking.date - timedelta(days=1) if slot.day_type == 'previous_day' else booking.date
    relative_label = '課程前一日' if slot.day_type == 'previous_day' else '課程當日'
    time_label = reservation.get_equipment_assistance_time_display() or slot.display_label()

    item = {
        'id': -(booking.id * 100000 + slot.id),
        'reservation_id': reservation.id,
        'group_id': reservation.group_id,
        'date': str(event_date),
        'start_time': _format_calendar_time(slot.start_time),
        'end_time': _format_calendar_time(slot.end_time),
        'course_name': f'裝備協助（{relative_label}）',
        'course_type': reservation.course_type.name if reservation.course_type else '',
        'ability_level': reservation.max_ability_level or '',
        'language': reservation.language or '',
        'language_label': reservation.get_language_display() if reservation else '',
        'equipment': reservation.equipment or '',
        'equipment_label': reservation.get_equipment_display() if reservation.equipment else '',
        'is_preferred_coach': bool(reservation.is_preferred_coach),
        'user_name': _reservation_user_name(reservation),
        'resort': reservation.resort.display_name if reservation.resort else '',
        'number_of_people': reservation.number_of_people if reservation else 0,
        'is_scheduled': booking.is_scheduled,
        'status': 'equipment_assistance',
        'event_type': 'equipment_assistance',
        'equipment_assistance_time_label': time_label,
        'linked_course_date': str(booking.date),
    }
    if include_coach:
        item['coach_name'] = reservation.preferred_coach.name if reservation.preferred_coach else ''
    return item


SCHEDULED_RESERVATION_STATUSES = [
    'auto_assigned',
    'manually_assigned',
    'pending_coach_confirmation',
    'completed',
    'form_filled',
]

COACH_VISIBLE_PAYMENT_STATUSES = ['pending', 'paid']


def _equipment_assistance_calendar_items(
    *,
    tenant=None,
    coach=None,
    start_date=None,
    end_date=None,
    include_coach=True,
    scheduled_only=False,
    completed_orders_only=False,
    require_booking_scheduled=True,
):
    qs = Reservation.objects.filter(
        equipment='purchaseAssistanceTime',
        equipment_assistance_time_slot__isnull=False,
        preferred_coach__isnull=False,
    ).exclude(status__in=['deleted', 'cancelled']).select_related(
        'equipment_assistance_time_slot',
        'preferred_coach',
        'resort',
        'course_type',
        'group__user',
    ).prefetch_related('bookings')

    if tenant:
        qs = qs.filter(group__client=tenant)
    if coach:
        qs = qs.filter(preferred_coach=coach)
    if completed_orders_only:
        qs = qs.filter(group__payments__status__in=COACH_VISIBLE_PAYMENT_STATUSES)
    if scheduled_only:
        qs = qs.filter(status__in=SCHEDULED_RESERVATION_STATUSES)
    if start_date:
        qs = qs.filter(bookings__date__gte=start_date)
    if end_date:
        qs = qs.filter(bookings__date__lte=end_date + timedelta(days=1))

    items = []
    for reservation in qs.distinct():
        for booking in reservation.bookings.all():
            if scheduled_only and require_booking_scheduled and not booking.is_scheduled:
                continue
            item = _equipment_assistance_calendar_item(reservation, booking, include_coach=include_coach)
            if not item:
                continue
            item_date = _parse_date_query(item['date'])
            if start_date and item_date and item_date < start_date:
                continue
            if end_date and item_date and item_date > end_date:
                continue
            items.append(item)
    return items


def _sort_calendar_items(items):
    return sorted(items, key=lambda item: (
        item.get('date') or '',
        item.get('start_time') or '',
        item.get('course_name') or '',
        str(item.get('id') or ''),
    ))


def _calendar_date_keys(start_date, end_date):
    if not start_date or not end_date or end_date < start_date:
        return []
    days = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def _daily_coach_availability_summary(*, tenant, start_date, end_date):
    if not tenant or not start_date or not end_date:
        return []

    coaches = Coach.objects.filter(
        client=tenant,
        availability_status__in=['active', 'passive'],
    ).values_list('id', 'name')
    coach_names = {coach_id: name for coach_id, name in coaches}
    coach_ids = set(coach_names.keys())
    total_coaches = len(coach_ids)

    booked_by_date = defaultdict(set)
    if coach_ids:
        booking_rows = Booking.objects.filter(
            reservation__group__client=tenant,
            reservation__group__payments__status__in=COACH_VISIBLE_PAYMENT_STATUSES,
            reservation__preferred_coach_id__in=coach_ids,
            reservation__status__in=SCHEDULED_RESERVATION_STATUSES,
            date__gte=start_date,
            date__lte=end_date,
        ).values('date', 'reservation__preferred_coach_id').distinct()
        for row in booking_rows:
            coach_id = row.get('reservation__preferred_coach_id')
            if row.get('date') and coach_id:
                booked_by_date[row['date']].add(coach_id)

        equipment_reservations = Reservation.objects.filter(
            group__client=tenant,
            equipment='purchaseAssistanceTime',
            equipment_assistance_time_slot__isnull=False,
            preferred_coach_id__in=coach_ids,
            status__in=SCHEDULED_RESERVATION_STATUSES,
            group__payments__status__in=COACH_VISIBLE_PAYMENT_STATUSES,
        ).select_related(
            'equipment_assistance_time_slot',
        ).prefetch_related('bookings')

        for reservation in equipment_reservations.distinct():
            slot = reservation.equipment_assistance_time_slot
            if not slot:
                continue
            for booking in reservation.bookings.all():
                event_date = booking.date - timedelta(days=1) if slot.day_type == 'previous_day' else booking.date
                if start_date <= event_date <= end_date:
                    booked_by_date[event_date].add(reservation.preferred_coach_id)

    leave_by_date = defaultdict(set)
    if coach_ids:
        leaves = CoachLeaveRequest.objects.filter(
            coach_id__in=coach_ids,
            status='approved',
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        for leave in leaves:
            leave_start = max(leave.start_date, start_date)
            leave_end = min(leave.end_date, end_date)
            for day in _calendar_date_keys(leave_start, leave_end):
                leave_by_date[day].add(leave.coach_id)

    summary = []
    for day in _calendar_date_keys(start_date, end_date):
        booked_ids = booked_by_date.get(day, set())
        leave_ids = leave_by_date.get(day, set())
        unavailable_ids = booked_ids | leave_ids
        free_ids = coach_ids - unavailable_ids
        summary.append({
            'date': day.isoformat(),
            'total_coaches': total_coaches,
            'booked_coaches': len(booked_ids),
            'leave_coaches': len(leave_ids),
            'free_coaches': len(free_ids),
        })
    return summary


def _coach_visible_window():
    today = timezone.localdate()
    return today, today + timedelta(days=10)


def _coach_can_view_full_schedule(coach):
    return True


def _booking_in_date_range(booking, start_date=None, end_date=None):
    if start_date and booking.date < start_date:
        return False
    if end_date and booking.date > end_date:
        return False
    return True


# ==================== Site Content ====================

class SiteContentAdminViewSet(ModelViewSet):
    serializer_class = SiteContentAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'cms'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return SiteContent.objects.none()

        qs = SiteContent.objects.filter(client=tenant)
        content_type = (self.request.query_params.get('content_type') or '').strip()
        location_key = (self.request.query_params.get('location_key') or '').strip()
        status_filter = (self.request.query_params.get('status') or '').strip()
        search = (self.request.query_params.get('search') or '').strip()

        if content_type:
            qs = qs.filter(content_type=content_type)
        if location_key:
            qs = qs.filter(location_key=location_key)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(subtitle__icontains=search) |
                Q(summary__icontains=search) |
                Q(body__icontains=search) |
                Q(location_key__icontains=search)
            )

        return qs.order_by('content_type', 'location_key', '-is_pinned', 'display_order', '-created_at')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def list(self, request, *args, **kwargs):
        return wrap_list(
            self.filter_queryset(self.get_queryset()),
            self.get_serializer_class(),
            request,
            self.get_serializer_context(),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'code': 200, 'msg': '官網內容已建立', 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'code': 200, 'msg': '官網內容已更新', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'code': 200, 'msg': '官網內容已刪除'})


# ==================== Coach ====================

class CoachAdminViewSet(ModelViewSet):
    serializer_class = CoachAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'coaches'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Coach.objects.none()
        return Coach.objects.filter(client=tenant).order_by('-id')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request,
                         self.get_serializer_context())

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'code': 200, 'msg': '教練建立成功', 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'code': 200, 'msg': '教練資料已更新', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'code': 200, 'msg': '教練已刪除'})


# ==================== Coach Leave Request ====================

class CoachLeaveAdminViewSet(ModelViewSet):
    serializer_class = CoachLeaveRequestAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'coaches'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CoachLeaveRequest.objects.none()
        return CoachLeaveRequest.objects.filter(coach__client=tenant).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # 只允許更新 status / processing_result（用於審核）
        new_status = request.data.get('status')
        if new_status in ('approved', 'rejected'):
            instance.status = new_status
            instance.processing_result = request.data.get('processing_result', '')
            instance.reviewed_by = request.user
            instance.reviewed_at = timezone.now()
            instance.save()
            serializer = self.get_serializer(instance)
            return Response({'code': 200, 'msg': '已更新請假狀態', 'data': serializer.data})
        return Response({'code': 400, 'msg': '無效的狀態'}, status=status.HTTP_400_BAD_REQUEST)


# ==================== Resorts ====================

class ResortAdminViewSet(ModelViewSet):
    serializer_class = ResortAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'resorts'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Resorts.objects.none()
        return Resorts.objects.filter(client=tenant).prefetch_related(
            'equipment_pricing_tiers',
            'equipment_rental_items',
            'equipment_assistance_time_slots',
            'equipment_assistance_time_slots__course_templates',
        ).order_by('id')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request,
                         self.get_serializer_context())

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'code': 200, 'msg': '雪場建立成功', 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'code': 200, 'msg': '雪場已更新', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'code': 200, 'msg': '雪場已刪除'})


# ==================== Course Categories / Types / Templates ====================

class CourseCategoryAdminViewSet(ModelViewSet):
    serializer_class = CourseCategoryAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'course_types'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CourseCategory.objects.none()
        return CourseCategory.objects.filter(client=tenant).prefetch_related(
            'available_resorts',
            'types__available_resorts',
            'types__templates__resorts',
            'types__templates__sessions',
            'types__templates__allowed_coaches',
        ).order_by('display_order', 'id')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request,
                         self.get_serializer_context())


class CourseTypeAdminViewSet(ModelViewSet):
    serializer_class = CourseTypeAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'course_types'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CourseType.objects.none()
        return CourseType.objects.filter(category__client=tenant).prefetch_related(
            'available_resorts',
            'templates__resorts',
            'templates__sessions',
            'templates__allowed_coaches',
        ).order_by('display_order', 'id')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request)


class CourseTemplateAdminViewSet(ModelViewSet):
    serializer_class = CourseTemplateAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'course_types'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CourseTemplate.objects.none()
        return CourseTemplate.objects.filter(course_type__category__client=tenant).prefetch_related(
            'resorts',
            'allowed_coaches',
            'sessions',
        ).order_by(
            'course_type__category__display_order',
            'course_type__display_order',
            'display_order',
            'duration_hours',
            'id',
        )

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request)


class CourseSessionAdminViewSet(ModelViewSet):
    permission_key = 'course_types'
    """課程時段 CRUD（直接附屬於 template）"""
    permission_classes = [IsTenantManager]

    def get_serializer_class(self):
        from .admin_serializers import CourseSessionAdminSerializer
        return CourseSessionAdminSerializer

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CourseSession.objects.none()
        return CourseSession.objects.filter(template__course_type__category__client=tenant).order_by('id')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request)


class CoursePricingAdminViewSet(ModelViewSet):
    permission_key = 'pricing'
    """
    課程定價 CRUD:一筆規則綁多個 template + 一個 resort。
    多租戶過濾走 templates 上溯 client。

    注意:CoursePricing 是「策略表」,改價會立即影響後續所有新訂單(舊訂單已寫入快照不受影響)。
    """
    serializer_class = CoursePricingAdminSerializer
    permission_classes = [IsTenantManager]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CoursePricing.objects.none()
        # 只回傳「templates 至少有一個屬於本租戶」的定價規則
        return (CoursePricing.objects
                .filter(templates__course_type__category__client=tenant)
                .prefetch_related('people_tiers')
                .distinct()
                .order_by('resort__display_name', 'id'))

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'code': 200, 'msg': '定價已建立', 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'code': 200, 'msg': '定價已更新', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'code': 200, 'msg': '定價已刪除'})


class DiscountCodeAdminViewSet(ModelViewSet):
    permission_key = 'discounts'
    """優惠折扣碼 CRUD。只管理設定；實際套用到付款需由預約流程另行呼叫驗證。"""
    serializer_class = DiscountCodeAdminSerializer
    permission_classes = [IsTenantManager]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return DiscountCode.objects.none()
        return DiscountCode.objects.filter(client=tenant).order_by('-is_active', '-created_at', 'code')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'code': 200, 'msg': '折扣碼已建立', 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'code': 200, 'msg': '折扣碼已更新', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'code': 200, 'msg': '折扣碼已刪除'})


class SeasonSettingAdminViewSet(ModelViewSet):
    permission_key = 'pricing'
    """
    旺/淡季區間 CRUD。SeasonSetting 是全域表(沒有 client FK),所以不分租戶。
    若未來要分租戶,需在模型加 client 欄位 + migration。
    """
    serializer_class = SeasonSettingAdminSerializer
    permission_classes = [IsTenantManager]

    def get_queryset(self):
        return SeasonSetting.objects.all().order_by('start_date', 'id')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'code': 200, 'msg': '季節區間已建立', 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'code': 200, 'msg': '季節區間已更新', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'code': 200, 'msg': '季節區間已刪除'})


# ==================== Orders ====================

class OrderAdminViewSet(ModelViewSet):
    permission_key = 'orders'
    """訂單管理：列表 / 詳情 / 編輯（指派教練、改付款、觸發排課）"""
    serializer_class = OrderAdminSerializer
    permission_classes = [IsTenantManager]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ReservationGroup.objects.none()
        qs = ReservationGroup.objects.filter(client=tenant).order_by('-created_at').select_related('user').prefetch_related(
            Prefetch(
                'reservations',
                queryset=Reservation.objects.select_related(
                    'resort',
                    'course_type',
                    'course_template',
                    'preferred_coach',
                    'equipment_assistance_time_slot',
                ).prefetch_related('bookings', 'rejected_coaches'),
            ),
            'payments',
        )

        # 伺服端搜尋與過濾(分頁後前端只看得到當前頁,所以搜尋一定要在後端做)
        params = self.request.query_params

        search = (params.get('search') or '').strip()
        if search:
            # SN 是序列化器算出來的虛擬欄位(YYYYMMDD-NNNN),DB 無法直接查
            # 解法:從輸入末尾抓最後一段純數字當訂單 id,可兼容新格式 / 舊 SL 格式 / 純數字
            from django.db.models import Q
            import re
            search_q = Q(user__username__icontains=search) | Q(user__email__icontains=search) | Q(name__icontains=search)
            tail_digits = re.search(r'(\d+)\s*$', search)
            if tail_digits:
                try:
                    search_q |= Q(id=int(tail_digits.group(1)))
                except ValueError:
                    pass
            qs = qs.filter(search_q)

        status_filter = (params.get('status') or '').strip()
        if status_filter:
            qs = qs.filter(reservations__status=status_filter).distinct()

        payment_filter = (params.get('payment_status') or '').strip()
        if payment_filter:
            qs = qs.filter(payments__status=payment_filter).distinct()

        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())

        try:
            page = max(int(request.query_params.get('page', 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(max(int(request.query_params.get('page_size', 10)), 1), 100)
        except (TypeError, ValueError):
            page_size = 10

        total = qs.count()
        total_pages = (total + page_size - 1) // page_size if total else 0
        if total_pages and page > total_pages:
            page = total_pages
        if not total_pages:
            page = 1
        start = (page - 1) * page_size
        items = qs[start:start + page_size]

        serializer = self.get_serializer(items, many=True)
        return Response({
            'code': 200, 'msg': 'OK',
            'data': {
                'list': serializer.data,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
            },
        })

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            context={**self.get_serializer_context(), 'include_available_coaches': True},
        )
        return Response({'code': 200, 'msg': 'OK', 'data': serializer.data})

    def update(self, request, *args, **kwargs):
        """
        編輯訂單：指派/變更教練、更新付款狀態
        Body: {
            "action": "save" | "schedule",  // save=只儲存, schedule=儲存後觸發 AI 排課
            "payment_status": "paid" | "pending" | "unpaid" | ...,  (optional)
            "reservation_updates": [
                {"reservation_id": 1, "coach_id": 5},   // null 表示移除教練
                {"reservation_id": 2, "coach_id": null},
            ]
        }
        """
        instance = self.get_object()
        data = request.data
        action = data.get('action', 'save')
        payment_status = data.get('payment_status')
        reservation_updates = data.get('reservation_updates', []) or []
        booking_updates = data.get('booking_updates', []) or []

        # 1. 更新付款狀態
        if payment_status:
            payment, _ = Payment.objects.get_or_create(
                reservation_group=instance,
                defaults={'status': payment_status, 'user': instance.user},
            )
            payment.status = payment_status
            payment.save()

        # 2. 收集課程日期 / 時段變更
        booking_changes = []
        for upd in booking_updates:
            booking_id = upd.get('booking_id')
            if not booking_id:
                continue
            try:
                booking = Booking.objects.select_related('reservation').get(
                    pk=booking_id,
                    reservation__group=instance,
                )
            except Booking.DoesNotExist:
                continue

            try:
                new_date = self._parse_booking_date(upd.get('date'), booking.date)
                new_start_time = self._parse_booking_time(upd.get('start_time'), booking.start_time)
                new_end_time = self._parse_booking_time(upd.get('end_time'), booking.end_time)
            except ValueError as exc:
                return Response({'code': 400, 'msg': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            if new_end_time <= new_start_time:
                return Response({'code': 400, 'msg': '課程結束時間必須晚於開始時間'}, status=status.HTTP_400_BAD_REQUEST)

            if booking.date != new_date or booking.start_time != new_start_time or booking.end_time != new_end_time:
                reservation = booking.reservation
                booking_changes.append({
                    'booking': booking,
                    'old_date': booking.date,
                    'old_start_time': booking.start_time,
                    'old_end_time': booking.end_time,
                    'old_is_scheduled': booking.is_scheduled,
                    'old_reservation_status': reservation.status,
                    'old_preferred_coach_id': reservation.preferred_coach_id,
                    'old_is_preferred_coach': reservation.is_preferred_coach,
                    'new_date': new_date,
                    'new_start_time': new_start_time,
                    'new_end_time': new_end_time,
                })

        # 3. 收集教練變更
        coach_changes = []
        for upd in reservation_updates:
            r_id = upd.get('reservation_id')
            new_coach_id = upd.get('coach_id')
            if not r_id:
                continue
            try:
                r = instance.reservations.get(pk=r_id)
            except Reservation.DoesNotExist:
                continue
            old_coach_id = r.preferred_coach_id
            if str(old_coach_id) != str(new_coach_id):
                if r.is_preferred_coach:
                    return Response({
                        'code': 400,
                        'msg': '此課程為客人指定教練，後台不可更換教練',
                    }, status=status.HTTP_400_BAD_REQUEST)
                coach_changes.append({
                    'reservation': r,
                    'old_coach_id': old_coach_id,
                    'old_status': r.status,
                    'old_is_preferred_coach': r.is_preferred_coach,
                    'old_bookings_scheduled': [(b.id, b.is_scheduled) for b in r.bookings.all()],
                    'new_coach_id': new_coach_id,
                })

        if action == 'save':
            # 純儲存
            self._apply_booking_changes(booking_changes)
            for c in coach_changes:
                r = c['reservation']
                new_coach_id = c['new_coach_id']
                if new_coach_id:
                    coach = Coach.objects.get(pk=new_coach_id)
                    r.preferred_coach = coach
                    r.is_preferred_coach = False
                    if r.status in ['created', 'auto_assigned']:
                        r.status = 'manually_assigned'
                    r.bookings.update(is_scheduled=True)
                else:
                    r.preferred_coach = None
                    r.is_preferred_coach = False
                    if r.status in ['auto_assigned', 'manually_assigned']:
                        r.status = 'created'
                    r.bookings.update(is_scheduled=False)
                r.save()

            return Response({'code': 200, 'msg': f'已儲存（更新 {len(coach_changes) + len(booking_changes)} 筆資料）'})

        elif action == 'schedule':
            # 觸發 AI 排課
            if not coach_changes and not booking_changes:
                return Response({'code': 200, 'msg': '沒有變更，無需排課'})

            # 套用變更
            self._apply_booking_changes(booking_changes)
            for c in coach_changes:
                r = c['reservation']
                new_coach_id = c['new_coach_id']
                if new_coach_id:
                    coach = Coach.objects.get(pk=new_coach_id)
                    r.preferred_coach = coach
                    r.is_preferred_coach = True
                    r.status = 'created'
                else:
                    r.preferred_coach = None
                    r.is_preferred_coach = False
                    r.status = 'created'
                r.save()

            try:
                from booking.scheduler import assign_coachs
                reservations_to_assign = list(
                    instance.reservations.select_related('preferred_coach', 'resort', 'course_type')
                    .prefetch_related('bookings', 'rejected_coaches')
                )
                ok, _schedule_report = assign_coachs(reservations_to_assign=reservations_to_assign)
                if ok:
                    for c in coach_changes:
                        r = Reservation.objects.get(pk=c['reservation'].id)
                        if r.is_preferred_coach:
                            r.is_preferred_coach = False
                            r.save(update_fields=['is_preferred_coach'])
                    return Response({
                        'code': 200,
                        'msg': f'排課成功！已更新 {len(coach_changes) + len(booking_changes)} 筆資料',
                    })
                # 失敗 → 回滾
                self._rollback_coach_changes(coach_changes)
                self._rollback_booking_changes(booking_changes)
                return Response({
                    'code': 400,
                    'msg': '排課失敗：時間衝突或教練不可用，已恢復原狀態',
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                self._rollback_coach_changes(coach_changes)
                self._rollback_booking_changes(booking_changes)
                return Response({
                    'code': 500,
                    'msg': f'排課發生錯誤：{e}',
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({'code': 400, 'msg': f'未知動作 {action}'}, status=400)

    def _parse_booking_date(self, value, fallback):
        if value in (None, ''):
            return fallback
        if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
            return value
        try:
            return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
        except ValueError:
            raise ValueError('課程日期格式錯誤，請使用 YYYY-MM-DD')

    def _parse_booking_time(self, value, fallback):
        if value in (None, ''):
            return fallback
        if hasattr(value, 'hour') and hasattr(value, 'minute'):
            return value
        try:
            return datetime.strptime(str(value)[:5], '%H:%M').time()
        except ValueError:
            raise ValueError('課程時間格式錯誤，請使用 HH:MM')

    def _apply_booking_changes(self, booking_changes):
        for c in booking_changes:
            booking = c['booking']
            reservation = booking.reservation
            booking.date = c['new_date']
            booking.start_time = c['new_start_time']
            booking.end_time = c['new_end_time']
            booking.is_scheduled = False
            booking.save(update_fields=['date', 'start_time', 'end_time', 'is_scheduled'])
            if reservation.status in ['auto_assigned', 'manually_assigned', 'pending_coach_confirmation']:
                reservation.status = 'created'
                update_fields = ['status']
                if not reservation.is_preferred_coach:
                    reservation.preferred_coach = None
                    reservation.is_preferred_coach = False
                    update_fields += ['preferred_coach', 'is_preferred_coach']
                reservation.save(update_fields=update_fields)

    def _rollback_coach_changes(self, coach_changes):
        """還原教練變更"""
        for c in coach_changes:
            try:
                r = Reservation.objects.get(pk=c['reservation'].id)
                if c['old_coach_id']:
                    r.preferred_coach = Coach.objects.get(pk=c['old_coach_id'])
                else:
                    r.preferred_coach = None
                r.status = c['old_status']
                r.is_preferred_coach = c['old_is_preferred_coach']
                r.save()
                for booking_id, old_scheduled in c['old_bookings_scheduled']:
                    Booking.objects.filter(pk=booking_id).update(is_scheduled=old_scheduled)
            except Exception:
                pass

    def _rollback_booking_changes(self, booking_changes):
        """還原課程日期 / 時段變更"""
        for c in booking_changes:
            try:
                booking = Booking.objects.get(pk=c['booking'].id)
                booking.date = c['old_date']
                booking.start_time = c['old_start_time']
                booking.end_time = c['old_end_time']
                booking.is_scheduled = c['old_is_scheduled']
                booking.save(update_fields=['date', 'start_time', 'end_time', 'is_scheduled'])

                reservation = Reservation.objects.get(pk=booking.reservation_id)
                reservation.status = c['old_reservation_status']
                reservation.preferred_coach_id = c['old_preferred_coach_id']
                reservation.is_preferred_coach = c['old_is_preferred_coach']
                reservation.save(update_fields=['status', 'preferred_coach', 'is_preferred_coach'])
            except Exception:
                pass


# ==================== Customers ====================

@api_view(['GET'])
@permission_classes([IsTenantManager])
def customers_list(request, client_code):
    denied = _require_admin_permission(request, 'customers')
    if denied:
        return denied
    """聚合 User + 預約紀錄成為 Customer"""
    # 注入 tenant（FBV 的 view kwargs 來自 client_code 參數）
    if not getattr(request, 'tenant', None):
        try:
            from Client.models import Client
            request.tenant = Client.objects.get(internal_code=client_code, is_active=True)
        except Exception:
            return Response({'code': 404, 'msg': 'Client not found'}, status=404)
    tenant = request.tenant

    # 找出所有曾在此 client 預約過的 user
    user_ids = ReservationGroup.objects.filter(client=tenant).values_list('user_id', flat=True).distinct()
    users = User.objects.filter(id__in=[uid for uid in user_ids if uid])

    data = []
    for u in users:
        groups = ReservationGroup.objects.filter(client=tenant, user=u)
        total_spent = 0
        last_visit = None
        for g in groups:
            for r in g.reservations.all():
                total_spent += (r.payment_amount or 0)
            if not last_visit or g.created_at > last_visit:
                last_visit = g.created_at

        # 從 MemberDetail 取最近的滑雪程度
        latest_md = MemberDetail.objects.filter(
            reservation__group__in=groups,
            user=u,
        ).order_by('-created_at').first()

        # 取 UserProfile（is_manager / is_coach）
        try:
            from Control.models import UserProfile
            profile = UserProfile.objects.filter(user=u).first()
        except Exception:
            profile = None

        data.append({
            'id': u.id,
            'name': u.username or u.email,
            'email': u.email,
            'phone': '',
            'total_reservations': groups.count(),
            'total_spent': total_spent,
            'last_visit': last_visit.strftime('%Y-%m-%d') if last_visit else '',
            'age_range': latest_md.age_range if latest_md else '',
            'snowboard_skills': list(latest_md.snowboard_skills) if latest_md and latest_md.snowboard_skills else [],
            'ski_skills': list(latest_md.ski_skills) if latest_md and latest_md.ski_skills else [],
            'notes': '',
            'is_manager': bool(profile and profile.is_manager),
            'is_coach': bool(profile and profile.is_coach),
        })

    return Response({
        'code': 200, 'msg': 'OK',
        'data': {'list': data, 'total': len(data)},
    })


# ==================== Scheduling (Booking 列表) ====================

class BookingScheduleAdminViewSet(ReadOnlyModelViewSet):
    permission_key = 'scheduling'
    serializer_class = BookingScheduleAdminSerializer
    permission_classes = [IsTenantManager]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Booking.objects.none()
        photo_booking_q = (
            Q(reservation__course_type__category__service_type='photo') |
            Q(reservation__course_type__category__name__icontains='攝影') |
            Q(reservation__course_type__category__name__icontains='Photography') |
            Q(reservation__course_type__category__name__icontains='Photo') |
            Q(reservation__course_type__name__icontains='攝影') |
            Q(reservation__course_type__name__icontains='Photography') |
            Q(reservation__course_type__name__icontains='Photo') |
            Q(reservation__course_template__name__icontains='攝影') |
            Q(reservation__course_template__name__icontains='Photography') |
            Q(reservation__course_template__name__icontains='Photo') |
            Q(course_type__icontains='攝影') |
            Q(course_type__icontains='Photography') |
            Q(course_type__icontains='Photo') |
            Q(course_name__icontains='攝影') |
            Q(course_name__icontains='Photography') |
            Q(course_name__icontains='Photo')
        )
        scheduled_course_q = (
            Q(reservation__preferred_coach__isnull=False) &
            Q(reservation__status__in=SCHEDULED_RESERVATION_STATUSES)
        )
        qs = Booking.objects.filter(
            reservation__group__client=tenant,
            reservation__group__payments__status__in=COACH_VISIBLE_PAYMENT_STATUSES,
        ).exclude(
            reservation__status__in=['deleted', 'cancelled', 'auto_assignment_failed'],
        ).filter(
            scheduled_course_q | photo_booking_q
        ).select_related(
            'reservation',
            'reservation__resort',
            'reservation__preferred_coach',
            'reservation__group__user',
            'reservation__course_type',
            'reservation__course_type__category',
            'reservation__course_template',
        ).distinct().order_by('date', 'start_time')

        # 可選 query 參數：start, end (YYYY-MM-DD)
        start = self.request.query_params.get('start')
        end = self.request.query_params.get('end')
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        items = [dict(item) for item in serializer.data]

        start_date = _parse_date_query(request.query_params.get('start'))
        end_date = _parse_date_query(request.query_params.get('end'))
        items.extend(_equipment_assistance_calendar_items(
            tenant=getattr(request, 'tenant', None),
        start_date=start_date,
        end_date=end_date,
        include_coach=True,
        scheduled_only=True,
        completed_orders_only=True,
        require_booking_scheduled=False,
    ))
        items = _sort_calendar_items(items)
        daily_summary = _daily_coach_availability_summary(
            tenant=getattr(request, 'tenant', None),
            start_date=start_date,
            end_date=end_date,
        )
        return Response({
            'code': 200, 'msg': 'OK',
            'data': {'list': items, 'total': len(items), 'daily_summary': daily_summary},
        })


# ==================== Dashboard 統計 ====================

@api_view(['GET'])
@permission_classes([IsTenantManager])
def dashboard_stats(request, client_code):
    denied = _require_admin_permission(request, 'analytics')
    if denied:
        return denied
    """儀表板統計"""
    if not getattr(request, 'tenant', None):
        try:
            from Client.models import Client
            request.tenant = Client.objects.get(internal_code=client_code, is_active=True)
        except Exception:
            return Response({'code': 404, 'msg': 'Client not found'}, status=404)
    tenant = request.tenant

    period = request.query_params.get('period', 'month')
    now = timezone.now()
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'yesterday':
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # month
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    groups = ReservationGroup.objects.filter(client=tenant, created_at__gte=start)
    if period == 'yesterday':
        groups = groups.filter(created_at__lt=end)

    total_orders = groups.count()
    total_revenue = 0
    for g in groups:
        for r in g.reservations.all():
            total_revenue += (r.payment_amount or 0)

    active_users = groups.values('user').distinct().count()
    avg_order = (total_revenue // total_orders) if total_orders else 0

    # 熱門課程 TOP 5
    top_items = []
    booking_counts = {}
    for g in groups:
        for r in g.reservations.all():
            for b in r.bookings.all():
                key = b.course_name or '未命名課程'
                if key not in booking_counts:
                    booking_counts[key] = {'name': key, 'quantity': 0, 'revenue': 0}
                booking_counts[key]['quantity'] += 1
                booking_counts[key]['revenue'] += (r.payment_amount or 0) // max(r.bookings.count(), 1)
    top_items = sorted(booking_counts.values(), key=lambda x: -x['quantity'])[:5]
    for i, item in enumerate(top_items):
        item['id'] = i + 1

    # 最近訂單
    recent_orders = []
    for g in groups.order_by('-created_at')[:5]:
        p = g.payments.last()
        first_r = g.reservations.first()
        recent_orders.append({
            'sn': f'SL{g.created_at.year}-{g.id:04d}',
            'member': g.user.username if g.user else (g.name or '訪客'),
            'amount': sum((r.payment_amount or 0) for r in g.reservations.all()),
            'status': p.status if p else 'unpaid',
            'created_at': g.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return Response({
        'code': 200, 'msg': 'OK',
        'data': {
            'stats': {
                'orders': total_orders,
                'revenue': total_revenue,
                'members': active_users,
                'avg_order_value': avg_order,
            },
            'top_items': top_items,
            'recent_orders': recent_orders,
        },
    })


# ==================== 員工權限管理 ====================

@api_view(['GET'])
@permission_classes([IsTenantManager])
def staff_list(request, client_code):
    denied = _require_admin_permission(request, 'staff')
    if denied:
        return denied
    """
    列出所有有權限的使用者（is_manager 或 is_coach）+ 可選搜尋 user
    GET /api/admin/<client>/staff/?q=name
    """
    from Control.models import UserProfile

    q = (request.query_params.get('q') or '').strip()

    # 預設：列出有 is_manager 或 is_coach 的 profile
    profiles = UserProfile.objects.filter(
        Q(is_manager=True) | Q(is_coach=True)
    ).select_related('user')

    # 搜尋模式：找所有 user（包括沒權限的）
    if q:
        users = User.objects.filter(
            Q(username__icontains=q) | Q(email__icontains=q) |
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )[:50]
    else:
        superusers = list(User.objects.filter(is_superuser=True))
        users = superusers + [p.user for p in profiles]

    users = list(users)
    user_ids = [u.id for u in users]
    reservation_counts = dict(
        ReservationGroup.objects.filter(client=request.tenant, user_id__in=user_ids)
        .values('user_id')
        .annotate(count=Count('id'))
        .values_list('user_id', 'count')
    )

    # 組裝資料
    items = []
    seen_ids = set()
    for u in users:
        if u.id in seen_ids:
            continue
        seen_ids.add(u.id)

        try:
            profile = u.userprofile
            is_manager = False if u.is_superuser else profile.is_manager
            is_coach = profile.is_coach
            admin_permissions = get_user_admin_permissions(u)
        except Exception:
            is_manager = False
            is_coach = False
            admin_permissions = []

        # 找對應的 Coach 紀錄（如果有）
        coach_record = Coach.objects.filter(user=u, client=request.tenant).first()

        reservation_count = reservation_counts.get(u.id, 0)

        items.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'name': u.get_full_name() or u.username,
            'is_member': reservation_count > 0,
            'reservation_count': reservation_count,
            'is_superuser': u.is_superuser,
            'is_manager': is_manager,
            'is_coach': is_coach,
            'permissions': admin_permissions,
            'has_coach_record': bool(coach_record),
            'coach_id': coach_record.id if coach_record else None,
            'coach_name': coach_record.name if coach_record else None,
            'date_joined': u.date_joined.strftime('%Y-%m-%d') if u.date_joined else '',
            'last_login': u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else None,
        })

    return Response({
        'code': 200, 'msg': 'OK',
        'data': {'list': items, 'total': len(items)},
    })


# ==================== 客戶權限管理 ====================

@api_view(['POST'])
@permission_classes([IsTenantManager])
def update_customer_permission(request, client_code, user_id):
    denied = _require_admin_permission(request, 'staff')
    if denied:
        return denied
    """
    設定使用者的 is_superuser / is_manager / is_coach 權限
    POST /api/admin/<client>/customers/<user_id>/permission/
    最大管理員與後台人員只能擇一。
    """
    try:
        target_user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'code': 404, 'msg': '使用者不存在'}, status=404)

    if target_user.is_superuser and not request.user.is_superuser:
        return Response({'code': 403, 'msg': '只有 Superuser 可以調整 Superuser 權限'}, status=403)

    raw_permissions = request.data.get('permissions', None)
    admin_permissions = normalize_admin_permissions(raw_permissions) if raw_permissions is not None else None

    try:
        from Control.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=target_user)
        was_manager = profile.is_manager
        requested_superuser = request.data.get('is_superuser', None)
        if requested_superuser is not None:
            if not request.user.is_superuser:
                return Response({'code': 403, 'msg': '只有最大管理員可以調整最大管理員'}, status=403)
            target_user.is_superuser = bool(requested_superuser)
            target_user.save(update_fields=['is_superuser'])

        is_manager = bool(request.data.get('is_manager', False))
        if target_user.is_superuser and is_manager:
            is_manager = False
        is_coach = bool(request.data.get('is_coach', False))
        profile.is_manager = is_manager
        profile.is_coach = is_coach
        if is_manager:
            if admin_permissions is not None:
                profile.admin_permissions = admin_permissions
            elif not was_manager and profile.admin_permissions is None:
                profile.admin_permissions = []
        else:
            profile.admin_permissions = []
        profile.save()
        return Response({
            'code': 200, 'msg': '權限已更新',
            'data': {
                'is_superuser': target_user.is_superuser,
                'is_manager': profile.is_manager,
                'is_coach': profile.is_coach,
                'permissions': get_user_admin_permissions(target_user),
            },
        })
    except Exception as e:
        return Response({'code': 500, 'msg': f'更新失敗：{e}'}, status=500)


# ==================== 雪場費用批量更新 ====================

@api_view(['POST'])
@permission_classes([IsTenantManager])
def bulk_update_resort_fees(request, client_code, resort_id):
    denied = _require_admin_permission(request, 'resorts')
    if denied:
        return denied
    """
    批量更新一個雪場的所有費用
    POST /api/admin/<client>/resorts/<resort_id>/bulk-fees/
    Body: { fees: [{ fee_type, price, is_active, description }] }
    沒提交的 fee_type 會被設為 is_active=false
    """
    try:
        resort = Resorts.objects.get(pk=resort_id, client=request.tenant)
    except Resorts.DoesNotExist:
        return Response({'code': 404, 'msg': '雪場不存在'}, status=404)

    fees_data = request.data.get('fees', [])
    if not isinstance(fees_data, list):
        return Response({'code': 400, 'msg': 'fees 需為陣列'}, status=400)

    from django.db import transaction
    from Resorts.models import ResortFee

    submitted_types = []
    with transaction.atomic():
        for item in fees_data:
            fee_type = item.get('fee_type')
            price = item.get('price')
            if not fee_type or price is None:
                continue
            ResortFee.objects.update_or_create(
                resort=resort, fee_type=fee_type,
                defaults={
                    'price': price,
                    'is_active': bool(item.get('is_active', True)),
                    'description': item.get('description', ''),
                },
            )
            submitted_types.append(fee_type)

        # 沒提交的設為 inactive（不刪除，保留歷史）
        ResortFee.objects.filter(resort=resort).exclude(fee_type__in=submitted_types).update(is_active=False)

    return Response({'code': 200, 'msg': f'已更新 {len(submitted_types)} 筆費用'})


# ==================== 教練視角：待確認課程 + 接受/拒絕 ====================

@api_view(['GET'])
@permission_classes([IsTenantCoach])
def coach_pending_confirmations(request, client_code):
    """
    教練本人的待確認課程列表
    GET /api/admin/<client>/coach/pending/
    （任何登入的教練都能看自己的，不要 IsTenantManager）
    """
    # 找當前 user 的 Coach
    try:
        coach = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        return Response({'code': 403, 'msg': '您不是教練'}, status=403)

    qs = Reservation.objects.filter(
        preferred_coach=coach,
        status='pending_coach_confirmation',
    ).select_related('resort', 'course_type', 'group__user').prefetch_related('bookings').distinct().order_by('-mdt_add')

    items = []
    for r in qs:
        items.append({
            'id': r.id,
            'group_id': r.group_id,
            'user_name': r.group.user.username if r.group.user else (r.group.name or '訪客'),
            'resort': r.resort.display_name if r.resort else '',
            'course_type': r.course_type.name if r.course_type else '',
            'ability_level': r.max_ability_level or '',
            'language': r.language,
            'number_of_people': r.number_of_people,
            'total_fee': r.total_fee,
            'bookings': [
                {'date': str(b.date), 'start_time': str(b.start_time), 'end_time': str(b.end_time)}
                for b in sorted(r.bookings.all(), key=lambda b: (str(b.date or ''), str(b.start_time or '')))
            ],
        })

    return Response({'code': 200, 'msg': 'OK', 'data': {'list': items, 'total': len(items), 'visibility_mode': 'all_pending'}})


@api_view(['POST'])
@permission_classes([IsTenantCoach])
def coach_confirm_course(request, client_code, reservation_id):
    """
    教練接受 / 拒絕指派
    POST /api/admin/<client>/coach/confirm/<reservation_id>/
    Body: { action: 'accept' | 'reject' }
    """
    try:
        coach = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        return Response({'code': 403, 'msg': '您不是教練'}, status=403)

    try:
        r = Reservation.objects.get(pk=reservation_id, preferred_coach=coach)
    except Reservation.DoesNotExist:
        return Response({'code': 404, 'msg': '課程不存在或非指派給您'}, status=404)

    action = request.data.get('action')
    if action == 'accept':
        if r.status != 'pending_coach_confirmation':
            return Response({'code': 400, 'msg': '此課程目前狀態不可接受'}, status=400)
        r.status = 'manually_assigned'
        r.save()
        return Response({'code': 200, 'msg': '已接受'})

    if action == 'reject':
        # 加入 rejected_coaches、清除指派、重排
        r.rejected_coaches.add(coach)
        r.preferred_coach = None
        r.is_preferred_coach = False
        r.status = 'created'
        r.save()
        for b in r.bookings.all():
            b.is_scheduled = False
            b.save()
        # 嘗試重新排課
        try:
            from booking.scheduler import reassign_single_reservation
            new_status = reassign_single_reservation(r)
            return Response({'code': 200, 'msg': f'已拒絕，重新排課狀態：{new_status}'})
        except Exception:
            return Response({'code': 200, 'msg': '已拒絕（無自動重排）'})

    return Response({'code': 400, 'msg': '未知 action'}, status=400)


# ==================== 教練視角：我的所有課程 ====================

@api_view(['GET'])
@permission_classes([IsTenantCoach])
def coach_my_courses(request, client_code):
    """
    教練的所有課程（不只 pending，包含已排定/已完成）
    GET /api/admin/<client>/coach/my-courses/
    Query: status=created|auto_assigned|... (optional), date_from, date_to
    """
    try:
        coach = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        return Response({'code': 403, 'msg': '您不是教練'}, status=403)

    full_schedule_visible = _coach_can_view_full_schedule(coach)
    visible_start, visible_end = _coach_visible_window()
    qs = Reservation.objects.filter(
        preferred_coach=coach,
        group__payments__status__in=COACH_VISIBLE_PAYMENT_STATUSES,
    ).exclude(status__in=['deleted', 'cancelled']).select_related(
        'resort', 'course_type', 'group__user'
    ).prefetch_related('bookings').distinct().order_by('-mdt_add')

    if not full_schedule_visible:
        qs = qs.filter(
            bookings__date__gte=visible_start,
            bookings__date__lte=visible_end,
        ).distinct()

    # 篩選
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from:
        qs = qs.filter(bookings__date__gte=date_from).distinct()
    if date_to:
        qs = qs.filter(bookings__date__lte=date_to).distinct()
    display_start = None if full_schedule_visible else visible_start
    display_end = None if full_schedule_visible else visible_end
    parsed_date_from = _parse_date_query(date_from)
    parsed_date_to = _parse_date_query(date_to)
    if parsed_date_from and (display_start is None or parsed_date_from > display_start):
        display_start = parsed_date_from
    if parsed_date_to and (display_end is None or parsed_date_to < display_end):
        display_end = parsed_date_to

    items = []
    for r in qs:
        items.append({
            'id': r.id,
            'group_id': r.group_id,
            'user_name': r.group.user.username if r.group.user else (r.group.name or '訪客'),
            'resort': r.resort.display_name if r.resort else '',
            'course_type': r.course_type.name if r.course_type else '',
            'ability_level': r.max_ability_level or '',
            'language': r.language,
            'number_of_people': r.number_of_people,
            'status': r.status,
            'total_fee': r.total_fee,
            'is_preferred_coach': bool(r.is_preferred_coach),
            'bookings': [
                {
                    'id': b.id,
                    'date': str(b.date),
                    'start_time': str(b.start_time),
                    'end_time': str(b.end_time),
                    'is_scheduled': b.is_scheduled,
                }
                for b in r.bookings.all()
                if _booking_in_date_range(b, display_start, display_end)
            ],
            'mdt_add': r.mdt_add.strftime('%Y-%m-%d %H:%M') if r.mdt_add else '',
        })

    return Response({
        'code': 200,
        'msg': 'OK',
        'data': {
            'list': items,
            'total': len(items),
            'visibility_mode': 'full' if full_schedule_visible else 'recent_10_days',
        },
    })


@api_view(['GET'])
@permission_classes([IsTenantCoach])
def coach_my_calendar(request, client_code):
    """
    教練本人的月曆 booking 列表
    GET /api/admin/<client>/coach/my-calendar/?start=&end=
    """
    try:
        coach = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        return Response({'code': 403, 'msg': '您不是教練'}, status=403)

    full_schedule_visible = _coach_can_view_full_schedule(coach)
    visible_start, visible_end = _coach_visible_window()
    qs = Booking.objects.filter(
        reservation__preferred_coach=coach,
        reservation__status__in=SCHEDULED_RESERVATION_STATUSES,
        reservation__group__payments__status__in=COACH_VISIBLE_PAYMENT_STATUSES,
    ).select_related(
        'reservation',
        'reservation__resort',
        'reservation__course_type',
        'reservation__preferred_coach',
        'reservation__group__user',
    ).distinct().order_by('date', 'start_time')

    if not full_schedule_visible:
        qs = qs.filter(date__gte=visible_start, date__lte=visible_end)

    start = request.query_params.get('start')
    end = request.query_params.get('end')
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    query_start = _parse_date_query(start)
    query_end = _parse_date_query(end)
    if full_schedule_visible:
        equipment_start = query_start
        equipment_end = query_end
    else:
        equipment_start = max([d for d in [visible_start, query_start] if d])
        equipment_end = min([d for d in [visible_end, query_end] if d])

    items = []
    for b in qs:
        try:
            user = b.reservation.group.user
            user_name = user.username if user else (b.reservation.group.name or '')
        except Exception:
            user_name = ''
        items.append({
            'id': b.id,
            'reservation_id': b.reservation_id,
            'group_id': b.reservation.group_id if b.reservation else None,
            'date': str(b.date),
            'start_time': str(b.start_time),
            'end_time': str(b.end_time),
            'course_name': b.course_name,
            'course_type': b.reservation.course_type.name if b.reservation and b.reservation.course_type else '',
            'ability_level': b.reservation.max_ability_level if b.reservation else '',
            'language': b.reservation.language if b.reservation else '',
            'language_label': b.reservation.get_language_display() if b.reservation else '',
            'equipment': b.reservation.equipment if b.reservation else '',
            'equipment_label': b.reservation.get_equipment_display() if b.reservation and b.reservation.equipment else '',
            'equipment_assistance_time_label': b.reservation.get_equipment_assistance_time_display() if b.reservation else '',
            'is_preferred_coach': bool(b.reservation.is_preferred_coach) if b.reservation else False,
            'coach_name': b.reservation.preferred_coach.name if b.reservation and b.reservation.preferred_coach else '',
            'user_name': user_name,
            'resort': b.reservation.resort.display_name if b.reservation and b.reservation.resort else '',
            'number_of_people': b.reservation.number_of_people if b.reservation else 0,
            'status': b.reservation.status if b.reservation else 'unknown',
            'is_scheduled': b.is_scheduled,
            'event_type': 'course',
        })

    items.extend(_equipment_assistance_calendar_items(
        coach=coach,
        start_date=equipment_start,
        end_date=equipment_end,
        include_coach=False,
        scheduled_only=True,
        completed_orders_only=True,
        require_booking_scheduled=False,
    ))
    items = _sort_calendar_items(items)

    return Response({
        'code': 200,
        'msg': 'OK',
        'data': {
            'list': items,
            'total': len(items),
            'visibility_mode': 'full' if full_schedule_visible else 'recent_10_days',
        },
    })


# ==================== 教練本人請假 ====================

@api_view(['GET'])
@permission_classes([IsTenantCoach])
def coach_my_leaves(request, client_code):
    """教練本人的請假紀錄"""
    try:
        coach = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        return Response({'code': 403, 'msg': '您不是教練'}, status=403)

    qs = CoachLeaveRequest.objects.filter(coach=coach).order_by('-created_at')
    items = []
    for l in qs:
        items.append({
            'id': l.id,
            'start_date': str(l.start_date),
            'end_date': str(l.end_date),
            'leave_days': l.leave_days,
            'reason': l.reason,
            'status': l.status,
            'processing_result': l.processing_result or '',
            'reviewed_at': l.reviewed_at.strftime('%Y-%m-%d %H:%M') if l.reviewed_at else None,
            'created_at': l.created_at.strftime('%Y-%m-%d %H:%M'),
            'affected_count': l.affected_reservations.count(),
        })
    return Response({'code': 200, 'msg': 'OK', 'data': {'list': items, 'total': len(items)}})


@api_view(['POST'])
@permission_classes([IsTenantCoach])
def coach_apply_leave(request, client_code):
    """
    教練提交請假申請
    POST /api/admin/<client>/coach/apply-leave/
    Body: { start_date, end_date, reason }
    """
    try:
        coach = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        return Response({'code': 403, 'msg': '您不是教練'}, status=403)

    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    reason = (request.data.get('reason') or '').strip()

    if not start_date or not end_date or not reason:
        return Response({'code': 400, 'msg': '請填寫完整資料'}, status=400)

    # 日期驗證
    from datetime import datetime
    try:
        sd = datetime.strptime(start_date, '%Y-%m-%d').date()
        ed = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return Response({'code': 400, 'msg': '日期格式錯誤（YYYY-MM-DD）'}, status=400)

    today = timezone.now().date()
    if sd < today:
        return Response({'code': 400, 'msg': '不能申請過去的日期'}, status=400)
    if ed < sd:
        return Response({'code': 400, 'msg': '結束日期不能早於開始日期'}, status=400)

    # 檢查是否已有重疊的 pending/approved 請假
    overlap = CoachLeaveRequest.objects.filter(
        coach=coach, status__in=['pending', 'approved'],
        start_date__lte=ed, end_date__gte=sd,
    ).exists()
    if overlap:
        return Response({'code': 400, 'msg': '該日期區間已有請假申請'}, status=400)

    # 找這段期間有沒有指派給這個教練的課
    affected = Reservation.objects.filter(
        preferred_coach=coach,
        bookings__date__gte=sd,
        bookings__date__lte=ed,
    ).exclude(status__in=['deleted', 'cancelled']).distinct()

    leave = CoachLeaveRequest.objects.create(
        coach=coach,
        start_date=sd,
        end_date=ed,
        reason=reason,
        status='pending',
    )
    if affected.exists():
        leave.affected_reservations.set(affected)

    return Response({
        'code': 200, 'msg': '請假申請已送出',
        'data': {
            'id': leave.id,
            'affected_count': affected.count(),
        },
    })


# ==================== 訂單寄信 ====================

@api_view(['POST'])
@permission_classes([IsTenantManager])
def send_order_email(request, client_code, order_id):
    denied = _require_admin_permission(request, 'orders')
    if denied:
        return denied
    """
    寄信給訂單聯絡人
    POST /api/admin/<client>/orders/<id>/send-email/
    Body: { recipient_email, subject, message }
    """
    try:
        group = ReservationGroup.objects.get(pk=order_id, client=request.tenant)
    except ReservationGroup.DoesNotExist:
        return Response({'code': 404, 'msg': '訂單不存在'}, status=404)

    recipient = (request.data.get('recipient_email') or '').strip()
    subject = (request.data.get('subject') or '').strip()
    message = (request.data.get('message') or '').strip()

    if not all([recipient, subject, message]):
        return Response({'code': 400, 'msg': '請填寫收件人、主旨、內容'}, status=400)

    import re
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', recipient):
        return Response({'code': 400, 'msg': 'Email 格式錯誤'}, status=400)

    full_msg = f"""{message}

──────────────────────────
{request.tenant.name}
此郵件為系統自動發送，請勿直接回覆。
"""
    try:
        from booking.scheduler import send_gmail
        result = send_gmail(subject, full_msg, recipient)
        if result == 'ok':
            return Response({'code': 200, 'msg': '已寄出'})
        return Response({'code': 500, 'msg': f'寄送失敗：{result}'}, status=500)
    except Exception as e:
        return Response({'code': 500, 'msg': f'寄送錯誤：{e}'}, status=500)


# ==================== 後台登入 / 登出 / 當前用戶 ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request, client_code):
    """
    後台帳號密碼登入
    POST /api/admin/<client>/login/
    Body: { "username": "...", "password": "..." }
    """
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    if not username or not password:
        return Response({'code': 400, 'msg': '請輸入帳號與密碼'}, status=400)

    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({'code': 401, 'msg': '帳號或密碼錯誤'}, status=401)

    # 必須是 manager 或 superuser
    is_admin = user.is_superuser
    try:
        if hasattr(user, 'userprofile') and user.userprofile.is_manager:
            is_admin = True
    except Exception:
        pass

    if not is_admin:
        return Response({'code': 403, 'msg': '此帳號無管理員權限'}, status=403)

    login(request, user)
    return Response({
        'code': 200, 'msg': '登入成功',
        'data': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.get_full_name() or user.username,
        },
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_logout(request, client_code):
    """登出"""
    logout(request)
    return Response({'code': 200, 'msg': '已登出'})


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_me(request, client_code):
    if not request.user.is_authenticated:
        return Response({'code': 401, 'msg': '未登入'}, status=401)

    is_superuser = request.user.is_superuser
    is_manager = False
    is_coach = False

    try:
        profile = request.user.userprofile
        is_manager = bool(profile.is_manager)
        is_coach = bool(profile.is_coach)
    except Exception:
        pass

    if not (is_superuser or is_manager or is_coach):
        return Response({'code': 403, 'msg': '無管理員權限'}, status=403)

    return Response({
        'code': 200,
        'msg': 'OK',
        'data': {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'name': request.user.get_full_name() or request.user.username,
            'is_superuser': is_superuser,
            'is_manager': is_manager,
            'is_coach': is_coach,
            'permissions': get_user_admin_permissions(request.user),
            'permission_definitions': ADMIN_PERMISSION_DEFINITIONS,
        },
    })


# ==================== 付款設定（銀行資訊 / 訂單表單選項）====================

BOOKING_FORM_OPTIONS_LOCATION_KEY = 'booking.form.options'
DEFAULT_MESSENGER_OPTIONS = ['LINE', 'WhatsApp', 'WeChat']
DEFAULT_REFERRAL_SOURCE_OPTIONS = [
    '朋友介紹',
    '舊生推薦',
    'Instagram',
    'Facebook',
    'Google 搜尋',
    '小紅書',
    'Dcard / PTT',
    'YouTube',
    '講座 / 限時活動',
    '抽獎活動',
    '其他',
]


def _normalize_string_options(value, fallback):
    if not isinstance(value, list):
        return list(fallback)
    seen = set()
    options = []
    for item in value:
        text = str(item or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        options.append(text)
    return options or list(fallback)


def _get_booking_form_options(tenant):
    item = SiteContent.objects.filter(
        client=tenant,
        content_type='setting',
        location_key=BOOKING_FORM_OPTIONS_LOCATION_KEY,
    ).first()
    metadata = item.metadata if item and isinstance(item.metadata, dict) else {}
    return {
        'messenger_options': _normalize_string_options(
            metadata.get('messenger_options'),
            DEFAULT_MESSENGER_OPTIONS,
        ),
        'referral_source_options': _normalize_string_options(
            metadata.get('referral_source_options'),
            DEFAULT_REFERRAL_SOURCE_OPTIONS,
        ),
    }


def _save_booking_form_options(tenant, payload):
    current = _get_booking_form_options(tenant)
    messenger_options = _normalize_string_options(
        payload.get('messenger_options', current['messenger_options']),
        DEFAULT_MESSENGER_OPTIONS,
    )
    referral_source_options = _normalize_string_options(
        payload.get('referral_source_options', current['referral_source_options']),
        DEFAULT_REFERRAL_SOURCE_OPTIONS,
    )
    item = SiteContent.objects.filter(
        client=tenant,
        content_type='setting',
        location_key=BOOKING_FORM_OPTIONS_LOCATION_KEY,
    ).first()
    defaults = {
        'title': '訂單表單選項',
        'summary': '通訊軟體與訂單來源選項',
        'status': 'active',
        'metadata': {
            'messenger_options': messenger_options,
            'referral_source_options': referral_source_options,
        },
    }
    if item:
        for key, value in defaults.items():
            setattr(item, key, value)
        item.save()
    else:
        SiteContent.objects.create(
            client=tenant,
            content_type='setting',
            location_key=BOOKING_FORM_OPTIONS_LOCATION_KEY,
            **defaults,
        )
    return {
        'messenger_options': messenger_options,
        'referral_source_options': referral_source_options,
    }

@api_view(['GET', 'PUT'])
@permission_classes([IsTenantManager])
def payment_settings_view(request, client_code=None):
    denied = _require_admin_permission(request, 'payment_settings')
    if denied:
        return denied
    """
    GET  /api/admin/<client_code>/payment-settings/  讀取
    PUT  /api/admin/<client_code>/payment-settings/  更新
    """
    tenant = _resolve_tenant(request, type('V', (), {'kwargs': {'client_code': client_code}})())
    if not tenant:
        return Response({'code': 404, 'msg': '找不到客戶'}, status=404)

    if request.method == 'GET':
        form_options = _get_booking_form_options(tenant)
        return Response({
            'code': 200, 'msg': 'OK',
            'data': {
                'bank_name': tenant.bank_name,
                'bank_branch': tenant.bank_branch,
                'bank_account_number': tenant.bank_account_number,
                'bank_account_holder': tenant.bank_account_holder,
                **form_options,
            },
        })

    # PUT
    payload = request.data or {}
    for f in ('bank_name', 'bank_branch', 'bank_account_number', 'bank_account_holder'):
        if f in payload:
            setattr(tenant, f, (payload[f] or '').strip())
    tenant.save()
    form_options = _save_booking_form_options(tenant, payload)
    return Response({
        'code': 200, 'msg': '已更新',
        'data': {
            'bank_name': tenant.bank_name,
            'bank_branch': tenant.bank_branch,
            'bank_account_number': tenant.bank_account_number,
            'bank_account_holder': tenant.bank_account_holder,
            **form_options,
        },
    })
