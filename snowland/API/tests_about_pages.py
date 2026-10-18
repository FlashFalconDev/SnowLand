from copy import deepcopy
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

from Client.about_pages import about_defaults, about_schema
from Client.models import Client, SiteContent


class AboutPageTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.user = User.objects.create_superuser('about-hq', password='qa-only')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/admin/snowland/site-content/'
        self.public = '/booking/snowland/api/site-content/?location_key=about.snowland'

    def test_initializer_dry_run_then_preserves_legacy_edits_and_status(self):
        blocks = [{'type': 'heading', 'text': '學員回饋機制'}, {'type': 'paragraph', 'text': '管理者改過。第二段！'}, {'type': 'heading', 'text': '課程預約系統'}, {'type': 'paragraph', 'text': '原預約說明'}]
        metadata = {'blocks': blocks, 'keep': '原欄位', 'page': {'blocks': [{'type': 'paragraph', 'text': '不應採用'}]}}
        row = SiteContent.objects.create(client=self.tenant, location_key='about.snowland', content_type='page', status='hidden', metadata=metadata, body='舊正文')
        call_command('initialize_about_page', client='snowland', stdout=StringIO())
        row.refresh_from_db(); self.assertEqual(row.metadata, metadata)
        call_command('initialize_about_page', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db()
        fields = [f for s in about_schema()['sections'] for f in s['fields']]
        feedback = next(f['key'] for f in fields if f.get('source_heading') == '學員回饋機制')
        self.assertEqual(row.metadata['layout']['values'][feedback], '管理者改過。\n第二段！')
        self.assertEqual(row.metadata['blocks'], blocks)
        self.assertEqual(row.metadata['keep'], '原欄位')
        self.assertEqual(row.body, '舊正文'); self.assertEqual(row.status, 'hidden')
        key = next(iter(row.metadata['layout']['values']))
        row.metadata['layout']['values'][key] = '已改的原版型'; row.save()
        call_command('initialize_about_page', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db(); self.assertEqual(row.metadata['layout']['values'][key], '已改的原版型')

    def test_initializer_new_page_and_missing_fields_never_overwrite_saved_values(self):
        call_command('initialize_about_page', client='snowland', stdout=StringIO())
        self.assertFalse(SiteContent.objects.exists())
        call_command('initialize_about_page', client='snowland', apply=True, stdout=StringIO())
        row = SiteContent.objects.get(client=self.tenant, location_key='about.snowland')
        values = row.metadata['layout']['values']; keys = list(values)
        original = values.pop(keys[-1]); values[keys[0]] = '保留修改'; row.save()
        call_command('initialize_about_page', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db(); self.assertEqual(row.metadata['layout']['values'][keys[0]], '保留修改')
        self.assertEqual(row.metadata['layout']['values'][keys[-1]], original)
        self.assertEqual(len(APIClient().get(self.public).data), 1)

    def test_initializer_duplicate_and_incompatible_rows_stop_without_changes(self):
        row = SiteContent.objects.create(client=self.tenant, location_key='about.snowland', metadata={'layout': None})
        with self.assertRaises(CommandError):
            call_command('initialize_about_page', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db(); self.assertEqual(row.metadata, {'layout': None})
        duplicate = SiteContent.objects.create(client=self.tenant, location_key='about.snowland', metadata={})
        with self.assertRaises(CommandError):
            call_command('initialize_about_page', client='snowland', apply=True, stdout=StringIO())
        duplicate.refresh_from_db(); self.assertEqual(duplicate.metadata, {})

    def test_schema_requires_cms_and_tenant_scope(self):
        url = self.url + 'about-schema/'
        self.assertEqual(self.api.get(url).status_code, 200)
        self.user.is_superuser = False; self.user.save()
        profile = self.user.userprofile; profile.is_manager = True; profile.role = 'web_editor'
        profile.manager_client = self.tenant; profile.admin_permissions = ['reviews']; profile.save()
        self.assertEqual(self.api.get(url).status_code, 403)
        profile.admin_permissions = ['cms']; profile.save()
        self.assertEqual(self.api.get(url).status_code, 200)
        Client.objects.create(name='Other', internal_code='other')
        self.assertEqual(self.api.get(url.replace('/snowland/', '/other/')).status_code, 403)

    def test_save_public_reload_and_hide_original_layout(self):
        metadata = {'keep': '原設定', 'layout': about_defaults()}
        key = next(iter(metadata['layout']['values'])); metadata['layout']['values'][key] = 'QA介紹同步'
        result = self.api.post(self.url, {'content_type': 'page', 'location_key': 'about.snowland', 'status': 'active', 'title': '後台名稱', 'metadata': metadata}, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(APIClient().get(self.public).data[0]['metadata'], metadata)
        self.assertEqual(self.api.patch(f"{self.url}{result.data['data']['id']}/", {'status': 'hidden'}, format='json').status_code, 200)
        self.assertEqual(APIClient().get(self.public).data, [])

    def test_invalid_images_and_structure_never_half_write(self):
        metadata = {'layout': about_defaults()}
        row = SiteContent.objects.create(client=self.tenant, location_key='about.snowland', content_type='page', status='active', title='原名稱', metadata=metadata)
        image = next(f['key'] for s in about_schema()['sections'] for f in s['fields'] if f['kind'] == 'image')
        variants = [None, [], {'version': True, 'page_key': 'about', 'values': {}}, {'version': 1, 'page_key': 'join-us', 'values': {}}, {**about_defaults(), 'values': {}}, {**about_defaults(), 'values': {**about_defaults()['values'], 'unexpected': '欄位'}}]
        for value in ['javascript:alert(1)', '//evil.test/image', '/bad\\path', '', [], 'https://']:
            changed = deepcopy(about_defaults()); changed['values'][image] = value; variants.append(changed)
        for changed in variants:
            response = self.api.patch(f'{self.url}{row.id}/', {'title': '不可半寫', 'metadata': {'layout': changed}}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            row.refresh_from_db(); self.assertEqual(row.title, '原名稱'); self.assertEqual(row.metadata, metadata)

    def test_empty_legacy_blocks_and_draft_do_not_resurrect_removed_copy(self):
        content = about_defaults({'blocks': [], 'page': {'blocks': [{'type': 'heading', 'text': '學員回饋機制'}, {'type': 'paragraph', 'text': '不可復活'}]}})
        feedback = next(f['key'] for s in about_schema()['sections'] for f in s['fields'] if f.get('source_heading') == '學員回饋機制')
        self.assertEqual(content['values'][feedback], '')
        response = self.api.post(self.url, {'content_type': 'page', 'location_key': 'about.snowland', 'status': 'draft', 'metadata': {'keep': '草稿'}}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(APIClient().get(self.public).data, [])
