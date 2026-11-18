import json
import os
import re

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import IntegrityError, transaction
from django.views.decorators.debug import sensitive_variables

from Client.models import Client
from .line import LineConfigurationError
from .models import LineChannelBinding


def cipher():
    try:
        return Fernet(os.environ.get('SNOWLAND_SOCIAL_CREDENTIAL_KEY', '').encode())
    except ValueError:
        return None


def legacy_code():
    return settings.LINE_CLIENT_CODE.strip() or 'snowland'


def connection_status(client):
    row = LineChannelBinding.objects.filter(client=client).first()
    runtime_ready = cipher() is not None
    return {
        'runtime_ready': runtime_ready,
        'enabled': bool(row and row.enabled),
        'verified': bool(runtime_ready and row and row.enabled and row.webhook_verified_at),
        'display_name': row.display_name if row else '',
        'legacy': not row and client.internal_code == legacy_code() and bool(settings.LINE_CHANNEL_SECRET),
        'webhook_path': f'/booking/{client.internal_code}/api/chat/line/webhook/',
    }


@sensitive_variables('payload', 'secret', 'token', 'encrypted')
def bind_line(client, payload):
    if not isinstance(payload, dict) or set(payload) != {'channel_secret', 'access_token'}:
        raise ValueError('請輸入 LINE Channel Secret 與 Channel Access Token')
    secret, token = payload['channel_secret'], payload['access_token']
    if (not isinstance(secret, str) or not re.fullmatch(r'[0-9a-fA-F]{32}', secret)
            or not isinstance(token, str) or not re.fullmatch(r'[!-~]{20,4096}', token)):
        raise ValueError('LINE 頻道資料格式不符')
    encryption = cipher()
    if encryption is None:
        raise ValueError('平台尚未設定社群憑證加密')
    try:
        info = requests.get('https://api.line.me/v2/bot/info',
                            headers={'Authorization': f'Bearer {token}'}, timeout=8, allow_redirects=False)
        data = info.json() if info.status_code == 200 else {}
        bot_id = data.get('userId', '')
        name = data.get('displayName', '')
        if not re.fullmatch(r'U[0-9a-f]{32}', bot_id) or not isinstance(name, str) or not name.strip():
            raise ValueError
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        raise ValueError('LINE 未能驗證 Access Token，請確認官方頻道設定') from None
    encrypted = encryption.encrypt(json.dumps({'client': client.pk, 'bot': bot_id, 'secret': secret, 'token': token}).encode())
    try:
        with transaction.atomic():
            Client.objects.select_for_update().get(pk=client.pk)
            row = LineChannelBinding.objects.filter(client=client).first()
            if row and row.enabled and row.bot_id != bot_id:
                raise ValueError('請先停用現有頻道，再綁定另一個官方帳號')
            LineChannelBinding.objects.update_or_create(client=client, defaults={
                'bot_id': bot_id, 'display_name': name[:100], 'credentials': encrypted.decode(),
                'enabled': True, 'webhook_verified_at': None,
            })
    except IntegrityError:
        raise ValueError('此 LINE 官方帳號已綁定其他租戶') from None


def line_credentials(client):
    row = LineChannelBinding.objects.filter(client=client).first()
    if row is None and client.internal_code == legacy_code():
        return None, settings.LINE_CHANNEL_SECRET, settings.LINE_CHANNEL_ACCESS_TOKEN
    encryption = cipher()
    if not row or not row.enabled or not encryption:
        raise LineConfigurationError('LINE 頻道尚未設定或已停用')
    try:
        data = json.loads(encryption.decrypt(row.credentials.encode()))
        if data['client'] == client.pk and data['bot'] == row.bot_id:
            return row, data['secret'], data['token']
    except (InvalidToken, ValueError, KeyError, TypeError):
        pass
    raise LineConfigurationError('LINE 頻道憑證無法讀取')
