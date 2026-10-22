"""Read-only Instagram professional-account media sync. Never publish to Instagram."""
from datetime import timedelta
import re
from urllib.parse import urlencode, urlsplit

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Client, InstagramConnection, SiteContent


class InstagramError(ValueError):
    pass


def configuration():
    values = {name: getattr(settings, 'SNOWLAND_INSTAGRAM_' + name, '') for name in
              ('APP_ID', 'APP_SECRET', 'REDIRECT_URI', 'TOKEN_KEY', 'API_VERSION')}
    missing = [name for name, value in values.items() if not value]
    if values['TOKEN_KEY']:
        try:
            Fernet(values['TOKEN_KEY'].encode())
        except (ValueError, TypeError, UnicodeError):
            missing.append('TOKEN_KEY（格式錯誤）')
    if values['API_VERSION'] and not re.fullmatch(r'v[0-9]{1,3}\.[0-9]{1,2}', values['API_VERSION']):
        missing.append('API_VERSION（格式錯誤）')
    try:
        redirect = urlsplit(values['REDIRECT_URI'])
    except ValueError:
        redirect = urlsplit('')
        missing.append('REDIRECT_URI（格式錯誤）')
    if values['REDIRECT_URI'] and (redirect.scheme != 'https' or not redirect.netloc or redirect.username or redirect.password or redirect.fragment or redirect.query):
        missing.append('REDIRECT_URI（須為已註冊的HTTPS回呼網址）')
    return values, missing


def _config():
    values, missing = configuration()
    if missing:
        raise InstagramError('請由系統管理員完成 IG 應用程式設定：' + '、'.join(missing))
    return values


def _json(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=(5, 15), allow_redirects=False, **kwargs)
        if response.status_code != 200:
            raise InstagramError('IG 授權已失效或服務暫時無法使用，請重新授權或稍後再試')
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        if isinstance(exc, InstagramError):
            raise
        # Exception URLs and provider bodies can contain tokens; never expose them.
        raise InstagramError('IG 連線失敗，既有貼文未變更') from None
    if not isinstance(data, dict) or data.get('error'):
        raise InstagramError('IG 回傳資料不完整，既有貼文未變更')
    return data


def authorization_url(state):
    values = _config()
    return 'https://www.instagram.com/oauth/authorize?' + urlencode({
        'client_id': values['APP_ID'], 'redirect_uri': values['REDIRECT_URI'],
        'response_type': 'code', 'scope': 'instagram_business_basic',
        'state': state, 'enable_fb_login': '0', 'force_authentication': '1'})


def _expiry(payload):
    seconds = payload.get('expires_in')
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 0 < seconds <= 120 * 86400:
        raise InstagramError('IG 未提供有效的授權期限，請重新授權')
    return timezone.now() + timedelta(seconds=seconds)


def connect_account(client, code):
    values = _config()
    short = _json('POST', 'https://api.instagram.com/oauth/access_token', data={
        'client_id': values['APP_ID'], 'client_secret': values['APP_SECRET'],
        'grant_type': 'authorization_code', 'redirect_uri': values['REDIRECT_URI'], 'code': code})
    token = short.get('access_token')
    if not isinstance(token, str) or not token:
        raise InstagramError('IG 未提供有效授權，請重新授權')
    long = _json('GET', 'https://graph.instagram.com/access_token', params={
        'grant_type': 'ig_exchange_token', 'client_secret': values['APP_SECRET'], 'access_token': token})
    token = long.get('access_token')
    if not isinstance(token, str) or not token:
        raise InstagramError('IG 長期授權交換失敗，原有連線保留')
    expiry = _expiry(long)
    identity = _json('GET', f"https://graph.instagram.com/{values['API_VERSION']}/me",
        params={'fields': 'user_id,username'}, headers={'Authorization': 'Bearer ' + token})
    account_id, username = str(identity.get('user_id') or identity.get('id') or ''), identity.get('username')
    if not re.fullmatch(r'[0-9]{1,40}', account_id) or not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.]{1,30}', username):
        raise InstagramError('IG 帳號資料不完整，原有連線保留')
    with transaction.atomic():
        Client.objects.select_for_update().get(pk=client.pk)
        current, _ = InstagramConnection.objects.get_or_create(client=client,
            defaults={'expected_username': 'snowlandcz' if client.internal_code == 'snowland' else ''})
        if not current.expected_username or username.lower() != current.expected_username.lower():
            raise InstagramError('授權的 IG 帳號不符後台設定，請改用官方帳號')
        current.username, current.account_id = username, account_id
        current.encrypted_token = Fernet(values['TOKEN_KEY'].encode()).encrypt(token.encode()).decode()
        current.token_expires_at, current.token_refreshed_at = expiry, timezone.now()
        current.enabled, current.last_error, current.last_synced_at = True, '', None
        current.save()
    return current


