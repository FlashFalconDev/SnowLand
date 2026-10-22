from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

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

    def test_resort_tab_edit_survives_reload_and_reaches_public_site_api(self):
        call_command('import_site_content_defaults', client='snowland')
        detail = SiteContent.objects.get(
            client=self.client_record,
            location_key='course.resort-pages',
            external_id='furano',
        )
        original_tabs = detail.metadata['resort']['tabs']
        changed_tabs = [dict(tab) for tab in original_tabs]
        lift_index = next(index for index, tab in enumerate(changed_tabs) if tab['slug'] == 'lift')
        changed_tabs[lift_index]['html'] = '<table><tr><td>2026-27 測試雪票</td><td>¥8,000</td></tr></table>'
        updated_metadata = {
            **detail.metadata,
            'resort': {**detail.metadata['resort'], 'tabs': changed_tabs},
        }
        admin = User.objects.create_superuser('cms-manager', 'cms-manager@example.test', 'local-test-only')
        api = APIClient()
        api.force_authenticate(admin)
        update_response = api.patch(
            f'/api/admin/snowland/site-content/{detail.id}/',
            {'metadata': updated_metadata}, format='json',
        )
        self.assertEqual(update_response.status_code, 200)

        detail.refresh_from_db()
        self.assertEqual(detail.metadata['resort']['tabs'][lift_index]['html'], changed_tabs[lift_index]['html'])
        self.assertEqual(len(detail.metadata['resort']['tabs']), len(original_tabs))
        response = self.client.get('/booking/snowland/api/site-content/', {'location_key': 'course.resort-pages'})
        self.assertEqual(response.status_code, 200)
        public_detail = next(item for item in response.json() if item['external_id'] == 'furano')
        self.assertIn('2026-27 測試雪票', public_detail['metadata']['resort']['tabs'][lift_index]['html'])

    def test_resort_content_cannot_be_changed_without_login_or_across_tenants(self):
        other_client = Client.objects.create(name='Other School', internal_code='other-school', is_active=True)
        other_detail = SiteContent.objects.create(
            client=other_client, content_type='page', location_key='course.resort-pages',
            title='Other resort', external_id='other-resort', status='active',
            metadata={'slug': 'other-resort', 'resort': {'tabs': []}},
        )
        url = f'/api/admin/snowland/site-content/{other_detail.id}/'
        anonymous_response = APIClient().patch(url, {'title': 'Changed'}, format='json')
        self.assertIn(anonymous_response.status_code, (401, 403))

        admin = User.objects.create_superuser('cms-manager', 'cms-manager@example.test', 'local-test-only')
        api = APIClient()
        api.force_authenticate(admin)
        cross_tenant_response = api.patch(url, {'title': 'Changed'}, format='json')
        self.assertEqual(cross_tenant_response.status_code, 404)
        other_detail.refresh_from_db()
        self.assertEqual(other_detail.title, 'Other resort')
