"""Fill missing imported guide bodies, never replace CMS edits or original special pages."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from Client.article_pages import validate_article_metadata
from Client.models import Client, SiteContent


SPECIAL_PATHS = {'/林間雪道', '/packing-checklist', '/第一次滑雪，新手懶人包'}


class Command(BaseCommand):
    help = 'Preview missing guide article bodies; --apply explicitly saves, never overwrites editor content.'

    def add_arguments(self, parser):
        parser.add_argument('--client', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--snapshot', type=Path, default=Path(__file__).resolve().parents[2] / 'fixtures/customer_guide_articles.json')

    @transaction.atomic
    def handle(self, *args, **options):
        client = Client.objects.filter(internal_code=options['client'], is_active=True).first()
        if not client:
            raise CommandError('找不到指定的啟用公司')
        try:
            snapshot = json.loads(options['snapshot'].read_text(encoding='utf-8'))
            rows = snapshot['articles']
            if not isinstance(rows, list) or not rows:
                raise ValueError('來源文章清單不可為空')
            urls = set()
            for row in rows:
                url = row['card']['url']
                if not isinstance(url, str) or url in urls:
                    raise ValueError('文章來源網址重複或格式錯誤')
                urls.add(url)
                validate_article_metadata({'article':row['article']}, True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(f'文章來源驗證失敗，沒有寫入：{exc}') from exc
        defaults = json.loads((Path(__file__).resolve().parents[2] / 'fixtures/site_content_defaults.json').read_text(encoding='utf-8'))
        old_keys = {row['link_url']:row['external_id'] for row in defaults if row['location_key']=='guides.articles'}
        existing = list(SiteContent.objects.select_for_update().filter(client=client, location_key='guides.articles'))
        created = initialized = preserved = special = 0
        for record in rows:
            card, article = record['card'], deepcopy(record['article'])
            url = card['url']
            is_special = unquote(urlsplit(url).path).rstrip('/') in SPECIAL_PATHS
            if is_special: special += 1
            key = old_keys.get(url, 'guide-' + hashlib.sha256(url.encode()).hexdigest()[:20])
            matches = [item for item in existing if item.external_id == key or item.link_url == url or isinstance(item.metadata,dict) and item.metadata.get('url') == url]
            if len(matches) > 1:
                raise CommandError('同一篇文章存在多筆後台資料，請先核對；沒有寫入任何變更')
            if matches:
                if is_special: continue
                item = matches[0]
                meta = item.metadata
                if item.source != 'frontend-import' or item.body.strip() or not isinstance(meta,dict) or any(name in meta for name in ('blocks','article','article_mode')) or item.link_url != url:
                    preserved += 1
                    continue
                # Preserve editor changes to card fields, status and scheduling.
                article.update(title=item.title, lead=item.summary, heroImage=item.image_url, date=meta.get('date',article.get('date','')))
                metadata = {**meta, 'article':article, 'article_mode':'internal', 'source_url':url}
                validate_article_metadata(metadata, item.status=='active')
                initialized += 1
                if options['apply']:
                    item.metadata = metadata
                    item.save(update_fields=['metadata','updated_at'])
            else:
                created += 1
                if options['apply']:
                    SiteContent.objects.create(client=client,content_type='article',location_key='guides.articles',
                        external_id=key,source='frontend-import',status='active',title=card['title'],summary=card['excerpt'],
                        image_url=card['image'],link_url=url,tags=[card['category']],
                        metadata={**card,'source_url':url,**({} if is_special else {'article':article,'article_mode':'internal'})})
        prefix = '已儲存' if options['apply'] else '僅預覽，未寫入'
        self.stdout.write(f'{prefix}：新增{created}、補全文{initialized}、保留編輯{preserved}、保留原獨立頁{special}')
