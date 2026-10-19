from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone

from Resorts.models import OperatingPolicy, PaymentAccount

from .models import Booking, CancellationRequest, NotificationDelivery, OrderRevision, ReservationGroup


def validate_class_group_url(value):
    if not isinstance(value, str):
        raise ValueError('請貼上完整的 HTTPS 群組連結')
    value = value.strip()
    if not value:
        return ''
    try:
        URLValidator(schemes=['https'])(value)
        parts = urlsplit(value)
        if len(value) > 500 or parts.username or parts.password:
            raise ValidationError('invalid')
    except (ValidationError, ValueError):
        raise ValueError('請貼上500字以內的完整 HTTPS 群組連結，不可包含帳號密碼')
    return value


def get_operating_policy(group):
    if group.campus_id:
        policy = OperatingPolicy.objects.filter(client=group.client, campus_id=group.campus_id).first()
        if policy:
            return policy
    return OperatingPolicy.objects.filter(client=group.client, campus__isnull=True).first() or OperatingPolicy.objects.create(client=group.client)


def resolve_payment_account(group, *, currency=None, lock=False):
    currency = currency or (group.currency_snapshot or {}).get('currency', 'TWD')
    resort_ids = list(group.reservations.exclude(resort_id=None).values_list('resort_id', flat=True))
    candidates = PaymentAccount.objects.filter(client=group.client, is_active=True, currency=currency)
    if lock:
        candidates = candidates.select_for_update()
    pools = (
        (candidates.filter(campuses=group.campus), candidates.filter(campuses__isnull=True))
        if group.campus_id else (candidates,)
    )
    for pool in pools:
        if resort_ids:
            resort_match = pool.filter(resorts__id__in=resort_ids).distinct().order_by('-is_default', 'display_order', 'id').first()
            if resort_match:
                return resort_match
        general = pool.filter(resorts__isnull=True).distinct().order_by('-is_default', 'display_order', 'id').first()
        if general:
            return general
    return None


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
                'resort_name': reservation.resort.display_name if reservation.resort else '',
                'course_type_id': reservation.course_type_id,
                'course_type_name': reservation.course_type.name if reservation.course_type else '',
                'course_template_id': reservation.course_template_id,
                'course_template_name': reservation.course_template.name if reservation.course_template else '',
                'coach_id': reservation.preferred_coach_id,
                'coach_name': reservation.preferred_coach.name if reservation.preferred_coach else '',
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
                        'course_template_id': booking.course_template_id,
                        'date': str(booking.date),
                        'start_time': booking.start_time.strftime('%H:%M'),
                        'end_time': booking.end_time.strftime('%H:%M'),
                        'course_name': booking.course_name,
                    }
                    for booking in reservation.bookings.all().order_by('date', 'start_time')
                ],
            }
            for reservation in group.reservations.select_related(
                'resort', 'course_type', 'course_template', 'preferred_coach',
            ).prefetch_related('bookings')
        ],
    }


def record_order_revision(group, user=None, change_type='modify', reason='', previous_total=None):
    snapshot = order_snapshot(group)
    current_total = sum(item['payable'] for item in snapshot['reservations'] if item.get('status') not in {'deleted', 'cancelled'})
    latest = group.revisions.order_by('-version').first()
    version = (latest.version + 1) if latest else 1
    if previous_total is None and latest:
        previous_total = sum(item.get('payable', 0) for item in latest.snapshot.get('reservations', []) if item.get('status') not in {'deleted', 'cancelled'})
    difference = current_total - int(current_total if previous_total is None else previous_total)
    return OrderRevision.objects.create(
        group=group,
        version=version,
        change_type=change_type,
        snapshot=snapshot,
        difference_amount=difference,
        reason=reason,
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )


def outstanding_amendments(group):
    return group.amendments.filter(status__in=['topup_due','topup_reported','refund_account_due','refund_due'])


def calculate_refund(group):
    active_courses = group.reservations.exclude(status__in=['deleted', 'cancelled'])
    first_course = active_courses.filter(bookings__date__isnull=False).values_list('bookings__date', flat=True).order_by('bookings__date').first()
    today = timezone.localdate()
    days_before = (first_course - today).days if first_course else 0
    policy = get_operating_policy(group)
    rules = sorted(policy.cancellation_rules or [], key=lambda item: int(item.get('days_before', 0)), reverse=True)
    refund_percent = 0
    for rule in rules:
        if days_before >= int(rule.get('days_before', 0)):
            refund_percent = int(rule.get('refund_percent', 0))
            break
    original_amount = sum(active_courses.values_list('payment_amount', flat=True))
    refundable = Decimal(original_amount) * Decimal(refund_percent) / Decimal(100)
    handling_fee = Decimal(original_amount) * Decimal(policy.cancellation_fee_percent) / Decimal(100)
    refund_amount = max(Decimal(0), refundable - handling_fee).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    requires_cash_review = outstanding_amendments(group).exists()
    return {
        'original_amount': original_amount,
        'days_before': days_before,
        'refund_percent': refund_percent,
        'handling_fee_percent': policy.cancellation_fee_percent,
        'refund_amount': None if requires_cash_review else int(refund_amount),
        'requires_cash_review': requires_cash_review,
        'available_rules': rules,
    }


