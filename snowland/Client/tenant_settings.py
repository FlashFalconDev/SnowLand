"""School-owned settings; missing credentials must never borrow another school's."""
import os
import re
from django.conf import settings
from .models import ModuleSetting, ModuleInfo


def module_enabled(client, key):
    if ModuleInfo.objects.filter(module_sid=key,is_active=False).exists():
        return False
    row=ModuleSetting.objects.filter(client=client,module__module_sid=key).select_related('module').first()
    return row is None or (row.is_active and row.module.is_active)


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
