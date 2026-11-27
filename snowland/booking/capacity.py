"""Private slot capacity shared by availability, checkout and payment."""

from collections import Counter
from dataclasses import dataclass, asdict
from datetime import date, time

from django.utils import timezone

from Client.tenant_settings import booking_capacity_recheck_enabled
from Coursekit.models import CourseTemplate
from .models import Booking, Reservation


PAYMENT_CAPACITY_CODE = 'slot_full_at_payment'
PAYMENT_CAPACITY_MESSAGE = '這個時段剛剛已經額滿，這筆訂單先不收款，我們的客服會與您聯絡協助改期。'
PAID_CAPACITY_REVISION_REASON = '付款後發現時段已滿，需主管跟進'


@dataclass(frozen=True)
class Slot:
    template: CourseTemplate
    date: date
    start_time: time
    end_time: time


@dataclass(frozen=True)
class SlotUnavailable:
    code: str
    message_zh: str
    date: str
    start_time: str
    end_time: str
    template_id: int
    template_name: str
    occupied: int
    capacity: int


def occupied_count(slot, *, exclude_group_id=None):
    # The template uniquely belongs to a tenant. Retain the original join:
    # each matching live Booking row counts under its Reservation's template.
    reservations = Reservation.objects.live().filter(
        course_template=slot.template, bookings__is_deleted=False, bookings__date=slot.date,
        bookings__start_time=slot.start_time, bookings__end_time=slot.end_time,
    ).exclude(status__in=['cancelled', 'deleted'])
    if exclude_group_id is not None:
        reservations = reservations.exclude(group_id=exclude_group_id)
    return reservations.count()


def slot_unavailable_reasons(slot, *, requested=1, exclude_group_id=None):
    if slot.template.shared_class_enabled:
        return []
    occupied = occupied_count(slot, exclude_group_id=exclude_group_id)
    capacity = slot.template.max_capacity or 6
    if occupied + requested <= capacity:
        return []
    day = slot.date.isoformat()
    start = slot.start_time.strftime('%H:%M')
    end = slot.end_time.strftime('%H:%M')
    return [SlotUnavailable(
        code='full', message_zh=f'所選的 {day} {start}–{end} 已經滿額，請改選其他日期或時段。',
        date=day, start_time=start, end_time=end, template_id=slot.template.pk,
        template_name=slot.template.name, occupied=occupied, capacity=capacity,
    )]


def checkout_conflicts(slots):
    return [
        reason for slot, requested in Counter(slots).items()
        for reason in slot_unavailable_reasons(slot, requested=requested)
    ]


def slot_full_response(conflicts):
    return {
        'code': 'slot_full',
        'message': conflicts[0].message_zh,
        'conflicts': [asdict(reason) for reason in conflicts],
    }


def group_capacity_conflicts(group):
    """Use each lesson's selected template, with the reservation as a legacy fallback."""
    bookings = Booking.objects.live().filter(
        reservation__group=group, reservation__shared_course_class__isnull=True,
    ).exclude(reservation__status__in=['cancelled', 'deleted']).select_related(
        'course_template__course_type__category', 'reservation__course_template__course_type__category',
    ).order_by('date', 'start_time', 'pk')
    slots = []
    for booking in bookings:
        template = booking.course_template or booking.reservation.course_template
        if template and template.course_type.category.client_id == group.client_id:
            slots.append(Slot(template, booking.date, booking.start_time, booking.end_time))
    return [
        reason for slot, requested in Counter(slots).items()
        for reason in slot_unavailable_reasons(slot, requested=requested, exclude_group_id=group.pk)
    ]


def record_paid_capacity_conflict(group, payment, *, user=None):
    """Call on a paid transition inside the transaction holding the order/payment locks."""
    stored = dict(payment.DataJSON) if isinstance(payment.DataJSON, dict) else {}
    if stored.get('capacity_conflict') or not booking_capacity_recheck_enabled(group.client):
        return
    conflicts = group_capacity_conflicts(group)
    if conflicts:
        from .operations import record_order_revision

        stored['capacity_conflict'] = {
            'detected_at': timezone.now().isoformat(),
            'conflicts': [asdict(reason) for reason in conflicts],
        }
        payment.DataJSON = stored
        payment.save(update_fields=['DataJSON', 'updated_at'])
        record_order_revision(group, user=user, reason=PAID_CAPACITY_REVISION_REASON)
