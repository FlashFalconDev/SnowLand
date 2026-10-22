import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from Client.models import Client, SiteContent


class Command(BaseCommand):
    help = 'Import the current public-site content into SiteContent without overwriting editor changes.'

    def add_arguments(self, parser):
        parser.add_argument('--client', default='snowland', help='Client internal_code')
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite matching CMS records. Existing records are preserved by default.',
        )
        parser.add_argument(
            '--prune',
            action='store_true',
            help='Remove obsolete frontend-import records that are no longer present in the snapshot.',
        )

    def handle(self, *args, **options):
        client = Client.objects.filter(internal_code=options['client'], is_active=True).first()
        if not client:
            raise CommandError(f"找不到啟用中的客戶代碼: {options['client']}")

        fixture_path = Path(__file__).resolve().parents[2] / 'fixtures' / 'site_content_defaults.json'
        if not fixture_path.exists():
            raise CommandError(f'找不到匯入檔: {fixture_path}')

        records = json.loads(fixture_path.read_text(encoding='utf-8'))
        if options['prune']:
            current_keys = {
                (record['content_type'], record['location_key'], record['external_id'])
                for record in records
            }
            obsolete_ids = [
                item.id
                for item in SiteContent.objects.filter(client=client, source='frontend-import')
                if (item.content_type, item.location_key, item.external_id) not in current_keys
            ]
            if obsolete_ids:
                SiteContent.objects.filter(id__in=obsolete_ids).delete()

        created = updated = preserved = 0
        for record in records:
            lookup = {
                'client': client,
                'content_type': record['content_type'],
                'location_key': record['location_key'],
                'external_id': record['external_id'],
            }
            existing = SiteContent.objects.filter(**lookup).first()
            if existing and not options['force']:
                preserved += 1
                continue

            defaults = {key: value for key, value in record.items() if key not in lookup}
            _, was_created = SiteContent.objects.update_or_create(defaults=defaults, **lookup)
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'CMS 匯入完成：新增 {created}、更新 {updated}、保留既有編輯 {preserved}'
        ))
