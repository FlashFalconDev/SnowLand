import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.models import CourseEvaluation, NotificationDelivery, NotificationTemplate, Payment, ReservationGroup
from booking.operations import schedule_group_notifications


class Command(BaseCommand):
    help = 'Expire unpaid orders, schedule reminders, and deliver due SnowLand notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show work without changing data or sending messages.')

    def handle(self, *args, **options):
        now = timezone.now()
        dry_run = options['dry_run']
        expired = Payment.objects.filter(status='unpaid', expires_at__isnull=False, expires_at__lte=now)
        expired_count = expired.count()
        if not dry_run:
            expired.update(status='expired', updated_at=now)

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
            for group in ReservationGroup.objects.filter(client_id=client_id).exclude(payments__status='expired').distinct():
                if dry_run:
                    continue
                scheduled_count += len(schedule_group_notifications(group, event))

        deliveries = NotificationDelivery.objects.filter(status='scheduled', scheduled_at__lte=now).select_related(
            'template', 'group', 'group__campus'
        )
        sent = failed = 0
        for delivery in deliveries:
            if dry_run:
                sent += 1
                continue
            try:
                body = self._render(delivery.template.body, delivery)
                subject = self._render(delivery.template.subject, delivery)
                if delivery.template.channel == 'email':
                    send_mail(subject or 'SnowLand 通知', body, settings.DEFAULT_FROM_EMAIL, [delivery.recipient])
                elif delivery.template.channel == 'line':
                    from chatbooking.line import LineMessagingClient
                    retry_key = uuid.uuid5(uuid.NAMESPACE_URL, f'snowland-notification-{delivery.pk}')
                    LineMessagingClient().push(delivery.recipient, body, retry_key=retry_key)
                delivery.status = 'sent'
                delivery.sent_at = now
                delivery.error_message = ''
                delivery.save(update_fields=['status', 'sent_at', 'error_message'])
                sent += 1
            except Exception as exc:
                delivery.status = 'failed'
                delivery.error_message = str(exc)[:1000]
                delivery.save(update_fields=['status', 'error_message'])
                failed += 1

        mode = 'DRY RUN' if dry_run else 'DONE'
        self.stdout.write(self.style.SUCCESS(
            f'{mode}: expired={expired_count}, evaluations={evaluation_count}, scheduled={scheduled_count}, sent={sent}, failed={failed}'
        ))

    @staticmethod
    def _render(text, delivery):
        values = {
            'order_number': delivery.group.order_number,
            'customer_name': delivery.group.name or '',
            'campus_name': delivery.group.campus.name if delivery.group.campus else '',
            'line_group_url': delivery.group.line_group_url or '',
        }
        rendered = str(text or '')
        for key, value in values.items():
            rendered = rendered.replace('{' + key + '}', str(value))
        return rendered
