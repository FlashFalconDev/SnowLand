from django.core.management import call_command
from django.test import TestCase

from Client.models import Client, SiteContent


class ImportSiteContentDefaultsTests(TestCase):
    def setUp(self):
        self.client_record = Client.objects.create(
            name='SnowLand',
            internal_code='snowland',
            is_active=True,
        )

    def test_imports_public_site_snapshot_and_preserves_editor_changes(self):
        call_command('import_site_content_defaults', client='snowland')

        self.assertEqual(
            SiteContent.objects.filter(client=self.client_record, location_key='course.resorts').count(),
            14,
        )
        self.assertEqual(
            SiteContent.objects.filter(client=self.client_record, location_key='photography.gallery').count(),
            76,
        )
        self.assertEqual(
            SiteContent.objects.filter(client=self.client_record, location_key='course.pricing').count(),
            14,
        )

        for slug in ('asahikawasantapresentpark', 'furano', 'pippu', 'canmore', 'onze', 'asari'):
            detail = SiteContent.objects.get(
                client=self.client_record,
                location_key='course.resort-pages',
                external_id=slug,
            )
            self.assertGreaterEqual(len(detail.metadata['resort']['tabs']), 5)
            self.assertNotIn('可由後台補充', detail.metadata['resort']['description'])

        pricing = SiteContent.objects.get(
            client=self.client_record,
            location_key='course.pricing',
            external_id='tomamu',
        ).metadata['pricing']
        self.assertEqual(len(pricing['plans']['regular']['rows']), 6)
        self.assertEqual(pricing['plans']['regular']['rows'][0]['full'], 19200)

        resort = SiteContent.objects.get(
            client=self.client_record,
            location_key='course.resorts',
            external_id='furano',
        )
        resort.title = '後台人工修改的富良野名稱'
        resort.save(update_fields=['title'])

        call_command('import_site_content_defaults', client='snowland')
        resort.refresh_from_db()
        self.assertEqual(resort.title, '後台人工修改的富良野名稱')
