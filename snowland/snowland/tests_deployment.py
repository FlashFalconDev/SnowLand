import os
import runpy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from storages.backends.s3 import S3Storage

from booking import media_files


class DeploymentSettingsTests(SimpleTestCase):
    def read_settings(self, values=None, token_response=None, ip_response=None):
        environment = {
            'DJANGO_SECRET_KEY': 'isolated-test-secret-never-use-in-production',
            'AWS_STORAGE_BUCKET_NAME': 'test-static-bucket',
            'AWS_REGION': 'ap-northeast-1',
            'STATIC_URL': 'https://static.example.test/static/',
        }
        environment.update(values or {})
        with patch.dict(os.environ, environment, clear=True), \
                patch('dotenv.load_dotenv'), \
                patch('dotenv.dotenv_values', return_value={}), \
                patch('requests.put') as put, patch('requests.get') as get:
            if token_response is None:
                put.side_effect = requests.Timeout()
            else:
                put.return_value = token_response
                get.return_value = ip_response
            config = runpy.run_path(str(Path(__file__).with_name('settings.py')))
        return config, put, get

    def test_production_defaults_and_static_storage_use_only_customer_configuration(self):
        config, _, _ = self.read_settings()
        self.assertFalse(config['DEBUG'])
        self.assertEqual(config['SECRET_KEY'], 'isolated-test-secret-never-use-in-production')
        self.assertEqual(config['STATIC_URL'], 'https://static.example.test/static/')
        self.assertNotIn('AWS_ACCESS_KEY_ID', config)
        self.assertNotIn('AWS_SECRET_ACCESS_KEY', config)
        self.assertNotIn('STATICFILES_STORAGE', config)
        backend = config['STORAGES']['staticfiles']
        self.assertEqual(backend['BACKEND'], 'storages.backends.s3.S3Storage')
        storage = S3Storage(**backend['OPTIONS'])
        self.assertEqual(storage.bucket_name, 'test-static-bucket')
        self.assertEqual(storage.url('admin/css/base.css'),
                         'https://static.example.test/static/admin/css/base.css')
        self.assertIsNone(storage.access_key)
        self.assertIsNone(storage.secret_key)

    def test_secret_is_required_even_if_an_old_dotenv_file_exists(self):
        with patch.dict(os.environ, {}, clear=True), patch('dotenv.load_dotenv'):
            with self.assertRaisesRegex(KeyError, 'DJANGO_SECRET_KEY'):
                runpy.run_path(str(Path(__file__).with_name('settings.py')))

    def test_debug_requires_explicit_one_and_local_static_files_remain_available(self):
        config, _, _ = self.read_settings({'DJANGO_DEBUG': '1', 'STATIC_URL': '/static/'})
        self.assertTrue(config['DEBUG'])
        self.assertEqual(config['STORAGES']['staticfiles']['BACKEND'],
                         'django.contrib.staticfiles.storage.StaticFilesStorage')
        config, _, _ = self.read_settings({'DJANGO_DEBUG': 'true'})
        self.assertFalse(config['DEBUG'])

    def test_hosts_and_csrf_origins_are_comma_separated_and_trimmed(self):
        config, _, _ = self.read_settings({
            'DJANGO_ALLOWED_HOSTS': ' api.example.test, ,booking.example.test ',
            'DJANGO_CSRF_TRUSTED_ORIGINS': ' https://web.example.test, ,https://admin.example.test ',
        })
        self.assertEqual(config['ALLOWED_HOSTS'], ['api.example.test', 'booking.example.test'])
        self.assertEqual(config['CSRF_TRUSTED_ORIGINS'],
                         ['https://web.example.test', 'https://admin.example.test'])

    def test_imdsv2_passes_token_and_adds_only_valid_ipv4(self):
        token = Mock(status_code=200, text='test-metadata-token')
        address = Mock(status_code=200, text=' 10.0.1.23\n')
        config, put, get = self.read_settings(token_response=token, ip_response=address)
        put.assert_called_once_with(
            'http://169.254.169.254/latest/api/token',
            headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
            timeout=0.2, allow_redirects=False,
        )
        get.assert_called_once_with(
            'http://169.254.169.254/latest/meta-data/local-ipv4',
            headers={'X-aws-ec2-metadata-token': 'test-metadata-token'},
            timeout=0.2, allow_redirects=False,
        )
        self.assertIn('10.0.1.23', config['ALLOWED_HOSTS'])
        for invalid in ('<html>Unauthorized</html>', '::1', '', '10.0.1.23/24'):
            with self.subTest(address=invalid):
                config, _, _ = self.read_settings(
                    token_response=token, ip_response=Mock(status_code=200, text=invalid),
                )
                self.assertIsNone(config['ec2_private_ip'])
                self.assertNotIn(invalid, config['ALLOWED_HOSTS'])

    def test_imds_failure_never_falls_back_to_imdsv1(self):
        config, _, get = self.read_settings()
        self.assertIsNone(config['ec2_private_ip'])
        get.assert_not_called()
        failed_token = Mock(status_code=401, text='Unauthorized')
        failed_token.raise_for_status.side_effect = requests.HTTPError()
        _, _, get = self.read_settings(token_response=failed_token)
        get.assert_not_called()
        _, _, get = self.read_settings(token_response=Mock(status_code=200, text=''))
        get.assert_not_called()


