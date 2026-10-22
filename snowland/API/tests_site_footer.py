from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, SiteContent


class SiteFooterTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.api = APIClient()
        self.public = '/booking/snowland/api/site-content/'
        self.admin = '/api/admin/snowland/site-content/'

    def initialize(self, apply=False):
        call_command('initialize_site_footer', client='snowland', apply=apply, stdout=StringIO())

    def staff(self):
        self.api.force_authenticate(User.objects.create_superuser('footer-hq', password='qa-only'))

    def test_preview_apply_preserves_edits_hidden_status_and_is_idempotent(self):
        self.initialize()
        self.assertFalse(SiteContent.objects.exists())
        self.initialize(True)
        row = SiteContent.objects.get(location_key='site.footer')
        self.assertEqual(len(row.metadata['social_links']), 8)
        row.metadata = {'company_name': '自行設定', 'custom': '保留'}
        row.status = 'hidden'
        row.save()
        self.initialize(True)
        row.refresh_from_db()
        self.assertEqual(SiteContent.objects.count(), 1)
        self.assertEqual(row.metadata['company_name'], '自行設定')
        self.assertEqual(row.status, 'hidden')

    def test_initializer_rejects_conflicts_and_unknown_tenant(self):
        SiteContent.objects.create(client=self.tenant, location_key='site.footer', content_type='page')
        with self.assertRaises(CommandError):
            self.initialize(True)
        with self.assertRaises(CommandError):
            call_command('initialize_site_footer', client='unknown', apply=True, stdout=StringIO())
        self.assertEqual(SiteContent.objects.count(), 1)

    def test_real_edit_public_reflection_clear_hide_and_metadata_preservation(self):
        self.initialize(True)
        self.staff()
        row = SiteContent.objects.get(location_key='site.footer')
        url = f'{self.admin}{row.pk}/'
        metadata = {'company_name': 'QA新公司', 'company_name_secondary': '<script>只作文字</script>',
                    'email': 'qa@example.test', 'copyright': 'QA版權', 'custom': '保留',
                    'social_links': {'instagram': 'https://instagram.com/qa/', 'line': ''}}
        response = self.api.patch(url, {'metadata': metadata}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        public = self.api.get(self.public, {'location_key': 'site.footer'}).data
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0]['metadata'], metadata)
        self.assertEqual(self.api.patch(url, {'metadata': {}}, format='json').status_code, 200)
        self.assertEqual(self.api.get(self.public, {'location_key': 'site.footer'}).data[0]['metadata'], {})
        self.assertEqual(self.api.patch(url, {'status': 'hidden'}, format='json').status_code, 200)
        self.assertEqual(self.api.get(self.public, {'location_key': 'site.footer'}).data, [])

    def test_invalid_metadata_rejected_without_partial_write(self):
        self.initialize(True)
        self.staff()
        row = SiteContent.objects.get(location_key='site.footer')
        url = f'{self.admin}{row.pk}/'
        invalid = [
            {'email': 'not-an-email'}, {'email': 'a@b.test\r\nBcc:evil@test.test'}, {'email': 7},
            {'company_name': []}, {'company_name': 'x' * 301}, {'copyright': {}},
            {'social_links': []}, {'social_links': {'unknown': 'https://example.test'}},
        ]
        for link in ['javascript:alert(1)', '//example.test', '/contact', 'http://example.test',
                     'https://a@evil.test', 'https://a:b@evil.test', 'https://example.test:bad',
                     'https://example.test/\n', 'https://example.test/a b', 'https:\\evil.test', {}, 'x' * 2001]:
            invalid.append({'social_links': {'instagram': link}})
        for metadata in invalid:
            with self.subTest(metadata=metadata):
                response = self.api.patch(url, {'title': '不可半寫', 'metadata': metadata}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
        row.refresh_from_db()
        self.assertNotEqual(row.title, '不可半寫')

    def test_tenant_isolation_anonymous_and_ordinary_member_cannot_write(self):
        self.initialize(True)
        row = SiteContent.objects.get(location_key='site.footer')
        url = f'{self.admin}{row.pk}/'
        self.assertIn(self.api.patch(url, {'title': '匿名不能改'}, format='json').status_code, (401, 403))
        self.api.force_authenticate(User.objects.create_user('footer-member', password='qa-only'))
        self.assertEqual(self.api.patch(url, {'title': '會員不能改'}, format='json').status_code, 403)
        other = Client.objects.create(name='other', internal_code='other')
        other_row = SiteContent.objects.create(client=other, content_type='setting', location_key='site.footer', status='active', title='其他公司')
        self.staff()
        self.assertEqual(self.api.patch(f'{self.admin}{other_row.pk}/', {'title': '越界'}, format='json').status_code, 404)
        self.assertEqual(len(self.api.get(self.public, {'location_key': 'site.footer'}).data), 1)

    def test_duplicate_and_wrong_type_rejected_and_empty_fields_allowed(self):
        self.initialize(True)
        self.staff()
        row = SiteContent.objects.get(location_key='site.footer')
        self.assertEqual(self.api.post(self.admin, {'content_type': 'setting', 'location_key': 'site.footer', 'title': '重複'}, format='json').status_code, 400)
        self.assertEqual(self.api.patch(f'{self.admin}{row.pk}/', {'content_type': 'page'}, format='json').status_code, 400)
        self.assertEqual(self.api.patch(f'{self.admin}{row.pk}/', {'metadata': {'email': '', 'social_links': {'line': ''}}}, format='json').status_code, 200)

    def test_editor_can_create_without_initializer(self):
        self.staff()
        response = self.api.post(self.admin, {'content_type': 'setting', 'location_key': 'site.footer',
            'title': '官網頁尾', 'status': 'active', 'metadata': {'company_name': '自行新增', 'social_links': {}}}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.api.get(self.public, {'location_key': 'site.footer'}).data[0]['metadata']['company_name'], '自行新增')
