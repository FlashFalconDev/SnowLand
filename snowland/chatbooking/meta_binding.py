import hashlib
import hmac
import json
import os
import re
from urllib.parse import urlencode, urlsplit

import requests
from cryptography.fernet import InvalidToken
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.views.decorators.debug import sensitive_variables

from Client.models import Client
from .channel_binding import cipher
from .models import MetaPageBinding


class MetaBindingError(ValueError):
    pass


def platform_config():
    config = {key.lower(): os.getenv(f'SNOWLAND_META_{key}', '').strip()
              for key in ('APP_ID', 'APP_SECRET', 'CONFIG_ID', 'GRAPH_VERSION', 'REDIRECT_URI')}
    try:
        redirect = urlsplit(config['redirect_uri'])
    except ValueError:
        raise MetaBindingError('平台尚未設定 Meta 商家登入') from None
    if (not all(config.values()) or not cipher() or redirect.scheme != 'https' or not redirect.hostname
            or redirect.username or redirect.password or redirect.query or redirect.fragment
            or redirect.path != reverse('meta-social-callback')
            or not re.fullmatch(r'v[0-9]{1,3}\.[0-9]+', config['graph_version'])):
        raise MetaBindingError('平台尚未設定 Meta 商家登入')
    return config


def authorization_url(state):
    config = platform_config()
    query = urlencode({'client_id': config['app_id'], 'config_id': config['config_id'],
                       'response_type': 'code', 'override_default_response_type': 'true',
                       'redirect_uri': config['redirect_uri'], 'state': state})
    return f'https://www.facebook.com/{config["graph_version"]}/dialog/oauth?{query}'


def status(client):
    try:
        platform_config()
        configured = True
    except MetaBindingError:
        configured = False
    row = MetaPageBinding.objects.filter(client=client).first()
    return {'platform_ready': configured, 'page_id': row.page_id if row else '',
            'page_name': row.page_name if row else '', 'instagram_name': row.instagram_name if row else ''}


@sensitive_variables('config', 'fields', 'token', 'body')
def _graph(config, path, fields, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
        fields = {**fields, 'appsecret_proof': hmac.new(config['app_secret'].encode(), token.encode(), hashlib.sha256).hexdigest()}
    try:
        response = requests.get(f'https://graph.facebook.com/{config["graph_version"]}/{path}',
                                params=fields, headers=headers, timeout=8, allow_redirects=False)
        body = response.json() if response.status_code == 200 else None
        if isinstance(body, dict) and 'error' not in body:
            return body
    except (requests.RequestException, ValueError):
        pass
    raise MetaBindingError('Meta 未能確認所選帳號的授權')


@sensitive_variables('code', 'config', 'user_token')
def _exchange_code(config, code):
    user_token = _graph(config, 'oauth/access_token', {'client_id': config['app_id'],
        'client_secret': config['app_secret'], 'redirect_uri': config['redirect_uri'], 'code': code}).get('access_token')
    if not isinstance(user_token, str) or not user_token:
        raise MetaBindingError('Meta 未回傳授權')
    return user_token


@sensitive_variables('config', 'user_token', 'result', 'page')
def _authorized_pages(config, user_token):
    fields = {'fields': 'id,name,access_token,tasks,instagram_business_account{id,username}', 'limit': 100}
    for _ in range(5):
        result = _graph(config, 'me/accounts', fields, user_token)
        for page in result.get('data') or []:
            if (isinstance(page, dict) and re.fullmatch(r'[0-9]{1,32}', str(page.get('id', '')))
                    and 'MESSAGING' in (page.get('tasks') or [])
                    and isinstance(page.get('access_token'), str) and page['access_token']):
                yield page
        paging = result.get('paging') or {}
        after = (paging.get('cursors') or {}).get('after')
        if not paging.get('next') or not isinstance(after, str) or not after:
            break
        fields['after'] = after


@sensitive_variables('code', 'config', 'user_token', 'page')
def page_choices(code):
    config = platform_config()
    user_token = _exchange_code(config, code)
    choices = {}
    for page in _authorized_pages(config, user_token):
        page_id = str(page['id'])
        account = page.get('instagram_business_account') or {}
        choices[page_id] = {'id': page_id, 'name': str(page.get('name') or page_id)[:160],
                            'instagram_name': str(account.get('username') or '')[:80]}
    if not choices:
        raise MetaBindingError('沒有可綁定的粉絲專頁，請在 Meta 授權時選擇擁有訊息管理權限的專頁')
    return list(choices.values()), cipher().encrypt(user_token.encode()).decode()


@sensitive_variables('code', 'config', 'user_token')
def bind_page(client, code, page_id):
    config = platform_config()
    _bind_authorized_page(client, config, _exchange_code(config, code), page_id)


@sensitive_variables('credential', 'config', 'user_token')
def bind_page_choice(client, credential, page_id):
    config = platform_config()
    try:
        user_token = cipher().decrypt(credential.encode(), ttl=600).decode()
    except (InvalidToken, UnicodeError):
        raise MetaBindingError('Meta 授權已逾時，請重新授權') from None
    _bind_authorized_page(client, config, user_token, page_id)


@sensitive_variables('config', 'user_token', 'page', 'page_token', 'encrypted')
def _bind_authorized_page(client, config, user_token, page_id):
    page = next((page for page in _authorized_pages(config, user_token) if str(page['id']) == page_id), None)
    if not page:
        raise MetaBindingError('未授權指定的 Facebook 粉絲專頁或缺少訊息管理權限')
    page_token = page['access_token']
    account = page.get('instagram_business_account') or {}
    ig_id = str(account.get('id', ''))
    encrypted = cipher().encrypt(json.dumps({'client': client.pk, 'page': page_id, 'token': page_token}).encode())
    try:
        with transaction.atomic():
            Client.objects.select_for_update().get(pk=client.pk)
            MetaPageBinding.objects.update_or_create(client=client, defaults={
                'page_id': page_id, 'page_name': str(page.get('name', ''))[:160],
                'instagram_id': ig_id if re.fullmatch(r'[0-9]{1,32}', ig_id) else None,
                'instagram_name': str(account.get('username', ''))[:80], 'credentials': encrypted.decode(),
            })
    except IntegrityError:
        raise MetaBindingError('這個 Facebook 或 Instagram 帳號已由其他租戶綁定') from None
