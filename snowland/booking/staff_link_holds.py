from collections import Counter

from django.utils import timezone

from Resorts.models import Resorts

from .capacity import Slot, cart_capacity_slots, checkout_closure_conflicts, checkout_conflicts
from .models import StaffLinkCapacityHold


def private_hold_slots(tenant, snapshot):
    slots = [(slot, resort) for slot, resort in cart_capacity_slots(tenant, snapshot)
             if not slot.template.shared_class_enabled]
    if any(slot.end_time <= slot.start_time for slot, _ in slots):
        raise ValueError('課程結束時間必須晚於開始時間')
    return slots


def hold_slots_match(holds, slots):
    return Counter(
        (Slot(hold.course_template, hold.date, hold.start_time, hold.end_time), hold.resort.name)
        for hold in holds
    ) == Counter(slots)


def hold_conflicts(tenant, slots, *, exclude_staff_link_id=None):
    closures = checkout_closure_conflicts(tenant, slots)
    capacity = checkout_conflicts(
        (slot for slot, _ in slots), exclude_staff_link_id=exclude_staff_link_id,
    )
    return closures + capacity


def create_holds(link, slots, user):
    resorts = dict(Resorts.objects.filter(client_id=link.client_id, campuses=link.campus_id,
                                        name__in={name for _, name in slots}).values_list('name', 'pk'))
    StaffLinkCapacityHold.objects.bulk_create([
        StaffLinkCapacityHold(
            client_id=link.client_id, staff_link=link, course_template=slot.template,
            resort_id=resorts[name], date=slot.date, start_time=slot.start_time, end_time=slot.end_time,
            expires_at=link.expires_at, created_by=user,
        )
        for slot, name in slots
    ])


def release_holds(link, *, converted=False):
    now = timezone.now()
    holds = link.capacity_holds.filter(client_id=link.client_id, released_at__isnull=True)
    if converted:
        holds = holds.filter(expires_at__gt=now)
        return holds.update(released_at=now, converted_at=now)
    return holds.update(released_at=now)
