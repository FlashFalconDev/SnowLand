"""
後台管理 API
所有後台用 ViewSet 都在這裡
URL 格式：/api/admin/<client_code>/<resource>/
"""
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin
from rest_framework.permissions import IsAuthenticated, AllowAny, SAFE_METHODS
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum, Count, Max, Q, Prefetch, OuterRef, Subquery
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta, datetime, date, time
from collections import defaultdict

from Client.models import SiteContent
from .payroll_security import PayrollCsrfMixin
from Coach.models import Coach, CoachLeaveRequest, CoachPayRule, PayrollStatement, StaffIncentiveRule
from Resorts.models import Resorts, Campus, PaymentAccount, OperatingPolicy
from Coursekit.models import CourseCategory, CourseType, CourseTemplate, CourseSession, CoursePricing, SeasonSetting, DiscountCode
from booking.models import (
    ReservationGroup, Reservation, Booking, MemberDetail, Payment, SharedCourseClass,
    CancellationRequest, CourseEvaluation, NotificationTemplate, NotificationDelivery,
    StaffBookingLink,
)
from booking.payment_access import PAYMENT_LINK_MAX_AGE, payment_url_for_group
from booking.marketing_source import display_marketing_source

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
    CampusManagerOrderSerializer,
    CustomerAdminSerializer,
    BookingScheduleAdminSerializer,
    CampusAdminSerializer,
    PaymentAccountAdminSerializer,
    OperatingPolicyAdminSerializer,
    CancellationRequestAdminSerializer,
    CancellationRequestSummarySerializer,
    CourseEvaluationAdminSerializer,
    CoachCourseEvaluationSerializer,
    NotificationTemplateAdminSerializer,
    NotificationDeliveryAdminSerializer,
    CoachPayRuleAdminSerializer,
    StaffIncentiveRuleAdminSerializer,
    PayrollStatementAdminSerializer,
    OrderRevisionAdminSerializer,
    StaffBookingLinkAdminSerializer,
    InsuranceRecordAdminSerializer,
    InsuranceRecordDetailAdminSerializer,
    InsuranceProcessingInputSerializer,
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


HEADQUARTERS_ROLES = {'hq_admin', 'marketing', 'web_editor', 'insurance', 'assistant'}


def _campus_scope_for_user(user, tenant):
    if user.is_superuser:
        return Campus.objects.filter(client=tenant, is_active=True), True
    try:
        profile = user.userprofile
    except Exception:
        return Campus.objects.none(), False
    if profile.is_manager and profile.manager_client_id != tenant.id:
        return Campus.objects.none(), False
    if profile.is_coach and not profile.is_manager:
        coach = Coach.objects.filter(user=user, client=tenant).first()
        return (coach.campuses.filter(client=tenant, is_active=True) if coach else Campus.objects.none()), False
    # 舊管理員資料尚未設定 role；維持原本可管理全公司的行為，避免升級後全部 403。
    if profile.role in HEADQUARTERS_ROLES or (not profile.role and profile.admin_permissions is None):
        return Campus.objects.filter(client=tenant, is_active=True), True
    return profile.campuses.filter(client=tenant, is_active=True), False


def _resolve_campus_scope(request, tenant):
    accessible, can_view_all = _campus_scope_for_user(request.user, tenant)
    selected = request.headers.get('X-Campus-ID') or request.query_params.get('campus_id')
    if selected in (None, '', 'all'):
        request.campus_ids = list(accessible.values_list('id', flat=True))
        request.selected_campus_id = None
        request.can_view_all_campuses = can_view_all
        return bool(request.campus_ids) or can_view_all
    try:
        selected_id = int(selected)
    except (TypeError, ValueError):
        return False
    if not accessible.filter(id=selected_id).exists():
        return False
    request.campus_ids = [selected_id]
    request.selected_campus_id = selected_id
    request.can_view_all_campuses = can_view_all
    return True

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
            return _resolve_campus_scope(request, tenant)

        # 一般 user 必須有 UserProfile.is_manager
        try:
            profile = request.user.userprofile
            if not profile.is_manager:
                return False
        except Exception:
            return False

        permission_key = getattr(view, 'permission_key', None)
        if permission_key and not user_has_admin_permission(request.user, permission_key):
            read_permissions = getattr(view, 'read_permission_keys', ())
            if request.method not in SAFE_METHODS or not any(
                user_has_admin_permission(request.user, key) for key in read_permissions
            ):
                return False
        return _resolve_campus_scope(request, tenant)


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


def _campus_ids(request):
    return getattr(request, 'campus_ids', [])


def _require_headquarters(request):
    if request.user.is_superuser:
        return
    try:
        if request.user.userprofile.role == 'hq_admin':
            return
    except Exception:
        pass
    raise PermissionDenied('只有總部管理員可以變更校區架構')


def _parse_date_query(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _query_date_bounds(request, start_key='start', end_key='end'):
    values = []
    for key in (start_key, end_key):
        raw = request.query_params.get(key)
        parsed = _parse_date_query(raw)
        if raw and parsed is None:
            raise ValidationError({key: '請使用有效日期（YYYY-MM-DD）'})
        values.append(parsed)
    start, end = values
    if start and end and end < start:
        raise ValidationError({end_key: '結束日期不得早於開始日期'})
    return start, end


def _format_calendar_time(value):
    if not value:
        return ''
    return value.strftime('%H:%M:%S') if hasattr(value, 'strftime') else str(value)


def _reservation_user_alias(reservation):
    try:
        user = reservation.group.user
        return (user.first_name or '學員') if user else (reservation.group.name or '學員')
    except Exception:
        return '學員'


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
        'order_number': reservation.group.order_number,
        'sn': (
            f'{reservation.group.created_at:%Y%m%d}-{reservation.group_id:04d}'
            if reservation.group.created_at else f'00000000-{reservation.group_id:04d}'
        ),
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
        'user_name': _reservation_user_alias(reservation),
        'resort': reservation.resort.display_name if reservation.resort else '',
        'campus_name': reservation.group.campus.name if reservation.group.campus else '',
        'campus_is_active': reservation.group.campus.is_active if reservation.group.campus else True,
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


def _with_current_schedule_payment(queryset, group_field):
    latest = Payment.objects.filter(reservation_group_id=OuterRef(group_field)).order_by('-created_at', '-pk')
    return queryset.alias(_schedule_payment_status=Subquery(latest.values('status')[:1])).filter(
        _schedule_payment_status__in=COACH_VISIBLE_PAYMENT_STATUSES,
    )


def _equipment_assistance_calendar_items(
    *,
    tenant=None,
    campus_ids=None,
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
        'group__campus',
    ).prefetch_related('bookings')

    if tenant:
        qs = qs.filter(group__client=tenant)
    if campus_ids is not None:
        qs = qs.filter(group__campus_id__in=campus_ids)
    if coach:
        qs = qs.filter(preferred_coach=coach)
    if completed_orders_only:
        qs = _with_current_schedule_payment(qs, 'group_id')
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


def _daily_coach_availability_summary(*, tenant, start_date, end_date, campus_ids=None):
    if not tenant or not start_date or not end_date:
        return []

    coaches = Coach.objects.filter(
        client=tenant,
        availability_status__in=['active', 'passive'],
    )
    if campus_ids is not None:
        coaches = coaches.filter(campuses__id__in=campus_ids).distinct()
    coaches = coaches.values_list('id', 'name')
    coach_names = {coach_id: name for coach_id, name in coaches}
    coach_ids = set(coach_names.keys())
    total_coaches = len(coach_ids)

    booked_by_date = defaultdict(set)
    if coach_ids:
        booking_rows = Booking.objects.filter(
            reservation__group__client=tenant,
            reservation__preferred_coach_id__in=coach_ids,
            reservation__status__in=SCHEDULED_RESERVATION_STATUSES,
            date__gte=start_date,
            date__lte=end_date,
        )
        booking_rows = _with_current_schedule_payment(booking_rows, 'reservation__group_id')
        if campus_ids is not None:
            booking_rows = booking_rows.filter(reservation__group__campus_id__in=campus_ids)
        booking_rows = booking_rows.values('date', 'reservation__preferred_coach_id').distinct()
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
        )
        equipment_reservations = _with_current_schedule_payment(equipment_reservations, 'group_id')
        if campus_ids is not None:
            equipment_reservations = equipment_reservations.filter(group__campus_id__in=campus_ids)
        equipment_reservations = equipment_reservations.select_related(
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
    return None, today + timedelta(days=10)


def _coach_can_view_full_schedule(coach):
    return coach.schedule_visibility == 'full'


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

    @action(detail=False, methods=['get'], url_path='photography-schema')
    def photography_schema(self, request, *args, **kwargs):
        denied = _require_admin_permission(request, 'cms')
        if denied is not None:
            return denied
        from Client.photography_pages import photography_schema
        try:
            schema = photography_schema(request.query_params.get('season', ''))
        except ValueError as exc:
            raise ValidationError({'season': str(exc)})
        return Response({'code': 200, 'data': schema})

    def get_permissions(self):
        self.permission_key = 'cms' if user_has_admin_permission(self.request.user, 'cms') else 'reviews'
        return super().get_permissions()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in SAFE_METHODS:
            from django.middleware.csrf import get_token
            get_token(request._request)
        else:
            from rest_framework.authentication import SessionAuthentication
            SessionAuthentication().enforce_csrf(request)

    def _review_content_groups(self):
        groups = [
            {'id': 'homepage', 'label': '首頁', 'description': '學生評價', 'locations': [
                {'key': 'homepage.reviews', 'label': '學生評價', 'hint': '首頁的評論卡片', 'type': 'review'}]},
            {'id': 'photography', 'label': '攝影作品', 'description': '公開攝影作品', 'locations': [
                {'key': 'photography.gallery', 'label': '攝影作品', 'hint': '攝影作品集圖片與連結', 'type': 'media'}]},
        ]
        structure = SiteContent.objects.filter(client=self.request.tenant, content_type='setting', location_key='cms.structure').first()
        metadata = structure.metadata if structure and isinstance(structure.metadata, dict) else {}
        configured = metadata.get('groups', [])
        for group in configured if isinstance(configured, list) else []:
            entries = group.get('locations', []) if isinstance(group, dict) else []
            locations = []
            for entry in entries if isinstance(entries, list) else []:
                if not isinstance(entry, dict):
                    continue
                key, kind = entry.get('key'), entry.get('type')
                if isinstance(key, str) and key and not key.startswith('cms.') and kind in ('review', 'media'):
                    locations.append({field: entry.get(field, '') for field in ('key', 'label', 'hint', 'type')})
            if locations:
                clean = {field: group.get(field, '') for field in ('id', 'label', 'description')}
                clean['locations'] = locations
                groups = [existing for existing in groups if existing['id'] != clean['id']]
                groups.append(clean)
        return groups

    def _review_locations(self):
        return {(entry['type'], entry['key']) for group in self._review_content_groups() for entry in group['locations']}

    @action(detail=False, methods=['get'], url_path='review-locations')
    def review_locations(self, request, *args, **kwargs):
        return Response({'code': 200, 'data': {'groups': self._review_content_groups()}})

    @action(detail=False, methods=['get'], url_path='review-coaches')
    def review_coaches(self, request, *args, **kwargs):
        rows=list(Coach.objects.filter(client=request.tenant).order_by('name','pk').values('id','name','website_enabled'))
        return Response({'code':200,'data':{'list':rows}})

    def _check_content_scope(self, serializer):
        if user_has_admin_permission(self.request.user, 'cms'):
            return
        pair = tuple(serializer.validated_data.get(field, getattr(serializer.instance, field, None))
                     for field in ('content_type', 'location_key'))
        if pair not in self._review_locations():
            raise ValidationError({'location_key': '此帳號僅可管理評價與攝影作品，不能修改其他官網內容'})

    def perform_create(self, serializer):
        self._check_content_scope(serializer)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._check_content_scope(serializer)
        super().perform_update(serializer)

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return SiteContent.objects.none()

        qs = SiteContent.objects.filter(client=tenant)
        if not user_has_admin_permission(self.request.user, 'cms'):
            allowed = Q(pk__in=[])
            for kind, location in self._review_locations():
                allowed |= Q(content_type=kind, location_key=location)
            qs = qs.filter(allowed)
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

    def _require_exclusive_campus(self, coach):
        if getattr(self.request, 'can_view_all_campuses', False):
            return
        allowed = set(_campus_ids(self.request))
        assigned = set(coach.campuses.values_list('id', flat=True))
        if not assigned or not assigned.issubset(allowed):
            raise PermissionDenied('這位教練也屬於其他校區，請由總部管理員修改')

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Coach.objects.none()
        qs = Coach.objects.filter(client=tenant)
        if _campus_ids(self.request) and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(campuses__id__in=_campus_ids(self.request)).distinct()
        return qs.order_by('-id')

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
        self._require_exclusive_campus(instance)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'code': 200, 'msg': '教練資料已更新', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._require_exclusive_campus(instance)
        if (Reservation.objects.filter(preferred_coach=instance).exists()
                or instance.payroll_statements.exists()
                or CoachLeaveRequest.objects.filter(coach=instance).exists()):
            raise ValidationError('教練已有課程、請假或薪資紀錄，請改設為「不可接課」保留歷史資料')
        self.perform_destroy(instance)
        return Response({'code': 200, 'msg': '教練已刪除'})


# ==================== Coach Leave Request ====================

class CoachLeaveAdminViewSet(PayrollCsrfMixin, UpdateModelMixin, ReadOnlyModelViewSet):
    serializer_class = CoachLeaveRequestAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'coaches'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CoachLeaveRequest.objects.none()
        qs = CoachLeaveRequest.objects.filter(coach__client=tenant).select_related(
            'coach', 'reviewed_by',
        ).prefetch_related('coach__campuses')
        if not (self.request.can_view_all_campuses and self.request.selected_campus_id is None):
            qs = qs.filter(coach__campuses__id__in=_campus_ids(self.request))
        return qs.distinct().order_by('-created_at', '-id')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request)

    def _can_create_special(self):
        profile = getattr(self.request.user, 'userprofile', None)
        return self.request.user.is_superuser or not (profile and profile.role == 'assistant')

    @action(detail=False, methods=['get'], url_path='special-options')
    def special_options(self, request, *args, **kwargs):
        can_create = self._can_create_special()
        coaches = []
        if can_create:
            for coach in Coach.objects.filter(client=request.tenant).prefetch_related('campuses').order_by('name', 'id'):
                candidate = CoachLeaveRequest(coach=coach, status='pending')
                if not self.get_serializer().get_review_block_reason(candidate):
                    coaches.append({'id': coach.pk, 'name': coach.name})
        return Response({'code': 200, 'data': {'can_create': can_create, 'coaches': coaches}})

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not self._can_create_special():
            raise PermissionDenied('行政小幫手僅能查看請假紀錄')
        if request.data.get('confirm_special_leave') is not True:
            return Response({'code': 400, 'msg': '請確認這是主管特別核准的休假，且會略過一般請假限制'}, status=400)
        data = {key: request.data.get(key) for key in ('coach', 'start_date', 'end_date', 'reason')}
        if not isinstance(data['reason'], str) or not data['reason'].strip() or len(data['reason']) > 1000:
            return Response({'code': 400, 'msg': '請填寫特批原因，最多1000字'}, status=400)
        data['reason'] = data['reason'].strip()
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        coach = Coach.objects.select_for_update().get(pk=serializer.validated_data['coach'].pk)
        if coach.client_id != request.tenant.pk:
            raise PermissionDenied('不能設定其他公司的教練休假')
        candidate = CoachLeaveRequest(coach=coach, status='pending')
        reason = self.get_serializer().get_review_block_reason(candidate)
        if reason:
            raise PermissionDenied(reason)
        start = serializer.validated_data['start_date']
        end = serializer.validated_data['end_date']
        if start < timezone.localdate() or end < start:
            return Response({'code': 400, 'msg': '請選擇今天以後的有效休假日期區間'}, status=400)
        if CoachLeaveRequest.objects.filter(coach=coach, status__in=['pending', 'approved'],
                start_date__lte=end, end_date__gte=start).exists():
            return Response({'code': 409, 'msg': '這段日期已有待審核或已批准的請假，請先查看原紀錄'}, status=409)
        leave = serializer.save(status='approved', reviewed_by=request.user,
                                reviewed_at=timezone.now(), processing_result='主管特別核准休假')
        leave.affected_reservations.set(Reservation.objects.filter(
            preferred_coach=coach, group__client=request.tenant,
            bookings__date__gte=start, bookings__date__lte=end,
        ).exclude(status__in=['deleted', 'cancelled']).distinct())
        return Response({'code': 201, 'msg': '特別核准休假已建立；受影響課程需另外處理',
                         'data': self.get_serializer(leave).data}, status=201)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        visible = self.get_object()
        Coach.objects.select_for_update().get(pk=visible.coach_id)
        instance = CoachLeaveRequest.objects.select_for_update().get(pk=visible.pk)
        # Recheck the current scope after acquiring locks, not a cached row.
        if not self.get_queryset().filter(pk=instance.pk).exists():
            raise NotFound('此請假不在目前可見校區')
        if instance.status != 'pending':
            return Response({'code': 409, 'msg': '此申請已處理，請重新載入，不能重複審核'}, status=409)
        reason = self.get_serializer(instance).data['review_block_reason']
        if reason:
            raise PermissionDenied(reason)
        new_status = request.data.get('status')
        note = request.data.get('processing_result', '')
        if not isinstance(note, str) or len(note) > 1000:
            return Response({'code': 400, 'msg': '處理備註須為文字，最多1000字'}, status=400)
        note = note.strip()
        if new_status == 'rejected' and not note:
            return Response({'code': 400, 'msg': '請填寫拒絕原因，方便教練了解結果'}, status=400)
        if new_status in ('approved', 'rejected'):
            instance.status = new_status
            instance.processing_result = note
            instance.reviewed_by = request.user
            instance.reviewed_at = timezone.now()
            instance.save()
            serializer = self.get_serializer(instance)
            return Response({'code': 200, 'msg': '已更新請假狀態', 'data': serializer.data})
        return Response({'code': 400, 'msg': '無效的狀態'}, status=status.HTTP_400_BAD_REQUEST)


