"""Private contact messages are never stored in the public SiteContent CMS."""
import logging
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from .models import ContactInboxSettings, ContactMessage

logger = logging.getLogger(__name__)


def send_contact_notification(message_id):
    # Serialize the claim: refresh/repeated submits cannot send the same notice twice.
    with transaction.atomic():
        row = ContactMessage.objects.select_for_update().get(pk=message_id)
        if row.notification_status != 'pending':
            return
        config = ContactInboxSettings.objects.filter(client_id=row.client_id).first()
        if not config or not config.notify_enabled or not config.notify_emails:
            row.notification_status = 'off'
        else:
            try:
                # No visitor contact details or message text leave the private inbox.
                email = EmailMessage(
                    subject=f'SnowLand 網站新留言 #{row.pk}',
                    body='網站收到一則新留言。請登入後台 → 營運管理 → 聯絡收件，查看並處理。',
                    from_email=settings.DEFAULT_FROM_EMAIL, to=list(config.notify_emails),
                    connection=get_connection(timeout=10),
                )
                row.notification_status = 'sent' if email.send() == 1 else 'failed'
            except Exception:
                row.notification_status = 'failed'
                logger.warning('Contact notification failed message_id=%s', row.pk)
        row.save(update_fields=['notification_status'])
