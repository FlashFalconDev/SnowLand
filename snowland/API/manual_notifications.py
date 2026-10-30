from Control.tenant_memberships import staff_profile, writable_staff_profile
"""Explicit, audited in-app messages. Never invokes Email/LINE or the global job runner."""
import re
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from Client.models import Client
from booking.models import MemberDetail, NotificationDelivery, NotificationTemplate, ReservationGroup
from .admin_permissions import user_has_admin_permission


class NotificationConflict(APIException):
    status_code = 409
    default_detail = '通知資料已改變，請重新預覽後再發送'


class ManualNotificationInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['order', 'member'])
    target_id = serializers.IntegerField(min_value=1)
    audience = serializers.ChoiceField(choices=['owner', 'participants'], default='owner')
    subject = serializers.CharField(max_length=200, trim_whitespace=True)
    body = serializers.CharField(max_length=10000, trim_whitespace=True)
    request_key = serializers.UUIDField(required=False)
    expected_recipient_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, allow_empty=False)

    def validate(self, attrs):
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError('不支援此通知欄位；此功能只發送站內通知')
        if attrs['kind'] == 'member' and attrs['audience'] != 'owner':
            raise serializers.ValidationError('會員通知只能發給所選會員')
        return attrs


def scoped_groups(request):
    groups = ReservationGroup.objects.filter(client=request.tenant)
    if not request.can_view_all_campuses or request.selected_campus_id is not None:
        groups = groups.filter(campus_id__in=request.campus_ids)
    return groups


def allowed_members(request):
    groups = scoped_groups(request)
    members = MemberDetail.objects.filter(reservation__group__in=groups).exclude(reservation__status='deleted')
    return User.objects.filter(is_active=True).filter(
        Q(pk__in=groups.values('user_id')) | Q(pk__in=members.values('user_id'))
        | Q(pk__in=members.values('guardian_id')),
    ).distinct()


def require_target_permission(request, kind):
    if kind not in {'order', 'member'}:
        raise serializers.ValidationError({'kind': '請選訂單或會員'})
    key = 'orders' if kind == 'order' else 'customers'
    if not user_has_admin_permission(request.user, key, getattr(request, 'tenant', None)):
        raise PermissionDenied('需要訂單管理權限' if kind == 'order' else '需要會員管理權限')
    profile = staff_profile(request.user, getattr(request, 'tenant', None))
    if not request.user.is_superuser and profile and profile.role in {'campus_principal', 'campus_manager'}:
        raise PermissionDenied('校區人員僅能查看訂單摘要，請由行政人員發送通知')


def target_options(request, kind, query):
    require_target_permission(request, kind)
    query = str(query or '').strip()[:100]
    if kind == 'order':
        rows = scoped_groups(request)
        if query:
            filters = Q(order_number__icontains=query) | Q(name__icontains=query) | Q(user__username__icontains=query) | Q(user__email__icontains=query)
            match = re.fullmatch(r'(?:\d{8}-|SL-\d{8}-)?(\d+)', query)
            if match and len(match.group(1)) < 19:
                filters |= Q(pk=int(match.group(1)))
            rows = rows.filter(filters)
        return [{'id': row.pk, 'label': f'{order_label(row)} · {row.name or "訂購人"}'}
                for row in rows.order_by('-pk')[:30]]
    rows = allowed_members(request)
    if query:
        rows = rows.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(email__icontains=query))
    return [{'id': row.pk, 'label': f'{row.get_full_name() or row.username} · {row.email or "未填信箱"}'}
            for row in rows.order_by('-pk')[:30]]


def order_label(group):
    from .admin_serializers import OrderAdminSerializer
    return OrderAdminSerializer().get_sn(group)


def resolve_target(request, data):
    require_target_permission(request, data['kind'])
    group = None
    if data['kind'] == 'order':
        group = scoped_groups(request).filter(pk=data['target_id']).first()
        if group is None:
            raise NotFound('找不到目前範圍內的訂單，請重新選擇')
        ids = {group.user_id} if group.user_id else set()
        if data['audience'] == 'participants':
            for member in MemberDetail.objects.filter(reservation__group=group).exclude(reservation__status__in=['cancelled', 'deleted']):
                ids.update([member.user_id, member.guardian_id])
        users = list(User.objects.filter(pk__in=ids - {None}, is_active=True).order_by('pk'))
        label = order_label(group)
        campus_id = group.campus_id
    else:
        user = allowed_members(request).filter(pk=data['target_id']).first()
        if user is None:
            raise NotFound('找不到目前範圍內的會員，請重新選擇')
        users = [user]
        label = user.get_full_name() or user.username
        campus_id = request.selected_campus_id
        if not request.can_view_all_campuses and campus_id is None:
            campus_id = next(iter(sorted(request.campus_ids)), None)
    if not users:
        raise serializers.ValidationError({'target_id': '沒有可接收站內通知的會員帳號；請先完成會員綁定'})
    return group, users, label, campus_id


def preview_notification(request, data):
    group, users, label, campus_id = resolve_target(request, data)
    return {'target_label': label, 'subject': data['subject'], 'body': data['body'],
            'recipients': [{'id': user.pk, 'name': user.get_full_name() or user.username} for user in users],
            'count': len(users)}


@transaction.atomic
def send_manual_notification(request, data):
    if not data.get('request_key') or not data.get('expected_recipient_ids'):
        raise serializers.ValidationError('請先預覽收件人，再確認發送')
    # Serialize only this tenant's tiny local publish transaction; no external transport under the lock.
    Client.objects.select_for_update().get(pk=request.tenant.pk)
    group, users, label, campus_id = resolve_target(request, data)
    ids = [user.pk for user in users]
    signature = {'kind': data['kind'], 'target_id': data['target_id'], 'audience': data['audience'],
                 'created_by': request.user.pk, 'recipient_ids': sorted(set(data['expected_recipient_ids']))}
    existing = NotificationTemplate.objects.filter(manual_key=data['request_key']).first()
    if existing:
        first = existing.deliveries.order_by('pk').first()
        if (existing.client_id != request.tenant.pk or existing.subject != data['subject']
                or existing.body != data['body'] or not first or first.payload.get('manual_request') != signature):
            raise NotificationConflict('此發送識別碼已使用，請重新預覽')
        return {'count': existing.deliveries.count(), 'duplicate': True, 'ids': list(existing.deliveries.values_list('pk', flat=True))}
    if signature['recipient_ids'] != ids:
        raise NotificationConflict('收件人已變更，請重新預覽後再發送')
    try:
        with transaction.atomic():
            template = NotificationTemplate.objects.create(client=request.tenant, campus_id=campus_id,
                manual_key=data['request_key'], name=data['subject'][:100], event='manual', channel='in_app',
                subject=data['subject'], body=data['body'], is_active=False)
    except IntegrityError:
        raise NotificationConflict('此發送識別碼已使用，請重新預覽')
    now = timezone.now()
    rows = [NotificationDelivery.objects.create(template=template, group=group, recipient=str(user.pk),
        status='sent', scheduled_at=now, sent_at=now, payload={
            'in_app_subject': data['subject'], 'in_app_body': data['body'], 'in_app_group_url': '',
            'manual_request': signature,
        }) for user in users]
    return {'count': len(rows), 'duplicate': False, 'ids': [row.pk for row in rows]}
