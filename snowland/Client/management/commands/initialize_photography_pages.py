from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from Client.models import Client, SiteContent
from Client.photography_pages import photography_defaults, photography_schema


class Command(BaseCommand):
    help = 'Initialize the existing winter/summer layout content; dry-run by default, never overwrite edits.'

    def add_arguments(self, parser):
        parser.add_argument('--client', required=True)
        parser.add_argument('--apply', action='store_true', help='Explicitly save new/missing photography fields')

    @transaction.atomic
    def handle(self, *args, **options):
        client = Client.objects.filter(internal_code=options['client'], is_active=True).first()
        if not client:
            raise CommandError('找不到指定的啟用公司')
        created = initialized = preserved = 0
        for season in ('winter', 'summer'):
            location = f'photography.{season}'
            rows = list(SiteContent.objects.filter(client=client, location_key=location))
            if len(rows) > 1:
                raise CommandError(f'{location}存在多筆內容，請先核對，不自動選擇或覆寫')
            schema = photography_schema(season)
            if not rows:
                created += 1
                if options['apply']:
                    SiteContent.objects.create(client=client, content_type='page', location_key=location,
                        title=schema['title'], status='active', source='photography-layout-import',
                        metadata={'photography': photography_defaults(season)})
            elif not isinstance(rows[0].metadata, dict):
                raise CommandError(f'{location}舊設定不是物件，請先核對，不自動覆寫')
            elif 'photography' not in rows[0].metadata:
                initialized += 1
                if options['apply']:
                    rows[0].metadata = {**rows[0].metadata, 'photography': photography_defaults(season)}
                    rows[0].save(update_fields=['metadata', 'updated_at'])
            else:
                content = rows[0].metadata['photography']
                defaults = photography_defaults(season)
                compatible = isinstance(content, dict) and content.get('version') == 1 and content.get('season') == season and isinstance(content.get('values'), dict)
                if compatible and set(defaults['values']) - set(content['values']):
                    initialized += 1
                    if options['apply']:
                        rows[0].metadata = {**rows[0].metadata, 'photography': {**content, 'values': {**defaults['values'], **content['values']}}}
                        rows[0].save(update_fields=['metadata', 'updated_at'])
                else:
                    preserved += 1
        prefix = '已儲存' if options['apply'] else '僅預覽，未寫入'
        self.stdout.write(f'{prefix}：新增頁面{created}、補欄位{initialized}、保留既有{preserved}；舊位置與舊正文均不刪除')
