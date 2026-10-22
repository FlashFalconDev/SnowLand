from __future__ import absolute_import, unicode_literals

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from Client.models import Client
from .models import Payment, ReservationGroup, SharedCourseClass
from .operations import get_operating_policy


def expire_unpaid_payment(payment_id, now=None):
    """Recheck one candidate under the same tenant/order locks as payment writers."""
    now = now or timezone.now()
    candidate = Payment.objects.select_related('reservation_group').filter(pk=payment_id).first()
    if not candidate or candidate.status != 'unpaid':
        return 0, 0
    # Policy lookup is intentionally outside the mutation lock. A candidate is
    # only a hint: the current row and deadline are checked again below.
    hold_days = get_operating_policy(candidate.reservation_group).unpaid_hold_days if candidate.expires_at is None else None
    with transaction.atomic():
        if candidate.reservation_group.client_id:
            Client.objects.select_for_update().get(pk=candidate.reservation_group.client_id)
        group = ReservationGroup.objects.select_for_update().filter(pk=candidate.reservation_group_id).first()
        if group is None:
            return 0, 0
        payment = Payment.objects.select_for_update().filter(pk=payment_id, reservation_group=group).first()
        if payment is None or payment.status != 'unpaid':
            return 0, 0
        active = group.reservations.exclude(status__in=['cancelled', 'deleted', 'completed'])
        if active.exclude(status__in=['auto_assigned', 'manually_assigned', 'form_filled']).exists():
            return 0, 0
        deadline = payment.expires_at
        if deadline is None:
            days = hold_days if hold_days is not None else get_operating_policy(group).unpaid_hold_days
            deadline = payment.created_at + timezone.timedelta(days=days)
        if deadline > now:
            return 0, 0
        reservations = group.reservations.exclude(status__in=['cancelled', 'deleted', 'completed'])
        shared_ids = list(reservations.exclude(shared_course_class__isnull=True).values_list('shared_course_class_id', flat=True).distinct())
        shared_classes = list(SharedCourseClass.objects.select_for_update().filter(pk__in=shared_ids).order_by('pk'))
        if any(shared.status == 'collecting' for shared in shared_classes):
            return 0, 0
        cancelled = 0
        if not group.payments.filter(status__in=['paid', 'pending']).exists():
            cancelled = reservations.update(status='cancelled')
            for shared in shared_classes:
                shared.refresh_readiness()
        payment.status = 'expired'
        payment.save(update_fields=['status'])
    return 1, cancelled


@shared_task
def auto_cancel_unpaid_reservations():
    """
    Expire unpaid reservation groups after their configured hold period.

    A bank-transfer order can be sent before the customer enters the last
    five digits. At that point the payment remains ``unpaid`` and should be
    held until its expires_at deadline. Once the customer submits transfer digits the payment
    becomes ``pending`` and is kept for staff reconciliation.
    """
    now = timezone.now()

    payments = Payment.objects.filter(
        status='unpaid',
    ).filter(
        Q(expires_at__lte=now) | Q(expires_at__isnull=True),
    ).values_list('pk', flat=True)

    expired_payments = 0
    cancelled_reservations = 0

    for payment_id in payments:
        expired, cancelled = expire_unpaid_payment(payment_id, now=now)
        expired_payments += expired
        cancelled_reservations += cancelled

    return (
        f'Expired {expired_payments} unpaid payments and cancelled '
        f'{cancelled_reservations} reservations'
    )
