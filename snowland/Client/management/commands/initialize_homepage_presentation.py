import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from Client.models import Client, SiteContent


class Command(BaseCommand):
    help = 'Preview original homepage hero, introduction, coach heading and contact banner; --apply adds only missing sections.'

    def add_arguments(self, parser):
        parser.add_argument('--client', required=True)
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        tenant = Client.objects.filter(internal_code=options['client'], is_active=True).first()
        if not tenant:
            raise CommandError('找不到指定的啟用公司')
        defaults = json.loads((Path(__file__).resolve().parents[2] / 'fixtures/homepage_presentation_defaults.json').read_text(encoding='utf-8'))
        for row in defaults:
            matches = list(SiteContent.objects.filter(client=tenant,location_key=row['location_key']))
            if len(matches)>1 or any(item.content_type not in ('setting','page') for item in matches):
                raise CommandError('首頁展示區塊有多筆／類型不符，未寫入，請先核對')
        count = 0
        for row in defaults:
            if SiteContent.objects.filter(client=tenant,location_key=row['location_key']).exists():
                continue
            count += 1
            if options['apply']:
                SiteContent.objects.create(client=tenant,content_type='setting',status='active',source='homepage-presentation-import',**row)
        self.stdout.write(('已新增' if options['apply'] else '僅預覽，未寫入')+f' {count} 區；保留既有文字、設定與狀態')
