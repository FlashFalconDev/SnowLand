"""Order-scoped manual mail with an audit receipt and safe, explicitly related inbox copies."""
import hashlib
import json
import uuid

from django.db import IntegrityError, transaction
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from Client.models import Client
from booking.models import MemberDetail, NotificationDelivery, NotificationTemplate
from booking.notification_recipients import channel_recipient
from .manual_notifications import NotificationConflict


class OrderEmailInput(serializers.Serializer):
    recipient_email = serializers.EmailField(max_length=200, error_messages={'invalid': '請填寫正確的 Email 地址'})
    subject = serializers.CharField(max_length=200, error_messages={'blank': '請填寫郵件主旨'})
    message = serializers.CharField(max_length=10000, error_messages={'blank': '請填寫郵件內容'})
    request_key = serializers.UUIDField(required=False)


def mail_mode():
    local_test = settings.EMAIL_BACKEND in {'django.core.mail.backends.console.EmailBackend',
        'django.core.mail.backends.locmem.EmailBackend', 'django.core.mail.backends.filebased.EmailBackend',
        'django.core.mail.backends.dummy.EmailBackend'}
    return {'local_test': local_test}


def sync_accounts(group, recipient):
    recipient = channel_recipient('email', recipient)
    owner = group.user
    payment = group.payments.order_by('-created_at', '-pk').first()
    info = payment.DataJSON if payment and isinstance(payment.DataJSON, dict) else {}
    contact = info.get('contact') if isinstance(info.get('contact'), dict) else {}
    booking_contact = group.booking_contact if isinstance(group.booking_contact, dict) else {}
    owner_addresses = {channel_recipient('email', value) for value in [getattr(owner, 'email', ''),
                       contact.get('email'), booking_contact.get('email')]}
    # This is an order-contact mail, not an invitation to claim another account with the same address.
    if owner and owner.is_active and recipient in owner_addresses:
        return [owner.pk]
    users = {}
    for member in MemberDetail.objects.filter(reservation__group=group).exclude(reservation__status='deleted').select_related('user', 'guardian'):
        for user in [member.user, member.guardian]:
            if user and user.is_active and channel_recipient('email', user.email) == recipient:
                users[user.pk] = user
    # Ambiguous shared mailboxes must use the explicit member selector instead of exposing private mail.
    return list(users) if len(users) == 1 else []


@transaction.atomic
def prepare_email(request, group, data):
    Client.objects.select_for_update().get(pk=request.tenant.pk)
    key = data.get('request_key') or uuid.uuid4()  # Older clients remain compatible; the current UI always supplies a key.
    recipient = channel_recipient('email', data['recipient_email'])
    fingerprint = hashlib.sha256(json.dumps({'actor': request.user.pk, 'group': group.pk,
        'recipient': recipient, 'subject': data['subject'], 'message': data['message']}, sort_keys=True).encode()).hexdigest()
    template = NotificationTemplate.objects.filter(manual_key=key).first()
    if template:
        delivery = template.deliveries.filter(group=group, recipient=recipient).first()
        if template.client_id != request.tenant.pk or not delivery or delivery.payload.get('email_fingerprint') != fingerprint:
            raise NotificationConflict('此寄信識別碼已使用，請重新開啟寄信視窗')
        return delivery.pk
    body = f"{data['message']}\n\n──────────────────────────\n{request.tenant.name}\n此郵件為系統自動發送，請勿直接回覆。\n"
    try:
        with transaction.atomic():
            template = NotificationTemplate.objects.create(client=request.tenant, campus=group.campus,
                manual_key=key, name=data['subject'][:100], event='manual', channel='email',
                subject=data['subject'], body=body, is_active=False)
    except IntegrityError:
        raise NotificationConflict('此寄信識別碼已使用，請重新開啟寄信視窗')
    return NotificationDelivery.objects.create(template=template, group=group, recipient=recipient,
        scheduled_at=timezone.now(), status='sending', payload={'email_fingerprint': fingerprint,
            'created_by': request.user.pk, 'intended_account_ids': sync_accounts(group, recipient),
            'local_test': mail_mode()['local_test']}).pk


def result_for(delivery, *, duplicate=False):
    if delivery.status == 'sent':
        count = NotificationDelivery.objects.filter(payload__in_app_mirror_of=delivery.pk).count()
        message = f'Email 已寄出，已同步 {count} 位會員的站內通知' if count else 'Email 已寄出；收件信箱無法唯一對應本訂單會員，未建立站內副本'
        if delivery.payload.get('local_test'):
            message = f'已完成本機郵件測試（未對外寄送），同步 {count} 位會員的站內通知'
        return 200, {'code': 200, 'msg': message, 'data': {'delivery_id': delivery.pk, 'synced_count': count, 'duplicate': duplicate}}
    if delivery.status == 'failed':
        return 502, {'code': 502, 'msg': '郵件服務未確認送出。請先核對發送紀錄，避免重複寄信；需要重寄時請重新開啟寄信視窗。'}
    if delivery.status == 'cancelled':
        return 409, {'code':409,'msg':'通知已停止寄送，請以最新訂單狀態為準。'}
    return 202, {'code': 202, 'msg': '仍在發送或結果待確認；請稍後查詢，不會重複寄送。'}


def deliver_order_email(delivery_id):
    with transaction.atomic():
        delivery = NotificationDelivery.objects.select_for_update().select_related('template','group__user').get(pk=delivery_id)
        if delivery.status != 'sending' or delivery.payload.get('email_claimed'):
            return result_for(delivery, duplicate=True)
        if delivery.payload.get('amendment_notice'):
            from booking.amendment_notifications import amendment_delivery_is_current
            if not amendment_delivery_is_current(delivery):
                delivery.status='cancelled';delivery.error_message='訂購人或差額狀態已更新，不寄送過期通知'
                delivery.save(update_fields=['status','error_message'])
                return result_for(delivery)
        delivery.payload = {**delivery.payload, 'email_claimed': True}
        delivery.save(update_fields=['payload'])
    # No database locks are held across SMTP. A crashed process remains "result unconfirmed", never auto-resends.
    try:
        from booking.scheduler import send_gmail
        if send_gmail(delivery.template.subject, delivery.template.body, delivery.recipient) != 'ok':
            raise RuntimeError('mail not confirmed')
    except Exception:
        with transaction.atomic():
            delivery = NotificationDelivery.objects.select_for_update().get(pk=delivery_id)
            delivery.status = 'failed'
            delivery.error_message = '郵件服務未確認送出，請核對紀錄後再決定是否重寄'
            delivery.save(update_fields=['status', 'error_message'])
        return result_for(delivery)
    with transaction.atomic():
        delivery = NotificationDelivery.objects.select_for_update().select_related('template', 'group__user').get(pk=delivery_id)
        now = timezone.now()
        delivery.status = 'sent'; delivery.sent_at = now; delivery.error_message = ''
        delivery.save(update_fields=['status', 'sent_at', 'error_message'])
        current = set(sync_accounts(delivery.group, delivery.recipient))
        for user_id in current.intersection(delivery.payload.get('intended_account_ids', [])):
            NotificationDelivery.objects.create(template=delivery.template, group=delivery.group, recipient=str(user_id),
                status='sent', scheduled_at=now, sent_at=now, payload={'in_app_mirror_of': delivery.pk,
                    'in_app_subject': delivery.template.subject, 'in_app_body': delivery.template.body, 'in_app_group_url': '',
                    'insurance_reminder_reservation_id': delivery.payload.get('insurance_reminder_reservation_id'),
                    'local_test': delivery.payload.get('local_test', False)})
    return result_for(delivery)
