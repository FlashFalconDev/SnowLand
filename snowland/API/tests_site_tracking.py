from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, SiteContent


class SiteTrackingTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='QA tracking', internal_code='snowland')
        self.api = APIClient()
        self.admin = '/api/admin/snowland/site-content/'
        self.api.force_authenticate(User.objects.create_superuser('tracking-hq', password='qa-only'))

    def create(self, metadata=None):
        return self.api.post(self.admin, {'content_type': 'setting', 'location_key': 'site.tracking',
            'title': '分析追蹤', 'status': 'draft', 'metadata': metadata or {}}, format='json')

    def test_default_off_and_reload_ids_then_clear(self):
        response = self.create({'ga4_id': ' G-QA12345678 ', 'meta_pixel_id': '1234567890'})
        self.assertEqual(response.status_code, 201, response.data)
        row = SiteContent.objects.get(location_key='site.tracking')
        self.assertEqual(row.metadata, {'ga4_id': 'G-QA12345678', 'meta_pixel_id': '1234567890', 'enabled': False, 'auto_events_disabled': False})
        url = f'{self.admin}{row.pk}/'
        self.assertEqual(self.api.get(url).data['metadata'], row.metadata)
        self.assertEqual(self.api.patch(url, {'metadata': {}}, format='json').status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.metadata, {'ga4_id': '', 'meta_pixel_id': '', 'enabled': False, 'auto_events_disabled': False})

    def test_invalid_config_never_partially_saved(self):
        for metadata in ({'ga4_id': '<script>'}, {'ga4_id': 123}, {'meta_pixel_id': '１２３４５'},
                         {'meta_pixel_id': '12345\n<script>'}, {'meta_pixel_id': '1' * 26},
                         {'token': 'must-not-save'}, {'script': 'alert(1)'}, {'enabled': 'false'}, {'enabled': True}):
            with self.subTest(metadata=metadata):
                self.assertEqual(self.create(metadata).status_code, 400)
        self.assertFalse(SiteContent.objects.exists())

    def test_duplicate_wrong_type_rename_and_enable_rejected(self):
        self.assertEqual(self.create().status_code, 201)
        row = SiteContent.objects.get(location_key='site.tracking')
        url = f'{self.admin}{row.pk}/'
        self.assertEqual(self.create().status_code, 400)
        for patch in ({'content_type': 'page'}, {'location_key': 'site.footer'}, {'metadata': {'enabled': True}}):
            self.assertEqual(self.api.patch(url, patch, format='json').status_code, 400)
        row.refresh_from_db()
        self.assertEqual(row.location_key, 'site.tracking')
        self.assertFalse(row.metadata['enabled'])

    def test_cms_editor_cannot_create_edit_move_or_delete_tracking(self):
        self.create()
        row = SiteContent.objects.get(location_key='site.tracking')
        ordinary = SiteContent.objects.create(client=self.tenant, location_key='homepage.test', content_type='setting')
        editor = User.objects.create_user('tracking-editor', password='qa-only')
        profile = editor.userprofile
        profile.is_manager = True
        profile.role = 'web_editor'
        profile.manager_client = self.tenant
        profile.admin_permissions = ['cms']
        profile.save()
        self.api.force_authenticate(editor)
        self.assertEqual(self.api.patch(f'{self.admin}{ordinary.pk}/', {'title': 'ordinary edit allowed'}, format='json').status_code, 200)
        url = f'{self.admin}{row.pk}/'
        self.assertEqual(self.api.patch(url, {'title': 'not allowed'}, format='json').status_code, 403)
        self.assertEqual(self.api.delete(url).status_code, 403)
        # Invalid duplicate is rejected by validation before permission, with no write.
        self.assertIn(self.create().status_code, (400, 403))
        self.assertIn(self.api.patch(f'{self.admin}{ordinary.pk}/', {'location_key': 'site.tracking'}, format='json').status_code, (400, 403))
        row.delete()
        self.assertEqual(self.create().status_code, 403)
        self.assertEqual(self.api.patch(f'{self.admin}{ordinary.pk}/', {'location_key': 'site.tracking'}, format='json').status_code, 403)
        ordinary.refresh_from_db()
        self.assertEqual(ordinary.location_key, 'homepage.test')

    def test_other_tenant_and_anonymous_cannot_write(self):
        other = Client.objects.create(name='other', internal_code='tracking-other')
        row = SiteContent.objects.create(client=other, location_key='site.tracking', content_type='setting')
        self.assertEqual(self.api.patch(f'{self.admin}{row.pk}/', {'title': 'not allowed'}, format='json').status_code, 404)
        self.api.force_authenticate(None)
        self.assertIn(self.create().status_code, (401, 403))

    def test_tenant_headquarters_can_edit_and_delete_without_superuser(self):
        user = User.objects.create_user('tracking-tenant-hq', password='qa-only')
        profile = user.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'hq_admin'
        profile.admin_permissions = ['cms']
        profile.save()
        self.api.force_authenticate(user)
        self.assertEqual(self.create().status_code, 201)
        row = SiteContent.objects.get(location_key='site.tracking')
        url = f'{self.admin}{row.pk}/'
        self.assertEqual(self.api.patch(url, {'metadata': {'ga4_id': 'G-QA12345678'}}, format='json').status_code, 200)
        self.assertEqual(self.api.delete(url).status_code, 200)
        self.assertFalse(SiteContent.objects.filter(pk=row.pk).exists())

    def test_draft_not_exposed_publicly_and_no_secrets_accepted(self):
        self.create({'ga4_id': 'G-QA12345678'})
        response = self.api.get('/booking/snowland/api/site-content/', {'location_key': 'site.tracking'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_activation_requires_id_and_explicit_automatic_events_confirmation(self):
        for metadata in ({'enabled': True}, {'enabled': True, 'ga4_id': 'G-QA12345678'},
                         {'enabled': True, 'ga4_id': 'G-QA12345678', 'auto_events_disabled': 'true'}):
            self.assertEqual(self.create(metadata).status_code, 400)
        result = self.create({'enabled': True, 'ga4_id': 'G-QA12345678',
                              'meta_pixel_id': '1234567890', 'auto_events_disabled': True})
        self.assertEqual(result.status_code, 201, result.data)
        row = SiteContent.objects.get(location_key='site.tracking')
        self.assertTrue(row.metadata['enabled'])
        self.assertEqual(self.api.patch(f'{self.admin}{row.pk}/', {'status': 'active'}, format='json').status_code, 200)
        public = self.api.get('/booking/snowland/api/site-content/', {'location_key': 'site.tracking'}).data
        self.assertEqual(len(public), 1)
        self.assertTrue(public[0]['metadata']['enabled'])
