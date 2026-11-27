"""Private slot capacity shared by availability, checkout and payment."""

from collections import Counter
from dataclasses import dataclass, asdict
from datetime import date, datetime, time

from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from Client.tenant_settings import booking_capacity_recheck_enabled
from Coursekit.models import CourseTemplate
from Resorts.models import Resorts
from .closures import active_booking_closures, closed_slot_message, matching_booking_closure
from .models import Booking, Payment, Reservation, StaffLinkCapacityHold


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
    occupied: int | None
    capacity: int | None


def active_staff_link_holds(*, client_id):
    now = timezone.now()
    campus_resorts = Resorts.objects.filter(pk=OuterRef('resort_id'), campuses=OuterRef('staff_link__campus_id'))
    template_resorts = CourseTemplate.objects.filter(pk=OuterRef('course_template_id')).filter(
        Q(resorts=OuterRef('resort_id'))
        | Q(resorts__isnull=True, pricing_options__is_active=True, pricing_options__resort_id=OuterRef('resort_id')),
    )
    return StaffLinkCapacityHold.objects.filter(
        client_id=client_id, released_at__isnull=True, expires_at__gt=now,
        staff_link__client_id=client_id, staff_link__is_active=True,
        staff_link__used_at__isnull=True, staff_link__expires_at__gt=now,
        staff_link__campus__is_active=True, staff_link__campus__client_id=client_id,
        course_template__is_active=True, course_template__shared_class_enabled=False,
        course_template__course_type__category__client_id=client_id, resort__client_id=client_id,
    ).filter(Exists(campus_resorts), Exists(template_resorts))


def occupied_count(slot, *, exclude_group_id=None, paid_only=False, exclude_staff_link_id=None):
    # A reservation can have more than one matching live lesson.
    reservations = Reservation.objects.live().filter(
        course_template=slot.template, bookings__is_deleted=False, bookings__date=slot.date,
        bookings__start_time=slot.start_time, bookings__end_time=slot.end_time,
    ).exclude(status__in=['cancelled', 'deleted'])
    if exclude_group_id is not None:
        reservations = reservations.exclude(group_id=exclude_group_id)
        paid = Exists(Payment.objects.live().filter(reservation_group_id=OuterRef('group_id'), status='paid'))
        if paid_only:
            reservations = reservations.filter(paid)
        else:
            reservations = reservations.filter(Q(paid) | Q(group_id__lt=exclude_group_id))
    holds = active_staff_link_holds(client_id=slot.template.course_type.category.client_id).filter(
        course_template=slot.template, date=slot.date, start_time=slot.start_time, end_time=slot.end_time,
    )
    if exclude_staff_link_id is not None:
        holds = holds.exclude(staff_link_id=exclude_staff_link_id)
    # Read both counts in one statement so checkout cannot move a hold to a
    # reservation between the availability reads.
    reservation_count = reservations.order_by().values('course_template').annotate(
        total=Count('pk', distinct=True),
    ).values('total')
    hold_count = holds.order_by().values('course_template').annotate(total=Count('pk')).values('total')
    occupied = CourseTemplate.objects.filter(pk=slot.template.pk).annotate(
        total=Coalesce(Subquery(reservation_count), 0) + Coalesce(Subquery(hold_count), 0),
    ).values_list('total', flat=True).first()
    return occupied or 0


def slot_unavailable_reasons(
    slot, *, requested=1, exclude_group_id=None, paid_only=False, exclude_staff_link_id=None,
    closures=(), resort_id=None, check_capacity=True,
):
    reasons = []
    if matching_booking_closure(
        closures, day=slot.date, resort_id=resort_id, template_id=slot.template.pk,
        start_time=slot.start_time, end_time=slot.end_time,
    ):
        reasons.append(SlotUnavailable(
            code='closed', message_zh=closed_slot_message(slot.date), date=slot.date.isoformat(),
            start_time=slot.start_time.strftime('%H:%M'), end_time=slot.end_time.strftime('%H:%M'),
            template_id=slot.template.pk, template_name=slot.template.name, occupied=None, capacity=None,
        ))
    if not check_capacity or slot.template.shared_class_enabled:
        return reasons
    occupied = occupied_count(
        slot, exclude_group_id=exclude_group_id, paid_only=paid_only, exclude_staff_link_id=exclude_staff_link_id,
    )
    capacity = slot.template.max_capacity or 6
    if occupied + requested <= capacity:
        return reasons
    day = slot.date.isoformat()
    start = slot.start_time.strftime('%H:%M')
    end = slot.end_time.strftime('%H:%M')
    return [*reasons, SlotUnavailable(
        code='full', message_zh=f'所選的 {day} {start}–{end} 已經滿額，請改選其他日期或時段。',
        date=day, start_time=start, end_time=end, template_id=slot.template.pk,
        template_name=slot.template.name, occupied=occupied, capacity=capacity,
    )]


