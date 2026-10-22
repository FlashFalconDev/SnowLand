from copy import deepcopy
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

from Client.about_pages import about_defaults, about_schema
from Client.models import Client, SiteContent


class RecruitmentPageTests(TestCase):
    def setUp(self):
        self.client_row = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.user = User.objects.create_superuser('recruit-hq', password='qa-only')
        self.api = APIClient(); self.api.force_authenticate(self.user)
        self.url = '/api/admin/snowland/site-content/'
        self.public = '/booking/snowland/api/site-content/?location_key=about.join-us'

    def test_initialize_dry_run_idempotent_and_preserves_original_edits(self):
        metadata = {'blocks': [{'type': 'heading', 'text': 'Step 1.'}, {'type': 'paragraph', 'text': '管理者改過的流程。不要加第二段。'}, {'type': 'heading', 'text': '薪資與福利'}, {'type': 'paragraph', 'text': '依公司設定'}], 'keep': '原設定'}
        row = SiteContent.objects.create(client=self.client_row, location_key='about.join-us', content_type='page', status='hidden', metadata=metadata)
        call_command('initialize_join_us_page', client='snowland', stdout=StringIO())
        row.refresh_from_db(); self.assertEqual(row.metadata, metadata)
        call_command('initialize_join_us_page', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db(); self.assertEqual(row.metadata['layout']['page_key'], 'join-us')
        self.assertEqual(row.metadata['layout']['values']['join_002'], '管理者改過的流程。')
        self.assertEqual(row.metadata['keep'], '原設定'); self.assertEqual(row.status, 'hidden')
        row.metadata['layout']['values']['join_apply_url'] = '/coach-application'; row.save()
        call_command('initialize_join_us_page', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db(); self.assertEqual(row.metadata['layout']['values']['join_apply_url'], '/coach-application')

    def test_new_page_missing_fields_and_duplicate_refusal(self):
        call_command('initialize_join_us_page', client='snowland', apply=True, stdout=StringIO())
        row = SiteContent.objects.get(client=self.client_row, location_key='about.join-us')
        row.metadata['layout']['values'].pop('join_apply_url'); row.metadata['layout']['values']['join_001'] = '自改步驟'; row.save()
        call_command('initialize_join_us_page', client='snowland', apply=True, stdout=StringIO())
        row.refresh_from_db(); self.assertEqual(row.metadata['layout']['values']['join_001'], '自改步驟')
        self.assertEqual(row.metadata['layout']['values']['join_apply_url'], 'https://www.surveycake.com/s/mYz4K')
        SiteContent.objects.create(client=self.client_row, location_key='about.join-us')
        with self.assertRaises(CommandError):
            call_command('initialize_join_us_page', client='snowland', apply=True, stdout=StringIO())

    def test_save_public_reload_hide_and_original_metadata(self):
        content = about_defaults(page_key='join-us'); content['values']['join_032'] = '由管理者自行更新的本季條件'
        metadata = {'layout': content, 'page': {'title': '原招募頁', 'blocks': []}}
        response = self.api.post(self.url, {'content_type': 'page', 'location_key': 'about.join-us', 'metadata': metadata, 'status': 'active'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(APIClient().get(self.public).data[0]['metadata'], metadata)
        self.assertEqual(self.api.patch(f"{self.url}{response.data['data']['id']}/", {'status': 'hidden'}, format='json').status_code, 200)
        self.assertEqual(APIClient().get(self.public).data, [])

    def test_schema_requires_cms_and_tenant_scope(self):
        url = self.url + 'join-schema/'
        self.assertEqual(self.api.get(url).data['data']['page_key'], 'join-us')
        self.user.is_superuser = False; self.user.save()
        profile = self.user.userprofile; profile.is_manager = True; profile.role = 'web_editor'; profile.manager_client = self.client_row; profile.admin_permissions = ['reviews']; profile.save()
        self.assertEqual(self.api.get(url).status_code, 403)
        profile.admin_permissions = ['cms']; profile.save(); self.assertEqual(self.api.get(url).status_code, 200)
        Client.objects.create(name='Other', internal_code='other')
        self.assertEqual(self.api.get(url.replace('/snowland/', '/other/')).status_code, 403)

    def test_invalid_links_images_and_wrong_page_do_not_half_write(self):
        data = about_defaults(page_key='join-us')
        row = SiteContent.objects.create(client=self.client_row, location_key='about.join-us', content_type='page', status='active', title='原招募', metadata={'layout': data})
        variants = [about_defaults(), {**deepcopy(data), 'version': True}]
        image = next(f['key'] for s in about_schema('join-us')['sections'] for f in s['fields'] if f['kind'] == 'image')
        for key in (image, 'join_apply_url'):
            for value in ('javascript:alert(1)', '//evil.test/file', '', [], 'https://'):
                changed = deepcopy(data); changed['values'][key] = value; variants.append(changed)
        for changed in variants:
            response = self.api.patch(f'{self.url}{row.id}/', {'title': '不可半寫', 'metadata': {'layout': changed}}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            row.refresh_from_db(); self.assertEqual(row.title, '原招募'); self.assertEqual(row.metadata, {'layout': data})

    def test_empty_blocks_and_note_filter_do_not_resurrect_old_values(self):
        schema = about_schema('join-us')
        field = next(f for s in schema['sections'] for f in s['fields'] if f.get('source_contains'))
        metadata = {'blocks': [{'type': 'heading', 'text': field['source_heading']}, {'type': 'paragraph', 'text': '不相干的其他資格'}, {'type': 'paragraph', 'text': '※ 具備以上加分語言者優先錄取'}]}
        self.assertEqual(about_defaults(metadata, 'join-us')['values'][field['key']], '※ 具備以上加分語言者優先錄取')
        self.assertEqual(about_defaults({'blocks': []}, 'join-us')['values']['join_002'], '')
