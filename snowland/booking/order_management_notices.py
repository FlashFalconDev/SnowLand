import uuid
from functools import partial

from django.db import transaction
from django.utils import timezone

from .models import NotificationDelivery, NotificationTemplate
from .notification_recipients import channel_recipient


def prepare_management_notice(group, *, event, event_id, subject, instruction):
    """Record the staff-only receipt under the caller's order lock, then send on commit."""
    from API.order_email_notifications import deliver_order_email, mail_mode

    recipient = channel_recipient('email', group.client.order_management_email)
    if not recipient:
        return
    key = uuid.uuid5(uuid.NAMESPACE_URL, f'snowland-management:{group.pk}:{event}:{event_id}')
    template, _ = NotificationTemplate.objects.get_or_create(manual_key=key, defaults={
        'client_id': group.client_id,
        'campus_id': group.campus_id,
        'event': 'manual',
        'channel': 'email',
        'name': subject,
        'subject': subject,
        'body': f'訂單：{group.order_number or group.pk}\n{instruction}',
        'is_active': False,
    })
    delivery, created = NotificationDelivery.objects.get_or_create(template=template, group=group, defaults={
        'recipient': recipient,
        'status': 'sending',
        'scheduled_at': timezone.now(),
        'payload': {'intended_account_ids': [], 'management_event': event, **mail_mode()},
    })
    if created:
        transaction.on_commit(partial(deliver_order_email, delivery.pk), robust=True)
