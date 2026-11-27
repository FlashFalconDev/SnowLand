"""Transactions for the school's prepaid insurance account."""
from datetime import date, datetime, time
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .insurance_ledger_models import InsuranceLedgerEntry, InsurancePrepaidAccount, InsuranceReconciliation


Kind = InsuranceLedgerEntry.Kind
ZERO = Decimal('0.00')
MAX_BALANCE = Decimal('99999999999999.99')


def account_for_update(client):
    """All writers hold the tenant row first, including while opening an account."""
    return InsurancePrepaidAccount.objects.select_for_update().filter(client=client).first()


def ledger_writable(config, account):
    return config.enabled and bool(config.currency) and (account is None or account.currency == config.currency)


def require_writable(config, account):
    if not config.enabled:
        raise PermissionDenied('預付保費帳本已停用，目前僅供查閱。')
    if not ledger_writable(config, account):
        raise ValidationError({'msg': '請先設定有效幣別，且須與已開立的帳戶幣別一致。'})


def replay_entry(client, key, fingerprint):
    if key is None:
        return None
    entry = InsuranceLedgerEntry.objects.filter(idempotency_key=key).select_related('account').first()
    if entry and (entry.account.client_id != client.pk or entry.request_fingerprint != fingerprint):
        raise ValidationError({'msg': '此識別碼已用於其他帳務請求，請重新核對後送出。'})
    return entry


def entry_change(kind, amount, target=None):
    if kind == Kind.REVERSAL:
        return -entry_change(target.kind, amount)
    return -amount if kind == Kind.DEDUCTION else amount


def append_entry(account, kind, amount, actor, *, key=None, fingerprint='', member=None,
                 target=None, reference='', note='', posted_at=None):
    balance = account.balance + entry_change(kind, amount, target)
    if balance < ZERO:
        raise ValidationError({'msg': '預付保費餘額不足，請由財務確認並儲值後再試。'})
    if balance > MAX_BALANCE:
        raise ValidationError({'msg': '入帳後餘額超過可記錄上限。'})
    source = ({
        'member_id': member.pk, 'member_record_id': member.pk, 'order_id': member.reservation.group_id,
    } if member else {
        'member_id': target.member_id, 'member_record_id': target.member_record_id, 'order_id': target.order_id,
    } if target else {})
    # The unique UUID also arbitrates coincidental reuse by another tenant.
    try:
        with transaction.atomic():
            entry = InsuranceLedgerEntry.objects.create(
                account=account, kind=kind, amount=amount, balance_after=balance, actor=actor,
                sequence=account.version + 1, reverses=target, reference=reference, note=note,
                created_at=posted_at or timezone.now(),
                request_fingerprint=fingerprint, **source, **({'idempotency_key': key} if key else {}),
            )
    except IntegrityError:
        if key and InsuranceLedgerEntry.objects.filter(idempotency_key=key).exists():
            raise ValidationError({'msg': '此識別碼已用於其他帳務請求，請重新核對後送出。'})
        raise
    account.balance = balance
    account.version = entry.sequence
    account.save(update_fields=['balance', 'version'])
    return entry


def deposit(client, account, config, actor, data, fingerprint):
    require_writable(config, account)
    kind = data['kind']
    if account is None:
        if kind != Kind.OPENING:
            raise ValidationError({'msg': '請先核對並登錄期初餘額。'})
        account = InsurancePrepaidAccount.objects.create(client=client, currency=config.currency, balance=ZERO)
    elif kind == Kind.OPENING:
        raise ValidationError({'msg': '此帳戶已登錄期初，請使用儲值或沖正。'})
    return append_entry(account, kind, data['amount'], actor, key=data['idempotency_key'],
                        fingerprint=fingerprint, reference=data['reference'], note=data.get('note', ''))


def reverse_entry(account, target, actor, *, note, key=None, fingerprint='', reference='', posted_at=None):
    if target.kind == Kind.REVERSAL or InsuranceLedgerEntry.objects.filter(reverses=target).exists():
        raise ValidationError({'msg': '這筆分錄已沖正，或本身就是沖正分錄。'})
    return append_entry(account, Kind.REVERSAL, target.amount, actor, target=target,
                        key=key, fingerprint=fingerprint, reference=reference, note=note, posted_at=posted_at)