# ==================== Resorts ====================

class CampusAdminViewSet(ModelViewSet):
    serializer_class = CampusAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'campuses'
    read_permission_keys = ('staff',)

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Campus.objects.none()
        qs = Campus.objects.filter(client=tenant).prefetch_related('resorts', 'staff_profiles', 'coaches')
        if not getattr(self.request, 'can_view_all_campuses', False):
            qs = qs.filter(id__in=_campus_ids(self.request))
        return qs.order_by('display_order', 'id')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()), self.get_serializer_class(), request, self.get_serializer_context())

    def perform_create(self, serializer):
        _require_headquarters(self.request)
        serializer.save()

    def perform_update(self, serializer):
        _require_headquarters(self.request)
        serializer.save()

    def perform_destroy(self, instance):
        _require_headquarters(self.request)
        in_use = any(relation.exists() for relation in (
            instance.reservation_groups,
            instance.staff_profiles,
            instance.coaches,
            instance.payment_accounts,
            instance.payroll_statements,
            instance.staff_incentive_rules,
            instance.notification_templates,
            instance.shared_course_classes,
            instance.staff_booking_links,
        ))
        if in_use:
            raise PermissionDenied('這個校區已有訂單、人員或營運設定，請改為「停用」，不能刪除')
        instance.delete()


class PaymentAccountAdminViewSet(ModelViewSet):
    serializer_class = PaymentAccountAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'payment_settings'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return PaymentAccount.objects.none()
        qs = PaymentAccount.objects.filter(client=tenant).prefetch_related('campuses', 'resorts')
        if not getattr(self.request, 'can_view_all_campuses', False):
            qs = qs.filter(campuses__id__in=_campus_ids(self.request)).distinct()
        return qs.order_by('display_order', 'id')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()), self.get_serializer_class(), request, self.get_serializer_context())

    def perform_destroy(self, instance):
        if not getattr(self.request, 'can_view_all_campuses', False):
            allowed_ids = set(_campus_ids(self.request))
            account_ids = set(instance.campuses.values_list('id', flat=True))
            if not account_ids or not account_ids.issubset(allowed_ids):
                raise PermissionDenied('此帳戶也適用其他校區，請由總部管理員刪除')
        instance.delete()


class OperatingPolicyAdminViewSet(ModelViewSet):
    serializer_class = OperatingPolicyAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'campuses'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return OperatingPolicy.objects.none()
        qs = OperatingPolicy.objects.filter(client=tenant).select_related('campus')
        if not getattr(self.request, 'can_view_all_campuses', False):
            qs = qs.filter(Q(campus_id__in=_campus_ids(self.request)) | Q(campus__isnull=True))
        return qs.order_by('campus_id', 'id')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()), self.get_serializer_class(), request, self.get_serializer_context())

    def perform_destroy(self, instance):
        if instance.campus_id is None:
            raise PermissionDenied('全公司預設不可刪除')
        if not getattr(self.request, 'can_view_all_campuses', False) and instance.campus_id not in _campus_ids(self.request):
            raise PermissionDenied('只能重設自己管理的校區規則')
        instance.delete()


class ResortAdminViewSet(ModelViewSet):
    serializer_class = ResortAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'resorts'
    read_permission_keys = ('coaches',)

    @action(detail=False, methods=['get'], url_path='course-template-options')
    def course_template_options(self, request, client_code=None):
        visible_resorts = Resorts.objects.filter(client=request.tenant)
        if _campus_ids(request) and (
            not request.can_view_all_campuses or request.selected_campus_id is not None
        ):
            visible_resorts = visible_resorts.filter(campuses__id__in=_campus_ids(request))
        visible_resort_ids = set(visible_resorts.values_list('id', flat=True))
        templates = CourseTemplate.objects.filter(
            course_type__category__client=request.tenant,
            resorts__id__in=visible_resort_ids,
        ).distinct().select_related('course_type').prefetch_related('resorts').order_by('id')
        options = [{
            'id': template.id,
            'name': template.name,
            'course_type_name': template.course_type.name,
            'duration_hours': template.duration_hours,
            'resorts': [resort.id for resort in template.resorts.all() if resort.id in visible_resort_ids],
        } for template in templates]
        return Response({'code': 200, 'msg': 'OK', 'data': {'list': options, 'total': len(options)}})

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Resorts.objects.none()
        qs = Resorts.objects.filter(client=tenant)
        if _campus_ids(self.request) and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(campuses__id__in=_campus_ids(self.request)).distinct()
        return qs.prefetch_related(
            'campuses',
            'equipment_pricing_tiers',
            'equipment_rental_items',
            'equipment_assistance_time_slots',
            'equipment_assistance_time_slots__course_templates',
        ).order_by('id')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        if getattr(self.request, 'can_view_all_campuses', False):
            serializer.save()
            return
        campus_ids = _campus_ids(self.request)
        if len(campus_ids) != 1:
            raise ValidationError('請先在右上角選擇一個校區，再新增雪場')
        with transaction.atomic():
            resort = serializer.save()
            Campus.objects.get(id=campus_ids[0], client=self.request.tenant).resorts.add(resort)

    def _require_unshared_resort(self, resort):
        if not getattr(self.request, 'can_view_all_campuses', False) and resort.campuses.filter(is_active=True).count() != 1:
            raise PermissionDenied('共用雪場只能由總部管理員修改；請聯絡總部')

    def perform_update(self, serializer):
        self._require_unshared_resort(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._require_unshared_resort(instance)
        if (Reservation.objects.filter(resort=instance).exists()
                or instance.shared_course_classes.exists()
                or instance.courses.exists()):
            raise ValidationError('此雪場已有訂單或課程紀錄，無法刪除；請保留雪場以維持歷史資料')
        instance.delete()

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

def _pricing_resorts_for_request(request, tenant):
    resorts = Resorts.objects.filter(client=tenant)
    if getattr(request, 'can_view_all_campuses', False):
        return resorts
    shared_ids = resorts.annotate(campus_count=Count(
        'campuses', filter=Q(campuses__is_active=True), distinct=True,
    )).filter(
        campus_count__gt=1,
    ).values('id')
    return resorts.filter(campuses__id__in=_campus_ids(request)).exclude(id__in=shared_ids).distinct()


def _course_template_resorts_for_request(request, tenant):
    resorts = Resorts.objects.filter(client=tenant)
    if getattr(request, 'can_view_all_campuses', False) and not getattr(request, 'selected_campus_id', None):
        return resorts
    shared_ids = resorts.annotate(campus_count=Count(
        'campuses', filter=Q(campuses__is_active=True), distinct=True,
    )).filter(
        campus_count__gt=1,
    ).values('id')
    return resorts.filter(campuses__id__in=_campus_ids(request)).exclude(id__in=shared_ids).distinct()


def _course_templates_for_request(request, tenant):
    templates = CourseTemplate.objects.filter(course_type__category__client=tenant)
    if getattr(request, 'can_view_all_campuses', False) and not getattr(request, 'selected_campus_id', None):
        return templates
    allowed = _course_template_resorts_for_request(request, tenant)
    return templates.filter(resorts__in=allowed).exclude(
        resorts__in=Resorts.objects.filter(client=tenant).exclude(id__in=allowed.values('id'))
    ).distinct()


def _visible_course_templates_for_request(request, tenant):
    templates = CourseTemplate.objects.filter(course_type__category__client=tenant)
    if getattr(request, 'can_view_all_campuses', False) and not getattr(request, 'selected_campus_id', None):
        return templates
    return templates.filter(resorts__campuses__id__in=_campus_ids(request)).distinct()


def _visible_course_resorts_for_request(request, tenant):
    resorts = Resorts.objects.filter(client=tenant)
    if getattr(request, 'can_view_all_campuses', False) and not getattr(request, 'selected_campus_id', None):
        return resorts
    return resorts.filter(campuses__id__in=_campus_ids(request)).distinct()


def _course_types_for_request(request, tenant):
    resorts = _visible_course_resorts_for_request(request, tenant)
    templates = _visible_course_templates_for_request(request, tenant).prefetch_related(
        'resorts__campuses', 'allowed_coaches__campuses', 'sessions',
    )
    return CourseType.objects.filter(category__client=tenant).prefetch_related(
        Prefetch('available_resorts', queryset=resorts),
        Prefetch('templates', queryset=templates),
    ).order_by('display_order', 'id')


class HeadquartersCourseStructureWriteMixin:
    def create(self, request, *args, **kwargs):
        _require_headquarters(request)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require_headquarters(request)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        _require_headquarters(request)
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if isinstance(instance, CourseCategory):
            course_types = CourseType.objects.filter(category=instance)
        else:
            course_types = CourseType.objects.filter(pk=instance.pk)
        if Reservation.objects.filter(
            Q(course_type__in=course_types) | Q(course_template__course_type__in=course_types)
        ).exists() or SharedCourseClass.objects.filter(template__course_type__in=course_types).exists():
            raise ValidationError({'msg': '已有訂單或合班紀錄使用此課程，不能刪除；請保留原設定以維持歷史資料'})
        instance.delete()

class CourseCategoryAdminViewSet(HeadquartersCourseStructureWriteMixin, ModelViewSet):
    serializer_class = CourseCategoryAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'course_types'
    read_permission_keys = ('coaches',)

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CourseCategory.objects.none()
        return CourseCategory.objects.filter(client=tenant).prefetch_related(
            Prefetch('available_resorts', queryset=_visible_course_resorts_for_request(self.request, tenant)),
            Prefetch('types', queryset=_course_types_for_request(self.request, tenant)),
        ).order_by('display_order', 'id')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request,
                         self.get_serializer_context())


class CourseTypeAdminViewSet(HeadquartersCourseStructureWriteMixin, ModelViewSet):
    serializer_class = CourseTypeAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'course_types'
    read_permission_keys = ('coaches',)

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CourseType.objects.none()
        return _course_types_for_request(self.request, tenant)

    def list(self, request, *args, **kwargs):
        return wrap_list(self.filter_queryset(self.get_queryset()),
                         self.get_serializer_class(), request)