@transaction.atomic
def request_cancellation(group, *, reason, reason_note='', bank=None, user=None,
                         selected_rule_days_before=None, manual_refund_amount=None,
                         expected_user_id=None, expected_client_id=None, require_paid=False):
    # Serialize with refund processing; never trust a caller's cached order/payment.
    group = ReservationGroup.objects.select_for_update().get(pk=group.pk)
    if ((expected_user_id is not None and group.user_id != expected_user_id)
            or (expected_client_id is not None and group.client_id != expected_client_id)):
        from django.http import Http404
        raise Http404('找不到您的訂單')
    payment = group.payments.order_by('-created_at', '-pk').first()
    if require_paid and (not payment or payment.status != 'paid'):
        raise ValueError('目前僅已付款訂單可申請退款，其他情況請聯絡客服')
    if group.cancellation_requests.filter(status='refunded').exists() or (payment and payment.status == 'refunded'):
        raise ValueError('這張訂單已完成退款，不能再次提出退款申請')
    if group.cancellation_requests.filter(status__in=['requested', 'approved']).exists():
        raise ValueError('這張訂單已有待處理的取消申請')
    if not isinstance(reason, str) or reason not in dict(CancellationRequest.REASON_CHOICES):
        raise ValueError('請選擇取消原因')
    if not isinstance(reason_note, str) or len(reason_note) > 1000:
        raise ValueError('取消說明須為1000字以內的文字')
    if bank is not None and not isinstance(bank, dict):
        raise ValueError('退款銀行資料格式錯誤')
    bank = bank or {}
    for key in ('bank_name', 'account_number', 'account_holder'):
        value = bank.get(key, '')
        if not isinstance(value, str) or len(value) > 100:
            raise ValueError('退款銀行、帳號及戶名須為100字以內的文字')
    bank = {key: bank.get(key, '').strip() for key in ('bank_name', 'account_number', 'account_holder')}
    preview = calculate_refund(group)
    rules = preview.pop('available_rules')
    values = preview
    if preview['requires_cash_review']:
        if manual_refund_amount is not None or selected_rule_days_before is not None:
            raise ValueError('訂單有未結清差額，請先建立取消申請，再由行政核對實收款及退款金額')
        # Zero is only a storage placeholder, never a quoted or approved refund.
        values['refund_amount'] = 0
        values['cash_review_snapshot'] = {'outstanding_amendments': list(
            outstanding_amendments(group).values('id','balance_amount','status'))}
    calculation_mode = 'auto'
    if manual_refund_amount is not None and selected_rule_days_before is not None:
        raise ValueError('指定方案與手動金額只能選一種')
    if selected_rule_days_before is not None:
        try:
            parsed_days = int(selected_rule_days_before)
        except (TypeError, ValueError):
            raise ValueError('退費方案格式錯誤')
        if isinstance(selected_rule_days_before, bool) or str(parsed_days) != str(selected_rule_days_before).strip():
            raise ValueError('退費方案格式錯誤')
        selected_rule_days_before = parsed_days
        selected = next((rule for rule in rules if int(rule['days_before']) == selected_rule_days_before), None)
        if selected is None:
            raise ValueError('退費方案不在目前營運規則中')
        percent = int(selected['refund_percent'])
        fee = Decimal(preview['original_amount']) * Decimal(preview['handling_fee_percent']) / 100
        amount = Decimal(preview['original_amount']) * Decimal(percent) / 100 - fee
        values['refund_percent'] = percent
        values['refund_amount'] = int(max(Decimal(0), amount).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        calculation_mode = 'rule'
    elif manual_refund_amount is not None:
        try:
            amount = int(manual_refund_amount)
        except (TypeError, ValueError):
            raise ValueError('手動退款金額須為整數')
        if str(amount) != str(manual_refund_amount).strip() or not 0 <= amount <= preview['original_amount']:
            raise ValueError('手動退款金額不可超過訂單金額，也不可小於 0')
        values['refund_amount'] = amount
        values['handling_fee_percent'] = 0
        values['refund_percent'] = 0
        calculation_mode = 'manual'
    if payment and (preview['requires_cash_review'] or payment.payment_method not in ('newebpay', 'credit_card', 'apple_pay', 'google_pay')):
        if not all(bank.get(key) for key in ('bank_name', 'account_number', 'account_holder')):
            raise ValueError('匯款訂單必須填寫退款銀行、帳號與戶名')
    cancellation = CancellationRequest.objects.create(
        group=group,
        reason=reason,
        reason_note=reason_note,
        refund_bank_name=bank.get('bank_name', ''),
        refund_account_number=bank.get('account_number', ''),
        refund_account_holder=bank.get('account_holder', ''),
        calculation_mode=calculation_mode,
        selected_rule_days_before=selected_rule_days_before if calculation_mode == 'rule' else None,
        **values,
    )
    record_order_revision(group, user=user, change_type='cancel', reason=reason_note or reason)
    return cancellation


def notification_template_matches_group(template, group):
    if not template.is_active or template.client_id != group.client_id:
        return False
    if template.campus_id and template.campus_id != group.campus_id:
        return False
    return not template.course_templates.exists() or group.reservations.exclude(
        status__in=['cancelled', 'deleted'],
    ).filter(course_template__in=template.course_templates.all()).exists()


@transaction.atomic
def schedule_group_notifications(group, event):
    # Serialize scheduling for the same order so concurrent callers cannot add duplicate recipients.
    group = ReservationGroup.objects.select_for_update().select_related('client', 'user').get(pk=group.pk)
    from .notification_recipients import COURSE_RECIPIENT_EVENTS, course_notification_recipients
    templates = group.client.notification_templates.filter(is_active=True, event=event).filter(
        campus__isnull=True
    ) | group.client.notification_templates.filter(is_active=True, event=event, campus=group.campus)
    first_course = Booking.objects.filter(reservation__group=group).exclude(
        reservation__status__in=['cancelled', 'deleted'],
    ).order_by('date').values_list('date', flat=True).first()
    payment = group.payments.order_by('-created_at').first()
    payment_data = payment.DataJSON if payment and isinstance(payment.DataJSON, dict) else {}
    contact = payment_data.get('contact') if isinstance(payment_data.get('contact'), dict) else {}
    booking_contact = group.booking_contact if isinstance(group.booking_contact, dict) else {}
    email = contact.get('email') or booking_contact.get('email') or (group.user.email if group.user_id else '')
    recipient_by_channel = {'email': email, 'line': contact.get('messenger_id', ''), 'in_app': str(group.user_id or '')}
    deliveries = []
    for template in templates.distinct():
        if not notification_template_matches_group(template, group):
            continue
        scheduled_at = timezone.now()
        if template.days_before and first_course and event not in {'order_created', 'shared_class_ready', 'payment_confirmed'}:
            scheduled_at = timezone.make_aware(datetime.combine(first_course - timedelta(days=template.days_before), time.min))
        recipients = {
            recipient_by_channel.get(template.channel, ''): {'first_course': first_course, 'payload': {}},
        }
        if event in COURSE_RECIPIENT_EVENTS:
            recipients = course_notification_recipients(group, template)
            NotificationDelivery.objects.filter(template=template, group=group, status='scheduled').exclude(
                recipient__in=recipients,
            ).update(status='cancelled')
        initial_scheduled_at = scheduled_at
        for recipient, context in recipients.items():
            if not recipient:
                continue
            scheduled_at = initial_scheduled_at
            recipient_date = context['first_course']
            if template.days_before and recipient_date and event not in {'order_created', 'shared_class_ready', 'payment_confirmed'}:
                scheduled_at = timezone.make_aware(datetime.combine(recipient_date - timedelta(days=template.days_before), time.min))
            delivery = NotificationDelivery.objects.filter(
                template=template, group=group, recipient=recipient,
            ).exclude(status='cancelled').order_by('-id').first()
            payload = dict(context['payload'])
            if delivery and delivery.status == 'sent' and event == 'missing_documents' and template.repeat_interval_days:
                next_reminder = (delivery.sent_at or delivery.scheduled_at) + timedelta(days=template.repeat_interval_days)
                if next_reminder <= timezone.now():
                    payload['repeat_of'] = delivery.pk
                    scheduled_at = max(scheduled_at, next_reminder)
                    delivery = None
            elif delivery and delivery.status == 'scheduled' and (delivery.payload or {}).get('repeat_of'):
                if event != 'missing_documents' or not template.repeat_interval_days:
                    delivery.status = 'cancelled'
                    delivery.save(update_fields=['status'])
                    continue
                payload['repeat_of'] = delivery.payload['repeat_of']
                previous = NotificationDelivery.objects.filter(pk=payload['repeat_of'], template=template,
                    group=group, recipient=recipient, status='sent').first()
                if previous:
                    scheduled_at = max(scheduled_at, (previous.sent_at or previous.scheduled_at) + timedelta(days=template.repeat_interval_days))
            if delivery is None:
                delivery = NotificationDelivery.objects.create(
                    template=template, group=group, recipient=recipient, scheduled_at=scheduled_at, payload=payload,
                )
                deliveries.append(delivery)
            elif delivery.status == 'scheduled' and (
                (template.days_before and recipient_date and delivery.scheduled_at != scheduled_at)
                or delivery.payload != payload
            ):
                delivery.scheduled_at = scheduled_at
                delivery.payload = payload
                delivery.save(update_fields=['scheduled_at', 'payload'])
    return deliveries
