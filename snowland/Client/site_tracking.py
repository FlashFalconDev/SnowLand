"""Tenant-owned tracking IDs; no executable configuration or personal data."""
import re


def validate_site_tracking(attrs, instance, tenant):
    from .models import SiteContent

    def value(key, default=''):
        return attrs.get(key, getattr(instance, key, default))

    if value('content_type') != 'setting':
        raise ValueError('分析追蹤請使用區塊設定類型')
    duplicates = SiteContent.objects.filter(client=tenant, location_key='site.tracking')
    if instance:
        duplicates = duplicates.exclude(pk=instance.pk)
        if instance.location_key == 'site.tracking' and value('location_key') != instance.location_key:
            raise ValueError('分析追蹤設定不能移到其他位置')
    if duplicates.exists():
        raise ValueError('已有分析追蹤設定，請編輯既有資料')
    metadata = value('metadata', {})
    if not isinstance(metadata, dict) or set(metadata) - {'ga4_id', 'meta_pixel_id', 'enabled', 'auto_events_disabled'}:
        raise ValueError('只接受 GA4 ID、Meta Pixel ID 及啟用狀態，不接受自訂程式碼')
    clean = {}
    for key, pattern, message in (
        ('ga4_id', r'G-[A-Z0-9]{4,20}', 'GA4 請填寫 G- 開頭的評估 ID，或留空'),
        ('meta_pixel_id', r'[0-9]{5,25}', 'Meta Pixel 請填寫數字 ID，或留空'),
    ):
        raw = metadata.get(key, '')
        if not isinstance(raw, str):
            raise ValueError(message)
        raw = raw.strip()
        if raw and not re.fullmatch(pattern, raw, flags=re.ASCII):
            raise ValueError(message)
        clean[key] = raw
    enabled = metadata.get('enabled', False)
    if not isinstance(enabled, bool):
        raise ValueError('啟用狀態必須是勾選或取消勾選')
    acknowledged = metadata.get('auto_events_disabled', False)
    if not isinstance(acknowledged, bool):
        raise ValueError('自動事件確認必須是勾選或取消勾選')
    if enabled and (not acknowledged or not (clean['ga4_id'] or clean['meta_pixel_id'])):
        raise ValueError('啟用前請填寫至少一個 ID，並確認已關閉平台的自動事件與進階配對')
    clean.update(enabled=enabled, auto_events_disabled=acknowledged)
    return clean
