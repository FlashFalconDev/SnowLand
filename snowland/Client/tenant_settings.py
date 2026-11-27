"""School-owned settings; missing credentials must never borrow another school's."""
import os
import re
from decimal import Decimal
from typing import NamedTuple
from django.conf import settings
from .models import ModuleSetting, ModuleInfo


def module_enabled(client, key):
    if ModuleInfo.objects.filter(module_sid=key,is_active=False).exists():
        return False
    row=ModuleSetting.objects.filter(client=client,module__module_sid=key).select_related('module').first()
    return row is None or (row.is_active and row.module.is_active)


def learner_rename_policy(client):
    """Read learner_rename_policy from this tenant's booking module settings."""
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    policy = config.get('learner_rename_policy') if isinstance(config, dict) else None
    return policy if policy in ('unlinked_only', 'owner_all') else 'disabled'


def manual_payment_posting_date_mode(client):
    """Read the tenant's booking JSON from Django Admin → 模組設定."""
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    mode = config.get('manual_payment_posting_date_mode') if isinstance(config, dict) else None
    return mode if mode in ('optional', 'required', 'disabled') else 'optional'


def order_refund_charge_enabled(client):
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    return isinstance(config, dict) and config.get('order_refund_charge_enabled') is True


def course_album_coach_delete_enabled(client):
    """By default the current instructor may delete their own uploads."""
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    return not isinstance(config, dict) or config.get('course_album_coach_delete_enabled') is not False


class InsuranceLedgerSettings(NamedTuple):
    enabled: bool
    currency: str
    low_balance: Decimal | None


def insurance_ledger_settings(client):
    """Read the school's typed values from the active booking module."""
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    config = config if isinstance(config, dict) else {}
    currency = config.get('insurance_ledger_currency')
    currency = currency.strip().upper() if isinstance(currency, str) else ''
    if not re.fullmatch(r'[A-Z]{3}', currency):
        currency = ''
    threshold = config.get('insurance_ledger_low_balance')
    low_balance = Decimal(str(threshold)) if type(threshold) in (int, float) else None
    if low_balance is not None and (not low_balance.is_finite() or low_balance < 0):
        low_balance = None
    return InsuranceLedgerSettings(config.get('insurance_ledger_enabled') is True, currency, low_balance)


def test_order_marking_enabled(client):
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    return not isinstance(config, dict) or config.get('test_order_marking_enabled') is not False


def test_order_financial_override_enabled(client):
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    return not isinstance(config, dict) or config.get('test_order_financial_override_enabled') is not False


def order_source_override_enabled(client):
    """Enable order source corrections unless the tenant turns off editing."""
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    return not isinstance(config, dict) or config.get('order_source_override_enabled') is not False


def coach_course_payroll_summary_enabled(client):
    """Use payroll hours in My Courses unless the tenant opts out."""
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    return not isinstance(config, dict) or config.get('coach_course_payroll_summary_enabled') is not False


def evaluation_date_filter_defaults(client):
    """Return the admin list defaults, or None for the tenant's legacy list."""
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    config = config if isinstance(config, dict) else {}
    if config.get('evaluation_date_filters_enabled') is False:
        return None
    field = config.get('evaluation_default_date_field')
    days = config.get('evaluation_default_date_range_days')
    return (
        field if field in ('ordered', 'lesson') else 'ordered',
        days if type(days) is int and 1 <= days <= 366 else 30,
    )


def booking_discount_settings(client):
    """Read and validate the tenant's discount rules from its booking JSON."""
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    config = config if isinstance(config, dict) else {}
    basis = config.get('discount_course_scope_basis')
    if basis not in ('course_fee_only', 'legacy_group_subtotal'):
        basis = 'course_fee_only'
    codes = config.get('discount_photo_bundle_qualifying_course_codes')
    qualifying_codes = {
        code.strip().upper() for code in codes if isinstance(code, str) and code.strip()
    } if isinstance(codes, list) else set()
    return basis, qualifying_codes


def staff_booking_link_edit_enabled(client):
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    return not isinstance(config, dict) or config.get('staff_booking_link_edit_enabled') is not False


def _vehicle_review_settings(client):
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='vehicle_review', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    return config if isinstance(config, dict) else {}


def insurance_eligibility_settings(client) -> tuple[bool, bool]:
    """Return explicit (enabled, allow_admin) flags from the active booking settings."""
    config = ModuleSetting.objects.filter(
        client=client, module__module_sid='booking', module__is_active=True, is_active=True,
    ).values_list('settings', flat=True).first()
    if not isinstance(config, dict):
        return False, False
    return config.get('insurance_eligibility_enabled') is True, config.get('insurance_eligibility_allow_admin') is True


def vehicle_conflict_mode(client):
    mode = _vehicle_review_settings(client).get('vehicle_conflict_mode')
    # TODO(vehicle_conflict_mode=auto_revoke): keep using manual_review until scheduling supports automatic revocation.
    return mode if mode in ('manual_review', 'block') else 'manual_review'


def vehicle_calendar_visible_to_coaches(client):
    value = _vehicle_review_settings(client).get('vehicle_calendar_visible_to_coaches')
    if isinstance(value, str):
        return value.strip().lower() not in ('false', 'off', 'no', '0')
    # JSON false and numeric zero both compare equal to zero.
    return value != 0


def gateway_settings(client):
    prefix=(client.payment_env_prefix or '').strip()
    if prefix:
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}',prefix):
            return None
        values={key:os.getenv(f'{prefix}_{suffix}','').strip() for key,suffix in
            [('MerchantID','MERCHANT_ID'),('HashKey','HASH_KEY'),('HashIV','HASH_IV')]}
    elif client.internal_code == getattr(settings,'SNOWLAND_LEGACY_PAYMENT_CLIENT_CODE','snowland'):
        # Preserve the deployed school's existing configuration only.
        values={'MerchantID':settings.NEWEBPAY_MERCHANT_ID,'HashKey':settings.NEWEBPAY_HASH_KEY,'HashIV':settings.NEWEBPAY_HASH_IV}
    else:
        return None
    return values if all(values.values()) else None


def google_client_id(client):
    return client.google_oauth_client_id.strip() or settings.GOOGLE_OAUTH_CLIENT_ID
