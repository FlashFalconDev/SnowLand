from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, SiteContent


class PhotographyGalleryTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.user = User.objects.create_superuser('gallery-hq', password='qa-only')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/admin/snowland/site-content/'
        self.body = {'content_type': 'media', 'location_key': 'photography.gallery',
                     'title': 'QA新作品', 'image_url': '/vite.svg', 'status': 'active'}

    def test_new_photo_defaults_and_published_categories_are_returned(self):
        created = self.api.post(self.url, {**self.body, 'metadata': {
            'location': ' 富良野 ', 'section': ' 森林 ', 'shoot_types': ['親子', '親子', ' 情侶 '], 'other': '保留'}}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        row = SiteContent.objects.get(title='QA新作品')
        self.assertEqual(row.metadata, {'media_type': 'photo', 'location': '富良野', 'section': '森林',
                                       'shoot_types': ['親子', '情侶'], 'other': '保留'})
        result = APIClient().get('/booking/snowland/api/site-content/?location_key=photography.gallery')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data[0]['metadata']['location'], '富良野')
        hidden = self.api.patch(f'{self.url}{row.pk}/', {'status': 'hidden'}, format='json')
        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(APIClient().get('/booking/snowland/api/site-content/?location_key=photography.gallery').data, [])

    def test_invalid_metadata_or_photo_is_rejected_without_writing(self):
        changes = [
            {'metadata': {'media_type': 'document'}}, {'metadata': {'location': []}},
            {'metadata': {'section': 'x' * 81}}, {'metadata': {'shoot_types': '親子'}},
            {'metadata': {'shoot_types': [None]}}, {'metadata': {'shoot_types': ['x'] * 21}},
            {'image_url': ''}, {'image_url': 'javascript:alert(1)'}, {'image_url': '//evil.test/photo.jpg'},
            {'image_url': '/\\evil.test/photo.jpg'}, {'image_url': '/bad\n.jpg'},
        ]
        for patch in changes:
            with self.subTest(patch=patch):
                result = self.api.post(self.url, {**self.body, **patch}, format='json')
                self.assertEqual(result.status_code, 400, result.data)
                self.assertEqual(SiteContent.objects.count(), 0)

    def test_video_requires_id_and_draft_can_be_incomplete(self):
        result = self.api.post(self.url, {**self.body, 'metadata': {'media_type': 'video', 'video_id': '../bad'}}, format='json')
        self.assertEqual(result.status_code, 400)
        result = self.api.post(self.url, {**self.body, 'metadata': {'media_type': 'video', 'video_id': 'dQw4w9WgXcQ'}}, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        draft = self.api.post(self.url, {**self.body, 'image_url': '', 'status': 'draft'}, format='json')
        self.assertEqual(draft.status_code, 201, draft.data)
        self.assertEqual(self.api.patch(f"{self.url}{draft.data['data']['id']}/", {'status': 'active'}, format='json').status_code, 400)

    def test_editor_keeps_unknown_metadata_and_cannot_edit_other_tenant(self):
        self.user.is_superuser = False
        self.user.save()
        profile = self.user.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'web_editor'
        profile.admin_permissions = ['reviews']
        profile.save()
        row = SiteContent.objects.create(client=self.tenant, **self.body, metadata={'private_marker': 'keep'})
        result = self.api.patch(f'{self.url}{row.pk}/', {'title': '改標題'}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        row.refresh_from_db()
        self.assertEqual(row.metadata['private_marker'], 'keep')
        self.assertEqual(row.metadata['media_type'], 'photo')
        other = Client.objects.create(name='Other', internal_code='other')
        foreign = SiteContent.objects.create(client=other, **self.body)
        self.assertEqual(self.api.patch(f'{self.url}{foreign.pk}/', {'title': '錯誤'}, format='json').status_code, 404)
        self.api.force_authenticate(None)
        self.assertIn(self.api.get(self.url).status_code, (401, 403))
