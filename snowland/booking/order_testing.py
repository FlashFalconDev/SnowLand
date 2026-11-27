from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import OrderLoyalty, Payment


def exclude_test_orders(queryset, group_path=''):
    """Keep this explicit so history and administrative lookups can still see test orders."""
    field = f'{group_path}__is_test' if group_path else 'is_test'
    return queryset.exclude(**{field: True})


def _has_financial_history(group):
    from Coach.models import PayrollLine, StaffIncentiveLine

    return (
        group.newebpay_form_issued or group.newebpay_merchant_id is not None
        or Payment.all_objects.filter(reservation_group=group).filter(
            Q(status__in=('paid', 'refunded')) | Q(bank_posted_date__isnull=False)
            | Q(DataJSON__has_key='gateway_response') | Q(DataJSON__settlement__has_key='confirmed_at')
            | (Q(status='pending', bank_account__isnull=False) & ~Q(bank_account='')),
        ).exists()
        or group.amendments.filter(status__in=('topup_reported', 'refund_account_due', 'refund_due', 'settled')).exists()
        or group.cancellation_requests.filter(
            Q(status='refunded') | Q(actual_received_amount__gt=0),
        ).exists()
        or OrderLoyalty.all_objects.filter(group=group, paid_base__isnull=False).exists()
        or PayrollLine.all_objects.filter(booking__reservation__group=group).exclude(statement__status='draft').exists()
        or StaffIncentiveLine.all_objects.filter(group=group).exclude(statement__status='draft').exists()
    )


class InsuranceLedgerTestOrderError(ValueError):
    pass


@transaction.atomic
def set_order_test_status(group, *, is_test, actor, reason):
    """Call while holding the tenant and order locks, in that order."""
    from .discount_usage import rebuild_discount_usage
    from .loyalty import rebuild_loyalty_account
    from .models import InsuranceLedgerEntry, MemberLoyaltyAccount, MemberLoyaltyEntry, OrderDiscountUsage
    from .operations import record_order_revision

    if group.is_test == is_test:
        return
    if is_test and InsuranceLedgerEntry.objects.filter(account__client_id=group.client_id, order_id=group.pk).exists():
        raise InsuranceLedgerTestOrderError('此訂單已有預付保費分錄，不能標記為測試訂單。')
    if is_test and _has_financial_history(group):
        raise ValueError('此訂單已有付款、退款、差額或薪獎出帳紀錄，請先由主管依既有流程更正，再標記為測試訂單。')

    account_ids = MemberLoyaltyEntry.all_objects.filter(order__group=group).values('account_id')
    accounts = list(MemberLoyaltyAccount.objects.select_for_update().filter(
        client_id=group.client_id, pk__in=account_ids,
    ).order_by('pk'))
    # Initialize any legacy opening balances with the previous visibility still in effect.
    for account in accounts:
        if account.opening_points is None or account.opening_rewards is None:
            rebuild_loyalty_account(account)
    group.is_test = is_test
    group.test_marked_by = actor if is_test else None
    group.test_marked_at = timezone.now() if is_test else None
    group.save(update_fields=['is_test', 'test_marked_by', 'test_marked_at'])
    for account in accounts:
        rebuild_loyalty_account(account)
    rule_ids = set(OrderDiscountUsage.objects.filter(reservation__group=group).values_list('rule_id', flat=True))
    if rule_ids:
        rebuild_discount_usage(group.client, rule_ids)
    record_order_revision(group, user=actor, reason=reason,
                          change_type='mark_test' if is_test else 'unmark_test')