def checkout_conflicts(slots, *, exclude_staff_link_id=None):
    return [
        reason for slot, requested in Counter(slots).items()
        for reason in slot_unavailable_reasons(slot, requested=requested, exclude_staff_link_id=exclude_staff_link_id)
    ]


def parse_booking_time(value):
    try:
        return datetime.strptime(value, '%H:%M:%S').time()
    except ValueError:
        return datetime.strptime(value, '%H:%M').time()


def cart_capacity_slots(tenant, cart, *, split_reservations=False):
    course_groups = [item.get('courses') or [] for item in cart]
    templates = CourseTemplate.objects.filter(course_type__category__client=tenant).in_bulk(
        {course.get('courseTemplateId') for courses in course_groups for course in courses if course.get('courseTemplateId')},
    )
    slot_resorts = []
    for item, courses in zip(cart, course_groups):
        group_slots = []
        for course in courses:
            template = templates.get(int(course['courseTemplateId'])) if course.get('courseTemplateId') else None
            if template:
                group_slots.append(Slot(
                    template, datetime.strptime(course['date'], '%Y-%m-%d').date(),
                    parse_booking_time(course['timeSlotStart']), parse_booking_time(course['timeSlotEnd']),
                ))
        slot_resorts.extend(
            (slot, item.get('resort')) for slot in (group_slots if split_reservations else dict.fromkeys(group_slots))
        )
    return slot_resorts


def checkout_closure_conflicts(tenant, slot_resorts):
    if not slot_resorts:
        return []
    days = [slot.date for slot, _ in slot_resorts]
    closures = active_booking_closures(tenant, min(days), max(days))
    if not closures:
        return []
    resort_ids = dict(Resorts.objects.filter(
        client=tenant, name__in={name for _, name in slot_resorts},
    ).values_list('name', 'pk'))
    return [
        reason for slot, resort_name in dict.fromkeys(slot_resorts)
        for reason in slot_unavailable_reasons(
            slot, closures=closures, resort_id=resort_ids.get(resort_name), check_capacity=False,
        )
    ]


def slot_conflict_response(conflicts):
    return {
        'code': 'slot_closed' if conflicts[0].code == 'closed' else 'slot_full',
        'message': conflicts[0].message_zh,
        'conflicts': [asdict(reason) for reason in conflicts],
    }


def group_capacity_conflicts(group, *, paid_only=False):
    """Use each lesson's selected template, with the reservation as a legacy fallback."""
    bookings = Booking.objects.live().filter(
        reservation__group=group, reservation__shared_course_class__isnull=True,
    ).exclude(reservation__status__in=['cancelled', 'deleted']).select_related(
        'course_template__course_type__category', 'reservation__course_template__course_type__category',
    ).order_by('date', 'start_time', 'pk')
    reservations_by_slot = {}
    for booking in bookings:
        template = booking.course_template or booking.reservation.course_template
        if template and template.course_type.category.client_id == group.client_id:
            slot = Slot(template, booking.date, booking.start_time, booking.end_time)
            reservations_by_slot.setdefault(slot, set()).add(booking.reservation_id)
    return [
        reason for slot, reservation_ids in reservations_by_slot.items()
        for reason in slot_unavailable_reasons(
            slot, requested=len(reservation_ids), exclude_group_id=group.pk, paid_only=paid_only,
        )
    ]


def capacity_payment_hold(group, payment):
    if (payment is not None and payment.status != 'unpaid') or not booking_capacity_recheck_enabled(group.client):
        return None, None
    if group.reservations.live().exclude(status__in=['cancelled', 'deleted']).filter(
        Q(status__in=['manually_assigned', 'pending_coach_confirmation'])
        | Q(bookings__is_deleted=False, bookings__is_scheduled=True),
    ).exists():
        return None, None
    if group_capacity_conflicts(group):
        return PAYMENT_CAPACITY_MESSAGE, PAYMENT_CAPACITY_CODE
    return None, None


def record_paid_capacity_conflict(group, payment, *, user=None):
    """Call on a paid transition inside the transaction holding the tenant, order and payment locks."""
    stored = dict(payment.DataJSON) if isinstance(payment.DataJSON, dict) else {}
    if stored.get('capacity_conflict') or not booking_capacity_recheck_enabled(group.client):
        return
    conflicts = group_capacity_conflicts(group, paid_only=True)
    if conflicts:
        from .operations import record_order_revision

        stored['capacity_conflict'] = {
            'detected_at': timezone.now().isoformat(),
            'conflicts': [asdict(reason) for reason in conflicts],
        }
        payment.DataJSON = stored
        payment.save(update_fields=['DataJSON', 'updated_at'])
        record_order_revision(group, user=user, reason=PAID_CAPACITY_REVISION_REASON)
