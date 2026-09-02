from __future__ import absolute_import, unicode_literals

from celery import shared_task
from django.utils import timezone

from .models import Payment


@shared_task
def auto_cancel_unpaid_reservations():
    """
    Expire unpaid reservation groups after 24 hours.

    A bank-transfer order can be sent before the customer enters the last
    five digits. At that point the payment remains ``unpaid`` and should be
    held for 24 hours. Once the customer submits transfer digits the payment
    becomes ``pending`` and is kept for staff reconciliation.
    """
    time_threshold = timezone.now() - timezone.timedelta(hours=24)

    payments = Payment.objects.filter(
        status='unpaid',
        created_at__lte=time_threshold,
    ).select_related('reservation_group').prefetch_related(
        'reservation_group__reservations'
    )

    expired_payments = 0
    cancelled_reservations = 0

    for payment in payments:
        group = payment.reservation_group
        reservations = group.reservations.exclude(
            status__in=['cancelled', 'deleted', 'completed']
        )
        cancelled_reservations += reservations.update(status='cancelled')

        payment.status = 'expired'
        payment.save(update_fields=['status'])
        expired_payments += 1

        print(f'Expired unpaid payment {payment.id} for reservation group {group.id}')

    return (
        f'Expired {expired_payments} unpaid payments and cancelled '
        f'{cancelled_reservations} reservations'
    )
