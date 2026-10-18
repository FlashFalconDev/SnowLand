import re


def validate_course_area(attrs, instance, tenant):
    def value(key, default=''):
        return attrs.get(key, getattr(instance, key, default))
    slug = value('external_id')
    if value('content_type') != 'page':
        raise ValueError('官網校區請使用頁面類型')
    if not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*-area', slug) or len(slug) > 100:
        raise ValueError('官網校區代號請用小寫英文、數字及連字號，並以-area結尾')
    if instance and instance.external_id != slug:
        raise ValueError('已建立的官網校區代號不可更改，避免舊連結失效')
    from Client.models import SiteContent
    duplicates = SiteContent.objects.filter(client=tenant, location_key='course.areas', external_id=slug)
    if instance:
        duplicates = duplicates.exclude(pk=instance.pk)
    if duplicates.exists():
        raise ValueError('此官網校區代號已存在')
    metadata = value('metadata', {})
    slugs = metadata.get('resort_slugs', [])
    if not isinstance(slugs, list) or len(slugs) > 100 or any(not isinstance(s, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', s) for s in slugs):
        raise ValueError('請勾選有效的官網雪場')
    if len(slugs) != len(set(slugs)):
        raise ValueError('官網雪場不可重複')
    if value('status') == 'active' and (not value('title').strip() or not slugs):
        raise ValueError('公開前請填寫校區名稱並至少勾選一個雪場')
    known = set(SiteContent.objects.filter(client=tenant, location_key='course.resorts').values_list('external_id', flat=True))
    previous = set((getattr(instance, 'metadata', {}) or {}).get('resort_slugs', [])) if instance else set()
    if set(slugs) - known - previous:
        raise ValueError('選取的雪場不存在於本公司官網雪場列表')
    return metadata
