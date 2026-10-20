"""Administrator-reviewed deductions. No statutory rates and no money transfer."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import PayrollStatement


def number(value, label, maximum, places=0):
    if isinstance(value, (bool, float)):
        raise ValueError(f'{label}請使用正確的數字格式')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label}請使用正確的數字格式') from None
    if not result.is_finite() or result < 0 or result > maximum or result.as_tuple().exponent < -places:
        raise ValueError(f'{label}超出範圍或小數位數')
    return result


def rounded(value):
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


@transaction.atomic
def save_settlement(statement, data, user):
    statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
    if statement.status != 'draft':
        raise ValueError('僅草稿可設定稅金與發放幣別')
    if not isinstance(data, dict) or data.get('reviewed') is not True:
        raise ValueError('請由行政核對扣項、匯率與適用金額後再儲存')
    if data.get('expected_reviewed_at') != statement.settlement_snapshot.get('reviewed_at'):
        raise ValueError('核對版本已變更，請重新載入，避免覆蓋其他行政人員的設定')
    expected = number(data.get('base_amount'), '台幣應發基準', 1000000000)
    if expected != statement.total_amount or statement.total_amount < 0:
        raise ValueError('薪資金額已變更，請重新載入後核對')
    currency = data.get('currency')
    if currency not in {'TWD', 'JPY'}:
        raise ValueError('薪資僅支援台幣或日幣')
    rate = number(data.get('rate'), '匯率', 1000, 8)
    if rate <= 0 or (currency == 'TWD' and rate != 1):
        raise ValueError('台幣匯率必須為1；日幣匯率必須大於0')
    gross = rounded(expected * rate)
    if expected > 0 and gross == 0:
        raise ValueError('換算後應發金額不可小於1，請核對匯率')
    rows = data.get('deductions')
    if not isinstance(rows, list) or len(rows) > 10:
        raise ValueError('請提供最多10個扣項；無扣項請明確核對空清單')
    deductions = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('扣項格式錯誤')
        name = row.get('name')
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            raise ValueError('請填寫100字內的扣項名稱')
        basis = number(row.get('basis'), '扣項適用金額', gross)
        percent = number(row.get('percent'), '扣項比例', 100, 4)
        deductions.append({'name': name.strip(), 'basis': int(basis), 'percent': str(percent),
            'amount': rounded(basis * percent / Decimal(100))})
    deduction_total = sum(row['amount'] for row in deductions)
    if deduction_total > gross:
        raise ValueError('扣款合計不能超過應發薪資')
    note = data.get('note', '')
    if not isinstance(note, str) or len(note) > 1000:
        raise ValueError('核對說明請填寫1000字以內')
    net = gross - deduction_total
    # Allocate the original TWD basis, not a future/live exchange rate.
    base_net = rounded(expected * Decimal(net) / Decimal(gross)) if gross else int(expected)
    statement.settlement_snapshot = {'version': 1, 'base_currency': 'TWD', 'base_amount': int(expected),
        'currency': currency, 'rate': str(rate), 'gross_amount': gross, 'deductions': deductions,
        'deduction_total': deduction_total, 'net_amount': net, 'base_net_amount': base_net,
        'base_deduction_total': int(expected) - base_net, 'note': note.strip(),
        'reviewed_by': user.pk, 'reviewed_at': timezone.now().isoformat()}
    statement.save(update_fields=['settlement_snapshot', 'updated_at'])
    return statement
