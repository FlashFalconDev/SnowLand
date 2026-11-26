"""Tenant-owned, write-only merchant credentials; retain revisions for issued forms."""
import json
import os
import re

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.views.decorators.debug import sensitive_variables

from Client.tenant_settings import gateway_settings
from .models import NewebpayMerchant


def _cipher():
    try:
        return Fernet(os.environ.get('SNOWLAND_NEWEBPAY_CREDENTIAL_KEY', '').encode())
    except ValueError:
        return None


def current_merchant(client):
    return NewebpayMerchant.objects.filter(client=client).order_by('-pk').first()


def merchant_credentials(merchant):
    cipher = _cipher()
    if cipher is None:
        return None
    try:
        stored = json.loads(cipher.decrypt(merchant.encrypted_credentials.encode()))
        if stored['client'] == merchant.client_id:
            return stored['store']
    except (InvalidToken, ValueError, KeyError, TypeError):
        pass
    return None


def order_card_allowed(group):
    if group.is_test:
        return False
    if group.newebpay_override is not None:
        return group.newebpay_override
    return (group.source_country or 'TW') != 'TW'


def merchant_environment_allowed(merchant):
    return merchant.environment == 'production' or (
        merchant.environment == 'sandbox' and settings.SNOWLAND_NEWEBPAY_SANDBOX_ENABLED
    )


def order_gateway(group):
    active = current_merchant(group.client)
    if active is None:
        return None, gateway_settings(group.client)
    if not active.enabled:
        return None, None
    if group.newebpay_form_issued and not group.newebpay_merchant_id:
        return None, gateway_settings(group.client)
    if not group.newebpay_merchant_id and (group.source_country or 'TW') != 'TW':
        legacy = gateway_settings(group.client)
        if legacy:
            earliest = NewebpayMerchant.objects.filter(client=group.client).order_by('pk').first()
            if earliest and group.created_at < earliest.created_at:
                # Old hosted forms were not recorded before the Console rollout.
                return None, legacy
    merchant = group.newebpay_merchant if group.newebpay_merchant_id else active
    if merchant.client_id != group.client_id or not merchant_environment_allowed(merchant):
        return None, None
    return merchant, merchant_credentials(merchant)


def configuration_status(client):
    active = current_merchant(client)
    return {
        'configured': bool(merchant_credentials(active)) if active else bool(gateway_settings(client)),
        'enabled': active.enabled if active else False,
        'environment': active.environment if active else None,
        'runtime_ready': bool(_cipher()),
        'sandbox_available': settings.SNOWLAND_NEWEBPAY_SANDBOX_ENABLED,
        'legacy': active is None and bool(gateway_settings(client)),
    }


@sensitive_variables('payload', 'key', 'iv', 'encrypted')
def save_configuration(client, payload):
    allowed = {'merchant_id', 'hash_key', 'hash_iv', 'environment', 'enabled'}
    if set(payload) - allowed or type(payload.get('enabled')) is not bool:
        raise ValueError('藍新設定格式錯誤')
    active = current_merchant(client)
    supplied = {'merchant_id', 'hash_key', 'hash_iv', 'environment'} & set(payload)
    if supplied:
        merchant_id, key, iv, environment = (payload.get(field) for field in (
            'merchant_id', 'hash_key', 'hash_iv', 'environment',
        ))
        if (not isinstance(merchant_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,15}', merchant_id)
                or not isinstance(key, str) or not re.fullmatch(r'[!-~]{32}', key)
                or not isinstance(iv, str) or not re.fullmatch(r'[!-~]{16}', iv)
                or environment not in ('sandbox', 'production')):
            raise ValueError('請完整填入商店代號、32 字元 HashKey、16 字元 HashIV 和環境')
        cipher = _cipher()
        if cipher is None:
            raise ValueError('平台尚未設定金流憑證加密，不能保存金鑰')
        if payload['enabled']:
            raise ValueError('請先儲存新商店，再確認環境後另行啟用')
        encrypted = cipher.encrypt(json.dumps({
            'client': client.pk, 'store': {'MerchantID': merchant_id, 'HashKey': key, 'HashIV': iv},
        }).encode()).decode()
        NewebpayMerchant.objects.create(client=client, environment=environment, encrypted_credentials=encrypted)
    elif active:
        if payload['enabled'] and (not merchant_credentials(active) or not merchant_environment_allowed(active)):
            raise ValueError('商店尚未備妥，不能開啟刷卡')
        active.enabled = payload['enabled']
        active.save(update_fields=['enabled'])
    else:
        raise ValueError('請先設定本租戶的藍新商店')
    return configuration_status(client)
