from __future__ import absolute_import, unicode_literals

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Payment, SharedCourseClass
from .operations import get_operating_policy


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
    ).select_related('reservation_group').prefetch_related(
        'reservation_group__reservations'
    )

    expired_payments = 0
    cancelled_reservations = 0

    for payment in payments:
        group = payment.reservation_group
        if group.reservations.exclude(status__in=['cancelled', 'deleted']).filter(
            shared_course_class__status='collecting',
        ).exists():
            continue
        if payment.expires_at is None:
            legacy_deadline = payment.created_at + timezone.timedelta(
                days=get_operating_policy(group).unpaid_hold_days
            )
            if legacy_deadline > now:
                continue
        with transaction.atomic():
            # An older unpaid attempt must not cancel a reservation that was
            # subsequently paid or reported for bank-transfer reconciliation.
            if not group.payments.filter(status__in=['paid', 'pending']).exists():
                reservations = group.reservations.exclude(
                    status__in=['cancelled', 'deleted', 'completed']
                )
                shared_class_ids = reservations.exclude(
                    shared_course_class__isnull=True,
                ).values_list('shared_course_class_id', flat=True).distinct()
                shared_classes = list(SharedCourseClass.objects.select_for_update().filter(id__in=shared_class_ids))
                cancelled_reservations += reservations.update(status='cancelled')
                for shared_class in shared_classes:
                    shared_class.refresh_readiness()

            payment.status = 'expired'
            payment.save(update_fields=['status'])
        expired_payments += 1

        print(f'Expired unpaid payment {payment.id} for reservation group {group.id}')

    return (
        f'Expired {expired_payments} unpaid payments and cancelled '
        f'{cancelled_reservations} reservations'
    )