class CourseTemplateAdminViewSet(ModelViewSet):
    serializer_class = CourseTemplateAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'course_types'

    @action(detail=False, methods=['get'], url_path='editor-options')
    def editor_options(self, request, client_code=None):
        tenant = request.tenant
        scoped = not request.can_view_all_campuses or request.selected_campus_id is not None
        allowed = set(_campus_ids(request)) if scoped else None
        resorts = _visible_course_resorts_for_request(request, tenant).prefetch_related('campuses')
        coaches = Coach.objects.filter(client=tenant).prefetch_related('campuses')
        if scoped:
            coaches = coaches.filter(campuses__id__in=allowed).distinct()

        def option(instance, campus_ids):
            selectable = allowed is None or (bool(campus_ids) and set(campus_ids).issubset(allowed))
            return {'id': instance.id, 'name': instance.name, 'can_select': selectable}

        resort_options = []
        for resort in resorts:
            campus_ids = [campus.id for campus in resort.campuses.all() if campus.is_active]
            row = option(resort, campus_ids)
            row['display_name'] = resort.display_name
            row['can_select'] = row['can_select'] and (allowed is None or len(campus_ids) == 1)
            resort_options.append(row)
        coach_options = [
            option(coach, [campus.id for campus in coach.campuses.all()]) for coach in coaches
        ]
        return Response({'code': 200, 'msg': 'OK', 'data': {
            'resorts': resort_options, 'coaches': coach_options,
        }})

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CourseTemplate.objects.none()
        qs = _visible_course_templates_for_request(self.request, tenant)
        return qs.prefetch_related(
            'resorts__campuses',
            'allowed_coaches__campuses',
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

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not _course_templates_for_request(request, request.tenant).filter(pk=instance.pk).exists():
            raise PermissionDenied('共用雪場的課程模板請由總部在全部校區範圍修改')
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if not _course_templates_for_request(self.request, self.request.tenant).filter(pk=instance.pk).exists():
            raise PermissionDenied('共用雪場的課程模板請由總部在全部校區範圍刪除')
        if instance.reservations.exists() or instance.shared_course_classes.exists():
            raise ValidationError({'msg': '已有訂單或合班紀錄使用此模板，不能刪除；請保留原設定以維持歷史資料'})
        instance.delete()


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
        return CourseSession.objects.filter(template__in=_visible_course_templates_for_request(
            self.request, tenant,
        )).order_by('id')

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not _course_templates_for_request(request, request.tenant).filter(pk=instance.template_id).exists():
            raise PermissionDenied('共用雪場的課程時段請由總部在全部校區範圍修改')
        return super().update(request, *args, **kwargs)

    def _validate_template_scope(self, serializer):
        template = serializer.validated_data.get('template', getattr(serializer.instance, 'template', None))
        if not template or not _course_templates_for_request(self.request, self.request.tenant).filter(pk=template.pk).exists():
            raise PermissionDenied('只能設定目前校區可管理的課程時段')

    def perform_create(self, serializer):
        self._validate_template_scope(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validate_template_scope(serializer)
        serializer.save()

    def perform_destroy(self, instance):
        if not _course_templates_for_request(self.request, self.request.tenant).filter(pk=instance.template_id).exists():
            raise PermissionDenied('共用雪場的課程時段請由總部在全部校區範圍刪除')
        instance.delete()

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

    @action(detail=False, methods=['get'], url_path='catalog')
    def catalog(self, request, client_code=None):
        visible_resorts = list(_pricing_resorts_for_request(request, request.tenant).order_by('id').values('id', 'display_name'))
        visible_resort_ids = [resort['id'] for resort in visible_resorts]
        visible_ids = set(visible_resort_ids)
        can_view_all = request.can_view_all_campuses
        categories = []
        for category in CourseCategory.objects.filter(client=request.tenant).prefetch_related(
            'types__templates__resorts',
        ).order_by('display_order', 'id'):
            types = []
            for course_type in category.types.all():
                templates = []
                for template in course_type.templates.all():
                    resort_ids = [resort.id for resort in template.resorts.all() if resort.id in visible_ids]
                    if not can_view_all and not resort_ids:
                        continue
                    templates.append({
                        'id': template.id,
                        'name': template.name,
                        'duration_hours': template.duration_hours,
                        'max_capacity': template.max_capacity,
                        'billing_mode': template.billing_mode,
                        'resorts': resort_ids,
                        'booking_open_date': template.booking_open_date,
                        'booking_close_date': template.booking_close_date,
                        'course_start_date': template.course_start_date,
                        'course_end_date': template.course_end_date,
                    })
                if templates or can_view_all:
                    types.append({'id': course_type.id, 'name': course_type.name, 'templates': templates})
            if types or can_view_all:
                categories.append({'id': category.id, 'name': category.name, 'types': types})
        return Response({'code': 200, 'msg': 'OK', 'data': {
            'list': categories, 'total': len(categories),
            'resort_ids': visible_resort_ids, 'resorts': visible_resorts,
        }})

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return CoursePricing.objects.none()
        # 只回傳「templates 至少有一個屬於本租戶」的定價規則
        qs = CoursePricing.objects.filter(
            templates__course_type__category__client=tenant, resort__client=tenant,
        )
        if not getattr(self.request, 'can_view_all_campuses', False):
            qs = qs.filter(resort__in=_pricing_resorts_for_request(self.request, tenant))
        return qs.prefetch_related('people_tiers').distinct().order_by('resort__display_name', 'id')

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
        _require_headquarters(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'code': 200, 'msg': '季節區間已建立', 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        _require_headquarters(request)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'code': 200, 'msg': '季節區間已更新', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        _require_headquarters(request)
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'code': 200, 'msg': '季節區間已刪除'})


# ==================== Orders ====================

class OrderAdminViewSet(ModelViewSet):
    permission_key = 'orders'
    """訂單管理：列表 / 詳情 / 編輯（指派教練、改付款、觸發排課）"""
    serializer_class = OrderAdminSerializer
    permission_classes = [IsTenantManager]

    @action(detail=True,methods=['post'],url_path='amendment-quote')
    def amendment_quote(self,request,*args,**kwargs):
        from rest_framework.authentication import SessionAuthentication
        from .order_amendments import AmendmentQuoteInput, quote_order_amendment
        SessionAuthentication().enforce_csrf(request)
        group=self.get_object()
        serializer=AmendmentQuoteInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        result=quote_order_amendment(group,serializer.validated_data,request.user)
        return Response({'code':200,'msg':'價格預覽完成，尚未修改訂單','data':result})

    @action(detail=True,methods=['get','post'],url_path='amendment-balances')
    def amendment_balances(self,request,*args,**kwargs):
        from booking.amendment_balances import BalanceActionInput, balance_data, group_balances, process_balance
        from rest_framework.authentication import SessionAuthentication
        group=self.get_object()
        if request.method=='GET':return Response({'code':200,'data':{'items':group_balances(group,staff=True)}})
        SessionAuthentication().enforce_csrf(request)
        serializer=BalanceActionInput(data=request.data);serializer.is_valid(raise_exception=True)
        row,duplicate,event=process_balance(group,request.user,serializer.validated_data,staff=True,scope=self.get_queryset())
        from booking.amendment_notifications import deliver_amendment_notice
        deliver_amendment_notice(row,event)
        return Response({'code':200,'data':balance_data(row,staff=True),'duplicate':duplicate,'msg':'差額核對已留底；系統沒有執行轉帳。'})

    @action(detail=True,methods=['get'],url_path='amendment-options')
    def amendment_options(self,request,*args,**kwargs):
        from .order_amendments import amendment_editor_options
        return Response({'code':200,'data':amendment_editor_options(self.get_object())})

    @action(detail=True,methods=['post'],url_path='amendment-confirm')
    def amendment_confirm(self,request,*args,**kwargs):
        from rest_framework.authentication import SessionAuthentication
        from .order_amendment_commit import AmendmentConfirmInput, amendment_summary, confirm_order_amendment
        SessionAuthentication().enforce_csrf(request)
        serializer=AmendmentConfirmInput(data=request.data);serializer.is_valid(raise_exception=True)
        row,duplicate=confirm_order_amendment(request,kwargs['pk'],serializer.validated_data,self.get_queryset())
        from booking.amendment_notifications import deliver_amendment_notice
        deliver_amendment_notice(row)
        return Response({'code':200,'msg':'訂單修改已保存；差額另行處理，尚未收款或退款','data':amendment_summary(row,duplicate)},status=200 if duplicate else 201)

    def _is_campus_manager(self):
        profile = getattr(self.request.user, 'userprofile', None)
        return bool(profile and profile.role == 'campus_manager')

    def _is_campus_order_viewer(self):
        profile = getattr(self.request.user, 'userprofile', None)
        return bool(profile and profile.role in ('campus_manager', 'campus_principal'))

    def get_serializer_class(self):
        return CampusManagerOrderSerializer if self._is_campus_order_viewer() else OrderAdminSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self._is_campus_order_viewer() and (
            request.method not in SAFE_METHODS or self.action not in ('list', 'retrieve')
        ):
            raise PermissionDenied('校區人員只能查看所屬校區訂單摘要')

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ReservationGroup.objects.none()
        qs = ReservationGroup.objects.filter(client=tenant)
        # Headquarters' "all campuses" order history includes disabled campuses.
        # New orders and campus staff access still use active-campus scope.
        all_headquarters_history = (
            getattr(self.request, 'can_view_all_campuses', False)
            and getattr(self.request, 'selected_campus_id', None) is None
        )
        if _campus_ids(self.request) and not all_headquarters_history:
            qs = qs.filter(campus_id__in=_campus_ids(self.request))
        if self._is_campus_manager():
            today = timezone.localdate()
            qs = qs.filter(reservations__bookings__date__range=(today, today + timedelta(days=10))).distinct()
        qs = qs.order_by('-created_at').select_related('user', 'campus').prefetch_related(
            Prefetch(
                'reservations',
                queryset=Reservation.objects.select_related(
                    'resort',
                    'course_type',
                    'course_template',
                    'preferred_coach',
                    'shared_course_class',
                    'equipment_assistance_time_slot',
                ).prefetch_related('bookings', 'members', 'rejected_coaches'),
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
            if self._is_campus_order_viewer():
                search_q = (
                    Q(order_number__icontains=search)
                    | Q(user__first_name__icontains=search)
                    | Q(user__isnull=True, name__icontains=search)
                )
                tail_digits = re.fullmatch(r'(?:\d{8}-|SL-\d{8}-)?(\d+)', search)
            else:
                search_q = (
                    Q(user__username__icontains=search)
                    | Q(user__first_name__icontains=search)
                    | Q(user__last_name__icontains=search)
                    | Q(user__email__icontains=search)
                    | Q(name__icontains=search)
                )
                tail_digits = re.search(r'(\d+)\s*$', search)
            if tail_digits:
                try:
                    search_q |= Q(id=int(tail_digits.group(1)))
                except ValueError:
                    pass
            qs = qs.filter(search_q)

        status_filter = (params.get('status') or '').strip()
        if status_filter and not self._is_campus_order_viewer():
            qs = qs.filter(reservations__status=status_filter).distinct()

        payment_filter = (params.get('payment_status') or '').strip()
        if payment_filter and not self._is_campus_order_viewer():
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
        from django.middleware.csrf import get_token
        get_token(request._request)  # Issue the same-origin token used by QR uploads/removal.
        serializer = self.get_serializer(
            instance,
            context={**self.get_serializer_context(), 'include_available_coaches': True},
        )
        return Response({'code': 200, 'msg': 'OK', 'data': serializer.data})

    @action(detail=True, methods=['get'], url_path='payment-link')
    def payment_link(self, request, *args, **kwargs):
        """Let headquarters reissue a guest's expiring payment link."""
        _require_headquarters(request)
        group = self.get_object()
        if group.user_id:
            return Response({'code': 400, 'msg': '會員訂單請由本人登入會員專區付款'}, status=400)
        payment = group.payments.order_by('-created_at').first()
        if not payment or payment.status not in ('unpaid', 'pending'):
            return Response({'code': 400, 'msg': '此訂單目前不需要付款連結'}, status=400)
        if not group.reservations.exclude(status__in=('cancelled', 'deleted')).exists():
            return Response({'code': 400, 'msg': '此訂單已沒有可付款的課程'}, status=400)
        from booking.api_views import get_group_payment_hold
        hold_message, _ = get_group_payment_hold(group)
        if hold_message:
            return Response({'code': 400, 'msg': hold_message}, status=400)
        return Response({'code': 200, 'data': {
            'path': payment_url_for_group(f'/{request.tenant.internal_code}/payment', group),
            'valid_days': PAYMENT_LINK_MAX_AGE // (24 * 60 * 60),
        }})

    @action(detail=True, methods=['post'], url_path='complete-course')
    def complete_course(self, request, *args, **kwargs):
        group = self.get_object()
        with transaction.atomic():
            reservation = group.reservations.select_for_update().filter(pk=request.data.get('reservation_id')).first()
            if reservation is None:
                return Response({'code': 404, 'msg': '此訂單沒有這門課程'}, status=404)
            if reservation.status == 'completed':
                return Response({'code': 200, 'msg': '此課程已確認完成'})
            if reservation.status not in ('auto_assigned', 'manually_assigned', 'form_filled'):
                return Response({'code': 400, 'msg': '請先完成排課與教練確認'}, status=400)
            if not group.payments.filter(status='paid').exists():
                return Response({'code': 400, 'msg': '付款尚未確認，不能標記完課'}, status=400)
            bookings = list(reservation.bookings.all())
            if not reservation.preferred_coach_id or not bookings or any(not booking.is_scheduled for booking in bookings):
                return Response({'code': 400, 'msg': '請先排定教練及所有課程時段'}, status=400)
            now = timezone.localtime()
            if any(booking.date > now.date() or (booking.date == now.date() and booking.end_time > now.time()) for booking in bookings):
                return Response({'code': 400, 'msg': '還有課程尚未結束，不能標記完課'}, status=400)

            reservation.status = 'completed'
            reservation.save(update_fields=['status'])
            for booking in bookings:
                for member in reservation.members.all():
                    CourseEvaluation.objects.get_or_create(
                        booking=booking, member=member,
                        defaults={'coach': reservation.preferred_coach},
                    )
            from booking.operations import record_order_revision
            record_order_revision(group, user=request.user, reason='後台確認課程完成')
        return Response({'code': 200, 'msg': '課程已完成，評量與薪資時數已可處理'})

    @action(detail=True, methods=['get'], url_path='refund-preview')
    def refund_preview(self, request, *args, **kwargs):
        from booking.operations import calculate_refund
        return Response({'code': 200, 'msg': 'OK', 'data': calculate_refund(self.get_object())})

    @action(detail=True, methods=['post'], url_path='cancel')
    @transaction.atomic
    def cancel_order(self, request, *args, **kwargs):
        from booking.operations import request_cancellation
        from rest_framework.authentication import SessionAuthentication
        SessionAuthentication().enforce_csrf(request)
        group = self.get_object()
        group = get_object_or_404(ReservationGroup.objects.select_for_update(), pk=group.pk)
        if not self.get_queryset().filter(pk=group.pk).exists():
            raise NotFound('找不到這張訂單')
        reason = request.data.get('reason')
        if not isinstance(reason, str) or reason not in dict(CancellationRequest.REASON_CHOICES):
            return Response({'code': 400, 'msg': '請選擇取消原因'}, status=400)
        try:
            cancellation = request_cancellation(
                group,
                reason=reason,
                reason_note=request.data.get('reason_note', ''),
                bank=request.data.get('refund_bank'),
                user=request.user,
                selected_rule_days_before=request.data.get('selected_rule_days_before'),
                manual_refund_amount=request.data.get('manual_refund_amount'),
            )
        except ValueError as exc:
            return Response({'code': 400, 'msg': str(exc)}, status=400)
        return Response({'code': 200, 'msg': '取消申請已建立', 'data': CancellationRequestAdminSerializer(cancellation).data})

    @action(detail=True, methods=['get'], url_path='revisions')
    def revision_history(self, request, *args, **kwargs):
        revisions = self.get_object().revisions.select_related('created_by').all()
        return wrap_list(revisions, OrderRevisionAdminSerializer, request)

    @action(detail=True, methods=['post'], url_path='class-group-link')
    @transaction.atomic
    def class_group_link(self, request, *args, **kwargs):
        from booking.operations import validate_class_group_url, schedule_group_notifications
        group = self.get_object()
        if 'line_group_url' not in request.data:
            return Response({'code': 400, 'msg': '缺少群組連結欄位'}, status=400)
        try:
            value = validate_class_group_url(request.data['line_group_url'])
        except ValueError as exc:
            return Response({'code': 400, 'msg': str(exc)}, status=400)
        group.line_group_url = value
        group.save(update_fields=['line_group_url'])
        if not value and not group.line_group_qr:
            NotificationDelivery.objects.filter(group=group, template__event='line_group', status='scheduled').update(status='cancelled')
        if (value or group.line_group_qr) and group.payments.filter(status='paid').exists():
            schedule_group_notifications(group, 'line_group')
        return Response({'code': 200, 'msg': '上課群組連結已儲存' if value else '上課群組連結已移除'})

    @action(detail=True, methods=['post', 'delete'], url_path='class-group-qr')
    def class_group_qr(self, request, *args, **kwargs):
        from rest_framework.authentication import SessionAuthentication
        SessionAuthentication().enforce_csrf(request)
        from booking.class_group_qr import replace_group_qr, group_qr_url
        group = self.get_object()
        upload = request.FILES.get('file') if request.method == 'POST' else None
        if request.method == 'POST' and not upload:
            return Response({'code': 400, 'msg': '請選擇群組 QR 碼圖片'}, status=400)
        try:
            saved = replace_group_qr(group, upload)
        except ValueError as exc:
            return Response({'code': 400, 'msg': str(exc)}, status=400)
        return Response({'code': 200, 'msg': '群組 QR 碼已更新' if upload else '群組 QR 碼已移除',
                         'data': {'line_group_qr_url': group_qr_url(saved)}})

    @transaction.atomic
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
        instance = get_object_or_404(self.get_queryset().select_for_update(),pk=instance.pk)
        data = request.data
        action = data.get('action', 'save')
        payment_status = data.get('payment_status')
        reservation_updates = data.get('reservation_updates', []) or []
        booking_updates = data.get('booking_updates', []) or []

        if action not in ('save', 'schedule'):
            return Response({'code': 400, 'msg': '不支援的訂單操作'}, status=400)
        if payment_status and payment_status not in dict(Payment.STATUS_CHOICES):
            return Response({'code': 400, 'msg': '無效的付款狀態'}, status=400)
        if payment_status and instance.reservations.filter(shared_course_class__status='collecting').exists():
            return Response({'code': 400, 'msg': '團體班仍在湊班中，成班後才能修改付款狀態'}, status=400)
        if not isinstance(reservation_updates, list) or not isinstance(booking_updates, list):
            return Response({'code': 400, 'msg': '訂單變更格式錯誤'}, status=400)

        # 1. 先驗證課程變更，避免不合法時段或教練讓付款狀態先被儲存
        booking_changes = []
        for upd in booking_updates:
            if not isinstance(upd, dict):
                return Response({'code': 400, 'msg': '課程變更格式錯誤'}, status=400)
            booking_id = upd.get('booking_id')
            if not booking_id:
                return Response({'code': 400, 'msg': '缺少課程編號'}, status=400)
            try:
                booking = Booking.objects.select_related('reservation').get(
                    pk=booking_id,
                    reservation__group=instance,
                )
            except Booking.DoesNotExist:
                return Response({'code': 400, 'msg': '找不到這張訂單的課程'}, status=400)

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
                if reservation.shared_course_class_id:
                    return Response({
                        'code': 400,
                        'msg': '跨訂單團體班需整班調整，暫不可在單一訂單修改課程時段',
                    }, status=400)
                if reservation.status == 'completed':
                    return Response({'code': 400, 'msg': '課程已完課，不能直接變更時段；請先核對評量與薪資紀錄'}, status=400)
                if new_date != booking.date or (datetime.combine(new_date,new_end_time)-datetime.combine(new_date,new_start_time)) != (datetime.combine(booking.date,booking.end_time)-datetime.combine(booking.date,booking.start_time)):
                    return Response({'code':400,'msg':'變更日期或課程時長須使用「修改課程／人數與差額」，先核對後端價格再確認；原訂單未變更'},status=400)
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

        # 2. 收集教練變更
        coach_changes = []
        for upd in reservation_updates:
            if not isinstance(upd, dict):
                return Response({'code': 400, 'msg': '教練變更格式錯誤'}, status=400)
            r_id = upd.get('reservation_id')
            new_coach_id = upd.get('coach_id')
            if not r_id:
                return Response({'code': 400, 'msg': '缺少預約編號'}, status=400)
            try:
                r = instance.reservations.get(pk=r_id)
            except Reservation.DoesNotExist:
                return Response({'code': 400, 'msg': '找不到這張訂單的預約'}, status=400)
            old_coach_id = r.preferred_coach_id
            if str(old_coach_id) != str(new_coach_id):
                if r.shared_course_class_id:
                    return Response({
                        'code': 400,
                        'msg': '跨訂單團體班需整班調整，暫不可在單一訂單更換教練',
                    }, status=400)
                if r.status == 'completed':
                    return Response({'code': 400, 'msg': '課程已完課，不能直接更換教練；請先核對評量與薪資紀錄'}, status=400)
                if r.is_preferred_coach:
                    return Response({
                        'code': 400,
                        'msg': '此課程為客人指定教練，後台不可更換教練',
                    }, status=status.HTTP_400_BAD_REQUEST)
                coach = None
                if new_coach_id not in (None, ''):
                    try:
                        coach_id = int(new_coach_id)
                    except (TypeError, ValueError):
                        return Response({'code': 400, 'msg': '教練編號格式錯誤'}, status=400)
                    coaches = Coach.objects.filter(pk=coach_id, client=instance.client).exclude(
                        availability_status='unavailable'
                    )
                    if instance.campus_id:
                        coaches = coaches.filter(campuses__id=instance.campus_id)
                    if r.resort_id:
                        coaches = coaches.filter(coachresort__resort_id=r.resort_id)
                    coach = coaches.distinct().first()
                    if coach is None:
                        return Response({'code': 400, 'msg': '這位教練不能接此校區或雪場的課程'}, status=400)
                coach_changes.append({
                    'reservation': r,
                    'old_coach_id': old_coach_id,
                    'old_status': r.status,
                    'old_is_preferred_coach': r.is_preferred_coach,
                    'old_bookings_scheduled': [(b.id, b.is_scheduled) for b in r.bookings.all()],
                    'new_coach_id': coach.id if coach else None,
                })

        def save_payment_status():
            if not payment_status:
                return
            # A group may retain multiple historical payment attempts.
            payment = (Payment.objects.select_for_update()
                       .filter(reservation_group=instance)
                       .order_by('-created_at', '-pk').first())
            if payment is None:
                payment = Payment.objects.create(
                    reservation_group=instance,
                    status=payment_status,
                    user=instance.user,
                )
            payment.status = payment_status
            payment.save()
            if payment_status == 'paid':
                from booking.operations import schedule_group_notifications
                schedule_group_notifications(instance, 'payment_confirmed')

        if action == 'save':
            # 純儲存
            if not coach_changes and not booking_changes and not payment_status:
                return Response({'code': 200, 'msg': '沒有資料變更，未建立修改紀錄'})
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

            save_payment_status()
            from booking.operations import record_order_revision
            record_order_revision(instance, user=request.user, change_type='modify', reason=data.get('reason', '後台修改訂單'))

            changed_count = len(coach_changes) + len(booking_changes)
            if payment_status and not changed_count:
                message = '付款狀態已儲存'
            elif payment_status:
                message = f'已儲存付款狀態及 {changed_count} 筆課程資料'
            else:
                message = f'已儲存（更新 {changed_count} 筆資料）'
            return Response({'code': 200, 'msg': message})

        elif action == 'schedule':
            # 觸發 AI 排課
            if not coach_changes and not booking_changes:
                save_payment_status()
                return Response({'code': 200, 'msg': '付款狀態已儲存' if payment_status else '沒有變更，無需排課'})

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
                    save_payment_status()
                    for c in coach_changes:
                        r = Reservation.objects.get(pk=c['reservation'].id)
                        if r.is_preferred_coach:
                            r.is_preferred_coach = False
                            r.save(update_fields=['is_preferred_coach'])
                    from booking.operations import record_order_revision
                    record_order_revision(instance, user=request.user, change_type='modify', reason=data.get('reason', '後台修改並重新排課'))
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


class CancellationAdminViewSet(PayrollCsrfMixin, ReadOnlyModelViewSet):
    serializer_class = CancellationRequestAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'orders'

    def _summary_only(self):
        profile = getattr(self.request.user, 'userprofile', None)
        return bool(profile and profile.role in ('campus_manager', 'campus_principal'))

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self._summary_only() and request.method not in SAFE_METHODS:
            raise PermissionDenied('校區人員只能查看所屬校區訂單摘要，不能處理取消或退款')

    def get_serializer_class(self):
        return CancellationRequestSummarySerializer if self._summary_only() else CancellationRequestAdminSerializer

    def get_queryset(self):
        qs = CancellationRequest.objects.filter(group__client=self.request.tenant).select_related('group', 'reviewed_by')
        if (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(group__campus_id__in=_campus_ids(self.request))
        profile = getattr(self.request.user, 'userprofile', None)
        if profile and profile.role == 'campus_manager':
            today = timezone.localdate()
            qs = qs.filter(group__reservations__bookings__date__range=(today, today + timedelta(days=10))).distinct()
        return qs.order_by('-created_at')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def process(self, request, *args, **kwargs):
        cancellation = self.get_object()
        # Re-read under locks; a concurrent review or campus move invalidates the initial object.
        group = get_object_or_404(ReservationGroup.objects.select_for_update(), pk=cancellation.group_id)
        cancellation = get_object_or_404(CancellationRequest.objects.select_for_update(), pk=cancellation.pk, group=group)
        scoped = not request.can_view_all_campuses or request.selected_campus_id is not None
        if group.client_id != request.tenant.pk or (scoped and group.campus_id not in _campus_ids(request)):
            raise NotFound('找不到此校區可處理的取消申請')
        cancellation.group = group
        next_status = request.data.get('status')
        if next_status not in ('approved', 'rejected', 'refunded'):
            return Response({'code': 400, 'msg': '無效的處理狀態'}, status=400)
        allowed = {
            'requested': {'approved', 'rejected'},
            'approved': {'refunded'},
            'rejected': set(),
            'refunded': set(),
        }
        from booking.operations import outstanding_amendments
        pending=list(outstanding_amendments(group).values('id','balance_amount','status'))
        requires_review=cancellation.requires_cash_review or bool(pending)
        review_pending=requires_review and cancellation.actual_received_amount is None
        legacy_review=next_status=='approved' and cancellation.status=='approved' and review_pending
        if next_status not in allowed.get(cancellation.status, set()) and not legacy_review:
            return Response({'code': 400, 'msg': f'「{cancellation.get_status_display()}」不能改為這個狀態'}, status=400)
        review_fields={'actual_received_amount','refund_amount','cash_review_note','confirmed_received'}
        if set(request.data)-({'status'}|review_fields):
            return Response({'code':400,'msg':'取消處理包含不支援的欄位'},status=400)
        if next_status=='refunded' and review_pending:
            return Response({'code':400,'msg':'請先核對實收款及退款金額，不能直接記錄退款完成'},status=400)
        update_fields=['status','reviewed_by','reviewed_at','updated_at']
        if next_status=='approved' and review_pending:
            from .order_amendments import WholeNumber
            from rest_framework import serializers
            class CashReviewInput(serializers.Serializer):
                actual_received_amount=WholeNumber(min_value=0,max_value=2147483647)
                refund_amount=WholeNumber(min_value=0,max_value=2147483647)
                cash_review_note=serializers.CharField(max_length=1000)
                confirmed_received=serializers.BooleanField()
            review=CashReviewInput(data={key:request.data[key] for key in review_fields if key in request.data})
            review.is_valid(raise_exception=True)
            values=review.validated_data
            if not values['confirmed_received'] or values['refund_amount']>values['actual_received_amount']:
                return Response({'code':400,'msg':'請確認銀行實收紀錄；退款不可超過核對後的實收款'},status=400)
            cancellation.requires_cash_review=True
            cancellation.actual_received_amount=values['actual_received_amount']
            cancellation.refund_amount=values['refund_amount']
            cancellation.cash_review_note=values['cash_review_note']
            cancellation.calculation_mode='manual'
            cancellation.cash_review_snapshot={**cancellation.cash_review_snapshot,
                'outstanding_amendments':cancellation.cash_review_snapshot.get('outstanding_amendments',pending),
                'reviewed_by':request.user.pk,'reviewed_at':timezone.now().isoformat(),
                'actual_received_amount':values['actual_received_amount'],'refund_amount':values['refund_amount']}
            update_fields+=['requires_cash_review','actual_received_amount','refund_amount','cash_review_note','calculation_mode','cash_review_snapshot']
        elif set(request.data)&review_fields:
            return Response({'code':400,'msg':'只有待實收款核對的取消申請可設定此金額'},status=400)
        cancellation.status = next_status
        cancellation.reviewed_by = request.user
        cancellation.reviewed_at = timezone.now()
        cancellation.save(update_fields=update_fields)
        if next_status in ('approved', 'refunded'):
            shared_class_ids = cancellation.group.reservations.filter(
                shared_course_class__isnull=False,
            ).values_list('shared_course_class_id', flat=True).distinct()
            cancellation.group.reservations.update(status='cancelled')
            for shared_class in SharedCourseClass.objects.select_for_update().filter(id__in=shared_class_ids):
                shared_class.refresh_readiness()
        if next_status == 'refunded':
            cancellation.group.payments.update(status='refunded')
            outstanding_amendments(group).update(status='cancelled',updated_at=timezone.now())
        return Response({'code': 200, 'msg': '取消申請已更新', 'data': self.get_serializer(cancellation).data})


class NotificationTemplateAdminViewSet(ModelViewSet):
    serializer_class = NotificationTemplateAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'notifications'

    def get_queryset(self):
        qs = NotificationTemplate.objects.filter(client=self.request.tenant).exclude(event='manual').prefetch_related('course_templates')
        campus_ids = _campus_ids(self.request)
        if campus_ids and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(Q(campus_id__in=campus_ids) | Q(campus__isnull=True))
            if self.request.method not in SAFE_METHODS and not self.request.can_view_all_campuses:
                qs = qs.filter(campus_id__in=campus_ids)
        return qs.order_by('event', 'channel', 'id')

    def perform_create(self, serializer):
        campus = serializer.validated_data.get('campus')
        campus_ids = _campus_ids(self.request)
        if not self.request.can_view_all_campuses and (campus is None or campus.id not in campus_ids):
            raise PermissionDenied('只能建立自己校區的通知範本')
        if self.request.selected_campus_id and (campus is None or campus.id != self.request.selected_campus_id):
            raise PermissionDenied('請先切換到要建立範本的校區')
        serializer.save()

    def perform_update(self, serializer):
        campus = serializer.validated_data.get('campus', serializer.instance.campus)
        campus_ids = _campus_ids(self.request)
        if not self.request.can_view_all_campuses and (campus is None or campus.id not in campus_ids):
            raise PermissionDenied('只能修改自己校區的通知範本')
        if self.request.selected_campus_id and (campus is None or campus.id != self.request.selected_campus_id):
            raise PermissionDenied('請先切換到要修改範本的校區')
        serializer.save()

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request, self.get_serializer_context())


class NotificationDeliveryAdminViewSet(ReadOnlyModelViewSet):
    serializer_class = NotificationDeliveryAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'notifications'

    @action(detail=False, methods=['get'], url_path='targets')
    def targets(self, request, client_code=None):
        from .manual_notifications import target_options
        rows = target_options(request, request.query_params.get('kind', 'order'), request.query_params.get('q', ''))
        return Response({'code': 200, 'data': {'list': rows}})

    @action(detail=False, methods=['post'], url_path='preview')
    def preview(self, request, client_code=None):
        from .manual_notifications import ManualNotificationInput, preview_notification
        serializer = ManualNotificationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'code': 200, 'data': preview_notification(request, serializer.validated_data)})

    @action(detail=False, methods=['post'], url_path='send')
    def send(self, request, client_code=None):
        from .manual_notifications import ManualNotificationInput, send_manual_notification
        serializer = ManualNotificationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = send_manual_notification(request, serializer.validated_data)
        return Response({'code': 200, 'msg': '通知已發送' if not result['duplicate'] else '此通知已發送，沒有重複寄送', 'data': result})

    def get_queryset(self):
        qs = NotificationDelivery.objects.filter(template__client=self.request.tenant).filter(
            Q(group__client=self.request.tenant) | Q(group__isnull=True, template__event='manual'),
        ).select_related('template', 'group')
        if _campus_ids(self.request) and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(Q(group__campus_id__in=_campus_ids(self.request))
                           | Q(group__isnull=True, template__campus_id__in=_campus_ids(self.request)))
        return qs.order_by('-scheduled_at')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request)


