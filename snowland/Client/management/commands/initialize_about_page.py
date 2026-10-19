from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from Client.about_pages import about_defaults
from Client.models import Client, SiteContent


class Command(BaseCommand):
    help = 'Initialize school introduction fields; dry-run by default, never overwrite existing edits.'

    def add_arguments(self, parser):
        parser.add_argument('--client', required=True)
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        page_key = options.get('page_key', 'about')
        location = 'about.snowland' if page_key == 'about' else 'about.join-us'
        title = '滑雪學校介紹' if page_key == 'about' else '成為教練'
        client = Client.objects.filter(internal_code=options['client'], is_active=True).first()
        if not client:
            raise CommandError('找不到指定的啟用公司')
        rows = list(SiteContent.objects.filter(client=client, location_key=location))
        if len(rows) > 1:
            raise CommandError(f'{title}存在多筆內容，請先核對，不自動選擇或覆寫')
        action = '保留既有'
        if not rows:
            action = '新增原頁'
            if options['apply']:
                SiteContent.objects.create(client=client, content_type='page', location_key=location, title=title, status='active', source=f'{page_key}-layout-import', metadata={'layout': about_defaults(page_key=page_key)})
        else:
            row = rows[0]
            if not isinstance(row.metadata, dict):
                raise CommandError('舊設定不是物件，請先核對，不自動覆寫')
            defaults = about_defaults(row.metadata, page_key)
            if 'layout' not in row.metadata:
                action = '補原版型欄位'
                if options['apply']:
                    row.metadata = {**row.metadata, 'layout': defaults}
                    row.save(update_fields=['metadata', 'updated_at'])
            else:
                layout = row.metadata['layout']
                if not isinstance(layout, dict) or type(layout.get('version')) is not int or layout.get('version') != 1 or layout.get('page_key') != page_key or not isinstance(layout.get('values'), dict):
                    raise CommandError('既有版型資料不相容，請先核對，不自動覆寫')
                if set(defaults['values']) - set(layout['values']):
                    action = '補缺少欄位'
                    if options['apply']:
                        row.metadata = {**row.metadata, 'layout': {**layout, 'values': {**defaults['values'], **layout['values']}}}
                        row.save(update_fields=['metadata', 'updated_at'])
        self.stdout.write(('已儲存' if options['apply'] else '僅預覽，未寫入') + '：' + action + '；舊正文與原設定保留')
