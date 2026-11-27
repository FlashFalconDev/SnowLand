from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import OrderLoyalty, Payment


def exclude_test_orders(queryset, group_path=''):
    """Keep this explicit so history and administrative lookups can still see test orders."""
    field = f'{group_path}__is_test' if group_path else 'is_test'
    return queryset.exclude(**{field: True})


def financial_history_reasons(group):
    from Coach.models import PayrollLine, StaffIncentiveLine

    payments = Payment.all_objects.filter(reservation_group=group)
    checks = (
        (
            'payment_record', '付款紀錄',
            '到訂單詳情點「付款／排課」，或在「對帳與差額」搜尋訂單後點「核對付款」。',
            payments.filter(
                Q(status__in=('paid', 'refunded')) | Q(DataJSON__has_key='gateway_response')
                | Q(DataJSON__settlement__has_key='confirmed_at')
                | (Q(status='pending', bank_account__isnull=False) & ~Q(bank_account='')),
            ).exists(),
        ),
        (
            'bank_posted_date', '入帳日',
            '到「付款／排課」或「核對付款」查看入帳日期。狀態仍為已付款且租戶設定為選填時，才可清空。',
            payments.filter(bank_posted_date__isnull=False).exists(),
        ),
        (
            'newebpay', '藍新表單',
            '此訂單已產生藍新付款表單或已綁定商店。後台沒有清除入口，請交由帳務與工程確認。',
            group.newebpay_form_issued or group.newebpay_merchant_id is not None,
        ),
        (
            'refund', '退款',
            '到訂單詳情的「取消與退款處理」或「取消與退款」頁查看。後台無法撤銷已完成的退款。',
            group.cancellation_requests.filter(Q(status='refunded') | Q(actual_received_amount__gt=0)).exists(),
        ),
        (
            'amendment', '差額',
            '到「對帳與差額」開啟「差額回報與核對」。誤報補款可按「退回重填」，已結清的差額無法在後台單獨撤銷。',
            group.amendments.filter(status__in=('topup_reported', 'refund_account_due', 'refund_due', 'settled')).exists(),
        ),
        (
            'loyalty', '紅利',
            '此訂單已寫入紅利付款基準。後台沒有清除入口，請交由帳務與工程確認。',
            OrderLoyalty.all_objects.filter(group=group, paid_base__isnull=False).exists(),
        ),
        (
            'coach_payroll', '教練薪資',
            '到「薪資單與月結」查看明細。只有「待教練確認」且未過截止日的薪資單可以按「撤回草稿」。',
            PayrollLine.all_objects.filter(booking__reservation__group=group).exclude(statement__status='draft').exists(),
        ),
        (
            'staff_incentive', '行政獎金',
            '到「行政獎金」查看明細。後台目前無法撤回已確認或已發放的獎金。',
            StaffIncentiveLine.all_objects.filter(group=group).exclude(statement__status='draft').exists(),
        ),
    )
    return [{'code': code, 'label': label, 'hint': hint} for code, label, hint, matched in checks if matched]


class InsuranceLedgerTestOrderError(ValueError):
    pass


class FinancialHistoryTestOrderError(ValueError):
    def __init__(self, reasons, *, changed=False):
        super().__init__('帳務阻擋項目已變更，請重新核對後再確認。' if changed else
                         '此訂單已有帳務紀錄，無法標記為測試訂單。')
        self.reasons = reasons


@transaction.atomic
def set_order_test_status(group, *, is_test, actor, reason, acknowledged_reasons=None):
    """Call while holding the tenant and order locks, in that order."""
    from .discount_usage import rebuild_discount_usage
    from .loyalty import rebuild_loyalty_account
    from .models import InsuranceLedgerEntry, MemberLoyaltyAccount, MemberLoyaltyEntry, OrderDiscountUsage
    from .operations import record_order_revision

    if group.is_test == is_test:
        return
    if is_test and InsuranceLedgerEntry.objects.filter(account__client_id=group.client_id, order_id=group.pk).exists():
        raise InsuranceLedgerTestOrderError('此訂單已有預付保費分錄，不能標記為測試訂單。')
    reasons = financial_history_reasons(group) if is_test else []
    if acknowledged_reasons is None:
        if reasons:
            raise FinancialHistoryTestOrderError(reasons)
    elif set(acknowledged_reasons) != {item['code'] for item in reasons}:
        raise FinancialHistoryTestOrderError(reasons, changed=True)

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
                          change_type='mark_test' if is_test else 'unmark_test',
                          test_override_reasons=[{'code': item['code'], 'label': item['label']} for item in reasons])
