import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from Client.models import Client, SiteContent
from Client.site_footer import validate_site_footer


class Command(BaseCommand):
    help = 'Preview original footer data; --apply adds it only if missing and never overwrites editor changes.'

    def add_arguments(self, parser):
        parser.add_argument('--client', required=True)
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        tenant = Client.objects.filter(internal_code=options['client'], is_active=True).first()
        if not tenant:
            raise CommandError('找不到指定的啟用公司')
        matches = SiteContent.objects.filter(client=tenant, location_key='site.footer')
        if matches.count() > 1 or matches.exclude(content_type='setting').exists():
            raise CommandError('頁尾資料有多筆或類型不符，未寫入，請先核對')
        if matches.exists():
            self.stdout.write('保留既有頁尾文字、連結與狀態，未覆寫')
            return
        row = json.loads((Path(__file__).resolve().parents[2] / 'fixtures/site_footer_defaults.json').read_text(encoding='utf-8'))
        attrs = dict(row, location_key='site.footer', content_type='setting', status='active')
        validate_site_footer(attrs, None, tenant)
        if options['apply']:
            SiteContent.objects.create(client=tenant, source='site-footer-import', **attrs)
        self.stdout.write('已新增頁尾設定' if options['apply'] else '僅預覽，未寫入；可新增1筆頁尾設定')
