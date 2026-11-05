from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, FrontendRelease


def build_zip(name='dist.zip', path='index.html', content='test frontend'):
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archive:
        archive.writestr(ZipInfo(path), content)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='application/zip')


class FrontendReleaseTests(TestCase):
    endpoint = '/api/admin/flashfalcon/frontend-releases/'

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Client.objects.create(name='FlashFalcon', internal_code='flashfalcon')
        cls.other = Client.objects.create(name='SnowLand', internal_code='snowland')
        users = get_user_model().objects
        cls.admin = users.create_superuser(username='platform', email='platform@example.test')
        cls.staff = users.create_user(username='staff', is_staff=True)

    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.storage = FileSystemStorage(location=directory)
        self.enterContext(patch('API.frontend_releases.release_storage', return_value=self.storage))
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.admin)
        library = self.client.get(self.endpoint).json()
        self.assertEqual(library['versions'], [])
        self.assertTrue(library['storage_ready'])
        self.csrf = {'HTTP_X_CSRFTOKEN': self.client.cookies['csrftoken'].value}

    def upload(self, archive):
        return self.client.post(self.endpoint, {'archive': archive}, format='multipart', **self.csrf)

    def restore(self, version_id):
        return self.client.post(f'{self.endpoint}{version_id}/restore/', **self.csrf)

    def test_upload_history_duplicate_restore_and_download(self):
        original = build_zip('first.zip', content='first')
        archive_bytes = original.read()
        original.seek(0)
        first = self.upload(original)
        second = self.upload(build_zip('second.zip', content='second'))
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        first_id, second_id = first.json()['id'], second.json()['id']
        self.assertEqual(self.upload(build_zip('duplicate.zip', content='first')).json()['id'], first_id)
        with patch('API.frontend_publish.target_configuration', return_value=({'mode': 'local', 'root': self.storage.location, 'label': 'QA'}, '')):
            self.assertEqual(self.restore(first_id).status_code, 202)
            self.assertEqual(self.restore(second_id).status_code, 409)
        versions = self.client.get(self.endpoint).json()['versions']
        self.assertEqual([(item['id'], item['is_current']) for item in versions], [(second_id, False), (first_id, False)])
        download = self.client.get(f'{self.endpoint}{first_id}/download/')
        self.assertEqual(download.status_code, 200)
        self.assertIn('attachment;', download['Content-Disposition'])
        self.assertIn('no-store', download['Cache-Control'])
        self.assertEqual(b''.join(download.streaming_content), archive_bytes)
        self.assertTrue(download.closed)
        self.assertFalse(FrontendRelease.objects.filter(client=self.other).exists())

    def test_invalid_zip_does_not_create_version(self):
        invalid = (
            build_zip(path='dist/index.html'),
            build_zip(path='../index.html'),
            SimpleUploadedFile('corrupt.zip', b'invalid archive'),
        )
        for archive in invalid:
            with self.subTest(archive=archive.name):
                self.assertEqual(self.upload(archive).status_code, 400)
        self.assertFalse(FrontendRelease.objects.exists())
        self.assertFalse(self.storage.exists(str(self.tenant.pk)))

    def test_protects_writes_and_cross_tenant_access(self):
        version = self.upload(build_zip()).json()['id']
        self.assertEqual(self.client.post(f'{self.endpoint}{version}/restore/').status_code, 403)
        for client_code in ('snowland', 'FlashFalcon', 'missing'):
            wrong_url = self.endpoint.replace('flashfalcon', client_code)
            self.assertEqual(self.client.get(wrong_url).status_code, 404)
            self.assertEqual(self.client.post(wrong_url, **self.csrf).status_code, 404)
            self.assertEqual(self.client.post(f'{wrong_url}{version}/restore/', **self.csrf).status_code, 404)
            self.assertEqual(self.client.get(f'{wrong_url}{version}/download/').status_code, 404)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.endpoint).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(f'{self.endpoint}{version}/download/').status_code, 403)
        self.client.force_login(self.admin)
        self.tenant.is_active = False
        self.tenant.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(self.endpoint).status_code, 404)

    def test_missing_archive_does_not_replace_current_version(self):
        first = self.upload(build_zip(content='first')).json()['id']
        second = self.upload(build_zip(content='second')).json()['id']
        FrontendRelease.objects.filter(pk=first).update(is_current=True)
        self.storage.delete(FrontendRelease.objects.get(pk=second).archive_name)
        self.assertEqual(self.restore(second).status_code, 409)
        self.assertEqual(FrontendRelease.objects.get(is_current=True).pk, first)