def guard_paused_premium(config, *, has_history):
    if not config.enabled and has_history:
        raise ValidationError({'msg': '預付保費帳本已停用，請啟用帳本後再變更保費。'})


def record_premium(member, account, config, actor, data, fingerprint, *, can_deduct):
    amount = data['premium_amount']
    previous = member.insurance_premium_amount
    if (amount, data['currency']) == (previous, member.insurance_premium_currency):
        return
    if amount and (member.insurance_processing_status == 'ineligible' or data['status'] == 'ineligible'):
        raise ValidationError({'msg': '不符投保資格時無法新增投保金額，請先復原為對資料中。'})
    if not config.enabled:
        if amount or previous:
            guard_paused_premium(config, has_history=bool(account and account.version))
        return
    if not can_deduct and (amount or member.insurance_premium_ledger_key):
        raise PermissionDenied('沒有保費帳本扣款權限。')
    if not amount:
        return
    require_writable(config, account)
    if member.reservation.group.is_test:
        raise ValidationError({'msg': '測試訂單不能扣款。'})
    if data['currency'] != config.currency:
        raise ValidationError({'msg': f'保費幣別須為帳本幣別 {config.currency}。'})
    if account is None:
        raise ValidationError({'msg': '尚未開立預付保費帳戶，請由財務登錄期初。'})
    key = data.get('idempotency_key')
    if key is None:
        raise ValidationError({'msg': '保費扣款需要識別碼，請重新載入頁面後再試。'})
    prior = account.entries.filter(
        kind=Kind.DEDUCTION, idempotency_key=member.insurance_premium_ledger_key,
        member_record_id=member.pk, reversal__isnull=True,
    ).first()
    posted_at = timezone.now()
    if prior:
        if not data.get('correction_note'):
            raise ValidationError({'msg': '更正已扣款的保費時，請填寫沖正原因。'})
        reverse_entry(account, prior, actor, note=data['correction_note'], posted_at=posted_at)
    entry = append_entry(account, Kind.DEDUCTION, amount, actor, key=key, fingerprint=fingerprint,
                         member=member, note=data.get('correction_note', ''), posted_at=posted_at)
    member.insurance_premium_ledger_key = entry.idempotency_key


def month_bounds(month):
    next_month = date(month.year + 1, 1, 1) if month.month == 12 else month.replace(month=month.month + 1)
    zone = timezone.get_default_timezone()
    return tuple(timezone.make_aware(datetime.combine(day, time.min), zone) for day in (month, next_month))


def reconciliation_totals(account, month):
    start, end = month_bounds(month)
    previous = account.entries.filter(created_at__lt=start).order_by('-sequence').values('sequence', 'balance_after').first()
    totals = account.entries.filter(created_at__gte=start, created_at__lt=end).aggregate(
        cutoff_sequence=Max('sequence'),
        initial=Sum('amount', filter=Q(kind=Kind.OPENING), default=ZERO),
        top_ups=Sum('amount', filter=Q(kind=Kind.TOP_UP), default=ZERO),
        deductions=Sum('amount', filter=Q(kind=Kind.DEDUCTION), default=ZERO),
        reversal_credits=Sum('amount', filter=Q(kind=Kind.REVERSAL, reverses__kind=Kind.DEDUCTION), default=ZERO),
        reversal_debits=Sum('amount', filter=Q(kind=Kind.REVERSAL, reverses__kind__in=[Kind.OPENING, Kind.TOP_UP]), default=ZERO),
    )
    opening = totals['initial'] + (previous['balance_after'] if previous else ZERO)
    reversals = totals['reversal_credits'] - totals['reversal_debits']
    return {
        'opening': opening, 'top_ups': totals['top_ups'], 'deductions': totals['deductions'],
        'reversals': reversals, 'closing': opening + totals['top_ups'] - totals['deductions'] + reversals,
        'cutoff_sequence': totals['cutoff_sequence'] or (previous['sequence'] if previous else 0),
    }
