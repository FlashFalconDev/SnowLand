import uuid
from copy import copy
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from booking.models import Booking, CourseEvaluation, NotificationDelivery, NotificationTemplate, Payment, ReservationGroup
from booking.operations import notification_template_matches_group, schedule_group_notifications
from booking.notification_recipients import COURSE_RECIPIENT_EVENTS, channel_recipient, course_notification_recipients, email_notification_account_ids, group_documents_missing
from booking.tasks import auto_cancel_unpaid_reservations


MISSING_PAYMENT_URL_ERROR = 'SNOWLAND_PUBLIC_PAYMENT_URL 未設定，無法寄送團體班付款連結'
INVALID_PAYMENT_URL_ERROR = 'SNOWLAND_PUBLIC_PAYMENT_URL 必須是前台 /snowland/payment 的完整網址'


class Command(BaseCommand):
    help = 'Expire unpaid orders, schedule reminders, and deliver due SnowLand notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show work without changing data or sending messages.')

    def handle(self, *args, **options):
        now = timezone.now()
        dry_run = options['dry_run']
        from Coach.payroll_review import confirm_due_statements
        payroll_confirmed = confirm_due_statements(now, dry_run=dry_run)
        expired = Payment.objects.filter(status='unpaid', expires_at__isnull=False, expires_at__lte=now)
        expired_count = expired.count()
        if not dry_run:
            auto_cancel_unpaid_reservations()

        evaluation_count = 0
        completed_groups = ReservationGroup.objects.filter(
            reservations__status='completed'
        ).prefetch_related('reservations__bookings', 'reservations__members', 'reservations__preferred_coach').distinct()
        for group in completed_groups:
            for reservation in group.reservations.filter(status='completed'):
                for booking in reservation.bookings.all():
                    for member in reservation.members.all():
                        if not CourseEvaluation.objects.filter(booking=booking, member=member).exists():
                            evaluation_count += 1
                            if not dry_run:
                                CourseEvaluation.objects.create(
                                    booking=booking, member=member, coach=reservation.preferred_coach,
                                )

        scheduled_count = 0
        events = NotificationTemplate.objects.filter(
            is_active=True,
            event__in=['pre_course', 'missing_documents', 'line_group', 'evaluation_due'],
        ).values_list('client_id', 'event').distinct()
        for client_id, event in events:
            for group in ReservationGroup.objects.filter(client_id=client_id, payments__status='paid').distinct():
                if dry_run:
                    continue
                if not self._event_is_applicable(group, event):
                    continue
                scheduled_count += len(schedule_group_notifications(group, event))

        # Include immediate notices created during this command, not only those present at startup.
        now = timezone.now()
        deliveries = NotificationDelivery.objects.filter(self._due_status(), scheduled_at__lte=now)
        sent = failed = 0
        for delivery_id in deliveries.values_list('pk', flat=True):
            delivery_sent, delivery_failed = self._deliver_due(delivery_id, now, dry_run)
            sent += delivery_sent
            failed += delivery_failed
        if not dry_run:
            from booking.amendment_notifications import dispatch_pending_amendment_notices
            amendment_sent,amendment_failed=dispatch_pending_amendment_notices()
            sent+=amendment_sent;failed+=amendment_failed

        mode = 'DRY RUN' if dry_run else 'DONE'
        # Reuse this deployment-owned job instead of creating a second scheduler.
        # Authorization is opt-in and each connection checks its hourly due time.
        if not dry_run:
            from Client.models import InstagramConnection
            from Client.instagram_sync import InstagramError, run_sync
            for connection_id in InstagramConnection.objects.filter(enabled=True).values_list('pk', flat=True):
                try:
                    run_sync(connection_id, due_only=True)
                except InstagramError:
                    self.stderr.write('Instagram sync failed; see the headquarters social-sync page. Other jobs continue.')
        self.stdout.write(self.style.SUCCESS(
            f'{mode}: expired={expired_count}, evaluations={evaluation_count}, scheduled={scheduled_count}, sent={sent}, failed={failed}, payroll_confirmed={payroll_confirmed}'
        ))

    @staticmethod
    def _due_status():
        delivery_status = Q(status='scheduled')
        if settings.SNOWLAND_PUBLIC_PAYMENT_URL:
            delivery_status |= Q(
                status='failed', template__event='shared_class_ready',
                error_message__startswith='SNOWLAND_PUBLIC_PAYMENT_URL',
            )
        return delivery_status

    @transaction.atomic
    def _deliver_due(self, delivery_id, now, dry_run):
        # A second worker may have scanned this ID before the first worker sent it.
        # Lock and recheck current state before calling any external transport.
        delivery = NotificationDelivery.objects.select_for_update().filter(
            self._due_status(), pk=delivery_id, scheduled_at__lte=now,
        ).first()
        if delivery is None:
            return 0, 0
        return self._send_delivery(delivery, now, dry_run)

    def _send_delivery(self, delivery, now, dry_run):
        if (delivery.payload or {}).get('repeat_of') and (
            delivery.template.event != 'missing_documents' or not delivery.template.repeat_interval_days
        ):
            if not dry_run:
                delivery.status = 'cancelled'
                delivery.save(update_fields=['status'])
            return 0, 0
        repeat_of = (delivery.payload or {}).get('repeat_of')
        if repeat_of:
            previous = NotificationDelivery.objects.filter(pk=repeat_of, template_id=delivery.template_id,
                group_id=delivery.group_id, recipient=delivery.recipient, status='sent').first()
            if not previous:
                if not dry_run:
                    delivery.status = 'cancelled'
                    delivery.save(update_fields=['status'])
                return 0, 0
            from datetime import timedelta
            next_reminder = (previous.sent_at or previous.scheduled_at) + timedelta(days=delivery.template.repeat_interval_days)
            if next_reminder > now:
                if not dry_run:
                    delivery.scheduled_at = next_reminder
                    delivery.save(update_fields=['scheduled_at'])
                return 0, 0
        if not notification_template_matches_group(delivery.template, delivery.group):
            if not dry_run:
                delivery.status = 'cancelled'
                delivery.save(update_fields=['status'])
            return 0, 0
        if delivery.template.event == 'shared_class_ready' and not self._event_is_applicable(delivery.group, 'shared_class_ready'):
            if not dry_run:
                delivery.status = 'cancelled'
                delivery.save(update_fields=['status'])
            return 0, 0
        if delivery.template.event in {'pre_course', 'missing_documents', 'line_group', 'evaluation_due'}:
            latest_payment = delivery.group.payments.order_by('-created_at', '-pk').first()
            if not latest_payment or latest_payment.status != 'paid':
                if not dry_run and latest_payment and latest_payment.status in {'refunded', 'expired'}:
                    delivery.status = 'cancelled'
                    delivery.save(update_fields=['status'])
                return 0, 0
            if delivery.template.event in COURSE_RECIPIENT_EVENTS:
                recipients = course_notification_recipients(delivery.group, delivery.template)
                context = recipients.get(channel_recipient(delivery.template.channel, delivery.recipient))
                if not context:
                    if not dry_run:
                        delivery.status = 'cancelled'
                        delivery.save(update_fields=['status'])
                    return 0, 0
                # Refresh recipient audience at send-time; never render another person's saved name.
                delivery.payload = {**context['payload'], **(
                    {'repeat_of': delivery.payload['repeat_of']} if (delivery.payload or {}).get('repeat_of') else {}
                )}
            if not self._event_is_applicable(delivery.group, delivery.template.event):
                return 0, 0
        if dry_run:
            return 1, 0
        try:
            from booking.group_qr_notifications import body_with_group_qr, notification_qr_name, send_inline_group_qr
            body = self._render(delivery.template.body, delivery)
            body = body_with_group_qr(body, delivery)
            subject = self._render(delivery.template.subject, delivery)
            if notification_qr_name(delivery):
                delivery.payload = {**(delivery.payload or {}), 'in_app_group_qr_name': notification_qr_name(delivery)}
            if delivery.template.channel == 'email':
                delivered = send_inline_group_qr(subject, body, delivery)
                if delivered is None:
                    delivered = send_mail(subject or 'SnowLand 通知', body, settings.DEFAULT_FROM_EMAIL, [delivery.recipient])
                if delivered != 1:
                    raise RuntimeError('郵件服務未確認送出，請檢查發送紀錄')
            elif delivery.template.channel == 'line':
                from chatbooking.line import LineMessagingClient
                retry_key = uuid.uuid5(uuid.NAMESPACE_URL, f'snowland-notification-{delivery.pk}')
                LineMessagingClient().push(delivery.recipient, body, retry_key=retry_key)
            elif delivery.template.channel == 'in_app':
                delivery.payload = {**(delivery.payload or {}), 'in_app_subject': subject or 'SnowLand 通知',
                                    'in_app_body': body, 'in_app_group_url': delivery.group.line_group_url or ''}
            delivery.status = 'sent'
            delivery.sent_at = now
            delivery.error_message = ''
            delivery.save(update_fields=['status', 'sent_at', 'error_message', 'payload'])
            if delivery.template.channel == 'email':
                self._sync_email_in_app(delivery, subject, body, now)
            return 1, 0
        except Exception as exc:
            delivery.status = 'failed'
            delivery.error_message = str(exc)[:1000]
            delivery.save(update_fields=['status', 'error_message'])
            return 0, 1

    @staticmethod
    @transaction.atomic
    def _sync_email_in_app(delivery, subject, body, now):
        # The caller holds the source delivery lock. Keep a separate read state for each account.
        for user_id in email_notification_account_ids(delivery):
            recipient = str(user_id)
            if NotificationDelivery.objects.filter(template=delivery.template, group=delivery.group,
                recipient=recipient, payload__in_app_mirror_of=delivery.pk).exists():
                continue
            member_subject, member_body = subject, body
            participant = user_id != delivery.group.user_id
            if participant and (delivery.payload or {}).get('audience') != 'participant':
                # A shared contact email can represent several bound accounts; each gets their own greeting.
                member_delivery = copy(delivery)
                member_delivery.payload = {**(delivery.payload or {}), 'audience': 'participant'}
                member_subject = Command._render(delivery.template.subject, member_delivery)
                member_body = Command._render(delivery.template.body, member_delivery)
                from booking.group_qr_notifications import body_with_group_qr
                member_body = body_with_group_qr(member_body, member_delivery)
            NotificationDelivery.objects.create(template=delivery.template, group=delivery.group,
                recipient=recipient, scheduled_at=now, sent_at=now, status='sent', payload={
                    'in_app_mirror_of': delivery.pk,
                    'in_app_subject': member_subject or 'SnowLand 通知', 'in_app_body': member_body,
                    'in_app_group_url': delivery.group.line_group_url or '',
                    'in_app_group_qr_name': (delivery.payload or {}).get('in_app_group_qr_name', ''),
                    **({'audience': 'participant'} if participant else {}),
                })

    @staticmethod
    def _event_is_applicable(group, event):
        if event == 'shared_class_ready':
            return group.payments.filter(status='unpaid').exists() and group.reservations.filter(
                shared_course_class__status='ready',
            ).exclude(status__in=['cancelled', 'deleted']).exists()
        if event in {'pre_course', 'missing_documents', 'line_group'} and not Booking.objects.filter(
            reservation__group=group, date__gte=timezone.localdate(),
        ).exclude(reservation__status__in=['cancelled', 'deleted']).exists():
            return False
        if event == 'line_group':
            return bool(group.line_group_url or group.line_group_qr)
        if event == 'evaluation_due':
            return CourseEvaluation.objects.filter(
                booking__reservation__group=group,
                booking__reservation__status='completed',
                completed_at__isnull=True,
            ).exists()
        if event == 'missing_documents':
            return group_documents_missing(group)
        return True

    @staticmethod
    def _render(text, delivery):
        from booking.payment_access import payment_url_for_group

        payment_url = ''
        if delivery.template.event == 'shared_class_ready':
            public_url = settings.SNOWLAND_PUBLIC_PAYMENT_URL
            if not public_url:
                raise ValueError(MISSING_PAYMENT_URL_ERROR)
            from booking.payment_access import school_payment_base_url
            try:
                public_url = school_payment_base_url(delivery.group.client)
            except ValueError as exc:
                raise ValueError(INVALID_PAYMENT_URL_ERROR) from exc
            payment_url = payment_url_for_group(public_url, delivery.group)
        values = {
            'order_number': delivery.group.order_number,
            'customer_name': '學員／家長' if (delivery.payload or {}).get('audience') == 'participant' else delivery.group.name or '',
            'campus_name': delivery.group.campus.name if delivery.group.campus else '',
            'line_group_url': delivery.group.line_group_url or '',
            'payment_url': payment_url,
        }
        rendered = str(text or '')
        for key, value in values.items():
            rendered = rendered.replace('{' + key + '}', str(value))
        return rendered
