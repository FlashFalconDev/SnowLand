"""Editable public footer; business contact details live in SiteContent, not JS."""
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

SOCIAL_KEYS = ('facebook', 'instagram', 'threads', 'youtube', 'line', 'whatsapp', 'tiktok', 'xiaohongshu')


def validate_site_footer(attrs, instance, tenant):
    from .models import SiteContent

    def value(key, default=''):
        return attrs.get(key, getattr(instance, key, default))

    if value('content_type') != 'setting':
        raise ValueError('頁尾請使用區塊設定類型')
    duplicates = SiteContent.objects.filter(client=tenant, location_key='site.footer')
    if instance:
        duplicates = duplicates.exclude(pk=instance.pk)
    if duplicates.exists():
        raise ValueError('頁尾已有設定，請編輯既有資料')
    metadata = value('metadata', {})
    for key in ('company_name', 'company_name_secondary', 'copyright'):
        if not isinstance(metadata.get(key, ''), str) or len(metadata.get(key, '')) > 300:
            raise ValueError('公司名稱與版權文字請使用300字以內的文字')
    email = metadata.get('email', '')
    if not isinstance(email, str) or len(email) > 254:
        raise ValueError('請填寫有效的聯絡Email，或留空隱藏')
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError('請填寫有效的聯絡Email，或留空隱藏')
    links = metadata.get('social_links', {})
    if not isinstance(links, dict) or set(links) - set(SOCIAL_KEYS):
        raise ValueError('請使用表單提供的社群連結欄位')
    for key, link in links.items():
        if not isinstance(link, str) or len(link) > 2000 or '\\' in link or any(c.isspace() or ord(c) < 32 for c in link):
            raise ValueError('社群連結請填寫完整https網址，或留空隱藏')
        if not link:
            continue
        try:
            url = urlsplit(link)
            valid = url.scheme == 'https' and bool(url.hostname) and not url.username and not url.password
            _ = url.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError('社群連結請填寫完整https網址，或留空隱藏')
    if value('status') == 'active' and not value('title').strip():
        raise ValueError('請填寫後台辨識名稱')
    return metadata
