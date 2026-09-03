from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from Resorts.models import OperatingPolicy, PaymentAccount

from .models import CancellationRequest, NotificationDelivery, OrderRevision


def get_operating_policy(group):
    if group.campus_id:
        policy = OperatingPolicy.objects.filter(client=group.client, campus_id=group.campus_id).first()
        if policy:
            return policy
    return OperatingPolicy.objects.filter(client=group.client, campus__isnull=True).first() or OperatingPolicy.objects.create(client=group.client)


def resolve_payment_account(group):
    resort_ids = list(group.reservations.exclude(resort_id=None).values_list('resort_id', flat=True))
    candidates = PaymentAccount.objects.filter(client=group.client, is_active=True)
    if group.campus_id:
        scoped = candidates.filter(campuses=group.campus)
        candidates = scoped if scoped.exists() else candidates.filter(campuses__isnull=True)
    if resort_ids:
        resort_match = candidates.filter(resorts__id__in=resort_ids).distinct().order_by('-is_default', 'display_order', 'id').first()
        if resort_match:
            return resort_match
    return candidates.order_by('-is_default', 'display_order', 'id').first()


def payment_expiration_for(group):
    return timezone.now() + timedelta(days=get_operating_policy(group).unpaid_hold_days)


def order_snapshot(group):
    return {
        'order_number': group.order_number,
        'campus_id': group.campus_id,
        'name': group.name,
        'marketing_source': group.marketing_source,
        'reservations': [
            {
                'id': reservation.id,
                'resort_id': reservation.resort_id,
                'course_type_id': reservation.course_type_id,
                'course_template_id': reservation.course_template_id,
                'coach_id': reservation.preferred_coach_id,
                'people': reservation.number_of_people,
                'course_fee': reservation.course_fee,
                'coach_fee': reservation.coach_fee,
                'language_fee': reservation.language_fee,
                'equipment_fee': reservation.equipment_rental_fee,
                'discount': reservation.discount_amount,
                'payable': reservation.payment_amount,
                'status': reservation.status,
                'bookings': [
                    {
                        'id': booking.id,
                        'date': str(booking.date),
                        'start_time': booking.start_time.strftime('%H:%M'),
                        'end_time': booking.end_time.strftime('%H:%M'),
                        'course_name': booking.course_name,
                    }
                    for booking in reservation.bookings.all().order_by('date', 'start_time')
                ],
            }
            for reservation in group.reservations.all().prefetch_related('bookings')
        ],
    }


def record_order_revision(group, user=None, change_type='modify', reason='', previous_total=None):
    snapshot = order_snapshot(group)
    current_total = sum(item['payable'] for item in snapshot['reservations'])
    latest = group.revisions.order_by('-version').first()
    version = (latest.version + 1) if latest else 1
    if previous_total is None and latest:
        previous_total = sum(item.get('payable', 0) for item in latest.snapshot.get('reservations', []))
    difference = current_total - int(previous_total or current_total)
    return OrderRevision.objects.create(
        group=group,
        version=version,
        change_type=change_type,
        snapshot=snapshot,
        difference_amount=difference,
        reason=reason,
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )


def calculate_refund(group):
    first_course = group.reservations.filter(bookings__date__isnull=False).values_list('bookings__date', flat=True).order_by('bookings__date').first()
    today = timezone.localdate()
    days_before = (first_course - today).days if first_course else 0
    policy = get_operating_policy(group)
    rules = sorted(policy.cancellation_rules or [], key=lambda item: int(item.get('days_before', 0)), reverse=True)
    refund_percent = 0
    for rule in rules:
        if days_before >= int(rule.get('days_before', 0)):
            refund_percent = int(rule.get('refund_percent', 0))
            break
    original_amount = sum(group.reservations.exclude(status__in=['deleted', 'cancelled']).values_list('payment_amount', flat=True))
    refundable = Decimal(original_amount) * Decimal(refund_percent) / Decimal(100)
    handling_fee = Decimal(original_amount) * Decimal(policy.cancellation_fee_percent) / Decimal(100)
    refund_amount = max(Decimal(0), refundable - handling_fee).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return {
        'original_amount': original_amount,
        'days_before': days_before,
        'refund_percent': refund_percent,
        'handling_fee_percent': policy.cancellation_fee_percent,
        'refund_amount': int(refund_amount),
    }


@transaction.atomic
def request_cancellation(group, *, reason, reason_note='', bank=None, user=None):
    if group.cancellation_requests.filter(status__in=['requested', 'approved']).exists():
        raise ValueError('這張訂單已有待處理的取消申請')
    values = calculate_refund(group)
    payment = group.payments.order_by('-created_at').first()
    if payment and payment.payment_method not in ('newebpay', 'credit_card', 'apple_pay', 'google_pay'):
        bank = bank or {}
        if not all(bank.get(key) for key in ('bank_name', 'account_number', 'account_holder')):
            raise ValueError('匯款訂單必須填寫退款銀行、帳號與戶名')
    bank = bank or {}
    cancellation = CancellationRequest.objects.create(
        group=group,
        reason=reason,
        reason_note=reason_note,
        refund_bank_name=bank.get('bank_name', ''),
        refund_account_number=bank.get('account_number', ''),
        refund_account_holder=bank.get('account_holder', ''),
        **values,
    )
    record_order_revision(group, user=user, change_type='cancel', reason=reason_note or reason)
    return cancellation


def schedule_group_notifications(group, event):
    templates = group.client.notification_templates.filter(is_active=True, event=event).filter(
        campus__isnull=True
    ) | group.client.notification_templates.filter(is_active=True, event=event, campus=group.campus)
    first_course = group.reservations.values_list('bookings__date', flat=True).order_by('bookings__date').first()
    contact = (group.payments.order_by('-created_at').first().DataJSON or {}).get('contact', {}) if group.payments.exists() else {}
    recipient_by_channel = {'email': contact.get('email', ''), 'line': contact.get('messenger_id', ''), 'in_app': str(group.user_id or '')}
    deliveries = []
    for template in templates.distinct():
        scheduled_at = timezone.now()
        if template.days_before and first_course:
            scheduled_at = timezone.make_aware(datetime.combine(first_course - timedelta(days=template.days_before), time.min))
        recipient = recipient_by_channel.get(template.channel, '')
        if recipient:
            delivery, _ = NotificationDelivery.objects.get_or_create(
                template=template, group=group, recipient=recipient, scheduled_at=scheduled_at
            )
            deliveries.append(delivery)
    return deliveries