class HealthCheckTests(SimpleTestCase):
    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_anonymous_http_health_check_is_not_redirected(self):
        with patch('snowland.urls.connection.ensure_connection') as ensure:
            response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')
        self.assertEqual(response['Cache-Control'], 'no-store')
        ensure.assert_called_once_with()
        self.assertNotIn('Location', response)
        self.assertEqual(self.client.get('/test/').status_code, 301)

    def test_database_outage_returns_503_without_error_details(self):
        with patch('snowland.urls.connection.ensure_connection',
                   side_effect=OperationalError('private database details')):
            response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b'unavailable')
        self.assertNotIn(b'private database details', response.content)


class LiveDatabaseHealthCheckTests(TestCase):
    def test_health_check_connects_to_isolated_test_database(self):
        self.assertEqual(self.client.get('/healthz/').status_code, 200)


class PrivateStorageTests(SimpleTestCase):
    @override_settings(SNOWLAND_PRIVATE_MEDIA_BUCKET='')
    def test_unconfigured_bucket_uses_local_storage_and_keeps_private_urls_blocked(self):
        namespace = runpy.run_path(media_files.__file__)
        with TemporaryDirectory() as directory, override_settings(PRIVATE_COURSE_MEDIA_ROOT=directory):
            storage = namespace['PrivateCourseMediaStorage']()
            self.assertIsInstance(storage, FileSystemStorage)
            name = storage.save('course-records/local.png', ContentFile(b'local-image'))
            with storage.open(name, 'rb') as saved:
                self.assertEqual(saved.read(), b'local-image')
            with self.assertRaises(ValueError):
                storage.url(name)
            storage.delete(name)
            self.assertFalse(storage.exists(name))

    def s3_storage_class(self):
        with override_settings(
            SNOWLAND_PRIVATE_MEDIA_BUCKET='test-private-bucket',
            AWS_S3_CUSTOM_DOMAIN='public.example.test',
            AWS_S3_OBJECT_PARAMETERS={'ACL': 'public-read'},
            AWS_DEFAULT_ACL='public-read',
        ):
            namespace = runpy.run_path(media_files.__file__)
        return namespace['PrivateCourseMediaStorage']

    def test_private_s3_configuration_does_not_inherit_public_static_settings(self):
        storage = self.s3_storage_class()()
        self.assertIsInstance(storage, S3Storage)
        self.assertEqual(storage.bucket_name, 'test-private-bucket')
        self.assertEqual(storage.location, 'private_course_media')
        self.assertIsNone(storage.default_acl)
        self.assertTrue(storage.querystring_auth)
        self.assertIsNone(storage.custom_domain)
        self.assertEqual(storage.object_parameters, {})
        self.assertFalse(storage.file_overwrite)
        with self.assertRaises(ValueError):
            storage.url('course-records/private.png')

    def test_independent_s3_storage_instances_share_uploads_and_support_range_responses(self):
        # Mock only the remote S3 boundary; exercise the actual S3Storage/S3File APIs.
        objects = {}
        uploads = []
        bucket = Mock()

        def object_for(key):
            obj = Mock(content_length=len(objects.get(key, b'')), content_encoding=None)
            def upload(file, **kwargs):
                objects[key] = file.read()
                uploads.append(kwargs['ExtraArgs'])
            obj.upload_fileobj.side_effect = upload
            obj.download_fileobj.side_effect = lambda file, **kwargs: file.write(objects[key])
            obj.delete.side_effect = lambda: objects.pop(key)
            return obj

        bucket.Object.side_effect = object_for
        storage_class = self.s3_storage_class()
        writer, reader = storage_class(), storage_class()
        writer._bucket = reader._bucket = bucket
        content = b'\x00\x00\x00\x18ftypisom' + b'video-content'
        with patch.object(writer, 'exists', return_value=False):
            name = writer.save('course-records/lesson.mp4', ContentFile(content))
        self.assertEqual(objects['private_course_media/' + name], content)
        self.assertNotIn('ACL', uploads[0])
        self.assertEqual(reader.size(name), len(content))
        response = media_files.private_file_response(SimpleNamespace(file=reader.open(name, 'rb')))
        self.assertEqual(b''.join(response.streaming_content), content)
        response.close()
        response = media_files.private_file_response(
            SimpleNamespace(file=reader.open(name, 'rb')), 'bytes=4-11',
        )
        self.assertEqual(response.status_code, 206)
        self.assertEqual(b''.join(response.streaming_content), content[4:12])
        response.close()
        response = media_files.private_file_response(
            SimpleNamespace(file=reader.open(name, 'rb')), 'bytes=999-1000',
        )
        self.assertEqual(response.status_code, 416)
        reader.delete(name)
        self.assertFalse(objects)