def _safe_url(value, *, image=False):
    if not isinstance(value, str) or not value or len(value) > (2000 if image else 500):
        raise InstagramError('IG 貼文缺少可用的圖片或連結，既有貼文未變更')
    try:
        parts = urlsplit(value)
        host = (parts.hostname or '').lower()
        port = parts.port
    except ValueError:
        raise InstagramError('IG 貼文網址格式錯誤，既有貼文未變更') from None
    valid = host in {'instagram.com', 'www.instagram.com'} if not image else any(
        host == suffix or host.endswith('.' + suffix) for suffix in ('cdninstagram.com', 'fbcdn.net'))
    if parts.scheme != 'https' or parts.username or parts.password or port not in (None, 443) or not valid:
        raise InstagramError('IG 貼文網址不符合安全規則，既有貼文未變更')
    return value


def sync_connection(connection_id, *, due_only=False):
    # Never hold tenant/order database locks while waiting for Meta. Recheck this
    # snapshot under a short write lock after all external data is validated.
    connection = InstagramConnection.objects.select_related('client').get(pk=connection_id)
    original_token, original_sync = connection.encrypted_token, connection.last_synced_at
    now = timezone.now()
    if not connection.enabled or (due_only and connection.last_synced_at and connection.last_synced_at > now - timedelta(hours=1)):
        return 0
    if not connection.token_expires_at or connection.token_expires_at <= now:
        raise InstagramError('IG 授權已到期，請由官方帳號管理者重新授權')
    values = _config()
    try:
        token = Fernet(values['TOKEN_KEY'].encode()).decrypt(connection.encrypted_token.encode()).decode()
    except (InvalidToken, ValueError, UnicodeError):
        raise InstagramError('IG 授權無法解密，請確認加密金鑰或重新授權') from None
    if connection.token_expires_at < now + timedelta(days=14) and (
        not connection.token_refreshed_at or connection.token_refreshed_at <= now - timedelta(days=1)):
        renewed = _json('GET', 'https://graph.instagram.com/refresh_access_token',
            params={'grant_type': 'ig_refresh_token', 'access_token': token})
        token = renewed.get('access_token')
        if not isinstance(token, str) or not token:
            raise InstagramError('IG 授權更新失敗，原有連線保留')
        connection.token_expires_at = _expiry(renewed)
        connection.token_refreshed_at = now
        connection.encrypted_token = Fernet(values['TOKEN_KEY'].encode()).encrypt(token.encode()).decode()
    data = _json('GET', f"https://graph.instagram.com/{values['API_VERSION']}/{connection.account_id}/media",
        params={'fields': 'id,caption,media_type,media_url,thumbnail_url,permalink,timestamp', 'limit': 12},
        headers={'Authorization': 'Bearer ' + token})
    items = data.get('data')
    if not isinstance(items, list) or len(items) > 12:
        raise InstagramError('IG 貼文資料格式錯誤，既有貼文未變更')
    prepared = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not re.fullmatch(r'[0-9]{1,40}', str(item.get('id', ''))):
            raise InstagramError('IG 貼文識別碼格式錯誤，既有貼文未變更')
        caption = item.get('caption') or ''
        if not isinstance(caption, str):
            raise InstagramError('IG 貼文文字格式錯誤，既有貼文未變更')
        image = item.get('thumbnail_url') if item.get('media_type') == 'VIDEO' else item.get('media_url')
        prepared.append((str(item['id']), {'title': caption[:180] or f'Instagram @{connection.username}',
            'summary': caption, 'image_url': _safe_url(image, image=True), 'link_url': _safe_url(item.get('permalink')),
            'display_order': index, 'metadata': {'instagram_account': connection.username, 'published_at': item.get('timestamp', '')}}))
    with transaction.atomic():
        Client.objects.select_for_update().get(pk=connection.client_id)
        locked = InstagramConnection.objects.select_for_update().get(pk=connection_id)
        if not locked.enabled or locked.encrypted_token != original_token or locked.last_synced_at != original_sync:
            return 0  # A newer sync, fresh authorization or disconnect won.
        if prepared:
            # Keep historical cards without letting yesterday's display_order=0
            # displace today's first post. Manual cards/moderation are untouched.
            current_ids = [f'{connection.account_id}:{media_id}' for media_id, _ in prepared]
            SiteContent.objects.filter(client=connection.client, source='instagram_api').exclude(
                external_id__in=current_ids).update(display_order=1000)
        for media_id, defaults in prepared:
            identity = dict(client=connection.client, source='instagram_api', external_id=f'{connection.account_id}:{media_id}')
            current = SiteContent.objects.filter(**identity).first()
            # A moderator may hide an imported post; routine sync must not republish it.
            if current:
                for key, value in defaults.items():
                    setattr(current, key, value)
                current.save(update_fields=[*defaults, 'updated_at'])
            else:
                SiteContent.objects.create(**identity, content_type='social', location_key='news.social', status='active', **defaults)
        locked.encrypted_token = connection.encrypted_token
        locked.token_expires_at, locked.token_refreshed_at = connection.token_expires_at, connection.token_refreshed_at
        locked.last_synced_at, locked.last_error = timezone.now(), ''
        locked.save()
    return len(prepared)


def run_sync(connection_id, *, due_only=False):
    previous = InstagramConnection.objects.values('encrypted_token', 'last_synced_at').get(pk=connection_id)
    try:
        return sync_connection(connection_id, due_only=due_only)
    except InstagramError as exc:
        InstagramConnection.objects.filter(pk=connection_id, **previous).update(last_error=str(exc)[:200])
        raise
