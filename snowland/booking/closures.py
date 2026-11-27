"""Tenant-scoped rules for stopping new bookings."""

from Client.tenant_settings import booking_closures_enabled
from .models import BookingClosure


def active_booking_closures(client, date_from, date_to):
    if not booking_closures_enabled(client):
        return ()
    return tuple(BookingClosure.objects.live().filter(
        client=client, date_from__lte=date_to, date_to__gte=date_from,
    ).order_by('pk'))


def matching_booking_closure(closures, *, day, resort_id, template_id, start_time=None, end_time=None):
    """With no times, match all-day rules only. Adjacent time intervals do not overlap."""
    for rule in closures:
        if not rule.date_from <= day <= rule.date_to:
            continue
        if rule.resort_id is not None and rule.resort_id != resort_id:
            continue
        if rule.course_template_id is not None and rule.course_template_id != template_id:
            continue
        if rule.start_time is None or (
            start_time is not None and end_time is not None
            and start_time < rule.end_time and end_time > rule.start_time
        ):
            return rule
    return None


def closed_slot_message(day):
    return f'{day.isoformat()} 該時段已暫停接單'
