"""Reviewed alumni status and historical-point totals; no automatic reward rules."""
from django.db import transaction
from django.middleware.csrf import get_token
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from django.contrib.auth.models import User

from booking.models import MemberLoyaltyAccount, MemberLoyaltyReview, ReservationGroup
from .admin_views import IsTenantManager, _require_admin_permission, _campus_ids


def visible_customer_ids(request):
    groups = ReservationGroup.objects.filter(client=request.tenant)
    scoped = not request.can_view_all_campuses or request.selected_campus_id is not None
    if scoped:
        groups = groups.filter(campus_id__in=_campus_ids(request))
    ids = groups.exclude(user=None).values_list('user_id', flat=True)
    if scoped:
        return set(ids)
    # A returning student must be reviewable before placing their first new order.
    return set(ids) | set(MemberLoyaltyAccount.objects.filter(client=request.tenant).values_list('user_id', flat=True))


def can_review_loyalty(user):
    return user.is_superuser or getattr(getattr(user, 'userprofile', None), 'role', '') == 'hq_admin'


def loyalty_snapshot(account):
    return {name: getattr(account, name) for name in ('points', 'previous_points', 'alumni_verified', 'level')}


def loyalty_payload(account):
    return {**loyalty_snapshot(account), 'updated_at': account.updated_at.isoformat()}


class WholePoints(serializers.IntegerField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not str(data).isascii() or not str(data).isdecimal():
            self.fail('invalid')
        return super().to_internal_value(data)


class ReviewInput(serializers.Serializer):
    alumni_verified = serializers.BooleanField(required=True)
    previous_points = WholePoints(min_value=0, max_value=2147483647)
    reason = serializers.CharField(max_length=1000)
    expected_updated_at = serializers.CharField(max_length=50)


@api_view(['GET', 'POST'])
@permission_classes([IsTenantManager])
def customer_loyalty(request, client_code, user_id):
    denied = _require_admin_permission(request, 'customers')
    if denied:
        return denied
    if not can_review_loyalty(request.user):
        raise PermissionDenied('只有總部管理員可以審核舊生與補登點數')
    if user_id not in visible_customer_ids(request):
        return Response({'msg': '找不到目前範圍內的會員'}, status=404)
    if request.method == 'GET':
        get_token(request._request)
    else:
        SessionAuthentication().enforce_csrf(request)
    with transaction.atomic():
        # Serialize initial creation as well as subsequent edits on this user.
        User.objects.select_for_update().get(pk=user_id)
        account, _ = MemberLoyaltyAccount.objects.get_or_create(client=request.tenant, user_id=user_id)
        account = MemberLoyaltyAccount.objects.select_for_update().get(pk=account.pk)
        if request.method == 'POST':
            form = ReviewInput(data=request.data)
            form.is_valid(raise_exception=True)
            values = form.validated_data
            if values['expected_updated_at'] != account.updated_at.isoformat():
                return Response({'msg': '會員資料已被更新，請重新載入後再審核'}, status=409)
            if not values['alumni_verified'] and values['previous_points']:
                raise ValidationError({'previous_points': '請先確認舊生身分，才能補登歷史點數'})
            new_total = account.points - account.previous_points + values['previous_points']
            if not 0 <= new_total <= 2147483647:
                raise ValidationError({'previous_points': '點數資料需要先核對，無法套用此補登總額'})
            before = loyalty_snapshot(account)
            account.alumni_verified = values['alumni_verified']
            account.previous_points = values['previous_points']
            account.points = new_total
            if account.level in ('new', 'alumni'):
                account.level = 'alumni' if account.alumni_verified else 'new'
            after = loyalty_snapshot(account)
            # No-op saves never create duplicate credits or audit entries.
            if before != after:
                account.save(update_fields=['alumni_verified', 'previous_points', 'points', 'level', 'updated_at'])
                MemberLoyaltyReview.objects.create(account=account, reviewed_by=request.user,
                    before=before, after=after, reason=values['reason'])
        history = [{'id': item.pk, 'before': item.before, 'after': item.after,
                    'reason': item.reason, 'reviewed_by': item.reviewed_by.get_full_name() or item.reviewed_by.username if item.reviewed_by else '已移除的管理員',
                    'created_at': item.created_at.isoformat()}
                   for item in account.reviews.select_related('reviewed_by')[:20]]
        return Response({'code': 200, 'msg': '已儲存' if request.method == 'POST' else 'OK',
                         'data': {**loyalty_payload(account), 'history': history}})