class CourseEvaluationAdminViewSet(PayrollCsrfMixin, ModelViewSet):
    serializer_class = CourseEvaluationAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'evaluations'

    def _is_readonly_assistant(self):
        profile = getattr(self.request.user, 'userprofile', None)
        return bool(not self.request.user.is_superuser and profile and profile.role == 'assistant'
                    and not getattr(self, 'coach_scoped', False))

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in SAFE_METHODS and self._is_readonly_assistant():
            media_action = self.action in ('upload_media', 'add_media')
            media_only_patch = self.action == 'partial_update' and set(request.data) == {'new_media'}
            if not (media_action or media_only_patch):
                raise PermissionDenied('行政僅能查看評量及加入課程附件，不能修改評語、進度或完成狀態')

    @action(detail=True, methods=['get', 'patch'], url_path='upload', parser_classes=[MultiPartParser])
    def upload_media(self, request, *args, **kwargs):
        from booking.media_files import course_media_url, save_course_upload
        evaluation = self.get_object()
        if request.method == 'GET':
            return Response({'code': 200, 'data': {
                'photo_limit_bytes': settings.COURSE_MEDIA_MAX_PHOTO_BYTES,
                'video_limit_bytes': settings.COURSE_MEDIA_MAX_VIDEO_BYTES,
                'formats': ['JPEG', 'PNG', 'WebP', 'MP4/MOV', 'WebM'],
            }})
        try:
            media = save_course_upload(evaluation, request.user, request.FILES.get('file'))
        except ValueError as exc:
            return Response({'code': 400, 'msg': str(exc)}, status=400)
        except OSError:
            return Response({'code': 503, 'msg': '檔案暫時無法儲存，請稍後再試'}, status=503)
        return Response({'code': 201, 'msg': '課程附件已上傳，僅授權人員可讀取',
                         'data': {'id': media.pk, 'url': course_media_url(media), 'media_type': media.media_type}}, status=201)

    def get_queryset(self):
        qs = CourseEvaluation.objects.filter(member__is_active=True,booking__reservation__group__client=self.request.tenant).select_related(
            'booking__reservation__group__campus', 'booking__reservation__resort', 'member__user', 'coach',
        ).prefetch_related('media')
        if _campus_ids(self.request) and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(booking__reservation__group__campus_id__in=_campus_ids(self.request))
        return qs.order_by('-booking__date', '-id')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request, self.get_serializer_context())

    @action(detail=True, methods=['post'], url_path='media')
    def add_media(self, request, *args, **kwargs):
        from .admin_serializers import CourseMediaAdminSerializer
        evaluation = self.get_object()
        serializer = CourseMediaAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if self._is_readonly_assistant() and serializer.validated_data.get('is_public'):
            raise PermissionDenied('行政加入的課程附件僅供授權學員查看，不能直接公開')
        media = serializer.save(evaluation=evaluation, uploaded_by=request.user)
        return Response({'code': 200, 'msg': '媒體已加入', 'data': {'id': media.id, 'url': media.url}})


class CoachCourseEvaluationViewSet(CourseEvaluationAdminViewSet):
    permission_classes = [IsTenantCoach]
    serializer_class = CoachCourseEvaluationSerializer
    http_method_names = ['get', 'patch', 'head', 'options']
    coach_scoped = True

    def get_queryset(self):
        return CourseEvaluation.objects.filter(
            member__is_active=True,
            booking__reservation__group__client=self.request.tenant,
            booking__reservation__status='completed',
            booking__reservation__preferred_coach__user=self.request.user,
            coach__user=self.request.user, coach__client=self.request.tenant,
        ).select_related(
            'booking__reservation__group__campus', 'booking__reservation__resort', 'member__user', 'coach',
        ).prefetch_related('media').order_by('-booking__date', '-id')


class InsuranceRecordAdminViewSet(PayrollCsrfMixin, RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    serializer_class = InsuranceRecordAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'insurance_records'

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        profile = getattr(request.user, 'userprofile', None)
        if request.method not in SAFE_METHODS and self.action != 'reminder' and not request.user.is_superuser and profile and profile.role == 'assistant':
            raise PermissionDenied('行政小幫手僅能查看保險與聲明書，不能修改或標記完成')

    def get_serializer_class(self):
        # Personal data and signed snapshots are fetched only after opening
        # one authorized record; keep bulk lists limited to status summaries.
        if self.action == 'retrieve':
            return InsuranceRecordDetailAdminSerializer
        return self.serializer_class

    def get_queryset(self):
        qs = MemberDetail.objects.filter(reservation__group__client=self.request.tenant).select_related(
            'user', 'guardian', 'reservation__group__campus'
        ).prefetch_related('reservation__bookings')
        if _campus_ids(self.request) and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(reservation__group__campus_id__in=_campus_ids(self.request))
        status_filter = self.request.query_params.get('status')
        if status_filter == 'missing':
            qs = qs.filter(Q(insurance_completed_at__isnull=True) | Q(waiver_completed_at__isnull=True))
        elif status_filter == 'completed':
            qs = qs.filter(insurance_completed_at__isnull=False, waiver_completed_at__isnull=False)
        # Ordering by a related booking date makes SQL include that date in the
        # DISTINCT result, so one member appears once per course day.  The
        # serializer already returns all course dates; keep one row per member.
        return qs.order_by('id').distinct()

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request)

    @action(detail=True, methods=['get','post'], url_path='reminder')
    def reminder(self, request, *args, **kwargs):
        from Client.models import Client
        from .insurance_reminders import InsuranceReminderInput, reminder_preview
        from .order_email_notifications import prepare_email, deliver_order_email
        member = self.get_object()
        if request.method == 'GET':
            return Response({'code':200,'data':reminder_preview(member,request.query_params.get('field'))})
        serializer = InsuranceReminderInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            # Match the existing mail publisher: tenant → group → member.
            # No locks are held while the SMTP transport runs below.
            Client.objects.select_for_update().get(pk=request.tenant.pk)
            get_object_or_404(ReservationGroup.objects.select_for_update(),pk=member.reservation.group_id)
            member = get_object_or_404(self.get_queryset().select_for_update(),pk=member.pk)
            preview = reminder_preview(member,data['field'])
            if preview['recipient_email'] != data['recipient_email'].strip().lower():
                return Response({'code':409,'msg':'收件人已改變，請重新開啟提醒視窗確認'},status=409)
            delivery_id = prepare_email(request,member.reservation.group,{**preview,'request_key':data['request_key']})
        response_status, response = deliver_order_email(delivery_id)
        return Response(response,status=response_status)

    @action(detail=True, methods=['post'], url_path='processing')
    def processing(self, request, *args, **kwargs):
        member = self.get_object()
        serializer = InsuranceProcessingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            # Use the same group→member lock order as order/participant changes.
            ReservationGroup.objects.select_for_update().get(pk=member.reservation.group_id)
            member = get_object_or_404(self.get_queryset().select_for_update(), pk=member.pk)
            if member.insurance_processing_updated_at != data['expected_updated_at']:
                return Response({'code': 409, 'msg': '投保紀錄已被更新，請重新載入後核對'}, status=409)
            if data['status'] == 'insured' and member.insurance_processing_status != 'insured' and not data['confirm_insured']:
                return Response({'code': 400, 'msg': '請確認已在保險公司完成投保；系統只記錄狀態，不會自動投保'}, status=400)
            member.insurance_processing_status = data['status']
            member.insurance_premium_amount = data['premium_amount']
            member.insurance_premium_currency = data['currency']
            member.insurance_processing_updated_at = timezone.now()
            member.insurance_processing_updated_by = request.user
            member.save(update_fields=['insurance_processing_status', 'insurance_premium_amount', 'insurance_premium_currency',
                'insurance_processing_updated_at', 'insurance_processing_updated_by'])
        return Response({'code': 200, 'msg': '投保作業紀錄已儲存（不會自動投保）', 'data': self.get_serializer(member).data})

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, *args, **kwargs):
        member = self.get_object()
        field = request.data.get('field')
        if field not in ('insurance', 'waiver'):
            return Response({'code': 400, 'msg': '完成項目不正確'}, status=400)
        target = 'insurance_completed_at' if field == 'insurance' else 'waiver_completed_at'
        setattr(member, target, timezone.now())
        member.save(update_fields=[target])
        return Response({'code': 200, 'msg': '完成狀態已更新', 'data': self.get_serializer(member).data})


