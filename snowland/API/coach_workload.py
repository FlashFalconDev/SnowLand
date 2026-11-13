from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce

from Coach.models import Coach, CoachCourseLevel, CoachLeaveRequest, CoachResort, normalize_ability_levels
from Resorts.models import Campus, Resorts
from booking.models import Booking, Payment


def photography_booking_filter():
    fields = (
        'reservation__course_type__category__name', 'reservation__course_type__name',
        'reservation__course_template__name', 'course_type', 'course_name',
    )
    query = Q(reservation__course_type__category__service_type='photo')
    for field in fields:
        for name in ('攝影', 'Photography', 'Photo'):
            query |= Q(**{f'{field}__icontains': name})
    return query


def workload_resorts(tenant, campus_ids):
    resorts = Resorts.objects.filter(client=tenant)
    if campus_ids is not None:
        resorts = resorts.filter(campuses__id__in=campus_ids)
    return resorts.order_by('display_order', 'id').distinct()


def coach_workload(*, tenant, campus_ids, start, end, resort, schedule_statuses, can_view_settings):
    resorts = workload_resorts(tenant, campus_ids)
    report = {
        'start': start.isoformat(), 'end': end.isoformat(),
        'has_visible_dates': start <= end,
        'resorts': list(resorts.values('id', 'display_name')),
        'coaches': [],
    }
    if start > end:
        return report

    latest_payment = Payment.objects.filter(
        reservation_group_id=OuterRef('reservation__group_id'),
    ).order_by('-created_at', '-pk').values('status')[:1]
    lessons = Booking.objects.filter(
        Q(is_scheduled=True) | Q(reservation__status='completed'),
        date__range=(start, end),
        reservation__group__client=tenant,
        reservation__preferred_coach__client=tenant,
        reservation__status__in=schedule_statuses,
    ).alias(payment_status=Coalesce(Subquery(latest_payment), Value('unpaid'))).exclude(
        Q(payment_status__in=('expired', 'refunded'))
        | Q(reservation__shared_course_class__status='cancelled')
        | photography_booking_filter()
        | Q(course_name__icontains='旅拍') | Q(course_type__icontains='旅拍')
        | Q(reservation__course_template__course_type__category__service_type='photo')
        | Q(course_template__course_type__category__service_type='photo')
    )
    coaches = Coach.objects.filter(client=tenant)
    if campus_ids is not None:
        lessons = lessons.filter(reservation__group__campus_id__in=campus_ids)
        coaches = coaches.filter(campuses__id__in=campus_ids)
    if resort:
        lessons = lessons.filter(reservation__resort=resort)
        coaches = coaches.filter(coachresort__resort=resort)

    # A shared class can be represented by multiple reservations with different
    # attendance statuses. A completed row takes precedence for that class.
    slots_by_coach = defaultdict(dict)
    for pk, coach_id, shared_id, day, starts, ends, status, specified in lessons.values_list(
        'pk', 'reservation__preferred_coach_id', 'reservation__shared_course_class_id',
        'date', 'start_time', 'end_time', 'reservation__status', 'reservation__is_preferred_coach',
    ).iterator():
        duration = (datetime.combine(day, ends) - datetime.combine(day, starts)).total_seconds()
        if duration <= 0:
            continue
        key = (shared_id, day, starts, ends) if shared_id else (pk,)
        slots = slots_by_coach[coach_id]
        rank = 2 if status == 'completed' else 0 if status == 'pending_coach_confirmation' else 1
        old_rank, _, old_specified = slots.get(key, (rank, duration, False))
        slots[key] = (max(rank, old_rank), int(duration), bool(specified or old_specified))

    roster_ids = set(coaches.values_list('pk', flat=True))
    coaches = Coach.objects.filter(client=tenant, pk__in=roster_ids | slots_by_coach.keys())
    campuses = Campus.objects.filter(client=tenant)
    if campus_ids is not None:
        campuses = campuses.filter(pk__in=campus_ids)
    if can_view_settings:
        coaches = coaches.prefetch_related(
            Prefetch('campuses', queryset=campuses.order_by('display_order', 'pk'), to_attr='report_campuses'),
            Prefetch('coachresort_set', queryset=CoachResort.objects.filter(resort__in=resorts).select_related(
                'resort',
            ).order_by('resort__display_order', 'pk'), to_attr='report_resorts'),
            Prefetch('course_levels', queryset=CoachCourseLevel.objects.filter(
                course_type__category__client=tenant,
            ).select_related('course_type').order_by('course_type__name', 'pk'), to_attr='report_courses'),
        )
    leave_days = defaultdict(set)
    for coach_id, first, last in CoachLeaveRequest.objects.filter(
        coach_id__in=roster_ids, status='approved', start_date__lte=end, end_date__gte=start,
    ).values_list('coach_id', 'start_date', 'end_date'):
        first, last = max(first, start), min(last, end)
        leave_days[coach_id].update(first + timedelta(days=offset) for offset in range((last - first).days + 1))

    for coach in coaches.order_by('name', 'pk'):
        slots = slots_by_coach.get(coach.pk, {}).values()
        on_roster = coach.pk in roster_ids
        report['coaches'].append({
            'id': coach.pk, 'name': coach.name,
            'lesson_count': len(slots),
            'assigned_seconds': sum(seconds for _, seconds, _ in slots),
            'completed_seconds': sum(seconds for rank, seconds, _ in slots if rank == 2),
            'pending_seconds': sum(seconds for rank, seconds, _ in slots if rank == 0),
            'specified_seconds': sum(seconds for _, seconds, specified in slots if specified),
            'leave_days': len(leave_days[coach.pk]) if on_roster else None,
            'settings': {
                'availability': coach.get_availability_status_display(),
                'auto_assignment_enabled': coach.auto_assignment_enabled,
                'customer_selectable': coach.customer_selectable,
                'schedule_visibility': coach.get_schedule_visibility_display(),
                'languages': [dict(Coach.LANGUAGE_CHOICES).get(code, code) for code in coach.languages],
                'assignment_score': coach.assignment_score,
                'campuses': [campus.name for campus in coach.report_campuses],
                'resorts': [{
                    'id': link.resort_id, 'name': link.resort.display_name,
                    'priority': link.resort_priority, 'weight': link.assignment_score,
                    'auto_assignment_enabled': link.resort.auto_scheduling_enabled,
                } for link in coach.report_resorts],
                'courses': [{
                    'id': level.pk, 'name': level.course_type.name, 'order': level.course_order,
                    'ability_levels': normalize_ability_levels(level.ability_levels),
                    'price_level': level.get_price_level_display(),
                } for level in coach.report_courses],
            } if can_view_settings and on_roster else None,
        })
    report['coaches'].sort(key=lambda row: -row['assigned_seconds'])
    return report
