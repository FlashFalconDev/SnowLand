"""Order currency uses explicit decimal rates; existing price ledgers stay in TWD."""
from decimal import Decimal, ROUND_HALF_UP
import re

from django.db import transaction
from django.utils import timezone
from Resorts.models import PaymentCurrencySettings


def currency_settings_payload(tenant):
    config = PaymentCurrencySettings.objects.filter(client=tenant).first()
    return {
        'jpy_enabled': config.jpy_enabled if config else False,
        'jpy_per_twd': format(config.jpy_per_twd, '.8f') if config and config.jpy_per_twd is not None else '',
    }


def validate_currency_settings(value):
    if not isinstance(value, dict) or set(value) - {'jpy_enabled', 'jpy_per_twd'}:
        raise ValueError('日幣設定格式錯誤')
    enabled, raw = value.get('jpy_enabled'), value.get('jpy_per_twd')
    if not isinstance(enabled, bool):
        raise ValueError('開放日幣匯款必須是勾選值')
    if raw in ('', None) and not enabled:
        return {'jpy_enabled': False, 'jpy_per_twd': None}
    if not isinstance(raw, str) or not re.fullmatch(r'[0-9]{1,9}(?:\.[0-9]{1,8})?', raw.strip()):
        raise ValueError('請輸入大於0、最多8位小數的匯率（1台幣可換多少日幣）')
    rate = Decimal(raw.strip())
    if rate <= 0:
        raise ValueError('匯率必須大於0')
    return {'jpy_enabled': enabled, 'jpy_per_twd': rate}


def convert_twd_amount(amount, rate):
    if isinstance(amount, bool) or not isinstance(amount, int) or abs(amount) > 9007199254740991:
        raise ValueError('金額必須為安全範圍內的整數')
    result = int((Decimal(amount) * rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    if abs(result) > 9007199254740991:
        raise ValueError('換算金額超過可處理範圍，請調整匯率或聯絡行政')
    return result


@transaction.atomic
def initialize_order_currency(group, currency='TWD', *, expected_rate=None):
    """Called once after server pricing, even when waiting for a coach/class."""
    from .operations import resolve_payment_account
    if currency not in ('TWD', 'JPY'):
        raise ValueError('目前僅接受台幣或日幣')
    if group.currency_snapshot:
        if group.currency_snapshot['currency'] != currency:
            raise ValueError('訂單成立後不可變更付款幣別')
        return
    base_amount = sum(group.reservations.exclude(status__in=['deleted', 'cancelled']).values_list('payment_amount', flat=True))
    rate, bank = Decimal('1'), {}
    if currency == 'JPY':
        config = PaymentCurrencySettings.objects.select_for_update().filter(client=group.client).first()
        if not config or not config.jpy_enabled or not config.jpy_per_twd or config.jpy_per_twd <= 0:
            raise ValueError('目前未開放日幣付款，請改選台幣')
        rate = config.jpy_per_twd
        displayed = validate_currency_settings({'jpy_enabled':True,'jpy_per_twd':expected_rate})['jpy_per_twd']
        if displayed != rate:
            raise ValueError('日幣匯率已更新，請重新載入並確認金額後送出；本次未建立訂單')
        account = resolve_payment_account(group, currency='JPY', lock=True)
        if not account or not all(str(getattr(account, field)).strip() for field in ('bank_name','bank_branch','account_number','account_holder')):
            raise ValueError('所選校區尚無可用的日幣收款帳戶，請改選台幣或聯絡行政')
        bank = {'account_id':account.pk, 'bank_name':account.bank_name, 'bank_branch':account.bank_branch,
            'bank_account_number':account.account_number, 'bank_account_holder':account.account_holder,
            'overseas_details':account.overseas_details}
    snapshot = {'currency':currency, 'base_currency':'TWD', 'rate':format(rate,'.8f'),
        'base_amount':base_amount, 'amount':convert_twd_amount(base_amount,rate),
        'bank_info':bank, 'locked_at':timezone.now().isoformat()}
    if currency == 'JPY' and base_amount > 0 and snapshot['amount'] < 1:
        raise ValueError('換算後低於1日圓，請改選台幣或聯絡行政調整匯率')
    group.currency_snapshot = snapshot
    group.save(update_fields=['currency_snapshot'])


def order_settlement(group, *, base_amount=None):
    """Current payable at the original rate; never consult today's exchange rate."""
    if base_amount is None:
        base_amount = sum(group.reservations.exclude(status__in=['deleted', 'cancelled']).values_list('payment_amount',flat=True))
    snapshot = group.currency_snapshot or {'currency':'TWD','base_currency':'TWD','rate':'1.00000000','locked_at':None,'bank_info':{}}
    return {**snapshot, 'base_amount':base_amount, 'amount':convert_twd_amount(base_amount,Decimal(snapshot['rate']))}


def settlement_summary(group, *, base_amount=None):
    """Order listings expose amounts, not bank instructions before payment opens."""
    snapshot=order_settlement(group,base_amount=base_amount)
    return {key:snapshot[key] for key in ('currency','base_currency','base_amount','amount','rate','locked_at')}


def received_settlement_summary(group):
    payment=group.payments.order_by('-created_at','-pk').first()
    if not payment or payment.status!='paid' or not isinstance(payment.DataJSON,dict):
        return None
    snapshot=payment.DataJSON.get('settlement')
    if not isinstance(snapshot,dict) or not snapshot.get('confirmed_at'):
        return None
    keys=('currency','base_currency','base_amount','amount','rate','locked_at')
    return {key:snapshot[key] for key in keys} if all(key in snapshot for key in keys) else None


def amendment_settlement(group,previous_total,new_total,*,pending=()):
    """Subtract rounded order totals, not a rounded TWD difference, at the locked rate."""
    snapshot=group.currency_snapshot or {}
    if snapshot.get('currency')!='JPY':return {}
    rate=Decimal(snapshot['rate'])
    old=convert_twd_amount(previous_total,rate);new=convert_twd_amount(new_total,rate)
    balance=new-old
    for row in pending:
        previous=row.currency_snapshot
        if previous.get('currency')!='JPY' or previous.get('rate')!=snapshot['rate']:
            raise ValueError('舊差額缺少一致的日幣紀錄，請先核對後再修改')
        balance+=previous['balance_amount']
    if abs(balance)>9007199254740991:raise ValueError('日幣差額超過可處理範圍，請聯絡行政')
    return {'currency':'JPY','base_currency':'TWD','rate':snapshot['rate'],'locked_at':snapshot.get('locked_at'),
        'previous_total':old,'new_total':new,'difference_amount':new-old,'balance_amount':balance}


def cancellation_settlement(group,original_amount,refund_amount):
    snapshot=group.currency_snapshot or {}
    if snapshot.get('currency')!='JPY':return {}
    rate=Decimal(snapshot['rate'])
    return {'currency':'JPY','base_currency':'TWD','rate':snapshot['rate'],'locked_at':snapshot.get('locked_at'),
        'original_amount':convert_twd_amount(original_amount,rate),
        'refund_amount':None if refund_amount is None else convert_twd_amount(refund_amount,rate)}


def public_cancellation_settlement(cancellation):
    snapshot=cancellation.currency_snapshot or {}
    if snapshot.get('currency')!='JPY':return {}
    result={key:snapshot.get(key) for key in ('currency','base_currency','rate','locked_at','original_amount','refund_amount')}
    if cancellation.requires_cash_review and cancellation.actual_received_amount is None:result['refund_amount']=None
    return result