class CoachPayRuleAdminViewSet(PayrollCsrfMixin, ModelViewSet):
    serializer_class = CoachPayRuleAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'payroll'

    @action(detail=False, methods=['get'], url_path='coaches')
    def coaches(self, request, *args, **kwargs):
        qs = Coach.objects.filter(client=request.tenant)
        allowed = set(_campus_ids(request))
        if allowed and (
            not request.can_view_all_campuses or request.selected_campus_id is not None
        ):
            qs = qs.filter(campuses__id__in=allowed).distinct()
        rows = []
        for coach in qs.prefetch_related('campuses').order_by('name', 'id'):
            assigned = {campus.id for campus in coach.campuses.all()}
            rows.append({
                'id': coach.id,
                'name': coach.name,
                'campus_ids': sorted(assigned),
                'can_manage': bool(getattr(request, 'can_view_all_campuses', False) or (assigned and assigned.issubset(allowed))),
            })
        return Response({'code': 200, 'msg': '教練清單取得成功', 'data': {'list': rows, 'total': len(rows)}})

    def _require_manageable_coach(self, coach):
        if getattr(self.request, 'can_view_all_campuses', False):
            return
        assigned = set(coach.campuses.values_list('id', flat=True))
        if not assigned or not assigned.issubset(set(_campus_ids(self.request))):
            raise PermissionDenied('這位教練也屬於其他校區，請由總部管理員設定薪資規則')

    @transaction.atomic
    def perform_create(self, serializer):
        Coach.objects.select_for_update().get(pk=serializer.validated_data['coach'].pk)
        self._require_manageable_coach(serializer.validated_data['coach'])
        serializer.validate(dict(serializer.validated_data))
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.instance = CoachPayRule.objects.select_for_update().get(pk=serializer.instance.pk)
        coach_ids = {serializer.instance.coach_id, serializer.validated_data.get('coach', serializer.instance.coach).pk}
        list(Coach.objects.select_for_update().filter(pk__in=coach_ids).order_by('pk'))
        self._require_manageable_coach(serializer.instance.coach)
        self._require_manageable_coach(serializer.validated_data.get('coach', serializer.instance.coach))
        serializer.validate(dict(serializer.validated_data))
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        instance = CoachPayRule.objects.select_for_update().get(pk=instance.pk)
        Coach.objects.select_for_update().get(pk=instance.coach_id)
        self._require_manageable_coach(instance.coach)
        instance.delete()

    def get_queryset(self):
        qs = CoachPayRule.objects.filter(coach__client=self.request.tenant).select_related('coach', 'course_type')
        if _campus_ids(self.request) and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(coach__campuses__id__in=_campus_ids(self.request)).distinct()
        return qs.order_by('coach__name', 'discipline', 'course_type_id')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request)


class StaffIncentiveRuleAdminViewSet(PayrollCsrfMixin, ModelViewSet):
    serializer_class = StaffIncentiveRuleAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'payroll'

    @action(detail=False, methods=['get'], url_path='employees')
    def employees(self, request, *args, **kwargs):
        from Control.models import UserProfile
        campuses = Campus.objects.filter(client=request.tenant, is_active=True, pk__in=_campus_ids(request))
        allowed_ids = set(campuses.values_list('pk', flat=True))
        profiles = UserProfile.objects.filter(
            manager_client=request.tenant, is_manager=True, user__is_active=True,
        ).filter(Q(role__in=HEADQUARTERS_ROLES) | Q(campuses__pk__in=allowed_ids)).select_related('user').prefetch_related('campuses').distinct()
        rows = []
        for profile in profiles.order_by('user__username', 'pk'):
            assigned = allowed_ids if profile.role in HEADQUARTERS_ROLES else allowed_ids.intersection(c.pk for c in profile.campuses.all())
            rows.append({'id': profile.user_id, 'name': profile.user.get_full_name() or profile.user.username,
                         'campus_ids': sorted(assigned)})
        return Response({'code': 200, 'msg': 'OK', 'data': {'employees': rows,
            'campuses': list(campuses.order_by('name', 'pk').values('id', 'name'))}})

    def get_queryset(self):
        qs = StaffIncentiveRule.objects.filter(campus__client=self.request.tenant).select_related('user', 'campus')
        if not self.request.can_view_all_campuses or self.request.selected_campus_id is not None:
            qs = qs.filter(campus_id__in=_campus_ids(self.request))
        return qs.order_by('campus__name', 'user__username', 'pk')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request)

    def _require_campus(self, campus):
        if not self.request.can_view_all_campuses or self.request.selected_campus_id is not None:
            if campus.pk not in _campus_ids(self.request):
                raise PermissionDenied('只能設定目前可管理校區的員工獎金')

    @transaction.atomic
    def perform_create(self, serializer):
        campus = serializer.validated_data['campus']
        User.objects.select_for_update().get(pk=serializer.validated_data['user'].pk)
        Campus.objects.select_for_update().get(pk=campus.pk)
        self._require_campus(campus)
        serializer.validate(dict(serializer.validated_data))
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.instance = StaffIncentiveRule.objects.select_for_update().get(pk=serializer.instance.pk)
        user_ids = {serializer.instance.user_id, serializer.validated_data.get('user', serializer.instance.user).pk}
        list(User.objects.select_for_update().filter(pk__in=user_ids).order_by('pk'))
        campus = serializer.validated_data.get('campus', serializer.instance.campus)
        list(Campus.objects.select_for_update().filter(pk__in={campus.pk, serializer.instance.campus_id}).order_by('pk'))
        self._require_campus(serializer.instance.campus)
        self._require_campus(campus)
        serializer.validate(dict(serializer.validated_data))
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        instance = StaffIncentiveRule.objects.select_for_update().get(pk=instance.pk)
        User.objects.select_for_update().get(pk=instance.user_id)
        Campus.objects.select_for_update().get(pk=instance.campus_id)
        self._require_campus(instance.campus)
        instance.delete()


class PayrollStatementAdminViewSet(PayrollCsrfMixin, ModelViewSet):
    serializer_class = PayrollStatementAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'payroll'
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def create(self, request, *args, **kwargs):
        return Response({'code': 405, 'msg': '請使用薪資結算操作'}, status=405)

    @action(detail=False, methods=['get', 'post'], url_path='document-settings')
    def document_settings(self, request, *args, **kwargs):
        from .payroll_documents import document_settings
        return document_settings(self, request)

    @action(detail=True, methods=['post'], url_path='document')
    def generate_document(self, request, *args, **kwargs):
        from .payroll_documents import generate_document
        return generate_document(self, request)

    @action(detail=True, methods=['get'], url_path='signature-file')
    def signature_file(self, request, *args, **kwargs):
        from .payroll_documents import read_signature
        return read_signature(self)

    def get_queryset(self):
        qs = PayrollStatement.objects.filter(coach__client=self.request.tenant).select_related('coach', 'campus').prefetch_related('lines')
        if _campus_ids(self.request) and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(campus_id__in=_campus_ids(self.request))
        return qs.order_by('-period_start', 'coach__name')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request)

    @action(detail=True, methods=['post'])
    def publish(self, request, *args, **kwargs):
        from Coach.payroll_review import publish_statement
        statement = self.get_object()
        try:
            deadline = datetime.strptime(request.data.get('confirmation_deadline'), '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return Response({'code': 400, 'msg': '請選擇正確的確認截止日'}, status=400)
        try:
            statement = publish_statement(statement, deadline)
        except ValueError as exc:
            return Response({'code': 400, 'msg': str(exc)}, status=400)
        return Response({'code': 200, 'msg': '已送交教練確認；未進行發款', 'data': self.get_serializer(statement).data})

    @action(detail=True, methods=['post'])
    def withdraw(self, request, *args, **kwargs):
        from Coach.payroll_review import withdraw_statement
        try:
            statement = withdraw_statement(self.get_object())
        except ValueError as exc:
            return Response({'code': 409, 'msg': str(exc)}, status=409)
        return Response({'code': 200, 'msg': '已撤回草稿，教練端暫不顯示', 'data': self.get_serializer(statement).data})

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        statement = self.get_object()
        statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
        if statement.status != 'draft':
            return Response({'code': 400, 'msg': '僅草稿薪資單可以刪除；已確認或已發放的紀錄須保留'}, status=400)
        statement.delete()
        return Response(status=204)

    @action(detail=True, methods=['post'], url_path=r'adjustments/(?P<line_id>\d+)/edit')
    def edit_adjustment(self, request, line_id=None, *args, **kwargs):
        return self._change_adjustment(request, line_id)

    @action(detail=True, methods=['post'], url_path=r'adjustments/(?P<line_id>\d+)/remove')
    def remove_adjustment(self, request, line_id=None, *args, **kwargs):
        return self._change_adjustment(request, line_id, delete=True)

    def _change_adjustment(self, request, line_id, delete=False):
        from Coach.payroll import change_payroll_adjustment
        statement = self.get_object()
        try:
            statement = change_payroll_adjustment(statement=statement, line_id=line_id,
                description=request.data.get('description', ''), amount=request.data.get('amount'), delete=delete)
        except ValueError as exc:
            return Response({'code': 400, 'msg': str(exc)}, status=400)
        return Response({'code': 200, 'msg': '手動項目已刪除' if delete else '手動項目已修改', 'data': self.get_serializer(statement).data})

    @action(detail=True, methods=['post'], url_path='adjustments')
    def adjustments(self, request, *args, **kwargs):
        from Coach.payroll import add_payroll_adjustment
        try:
            statement = self.get_object()
            add_payroll_adjustment(
                statement=statement,
                description=request.data.get('description', ''),
                amount=request.data.get('amount'),
            )
            statement.refresh_from_db()
        except ValueError as exc:
            return Response({'code': 400, 'msg': str(exc)}, status=400)
        return Response({'code': 200, 'msg': '已加入手動項目', 'data': self.get_serializer(statement).data})

    @action(detail=False, methods=['post'])
    def calculate(self, request, *args, **kwargs):
        from Coach.payroll import calculate_payroll_statement
        try:
            coach = Coach.objects.get(pk=request.data.get('coach'), client=request.tenant)
            campus = Campus.objects.get(pk=request.data.get('campus'), client=request.tenant)
            if campus.id not in _campus_ids(request):
                raise PermissionDenied('不能結算其他校區')
            if not coach.campuses.filter(pk=campus.id).exists():
                raise ValueError('教練未被指派到此校區，請先至教練管理確認')
            period_start = datetime.strptime(request.data.get('period_start', ''), '%Y-%m-%d').date()
            period_end = datetime.strptime(request.data.get('period_end', ''), '%Y-%m-%d').date()
            if period_end < period_start:
                raise ValueError('結束日不能早於開始日')
            statement = calculate_payroll_statement(coach=coach, campus=campus, period_start=period_start, period_end=period_end)
        except (Coach.DoesNotExist, Campus.DoesNotExist, TypeError, ValueError) as exc:
            return Response({'code': 400, 'msg': str(exc) or '請檢查教練、校區與日期'}, status=400)
        return Response({'code': 200, 'msg': '薪資已計算', 'data': self.get_serializer(statement).data})


class CoachPayrollViewSet(PayrollCsrfMixin, ReadOnlyModelViewSet):
    serializer_class = PayrollStatementAdminSerializer
    permission_classes = [IsTenantCoach]
    coach_scoped = True

    def get_queryset(self):
        return PayrollStatement.objects.filter(coach__user=self.request.user,
            coach__client=self.request.tenant, status__in=['review', 'confirmed', 'paid']).select_related('coach', 'campus').prefetch_related('lines').order_by('-period_start', '-pk')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request, self.get_serializer_context())

    @action(detail=True, methods=['post'], url_path='signature', parser_classes=[MultiPartParser])
    def upload_signature(self, request, *args, **kwargs):
        from .payroll_documents import upload_signature
        return upload_signature(self, request)

    @action(detail=True, methods=['get'], url_path='signature-file')
    def signature_file(self, request, *args, **kwargs):
        from .payroll_documents import read_signature
        return read_signature(self)

    @action(detail=True, methods=['post'])
    def confirm(self, request, *args, **kwargs):
        from Coach.payroll_review import confirm_statement
        try:
            statement = confirm_statement(self.get_object(), request.user, request.data.get('review_token'))
        except ValueError as exc:
            return Response({'code': 409, 'msg': str(exc)}, status=409)
        return Response({'code': 200, 'msg': '薪資單已確認；未進行發款', 'data': self.get_serializer(statement).data})


