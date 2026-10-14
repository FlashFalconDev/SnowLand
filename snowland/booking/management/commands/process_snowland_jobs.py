import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.legal_documents import get_current_waiver
from booking.models import Booking, CourseEvaluation, MemberDetail, NotificationDelivery, NotificationTemplate, Payment, ReservationGroup
from booking.operations import notification_template_matches_group, schedule_group_notifications
from booking.tasks import auto_cancel_unpaid_reservations


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

        deliveries = NotificationDelivery.objects.filter(status='scheduled', scheduled_at__lte=now).select_related(
            'template', 'group', 'group__campus'
        )
        sent = failed = 0
        for delivery in deliveries:
            if not notification_template_matches_group(delivery.template, delivery.group):
                if not dry_run:
                    delivery.status = 'cancelled'
                    delivery.save(update_fields=['status'])
                continue
            if delivery.template.event in {'pre_course', 'missing_documents', 'line_group', 'evaluation_due'}:
                if not delivery.group.payments.filter(status='paid').exists():
                    continue
                if not self._event_is_applicable(delivery.group, delivery.template.event):
                    continue
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
    def _event_is_applicable(group, event):
        if event in {'pre_course', 'missing_documents', 'line_group'} and not Booking.objects.filter(
            reservation__group=group, date__gte=timezone.localdate(),
        ).exclude(reservation__status__in=['cancelled', 'deleted']).exists():
            return False
        if event == 'line_group':
            return bool(group.line_group_url)
        if event == 'evaluation_due':
            return CourseEvaluation.objects.filter(
                booking__reservation__group=group,
                booking__reservation__status='completed',
                completed_at__isnull=True,
            ).exists()
        if event == 'missing_documents':
            members = MemberDetail.objects.filter(reservation__group=group).exclude(
                reservation__status__in=['cancelled', 'deleted'],
            )
            if not members.exists():
                return True
            current_version = get_current_waiver(group.client)['version']
            for member in members:
                insurance = member.insurance_data or {}
                if not member.insurance_completed_at or not all(
                    insurance.get(key) for key in ('full_name', 'birth_date', 'id_number', 'phone')
                ):
                    return True
                if not member.waiver_completed_at or not member.waiver_signature or member.waiver_document_version != current_version:
                    return True
            return False
        return True

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
