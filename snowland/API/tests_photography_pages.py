from copy import deepcopy
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, SiteContent
from Client.photography_pages import photography_defaults, photography_schema


class PhotographyPageTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.user = User.objects.create_superuser('photography-hq', password='qa-only')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/admin/snowland/site-content/'

    def test_initialize_is_dry_run_and_idempotent_without_overwriting_old_copy(self):
        old = SiteContent.objects.create(client=self.tenant, content_type='page', location_key='legacy.photography-summer', metadata={'page': {'title': '舊內容保留'}})
        call_command('initialize_photography_pages', client='snowland', stdout=StringIO())
        self.assertEqual(SiteContent.objects.count(), 1)
        call_command('initialize_photography_pages', client='snowland', apply=True, stdout=StringIO())
        self.assertEqual(SiteContent.objects.count(), 3)
        row = SiteContent.objects.get(location_key='photography.winter')
        key = next(iter(row.metadata['photography']['values']))
        row.metadata['photography']['values'][key] = '後台已修改，不可覆寫'
        row.save()
        call_command('initialize_photography_pages', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db(); old.refresh_from_db()
        self.assertEqual(row.metadata['photography']['values'][key], '後台已修改，不可覆寫')
        self.assertEqual(old.metadata, {'page': {'title': '舊內容保留'}})

    def test_save_each_season_and_public_reload_uses_saved_values(self):
        for season in ('winter', 'summer'):
            metadata = {'keep': {'legacy': '保留'}, 'photography': photography_defaults(season)}
            key = next(iter(metadata['photography']['values']))
            metadata['photography']['values'][key] = 'https://example.test/new-photo.jpg'
            result = self.api.post(self.url, {'content_type': 'page', 'location_key': f'photography.{season}', 'title': 'QA攝影', 'status': 'active', 'metadata': metadata}, format='json')
            self.assertEqual(result.status_code, 201, result.data)
            public = APIClient().get(f'/booking/snowland/api/site-content/?location_key=photography.{season}')
            self.assertEqual(public.status_code, 200, public.data)
            self.assertEqual(public.data[0]['metadata'], metadata)
            self.assertEqual(self.api.patch(f"{self.url}{result.data['data']['id']}/", {'status': 'hidden'}, format='json').status_code, 200)
            self.assertEqual(APIClient().get(f'/booking/snowland/api/site-content/?location_key=photography.{season}').data, [])

    def test_schema_access_requires_cms_and_is_tenant_scoped(self):
        url = self.url + 'photography-schema/?season=winter'
        self.assertEqual(self.api.get(url).status_code, 200)
        self.assertEqual(self.api.get(url.replace('winter', 'bad')).status_code, 400)
        self.user.is_superuser = False; self.user.save()
        profile = self.user.userprofile
        profile.is_manager = True; profile.role = 'web_editor'; profile.manager_client = self.tenant
        profile.admin_permissions = ['reviews']; profile.save()
        self.assertEqual(self.api.get(url).status_code, 403)
        profile.admin_permissions = ['cms']; profile.save()
        self.assertEqual(self.api.get(url).status_code, 200)
        other = Client.objects.create(name='Other', internal_code='other')
        self.assertEqual(self.api.get(url.replace('/snowland/', '/other/')).status_code, 403)

    def test_bad_structure_partial_fields_and_dangerous_images_do_not_write(self):
        data = photography_defaults('winter')
        image_key = next(field['key'] for section in photography_schema('winter')['sections'] for field in section['fields'] if field['kind'] == 'image')
        variants = [None, [], {'season': 'summer', 'version': 1, 'values': {}}, {**data, 'version': True}, {**data, 'values': {}},
                    {**data, 'values': {**data['values'], image_key: 'javascript:alert(1)'}},
                    {**data, 'values': {**data['values'], image_key: '//bad.test/photo.jpg'}},
                    {**data, 'values': {**data['values'], image_key: []}}]
        for value in variants:
            result = self.api.post(self.url, {'content_type': 'page', 'location_key': 'photography.winter', 'status': 'active', 'metadata': {'photography': value}}, format='json')
            self.assertEqual(result.status_code, 400, result.data)
            self.assertEqual(SiteContent.objects.count(), 0)

    def test_existing_metadata_kept_when_initializing_missing_fields(self):
        row = SiteContent.objects.create(client=self.tenant, content_type='page', location_key='photography.winter', status='hidden', metadata={'blocks': [{'text': '原稿'}]})
        call_command('initialize_photography_pages', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db()
        self.assertEqual(row.status, 'hidden')
        self.assertEqual(row.metadata['blocks'], [{'text': '原稿'}])
        self.assertEqual(row.metadata['photography']['season'], 'winter')

    def test_new_fields_are_added_without_overwriting_saved_values(self):
        content = photography_defaults('summer')
        keys = list(content['values'])
        expected = content['values'].pop(keys[-1])
        content['values'][keys[0]] = '/qa-preserved.svg'
        row = SiteContent.objects.create(client=self.tenant, content_type='page', location_key='photography.summer', metadata={'photography': content, 'legacy': 'keep'})
        call_command('initialize_photography_pages', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db()
        self.assertEqual(row.metadata['photography']['values'][keys[-1]], expected)
        self.assertEqual(row.metadata['photography']['values'][keys[0]], '/qa-preserved.svg')
        self.assertEqual(row.metadata['legacy'], 'keep')
