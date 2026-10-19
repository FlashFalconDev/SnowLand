import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from Client.models import Client, SiteContent


class Command(BaseCommand):
    help = 'Preview course navigation groups; --apply adds only missing customer defaults.'

    def add_arguments(self, parser):
        parser.add_argument('--client', required=True)
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        tenant = Client.objects.filter(internal_code=options['client'], is_active=True).first()
        if not tenant:
            raise CommandError('找不到指定的啟用公司')
        defaults = json.loads((Path(__file__).resolve().parents[2] / 'fixtures/course_area_defaults.json').read_text(encoding='utf-8'))
        rows = list(SiteContent.objects.filter(client=tenant, location_key='course.areas'))
        for area in defaults:
            matches = [r for r in rows if r.external_id == area['external_id']]
            if len(matches) > 1 or any(r.content_type != 'page' for r in matches):
                raise CommandError('官網校區代號重複或類型不符，未寫入，請先核對')
        count = 0
        for index, area in enumerate(defaults):
            if any(r.external_id == area['external_id'] for r in rows):
                continue
            count += 1
            if options['apply']:
                SiteContent.objects.create(client=tenant, location_key='course.areas', content_type='page', status='active', source='course-area-import', display_order=index, **area)
        self.stdout.write(('已新增' if options['apply'] else '僅預覽，未寫入') + f' {count} 區；保留既有編輯、狀態及營運校區權限')