class StaffBookingLinkAdminViewSet(ModelViewSet):
    serializer_class = StaffBookingLinkAdminSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'orders'

    def get_queryset(self):
        qs = StaffBookingLink.objects.filter(client=self.request.tenant).select_related('campus', 'created_by')
        if _campus_ids(self.request) and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id
        ):
            qs = qs.filter(campus_id__in=_campus_ids(self.request))
        return qs.order_by('-created_at')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}

    def perform_create(self, serializer):
        campus = serializer.validated_data['campus']
        if campus.client_id != self.request.tenant.id or (_campus_ids(self.request) and campus.id not in _campus_ids(self.request)):
            raise PermissionDenied('不能為其他校區建立訂課連結')
        serializer.save(client=self.request.tenant, created_by=self.request.user)

    def perform_update(self, serializer):
        campus = serializer.validated_data.get('campus', serializer.instance.campus)
        if campus.client_id != self.request.tenant.id or (_campus_ids(self.request) and campus.id not in _campus_ids(self.request)):
            raise PermissionDenied('不能將訂課連結改到其他校區')
        serializer.save()

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request, self.get_serializer_context())


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
    scoped_groups = ReservationGroup.objects.filter(client=tenant)
    if _campus_ids(request) and (
        not request.can_view_all_campuses or request.selected_campus_id is not None
    ):
        scoped_groups = scoped_groups.filter(campus_id__in=_campus_ids(request))
    from .member_loyalty import visible_customer_ids
    from booking.models import MemberLoyaltyAccount
    user_ids = visible_customer_ids(request)
    users = User.objects.filter(id__in=[uid for uid in user_ids if uid])
    loyalty_accounts = {account.user_id: account for account in MemberLoyaltyAccount.objects.filter(client=tenant, user_id__in=user_ids)}

    data = []
    for u in users:
        groups = scoped_groups.filter(user=u)
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
            'loyalty': ({'alumni_verified': loyalty_accounts[u.id].alumni_verified,
                         'points': loyalty_accounts[u.id].points,
                         'previous_points': loyalty_accounts[u.id].previous_points}
                        if u.id in loyalty_accounts else None),
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

    def _visible_date_bounds(self):
        start, end = _query_date_bounds(self.request)
        profile = getattr(self.request.user, 'userprofile', None)
        if profile and profile.role == 'campus_manager':
            today = timezone.localdate()
            limit = today + timedelta(days=10)
            start = max(start, today) if start else today
            end = min(end, limit) if end else limit
        return start, end

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
        ).exclude(
            reservation__status__in=['deleted', 'cancelled', 'auto_assignment_failed'],
        ).filter(
            scheduled_course_q | photo_booking_q
        ).select_related(
            'reservation',
            'reservation__resort',
            'reservation__preferred_coach',
            'reservation__group__user',
            'reservation__group__campus',
            'reservation__course_type',
            'reservation__course_type__category',
            'reservation__course_template',
        ).distinct().order_by('date', 'start_time')
        qs = _with_current_schedule_payment(qs, 'reservation__group_id')
        if _campus_ids(self.request) and (
            not self.request.can_view_all_campuses or self.request.selected_campus_id is not None
        ):
            qs = qs.filter(reservation__group__campus_id__in=_campus_ids(self.request))

        # 可選 query 參數：start, end (YYYY-MM-DD)
        start, end = self._visible_date_bounds()
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        items = [dict(item) for item in serializer.data]

        start_date, end_date = self._visible_date_bounds()
        history_campus_ids = (
            _campus_ids(request)
            if not request.can_view_all_campuses or request.selected_campus_id is not None
            else None
        )
        items.extend(_equipment_assistance_calendar_items(
            tenant=getattr(request, 'tenant', None),
            campus_ids=history_campus_ids,
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
            campus_ids=_campus_ids(request),
        )
        return Response({
            'code': 200, 'msg': 'OK',
            'data': {'list': items, 'total': len(items), 'daily_summary': daily_summary},
        })

    @action(detail=False, methods=['get'], url_path='group-candidates')
    def group_candidates(self, request, *args, **kwargs):
        """Show cross-order class candidates without opening a class or changing payment."""
        start = _parse_date_query(request.query_params.get('start'))
        end = _parse_date_query(request.query_params.get('end'))
        if not start or not end or end < start or (end - start).days > 62:
            return Response({'code': 400, 'msg': '請提供 62 天內的有效起迄日期'}, status=400)

        visible_start, visible_end = self._visible_date_bounds()
        start = max(start, visible_start) if visible_start else start
        end = min(end, visible_end) if visible_end else end
        if start > end:
            return Response({'code': 200, 'msg': 'OK', 'data': {'list': [], 'total': 0}})

        bookings = Booking.objects.filter(
            reservation__group__client=request.tenant,
            reservation__group__campus_id__in=_campus_ids(request),
            reservation__course_template__billing_mode='per_person',
            date__gte=start,
            date__lte=end,
        ).exclude(reservation__status__in=['cancelled', 'deleted']).select_related(
            'reservation__group__campus', 'reservation__resort', 'reservation__course_template',
            'reservation__shared_course_class',
        ).prefetch_related('reservation__group__payments')

        profile = getattr(request.user, 'userprofile', None)
        can_view_payment = not (profile and profile.role in ('campus_manager', 'campus_principal'))
        candidates = {}
        for booking in bookings:
            reservation = booking.reservation
            counts = reservation.ability_level_counts or {}
            if not counts and reservation.number_of_people > 0:
                counts = {reservation.max_ability_level or 'unknown': reservation.number_of_people}
            payments = list(reservation.group.payments.all())
            latest_payment = max(payments, key=lambda payment: (payment.created_at, payment.id)) if payments else None
            payment_status = latest_payment.status if latest_payment else 'unpaid'
            if payment_status in ('expired', 'refunded'):
                continue
            for level, count in counts.items():
                if not isinstance(count, int) or count <= 0:
                    continue
                key = (
                    reservation.group.campus_id, reservation.resort_id,
                    reservation.course_template_id, booking.date,
                    booking.start_time, booking.end_time, level,
                    reservation.shared_course_class_id,
                )
                shared_class = reservation.shared_course_class
                candidate = candidates.setdefault(key, {
                    'campus_id': reservation.group.campus_id,
                    'campus_name': reservation.group.campus.name if reservation.group.campus else '未分校區',
                    'resort_id': reservation.resort_id,
                    'resort_name': reservation.resort.display_name if reservation.resort else '',
                    'template_id': reservation.course_template_id,
                    'template_name': reservation.course_template.name,
                    'date': booking.date.isoformat(),
                    'start_time': booking.start_time.strftime('%H:%M'),
                    'end_time': booking.end_time.strftime('%H:%M'),
                    'ability_level': level,
                    'shared_class_id': reservation.shared_course_class_id,
                    'shared_class_status': shared_class.status if shared_class else None,
                    'opening_mode': shared_class.opening_mode if shared_class else None,
                    'minimum_students': shared_class.minimum_students if shared_class else None,
                    'registered_students': 0,
                    'assigned_students': 0,
                    'orders': [],
                })
                candidate['registered_students'] += count
                already_assigned = bool(
                    reservation.preferred_coach_id and
                    reservation.status in SCHEDULED_RESERVATION_STATUSES
                )
                if already_assigned:
                    candidate['assigned_students'] += count
                if can_view_payment:
                    candidate['paid_students'] = candidate.get('paid_students', 0) + (count if payment_status == 'paid' else 0)
                order_info = {
                    'group_id': reservation.group_id,
                    'order_number': reservation.group.order_number,
                    'students': count,
                    'already_assigned': already_assigned,
                }
                if can_view_payment:
                    order_info['payment_status'] = payment_status
                candidate['orders'].append(order_info)

        # A school may open a class before anyone books it; it still belongs on the calendar.
        if settings.SHARED_CLASS_FEATURE_ENABLED:
            empty_classes = SharedCourseClass.objects.filter(
                client=request.tenant, campus_id__in=_campus_ids(request),
                date__gte=start, date__lte=end, opening_mode='school',
                status='collecting',
            ).select_related('campus', 'resort', 'template')
            for shared_class in empty_classes:
                if shared_class.registered_students:
                    continue
                key = (
                    shared_class.campus_id, shared_class.resort_id, shared_class.template_id,
                    shared_class.date, shared_class.start_time, shared_class.end_time,
                    shared_class.ability_level, shared_class.id,
                )
                if key in candidates:
                    continue
                candidate = {
                    'campus_id': shared_class.campus_id,
                    'campus_name': shared_class.campus.name,
                    'resort_id': shared_class.resort_id,
                    'resort_name': shared_class.resort.display_name,
                    'template_id': shared_class.template_id,
                    'template_name': shared_class.template.name,
                    'date': shared_class.date.isoformat(),
                    'start_time': shared_class.start_time.strftime('%H:%M'),
                    'end_time': shared_class.end_time.strftime('%H:%M'),
                    'ability_level': shared_class.ability_level,
                    'shared_class_id': shared_class.id,
                    'shared_class_status': shared_class.status,
                    'opening_mode': 'school',
                    'minimum_students': shared_class.minimum_students,
                    'registered_students': 0,
                    'assigned_students': 0,
                    'orders': [],
                }
                if can_view_payment:
                    candidate['paid_students'] = 0
                candidates[key] = candidate

        items = sorted(candidates.values(), key=lambda row: (
            row['date'], row['start_time'], row['resort_name'],
            row['template_name'], row['ability_level'], row['campus_id'] or 0,
        ))
        return Response({'code': 200, 'msg': 'OK', 'data': {'list': items, 'total': len(items)}})

    @action(detail=False, methods=['get', 'post'], url_path='shared-classes/open')
    def open_shared_class(self, request, *args, **kwargs):
        """Headquarters may offer an empty shared class for customers to join later."""
        _require_headquarters(request)
        if not settings.SHARED_CLASS_FEATURE_ENABLED:
            if request.method == 'GET':
                return Response({'code': 200, 'msg': 'OK', 'data': {'enabled': False}})
            return Response({'code': 400, 'msg': '團體班功能尚未開放'}, status=400)

        templates = CourseTemplate.objects.filter(
            course_type__category__client=request.tenant, is_active=True,
            shared_class_enabled=True, billing_mode='per_person',
        ).prefetch_related('resorts', 'sessions').order_by('name', 'id')
        if request.method == 'GET':
            campuses = Campus.objects.filter(
                client=request.tenant, is_active=True, id__in=_campus_ids(request),
            ).prefetch_related('resorts').order_by('display_order', 'id')
            return Response({'code': 200, 'msg': 'OK', 'data': {
                'enabled': True,
                'campuses': [{
                    'id': campus.id, 'name': campus.name,
                    'resorts': [{'id': resort.id, 'name': resort.display_name} for resort in campus.resorts.all()],
                } for campus in campuses],
                'templates': [{
                    'id': template.id, 'name': template.name,
                    'resort_ids': [resort.id for resort in template.resorts.all()],
                    'minimum_students': template.shared_class_minimum_students,
                    'max_capacity': template.max_capacity,
                    'sessions': [{
                        'id': session.id,
                        'label': f'{session.start_time:%H:%M}–{session.end_time:%H:%M}',
                    } for session in template.sessions.all() if session.is_active],
                } for template in templates],
                'levels': list(SharedCourseClass._meta.get_field('ability_level').choices),
                'languages': list(SharedCourseClass._meta.get_field('language').choices),
            }})

        def positive_id(name):
            try:
                value = int(request.data.get(name))
                return value if value > 0 else None
            except (TypeError, ValueError):
                return None

        campus = Campus.objects.filter(
            id=positive_id('campus_id'), client=request.tenant,
            is_active=True, id__in=_campus_ids(request),
        ).first()
        resort = Resorts.objects.filter(id=positive_id('resort_id'), client=request.tenant).first()
        template = templates.filter(id=positive_id('template_id')).first()
        lesson_date = _parse_date_query(request.data.get('date'))
        session = CourseSession.objects.filter(
            id=positive_id('session_id'), template=template, is_active=True,
        ).first() if template else None
        level = request.data.get('ability_level')
        language = request.data.get('language') or 'zh'
        valid_levels = {choice[0] for choice in SharedCourseClass._meta.get_field('ability_level').choices}
        valid_languages = {choice[0] for choice in SharedCourseClass._meta.get_field('language').choices}
        if not campus or not resort or not template or not session or not lesson_date or lesson_date < timezone.localdate() or (
            lesson_date == timezone.localdate() and session.start_time <= timezone.localtime().time()
        ):
            return Response({'code': 400, 'msg': '請選擇有效的校區、雪場、課程、日期與時段'}, status=400)
        if not campus.resorts.filter(pk=resort.pk).exists() or not template.resorts.filter(pk=resort.pk).exists():
            return Response({'code': 400, 'msg': '這個校區或課程沒有開放所選雪場'}, status=400)
        if (template.course_start_date and lesson_date < template.course_start_date) or (
            template.course_end_date and lesson_date > template.course_end_date
        ):
            return Response({'code': 400, 'msg': '日期不在課程開放期間'}, status=400)
        if level not in valid_levels or language not in valid_languages:
            return Response({'code': 400, 'msg': '請選擇有效的學員程度與授課語言'}, status=400)
        if template.shared_class_minimum_students > template.max_capacity:
            return Response({'code': 400, 'msg': '成班人數大於課程人數上限，請先修正模板'}, status=400)
        with transaction.atomic():
            shared_class, created = SharedCourseClass.objects.get_or_create(
                client=request.tenant, campus=campus, resort=resort, template=template,
                date=lesson_date, start_time=session.start_time, end_time=session.end_time,
                ability_level=level, language=language,
                defaults={
                    'opening_mode': 'school',
                    'minimum_students': template.shared_class_minimum_students,
                    'max_capacity': template.max_capacity,
                },
            )
        if not created:
            return Response({'code': 409, 'msg': '同校區、雪場、日期、時段及程度已有班級'}, status=409)
        return Response({'code': 200, 'msg': '已開班，客人可從訂課日曆加入湊班', 'data': {'id': shared_class.id}})

    @action(detail=False, methods=['get', 'post'], url_path=r'shared-classes/(?P<class_id>[0-9]+)/coach')
    def shared_class_coach(self, request, class_id=None, *args, **kwargs):
        """Headquarters assigns one qualified coach to every order in a ready shared class."""
        _require_headquarters(request)
        with transaction.atomic():
            shared_class = SharedCourseClass.objects.select_for_update().select_related(
                'campus', 'resort', 'template__course_type',
            ).filter(
                pk=class_id, client=request.tenant, campus_id__in=_campus_ids(request),
            ).first()
            if shared_class is None:
                return Response({'code': 404, 'msg': '找不到此校區的團體班'}, status=404)

            reservations = list(Reservation.objects.select_for_update().filter(
                shared_course_class=shared_class,
            ).exclude(status__in=['cancelled', 'deleted']).select_related('group').order_by('id'))
            bookings = list(Booking.objects.select_for_update().filter(
                reservation_id__in=[reservation.id for reservation in reservations],
            ))
            if shared_class.status != 'ready' or not reservations:
                return Response({'code': 400, 'msg': '團體班成班後才能整班指派教練'}, status=400)
            if shared_class.date < timezone.localdate() or (
                shared_class.date == timezone.localdate()
                and shared_class.start_time <= timezone.localtime().time()
            ) or any(
                reservation.status == 'completed' for reservation in reservations
            ):
                return Response({'code': 400, 'msg': '課程已開始或完課，不能直接改派教練'}, status=400)
            if len(bookings) != len(reservations) or any(
                booking.date != shared_class.date
                or booking.start_time != shared_class.start_time
                or booking.end_time != shared_class.end_time
                for booking in bookings
            ):
                return Response({'code': 409, 'msg': '班級與訂單時段不一致，請先由總部核對'}, status=409)
            if any(reservation.is_preferred_coach for reservation in reservations):
                return Response({'code': 409, 'msg': '班級含客人指定教練的訂單，請先由總部核對'}, status=409)

            from booking.scheduler import get_feasible_coaches
            feasible = get_feasible_coaches(
                shared_class.language, shared_class.resort,
                shared_class.template.course_type_id, shared_class.ability_level,
                course_template=shared_class.template,
            )
            feasible = [coach for coach in feasible if coach.client_id == request.tenant.id
                        and coach.campuses.filter(pk=shared_class.campus_id).exists()]
            busy_coach_ids = set(Booking.objects.filter(
                reservation__preferred_coach_id__in=[coach.id for coach in feasible],
                date=shared_class.date,
                start_time__lt=shared_class.end_time,
                end_time__gt=shared_class.start_time,
                is_scheduled=True,
            ).exclude(reservation__status__in=['cancelled', 'deleted']).exclude(
                reservation__shared_course_class=shared_class,
            ).values_list('reservation__preferred_coach_id', flat=True))
            leave_coach_ids = set(CoachLeaveRequest.objects.filter(
                coach_id__in=[coach.id for coach in feasible], status='approved',
                start_date__lte=shared_class.date, end_date__gte=shared_class.date,
            ).values_list('coach_id', flat=True))
            rejected_ids = set()
            for reservation in reservations:
                rejected_ids.update(reservation.rejected_coaches.values_list('id', flat=True))
            available = [coach for coach in feasible if coach.id not in busy_coach_ids
                         and coach.id not in leave_coach_ids and coach.id not in rejected_ids]

            current_coach_ids = {reservation.preferred_coach_id for reservation in reservations}
            current_coach_id = next(iter(current_coach_ids)) if len(current_coach_ids) == 1 else None
            data = {
                'shared_class_id': shared_class.id,
                'current_coach_id': current_coach_id,
                'current_coach_name': Coach.objects.filter(
                    pk=current_coach_id, client=request.tenant,
                ).values_list('name', flat=True).first() if current_coach_id else None,
                'coaches': [
                    {'id': coach.id, 'name': coach.name, 'availability_status': coach.availability_status}
                    for coach in available
                ],
            }
            if request.method == 'GET':
                return Response({'code': 200, 'msg': 'OK', 'data': data})

            raw_coach_id = request.data.get('coach_id')
            if isinstance(raw_coach_id, bool) or not str(raw_coach_id or '').isascii() or not str(raw_coach_id or '').isdecimal():
                return Response({'code': 400, 'msg': '請選擇有效的教練'}, status=400)
            coach = next((coach for coach in available if coach.id == int(raw_coach_id)), None)
            if coach is None:
                return Response({'code': 400, 'msg': '教練不符合此班資格，或當天已有課程／請假'}, status=400)
            if coach.availability_status == 'passive' and any(
                reservation.status == 'form_filled' for reservation in reservations
            ):
                return Response({'code': 409, 'msg': '班級已有課前表單，需由總部先確認教練接課狀態'}, status=409)
            if current_coach_id == coach.id and all(booking.is_scheduled for booking in bookings):
                return Response({'code': 200, 'msg': '整班已由這位教練授課，無需變更', 'data': data})

            next_status = 'pending_coach_confirmation' if coach.availability_status == 'passive' else 'manually_assigned'
            for reservation in reservations:
                reservation.preferred_coach = coach
                reservation.is_preferred_coach = False
                if reservation.status != 'form_filled':
                    reservation.status = next_status
                reservation.save(update_fields=['preferred_coach', 'is_preferred_coach', 'status'])
            Booking.objects.filter(pk__in=[booking.id for booking in bookings]).update(is_scheduled=True)
            from booking.operations import record_order_revision
            for group_id in {reservation.group_id for reservation in reservations}:
                record_order_revision(
                    ReservationGroup.objects.get(pk=group_id), user=request.user,
                    reason=f'跨訂單團體班整班改派教練：{coach.name}',
                )
            data['current_coach_id'] = coach.id
            data['current_coach_name'] = coach.name
            return Response({'code': 200, 'msg': '整班教練已更新', 'data': data})

    @action(detail=False, methods=['get', 'post'], url_path=r'shared-classes/(?P<class_id>[0-9]+)/schedule')
    def shared_class_schedule(self, request, class_id=None, *args, **kwargs):
        """Move a shared lesson as one unit, keeping every order and reminder in sync."""
        _require_headquarters(request)
        try:
            with transaction.atomic():
                shared_class = SharedCourseClass.objects.select_for_update().select_related(
                    'template',
                ).filter(
                    pk=class_id, client=request.tenant, campus_id__in=_campus_ids(request),
                ).first()
                if shared_class is None:
                    return Response({'code': 404, 'msg': '找不到此校區的團體班'}, status=404)

                reservations = list(Reservation.objects.select_for_update().filter(
                    shared_course_class=shared_class,
                ).exclude(status__in=['cancelled', 'deleted']).order_by('id'))
                bookings = list(Booking.objects.select_for_update().filter(
                    reservation_id__in=[reservation.id for reservation in reservations],
                ))
                if shared_class.status == 'cancelled' or not reservations:
                    return Response({'code': 400, 'msg': '此團體班已取消或沒有有效訂單'}, status=400)
                if shared_class.date < timezone.localdate() or (
                    shared_class.date == timezone.localdate()
                    and shared_class.start_time <= timezone.localtime().time()
                ) or any(reservation.status == 'completed' for reservation in reservations):
                    return Response({'code': 400, 'msg': '課程已開始或完課，不能直接改期'}, status=400)
                if len(bookings) != len(reservations) or any(
                    booking.date != shared_class.date
                    or booking.start_time != shared_class.start_time
                    or booking.end_time != shared_class.end_time
                    for booking in bookings
                ):
                    return Response({'code': 409, 'msg': '班級與訂單時段不一致，請先由總部核對'}, status=409)

                sessions = list(CourseSession.objects.filter(
                    template=shared_class.template, is_active=True,
                ).order_by('start_time', 'end_time').values('start_time', 'end_time'))
                data = {
                    'shared_class_id': shared_class.id,
                    'date': shared_class.date.isoformat(),
                    'start_time': shared_class.start_time.strftime('%H:%M'),
                    'end_time': shared_class.end_time.strftime('%H:%M'),
                    'sessions': [
                        {'start_time': row['start_time'].strftime('%H:%M'),
                         'end_time': row['end_time'].strftime('%H:%M')}
                        for row in sessions
                    ],
                    'affected_orders': len({reservation.group_id for reservation in reservations}),
                }
                if request.method == 'GET':
                    return Response({'code': 200, 'msg': 'OK', 'data': data})

                try:
                    new_date = datetime.strptime(request.data.get('date', ''), '%Y-%m-%d').date()
                except (TypeError, ValueError):
                    return Response({'code': 400, 'msg': '請選擇有效的上課日期'}, status=400)
                new_start = request.data.get('start_time')
                new_end = request.data.get('end_time')
                selected_session = next((row for row in sessions if (
                    row['start_time'].strftime('%H:%M') == new_start
                    and row['end_time'].strftime('%H:%M') == new_end
                )), None)
                if selected_session is None:
                    return Response({'code': 400, 'msg': '請選擇此課程已啟用的上課時段'}, status=400)
                new_start = selected_session['start_time']
                new_end = selected_session['end_time']
                if new_date < timezone.localdate() or (
                    new_date == timezone.localdate() and new_start <= timezone.localtime().time()
                ):
                    return Response({'code': 400, 'msg': '新時段必須尚未開始'}, status=400)
                if (shared_class.template.course_start_date and new_date < shared_class.template.course_start_date) or (
                    shared_class.template.course_end_date and new_date > shared_class.template.course_end_date
                ):
                    return Response({'code': 400, 'msg': '新日期不在此課程的開課期間內'}, status=400)
                if (new_date, new_start, new_end) == (
                    shared_class.date, shared_class.start_time, shared_class.end_time,
                ):
                    return Response({'code': 200, 'msg': '班級時段沒有變更', 'data': data})
                if SharedCourseClass.objects.filter(
                    client=shared_class.client, campus=shared_class.campus,
                    resort=shared_class.resort, template=shared_class.template,
                    date=new_date, start_time=new_start, end_time=new_end,
                    ability_level=shared_class.ability_level, language=shared_class.language,
                ).exclude(pk=shared_class.pk).exists():
                    return Response({'code': 409, 'msg': '新時段已有相同條件的團體班，請先核對班級'}, status=409)

                coach_ids = {reservation.preferred_coach_id for reservation in reservations}
                if len(coach_ids) != 1:
                    return Response({'code': 409, 'msg': '班內教練資料不一致，請先由總部核對'}, status=409)
                coach_id = next(iter(coach_ids))
                if (new_start, new_end) != (shared_class.start_time, shared_class.end_time):
                    for reservation in reservations:
                        slot = reservation.equipment_assistance_time_slot
                        if slot and not slot.matches_course(
                            duration_hours=shared_class.template.duration_hours,
                            session_start_time=new_start,
                            course_template_id=shared_class.template_id,
                        ):
                            return Response({'code': 409, 'msg': '有訂單的裝備協助時段不適用新課程時段，請先核對'}, status=409)
                        if not slot and reservation.equipment_assistance_time_label:
                            return Response({'code': 409, 'msg': '有訂單的裝備協助時間需人工核對，暫不可變更上課時段'}, status=409)
                if coach_id:
                    coach_status = Coach.objects.filter(pk=coach_id, client=request.tenant).values_list(
                        'availability_status', flat=True,
                    ).first()
                    if coach_status not in ('active', 'passive'):
                        return Response({'code': 409, 'msg': '原教練目前不可接課，請先整班更換教練'}, status=409)
                    if coach_status == 'passive' and any(
                        reservation.status == 'form_filled' for reservation in reservations
                    ):
                        return Response({'code': 409, 'msg': '已有課前表單，請先由總部與教練確認改期'}, status=409)
                    if Booking.objects.filter(
                        reservation__preferred_coach_id=coach_id,
                        date=new_date, start_time__lt=new_end, end_time__gt=new_start,
                        is_scheduled=True,
                    ).exclude(reservation__status__in=['cancelled', 'deleted']).exclude(
                        reservation__shared_course_class=shared_class,
                    ).exists() or CoachLeaveRequest.objects.filter(
                        coach_id=coach_id, status='approved',
                        start_date__lte=new_date, end_date__gte=new_date,
                    ).exists():
                        return Response({'code': 409, 'msg': '教練在新時段已有課程或請假，請先選其他時段'}, status=409)

                old_slot = f'{shared_class.date} {shared_class.start_time:%H:%M}–{shared_class.end_time:%H:%M}'
                shared_class.date = new_date
                shared_class.start_time = new_start
                shared_class.end_time = new_end
                shared_class.save(update_fields=['date', 'start_time', 'end_time'])
                Booking.objects.filter(pk__in=[booking.id for booking in bookings]).update(
                    date=new_date, start_time=new_start, end_time=new_end,
                )
                if coach_id and coach_status == 'passive':
                    Reservation.objects.filter(pk__in=[reservation.id for reservation in reservations]).update(
                        status='pending_coach_confirmation',
                    )
                from booking.operations import record_order_revision, schedule_group_notifications
                for group_id in {reservation.group_id for reservation in reservations}:
                    group = ReservationGroup.objects.get(pk=group_id)
                    record_order_revision(
                        group, user=request.user,
                        reason=f'跨訂單團體班整班改期：{old_slot} → {new_date} {new_start:%H:%M}–{new_end:%H:%M}',
                    )
                    schedule_group_notifications(group, 'pre_course')
                    schedule_group_notifications(group, 'missing_documents')
                data.update(date=new_date.isoformat(), start_time=new_start.strftime('%H:%M'),
                            end_time=new_end.strftime('%H:%M'))
                message = '整班時段已更新；請通知受影響客人確認新時間'
                if coach_id and coach_status == 'passive':
                    message += '，並請教練重新確認接課'
                return Response({'code': 200, 'msg': message, 'data': data})
        except IntegrityError:
            return Response({'code': 409, 'msg': '新時段已有團體班，請重新整理後再試'}, status=409)


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
    export_format = request.query_params.get('export', '')
    if export_format not in ('', 'csv', 'xlsx'):
        return Response({'code': 400, 'msg': '請選擇 CSV 或 Excel 匯出格式'}, status=400)
    date_basis = request.query_params.get('date_basis', 'created')
    if period not in ('today', 'yesterday', 'week', 'month', 'quarter', 'custom') or date_basis not in ('created', 'completed'):
        return Response({'code': 400, 'msg': '請選擇有效的統計期間與日期依據'}, status=400)
    now = timezone.localtime(timezone.now())
    end = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'yesterday':
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    elif period in ('month', 'quarter'):
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if period == 'quarter':
            start = start.replace(month=((now.month - 1) // 3) * 3 + 1)
        end = start
        for _ in range(3 if period == 'quarter' else 1):
            end = (end.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        try:
            first = date.fromisoformat(request.query_params.get('start_date', ''))
            last = date.fromisoformat(request.query_params.get('end_date', ''))
            if first > last:
                raise ValueError
            start = timezone.make_aware(datetime.combine(first, time.min))
            end = timezone.make_aware(datetime.combine(last + timedelta(days=1), time.min))
        except (ValueError, OverflowError):
            return Response({'code': 400, 'msg': '請填寫有效的開始與結束日期，結束日期不得早於開始日期'}, status=400)

    groups = ReservationGroup.objects.filter(client=tenant)
    if date_basis == 'created':
        groups = groups.filter(created_at__gte=start, created_at__lt=end)
    else:
        groups = groups.annotate(completion_date=Max('reservations__bookings__date',
            filter=~Q(reservations__status='deleted'))).filter(
                completion_date__gte=start.date(), completion_date__lt=end.date())
    campus_ids = _campus_ids(request)
    if campus_ids and (
        not request.can_view_all_campuses or request.selected_campus_id is not None
    ):
        groups = groups.filter(campus_id__in=campus_ids)

    accessible_resorts = Resorts.objects.filter(client=tenant)
    if not request.can_view_all_campuses or request.selected_campus_id is not None:
        history = Reservation.objects.filter(group__client=tenant, group__campus_id__in=campus_ids).values('resort_id')
        accessible_resorts = accessible_resorts.filter(Q(campuses__id__in=campus_ids) | Q(pk__in=history)).distinct()
    resort_options = list(accessible_resorts.order_by('id').values('id', 'display_name'))
    resort_names = {item['id']: item['display_name'] for item in resort_options}
    resort_id = request.query_params.get('resort_id')
    if resort_id:
        try:
            resort_id = int(resort_id)
            if resort_id <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'code': 400, 'msg': '請選擇有效雪場'}, status=400)
        if resort_id not in resort_names:
            return Response({'code': 403, 'msg': '無權查看此雪場的統計'}, status=403)
        groups = groups.filter(pk__in=Reservation.objects.filter(resort_id=resort_id).exclude(status='deleted').values('group_id'))

    groups = list(groups.select_related('campus', 'user').prefetch_related('reservations__bookings', 'payments'))
    # Match the completed-order basis used by administrative bonus settlement.
    # An old successful payment must not override a later refund/payment attempt.
    recognized_orders = {}
    for g in groups:
        reservations = [r for r in g.reservations.all() if r.status != 'deleted']
        payment = max(g.payments.all(), key=lambda p: (p.created_at, p.pk), default=None)
        if (reservations and payment and payment.status == 'paid'
                and all(r.status == 'completed' and r.bookings.all() for r in reservations)):
            recognized_orders[g.pk] = [r for r in reservations if not resort_id or r.resort_id == resort_id]
    revenue_by_group = {
        pk: sum(r.payment_amount or 0 for r in reservations)
        for pk, reservations in recognized_orders.items()
    }
    if date_basis == 'completed':
        groups = [g for g in groups if g.pk in recognized_orders]
    total_orders = len(groups)
    active_users = len({g.user_id for g in groups if g.user_id is not None})
    total_revenue = sum(revenue_by_group.values())
    completed_orders = len(recognized_orders)
    avg_order = (total_revenue // completed_orders) if completed_orders else 0
    student_visits = 0
    teaching_slots = {}
    for reservations in recognized_orders.values():
        for reservation in reservations:
            for booking in reservation.bookings.all():
                student_visits += reservation.number_of_people
                key = (('shared', reservation.shared_course_class_id, booking.date, booking.start_time, booking.end_time)
                       if reservation.shared_course_class_id else ('booking', booking.pk))
                teaching_slots[key] = max((datetime.combine(booking.date, booking.end_time)
                    - datetime.combine(booking.date, booking.start_time)).total_seconds(), 0)
    teaching_hours = round(sum(teaching_slots.values()) / 3600, 2)
    payment_counts = dict.fromkeys(('paid', 'pending', 'unpaid', 'expired', 'refunded'), 0)
    for group in groups:
        payment = max(group.payments.all(), key=lambda p: (p.created_at, p.pk), default=None)
        payment_counts[payment.status if payment else 'unpaid'] += 1

    # 熱門課程 TOP 5
    top_items = []
    booking_counts = {}
    for reservations in recognized_orders.values():
        for r in reservations:
            bookings = list(r.bookings.all())
            base, remainder = divmod(r.payment_amount or 0, len(bookings))
            for index, b in enumerate(bookings):
                key = b.course_name or '未命名課程'
                if key not in booking_counts:
                    booking_counts[key] = {'name': key, 'quantity': 0, 'revenue': 0}
                booking_counts[key]['quantity'] += 1
                booking_counts[key]['revenue'] += base + (index < remainder)
    top_items = sorted(booking_counts.values(), key=lambda x: -x['quantity'])[:5]
    for i, item in enumerate(top_items):
        item['id'] = i + 1

    marketing_sources = {}
    campus_summary = {}
    for g in groups:
        amount = revenue_by_group.get(g.pk, 0)
        source = display_marketing_source(g.marketing_source)
        marketing_sources.setdefault(source, {'name': source, 'orders': 0, 'revenue': 0})
        marketing_sources[source]['orders'] += 1
        marketing_sources[source]['revenue'] += amount
        campus_name = g.campus.name if g.campus else '未分校區'
        campus_summary.setdefault(campus_name, {
            'name': campus_name, 'orders': 0, 'revenue': 0,
            'is_active': g.campus.is_active if g.campus else None,
        })
        campus_summary[campus_name]['orders'] += 1
        campus_summary[campus_name]['revenue'] += amount

    # 最近訂單
    profile = getattr(request.user, 'userprofile', None)
    restricted_order_details = bool(
        not request.user.is_superuser
        and profile and profile.role in ('campus_manager', 'campus_principal')
    )
    recent_orders = []
    for g in sorted(groups, key=lambda g: (g.created_at, g.pk), reverse=True)[:5]:
        item = {
            'sn': f'SL{g.created_at.year}-{g.id:04d}',
            'member': (
                (g.user.first_name or '學員') if g.user else (g.name or '學員')
            ) if restricted_order_details else (
                (g.user.get_full_name() or g.user.username) if g.user else (g.name or '訪客')
            ),
            'created_at': timezone.localtime(g.created_at).strftime('%Y-%m-%d %H:%M'),
        }
        if not restricted_order_details:
            p = max(g.payments.all(), key=lambda p: (p.created_at, p.pk), default=None)
            item['amount'] = sum((r.payment_amount or 0) for r in g.reservations.all()
                                 if r.status != 'deleted' and (not resort_id or r.resort_id == resort_id))
            item['status'] = p.status if p else 'unpaid'
        recent_orders.append(item)

    data = {
            'stats': {
                'orders': total_orders,
                'revenue': total_revenue,
                'completed_orders': completed_orders,
                'members': active_users,
                'avg_order_value': avg_order,
                'student_visits': student_visits,
                'teaching_hours': teaching_hours,
            },
            'resort_options': resort_options,
            'payment_statuses': [
                {'status': key, 'name': dict(Payment.STATUS_CHOICES)[key], 'orders': count}
                for key, count in payment_counts.items()
            ],
            'top_items': top_items,
            'recent_orders': recent_orders,
            'restricted_order_details': restricted_order_details,
            'marketing_sources': sorted(marketing_sources.values(), key=lambda item: (-item['orders'], item['name'])),
            'campus_summary': sorted(campus_summary.values(), key=lambda item: (-item['revenue'], item['name'])),
        }
    if export_format:
        from .dashboard_reports import dashboard_report
        return dashboard_report(data, file_format=export_format, start=start.date().isoformat(),
            end=(end.date() - timedelta(days=1)).isoformat(), date_basis=date_basis,
            resort_name=resort_names[resort_id] if resort_id else '全部可查看雪場')
    return Response({'code': 200, 'msg': 'OK', 'data': data})


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

    tenant_user_ids = {request.user.id}
    tenant_user_ids.update(
        UserProfile.objects.filter(manager_client=request.tenant).values_list('user_id', flat=True)
    )
    tenant_user_ids.update(
        Coach.objects.filter(client=request.tenant, user_id__isnull=False).values_list('user_id', flat=True)
    )
    profiles = UserProfile.objects.filter(user_id__in=tenant_user_ids).filter(
        Q(is_manager=True) | Q(is_coach=True)
    ).select_related('user')

    # 完整 Email 可找尚未任職的一般帳號，供新增員工；不列出其他租戶的後台人員。
    if q:
        invitee_ids = User.objects.filter(email__iexact=q, is_superuser=False).exclude(
            Q(userprofile__is_manager=True) | Q(userprofile__is_coach=True)
        ).values_list('id', flat=True)
        users = User.objects.filter(
            Q(username__icontains=q) | Q(email__icontains=q) |
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
        ).filter(pk__in=tenant_user_ids.union(invitee_ids))[:50]
    else:
        superusers = list(User.objects.filter(pk__in=tenant_user_ids, is_superuser=True))
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
            role = profile.role
            campus_ids = list(profile.campuses.filter(client=request.tenant).values_list('id', flat=True))
        except Exception:
            is_manager = False
            is_coach = False
            admin_permissions = []
            role = ''
            campus_ids = []

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
            'role': role,
            'campus_ids': campus_ids,
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
        _require_headquarters(request)
        profile, _ = UserProfile.objects.get_or_create(user=target_user)
        if (profile.is_manager or profile.is_coach) and (
            (profile.manager_client_id and profile.manager_client_id != request.tenant.id)
            or
            profile.campuses.exclude(client=request.tenant).exists()
            or Coach.objects.filter(user=target_user).exclude(client=request.tenant).exists()
        ):
            return Response(
                {'code': 409, 'msg': '此帳號已在其他學校任職；目前無法跨學校共用同一組後台權限'},
                status=409,
            )
        was_manager = profile.is_manager
        requested_superuser = request.data.get('is_superuser', None)
        if requested_superuser is not None:
            if not request.user.is_superuser:
                return Response({'code': 403, 'msg': '只有最大管理員可以調整最大管理員'}, status=403)

        is_manager = bool(request.data.get('is_manager', False))
        will_be_superuser = bool(requested_superuser) if requested_superuser is not None else target_user.is_superuser
        if will_be_superuser and is_manager:
            is_manager = False
        is_coach = bool(request.data.get('is_coach', False))
        role = (request.data.get('role') or '').strip()
        valid_roles = {choice[0] for choice in profile.ROLE_CHOICES}
        if role and role not in valid_roles:
            return Response({'code': 400, 'msg': '員工角色不正確'}, status=400)
        raw_campus_ids = request.data.get('campus_ids', [])
        if not isinstance(raw_campus_ids, list):
            return Response({'code': 400, 'msg': '校區必須是清單'}, status=400)
        if any(
            isinstance(value, bool) or not isinstance(value, (int, str))
            or not str(value).isascii() or not str(value).isdecimal()
            for value in raw_campus_ids
        ):
            return Response({'code': 400, 'msg': '校區編號格式不正確'}, status=400)
        campus_ids = [int(value) for value in raw_campus_ids]
        campuses = list(Campus.objects.filter(client=request.tenant, id__in=campus_ids))
        if len(campuses) != len(campus_ids):
            return Response({'code': 400, 'msg': '包含無效或其他公司的校區'}, status=400)
        if is_manager and role not in HEADQUARTERS_ROLES:
            if not campuses:
                return Response({'code': 400, 'msg': '請先選擇這位後台人員負責的校區'}, status=400)
            if any(not campus.is_active for campus in campuses):
                return Response({'code': 400, 'msg': '不能指派已停用的校區'}, status=400)
        if requested_superuser is not None:
            target_user.is_superuser = will_be_superuser
            target_user.save(update_fields=['is_superuser'])
        profile.is_manager = is_manager
        profile.manager_client = request.tenant if is_manager else None
        profile.is_coach = is_coach
        profile.role = role
        if is_manager:
            if admin_permissions is not None:
                profile.admin_permissions = admin_permissions
            elif not was_manager and profile.admin_permissions is None:
                profile.admin_permissions = []
        else:
            profile.admin_permissions = []
        profile.save()
        profile.campuses.set(campuses)
        return Response({
            'code': 200, 'msg': '權限已更新',
            'data': {
                'is_superuser': target_user.is_superuser,
                'is_manager': profile.is_manager,
                'is_coach': profile.is_coach,
                'permissions': get_user_admin_permissions(target_user),
                'role': profile.role,
                'campus_ids': list(profile.campuses.values_list('id', flat=True)),
            },
        })
    except PermissionDenied:
        raise
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
    from django.middleware.csrf import get_token
    get_token(request._request)
    # 找當前 user 的 Coach
    try:
        coach = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        return Response({'code': 403, 'msg': '您不是教練'}, status=403)

    qs = Reservation.objects.filter(
        preferred_coach=coach,
        group__client=request.tenant,
        status='pending_coach_confirmation',
    ).filter(
        Q(shared_course_class__isnull=True) | Q(shared_course_class__status='ready'),
    ).select_related('resort', 'course_type', 'group__user').prefetch_related('bookings', 'members').distinct().order_by('-mdt_add')

    items = []
    for r in qs:
        items.append({
            'id': r.id,
            'group_id': r.group_id,
            'user_name': _reservation_user_alias(r),
            'resort': r.resort.display_name if r.resort else '',
            'course_type': r.course_type.name if r.course_type else '',
            'ability_level': r.max_ability_level or '',
            'language': r.language,
            'language_label': r.get_language_display(),
            'number_of_people': r.number_of_people,
            'age_ranges': [member.get_age_range_display() for member in r.members.all()],
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
    from rest_framework.authentication import SessionAuthentication
    SessionAuthentication().enforce_csrf(request)
    try:
        coach = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        return Response({'code': 403, 'msg': '您不是教練'}, status=403)

    try:
        r = Reservation.objects.get(pk=reservation_id, preferred_coach=coach, group__client=request.tenant)
    except Reservation.DoesNotExist:
        return Response({'code': 404, 'msg': '課程不存在或非指派給您'}, status=404)

    action = request.data.get('action')
    if r.shared_course_class_id:
        if action not in ('accept', 'reject'):
            return Response({'code': 400, 'msg': '未知 action'}, status=400)
        with transaction.atomic():
            shared_class = SharedCourseClass.objects.select_for_update().get(pk=r.shared_course_class_id)
            if action == 'accept' and shared_class.status != 'ready':
                return Response({'code': 409, 'msg': '此班仍在湊班或已取消，暫不能確認接課'}, status=409)
            siblings = list(Reservation.objects.select_for_update().filter(
                shared_course_class=shared_class,
            ).exclude(status__in=['cancelled', 'deleted']).order_by('id'))
            if not siblings or any(
                item.status != 'pending_coach_confirmation' or item.preferred_coach_id != coach.id
                for item in siblings
            ):
                return Response({'code': 409, 'msg': '整班指派狀態已變更，請重新整理'}, status=409)
            if action == 'accept':
                Reservation.objects.filter(pk__in=[item.id for item in siblings]).update(status='manually_assigned')
                message = '已接受整班課程'
            else:
                for item in siblings:
                    item.rejected_coaches.add(coach)
                Reservation.objects.filter(pk__in=[item.id for item in siblings]).update(
                    preferred_coach=None, is_preferred_coach=False, status='created',
                )
                Booking.objects.filter(reservation_id__in=[item.id for item in siblings]).update(is_scheduled=False)
                message = '已拒絕整班課程，需由總部重新指派教練'
            from booking.operations import record_order_revision
            for group_id in {item.group_id for item in siblings}:
                record_order_revision(
                    ReservationGroup.objects.get(pk=group_id), user=request.user,
                    reason=f'教練{message}',
                )
        return Response({'code': 200, 'msg': message})
    return _confirm_individual_course(request, coach, r.pk, action)


@transaction.atomic
def _confirm_individual_course(request, coach, reservation_id, action):
    # Recheck ownership and state under the row lock, so concurrent accept /
    # reject requests cannot both act on the same pending assignment.
    r = Reservation.objects.select_for_update().filter(
        pk=reservation_id, preferred_coach=coach, group__client=request.tenant,
    ).first()
    if r is None:
        return Response({'code': 404, 'msg': '課程不存在或非指派給您'}, status=404)
    if r.shared_course_class_id:
        return Response({'code': 409, 'msg': '課程已改為團體班，請重新整理後再操作'}, status=409)
    if action == 'accept':
        if r.status != 'pending_coach_confirmation':
            return Response({'code': 400, 'msg': '此課程目前狀態不可接受'}, status=400)
        r.status = 'manually_assigned'
        r.save()
        return Response({'code': 200, 'msg': '已接受'})

    if action == 'reject':
        if r.status != 'pending_coach_confirmation':
            return Response({'code': 400, 'msg': '此課程目前狀態不可拒絕'}, status=400)
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
            # A failed attempt must not leave partial scheduler writes behind;
            # keep the already successful rejection for manual assignment.
            with transaction.atomic():
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
        group__client=request.tenant,
    ).exclude(status__in=['deleted', 'cancelled']).select_related(
        'resort', 'course_type__category', 'course_template__course_type__category', 'group__user'
    ).prefetch_related('bookings', 'members').distinct().order_by('-mdt_add')
    qs = _with_current_schedule_payment(qs, 'group_id')

    # 篩選
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    display_start = None if full_schedule_visible else visible_start
    display_end = None if full_schedule_visible else visible_end
    parsed_date_from, parsed_date_to = _query_date_bounds(request, 'date_from', 'date_to')
    if parsed_date_from and (display_start is None or parsed_date_from > display_start):
        display_start = parsed_date_from
    if parsed_date_to and (display_end is None or parsed_date_to < display_end):
        display_end = parsed_date_to
    booking_date_filter = {}
    if display_start:
        booking_date_filter['bookings__date__gte'] = display_start
    if display_end:
        booking_date_filter['bookings__date__lte'] = display_end
    if display_start and display_end and display_start > display_end:
        qs = qs.none()
    elif booking_date_filter:
        qs = qs.filter(**booking_date_filter).distinct()

    items = []
    for r in qs:
        items.append({
            'id': r.id,
            'group_id': r.group_id,
            'user_name': _reservation_user_alias(r),
            'resort': r.resort.display_name if r.resort else '',
            'course_type': r.course_type.name if r.course_type else '',
            'course_category': (
                r.course_type.category.name if r.course_type else
                r.course_template.course_type.category.name if r.course_template else ''
            ),
            'ability_level': r.max_ability_level or '',
            'language': r.language,
            'language_label': r.get_language_display(),
            'number_of_people': r.number_of_people,
            'age_ranges': [member.get_age_range_display() for member in r.members.all()],
            'status': r.status,
            'is_preferred_coach': bool(r.is_preferred_coach),
            'shared_class_id': r.shared_course_class_id,
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
        reservation__group__client=request.tenant,
        reservation__status__in=SCHEDULED_RESERVATION_STATUSES,
    ).select_related(
        'reservation',
        'reservation__resort',
        'reservation__course_type',
        'reservation__preferred_coach',
        'reservation__group__user',
    ).distinct().order_by('date', 'start_time')
    qs = _with_current_schedule_payment(qs, 'reservation__group_id')

    if not full_schedule_visible:
        qs = qs.filter(date__lte=visible_end)

    query_start, query_end = _query_date_bounds(request)
    if query_start:
        qs = qs.filter(date__gte=query_start)
    if query_end:
        qs = qs.filter(date__lte=query_end)
    if full_schedule_visible:
        equipment_start = query_start
        equipment_end = query_end
    else:
        equipment_start = query_start
        equipment_end = min([d for d in [visible_end, query_end] if d])

    items = []
    for b in qs:
        user_name = _reservation_user_alias(b.reservation)
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
        tenant=request.tenant,
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
            'reviewed_at': timezone.localtime(l.reviewed_at).strftime('%Y-%m-%d %H:%M') if l.reviewed_at else None,
            'created_at': timezone.localtime(l.created_at).strftime('%Y-%m-%d %H:%M'),
            'affected_count': l.affected_reservations.count(),
        })
    return Response({'code': 200, 'msg': 'OK', 'data': {'list': items, 'total': len(items)}})


def _coach_leave_policy(request, coach, campus_id):
    campus = None
    if campus_id not in (None, ''):
        value = str(campus_id)
        if isinstance(campus_id, bool) or not value.isascii() or not value.isdecimal() or len(value) > 19 or not 0 < int(value) <= 9223372036854775807:
            raise ValueError('校區編號格式不正確')
        campus = coach.campuses.filter(id=int(value), client=request.tenant).first()
        if not campus:
            raise ValueError('請選擇您所屬的校區')
    elif coach.campuses.count() == 1:
        campus = coach.campuses.first()
    policy = (OperatingPolicy.objects.filter(client=request.tenant, campus=campus).first() if campus else None)
    policy = policy or OperatingPolicy.objects.filter(client=request.tenant, campus__isnull=True).first()
    return campus, policy or OperatingPolicy(client=request.tenant)


@api_view(['GET', 'POST'])
@permission_classes([IsTenantCoach])
@transaction.atomic
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

    today = timezone.localdate()
    try:
        campus, policy = _coach_leave_policy(request, coach,
            request.query_params.get('campus_id') if request.method == 'GET' else request.data.get('campus_id'))
    except ValueError as exc:
        return Response({'code': 400, 'msg': str(exc)}, status=400)
    if request.method == 'GET':
        from django.middleware.csrf import get_token
        get_token(request._request)
        return Response({'code': 200, 'data': {
            'today': today.isoformat(), 'minimum_start_date': (today+timedelta(days=policy.leave_advance_days)).isoformat(),
            'leave_advance_days': policy.leave_advance_days,
            'leave_max_consecutive_days': policy.leave_max_consecutive_days,
            'leave_daily_coach_limit': policy.leave_daily_coach_limit,
        }})

    from rest_framework.authentication import SessionAuthentication
    SessionAuthentication().enforce_csrf(request)
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    raw_reason = request.data.get('reason')
    if not isinstance(start_date, str) or not isinstance(end_date, str) or not isinstance(raw_reason, str):
        return Response({'code': 400, 'msg': '日期及請假原因格式不正確'}, status=400)
    reason = raw_reason.strip()
    if len(reason) > 1000:
        return Response({'code': 400, 'msg': '請假原因最多1000字'}, status=400)

    if not start_date or not end_date or not reason:
        return Response({'code': 400, 'msg': '請填寫完整資料'}, status=400)

    # 日期驗證
    from datetime import datetime
    try:
        sd = datetime.strptime(start_date, '%Y-%m-%d').date()
        ed = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return Response({'code': 400, 'msg': '日期格式錯誤（YYYY-MM-DD）'}, status=400)

    if sd < today:
        return Response({'code': 400, 'msg': '不能申請過去的日期'}, status=400)
    if ed < sd:
        return Response({'code': 400, 'msg': '結束日期不能早於開始日期'}, status=400)

    leave_days = (ed - sd).days + 1
    if (sd - today).days < policy.leave_advance_days:
        return Response({
            'code': 400,
            'msg': f'請假需至少提前 {policy.leave_advance_days} 天；緊急狀況請聯絡主管代為核准',
        }, status=400)
    if leave_days > policy.leave_max_consecutive_days:
        return Response({
            'code': 400,
            'msg': f'一般申請最多連續 {policy.leave_max_consecutive_days} 天；較長假期請聯絡主管特別核准',
        }, status=400)

    day = sd
    while day <= ed:
        daily_leaves = CoachLeaveRequest.objects.filter(
            coach__client=request.tenant,
            status__in=['pending', 'approved'],
            start_date__lte=day,
            end_date__gte=day,
        )
        if campus:
            daily_leaves = daily_leaves.filter(coach__campuses=campus)
        if daily_leaves.values('coach_id').distinct().count() >= policy.leave_daily_coach_limit:
            return Response({
                'code': 400,
                'msg': f'{day} 已達每日 {policy.leave_daily_coach_limit} 位教練請假上限，請改選日期或聯絡主管',
            }, status=400)
        day += timedelta(days=1)

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
        group__client=request.tenant,
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

@api_view(['GET', 'POST'])
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
    from .manual_notifications import require_target_permission, scoped_groups
    from .order_email_notifications import OrderEmailInput, deliver_order_email, prepare_email, mail_mode
    require_target_permission(request, 'order')
    group = scoped_groups(request).filter(pk=order_id).select_related('user', 'campus').first()
    if group is None:
        return Response({'code': 404, 'msg': '找不到目前校區範圍內的訂單'}, status=404)
    if request.method == 'GET':
        return Response({'code': 200, 'data': mail_mode()})
    serializer = OrderEmailInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    delivery_id = prepare_email(request, group, serializer.validated_data)
    response_status, response = deliver_order_email(delivery_id)
    return Response(response, status=response_status)

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

    tenant = _resolve_tenant(request, None)
    if not tenant:
        return Response({'code': 404, 'msg': '找不到公司資料'}, status=404)

    is_superuser = request.user.is_superuser
    is_manager = False
    is_coach = False
    role = ''
    assigned_campus_ids = []
    tenant_coach = Coach.objects.filter(user=request.user, client=tenant).first()

    try:
        profile = request.user.userprofile
        is_manager = bool(profile.is_manager and profile.manager_client_id == tenant.pk)
        is_coach = bool(profile.is_coach and tenant_coach)
        role = profile.role if is_manager else ('coach' if is_coach else '')
        if is_manager:
            assigned_campus_ids = list(profile.campuses.filter(client=tenant).values_list('id', flat=True))
    except Exception:
        pass

    accessible_campuses, can_view_all = _campus_scope_for_user(request.user, tenant)
    campus_items = list(accessible_campuses.values('id', 'name', 'code', 'is_active'))
    if is_manager and not is_superuser and (
        not get_user_admin_permissions(request.user) or (not can_view_all and not campus_items)
    ):
        is_manager = False
        role = 'coach' if is_coach else ''
        assigned_campus_ids = []
    if is_coach and not is_manager and not is_superuser:
        campus_items = list(tenant_coach.campuses.filter(client=tenant, is_active=True).values('id', 'name', 'code', 'is_active'))
        can_view_all = False
        assigned_campus_ids = [campus['id'] for campus in campus_items]
    if not (is_superuser or is_manager or is_coach):
        return Response({'code': 403, 'msg': '此帳號沒有本公司可用的後台權限，請聯絡總部確認角色與校區指派'}, status=403)

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
            'role': role,
            'assigned_campus_ids': assigned_campus_ids,
            'campuses': campus_items,
            'can_view_all_campuses': can_view_all,
            'permissions': get_user_admin_permissions(request.user) if (is_superuser or is_manager) else [],
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
    if request.method == 'PUT' and not getattr(request, 'can_view_all_campuses', False):
        raise PermissionDenied('全公司付款設定只能由總部管理員修改')
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
