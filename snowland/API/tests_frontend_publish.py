from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from rest_framework.test import APIClient

from API import frontend_publish as publish
from Client.models import Client, FrontendDeployment, FrontendRelease


def html(text='new', identity='SnowLand'):
    return f'<html><head><meta name="application-name" content="{identity}"></head><body>{text}</body></html>'.encode()


class FrontendPublicationTests(TransactionTestCase):
    endpoint = '/api/admin/flashfalcon/frontend-releases/'

    def setUp(self):
        folder = self.enterContext(TemporaryDirectory())
        self.root = Path(folder) / 'website'
        self.root.mkdir()
        (self.root / 'index.html').write_bytes(b'<html>existing website without the new build marker</html>')
        (self.root / 'old.txt').write_bytes(b'old file')
        (self.root / 'static').mkdir()
        (self.root / 'static/admin.css').write_bytes(b'Django static must survive')
        self.storage = FileSystemStorage(location=Path(folder) / 'private')
        self.enterContext(override_settings(DEBUG=True, SNOWLAND_FRONTEND_LOCAL_ROOT=str(self.root)))
        self.enterContext(patch('API.frontend_publish.target_configuration', return_value=(
            {'mode': 'local', 'root': str(self.root), 'label': 'isolated test website'}, '')))
        self.enterContext(patch('API.frontend_releases.release_storage', return_value=self.storage))
        self.enterContext(patch('API.frontend_publish.start_deployment', side_effect=publish.run_deployment))
        self.platform, _ = Client.objects.get_or_create(internal_code='flashfalcon', defaults={'name': 'FlashFalcon'})
        self.school, _ = Client.objects.get_or_create(internal_code='snowland', defaults={'name': 'SnowLand'})
        self.admin = get_user_model().objects.create_superuser(username='platform-publisher', email='publisher@example.test')
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.admin)
        self.client.get(self.endpoint)
        self.csrf = {'HTTP_X_CSRFTOKEN': self.client.cookies['csrftoken'].value}

    def upload(self, index=None, paths=None, script=b'new javascript'):
        return self.client.post(self.endpoint, {
            'files': [SimpleUploadedFile('index.html', html() if index is None else index),
                      SimpleUploadedFile('app.js', script)],
            'paths': ['index.html', 'assets/app.js'] if paths is None else paths,
        }, format='multipart', **self.csrf)

    def test_folder_publishes_real_files_backs_up_and_restores_real_old_site(self):
        before = (self.root / 'index.html').read_bytes()
        response = self.upload()
        self.assertEqual(response.status_code, 202)
        job = FrontendDeployment.objects.get(pk=response.json()['deployment']['id'])
        self.assertEqual(job.status, 'succeeded', job.message)
        self.assertEqual((self.root / 'index.html').read_bytes(), html())
        self.assertEqual((self.root / 'assets/app.js').read_bytes(), b'new javascript')
        self.assertFalse((self.root / 'old.txt').exists())
        self.assertEqual((self.root / 'static/admin.css').read_bytes(), b'Django static must survive')
        self.assertIsNotNone(job.backup_id)
        with self.storage.open(job.backup.archive_name, 'rb') as source, ZipFile(source) as archive:
            self.assertEqual(archive.read('index.html'), before)
            self.assertNotIn('static/admin.css', archive.namelist())
        result = self.client.get(self.endpoint).json()
        self.assertEqual([v['id'] for v in result['versions'] if v['is_current']], [job.release_id])
        restored = self.client.post(f'{self.endpoint}{job.backup_id}/restore/', **self.csrf)
        self.assertEqual(restored.status_code, 202)
        restored_job = FrontendDeployment.objects.get(pk=restored.json()['deployment']['id'])
        self.assertEqual(restored_job.status, 'succeeded', restored_job.message)
        self.assertEqual((self.root / 'index.html').read_bytes(), before)
        self.assertEqual((self.root / 'old.txt').read_bytes(), b'old file')
        self.assertIsNotNone(restored_job.backup_id)
        self.assertFalse(FrontendRelease.objects.filter(client=self.school).exists())

    def test_archive_size_is_correct_for_seekable_memory_stream(self):
        buffer = BytesIO()
        with ZipFile(buffer, 'w') as archive:
            archive.writestr('index.html', html())
        release = publish.save_release(self.platform, self.storage, buffer, 'size-test.zip')
        self.assertEqual(release.size, len(buffer.getvalue()))

    def test_invalid_builds_do_not_create_versions_or_modify_website(self):
        before = (self.root / 'index.html').read_bytes()
        for body, paths in ((html(identity='FlashFalcon Console'), None), (html(), ['../index.html', 'assets/app.js']),
                            (html(), ['index.html', 'INDEX.HTML']), (html(), ['dist/index.html', 'dist/app.js']),
                            (html(), ['index.html', 'static/admin.css'])):
            with self.subTest(paths=paths, body=body[:20]):
                self.assertEqual(self.upload(body, paths).status_code, 400)
                self.assertEqual((self.root / 'index.html').read_bytes(), before)
                self.assertFalse(FrontendDeployment.objects.exists())
                self.assertFalse(FrontendRelease.objects.exists())

    def test_archive_only_record_is_not_mislabeled_as_published(self):
        buffer = BytesIO()
        with ZipFile(buffer, 'w') as archive:
            archive.writestr('index.html', html())
        release = publish.save_release(self.platform, self.storage, buffer, 'previously-saved.zip')
        release.is_current = True
        release.save(update_fields=['is_current'])
        self.assertFalse(self.client.get(self.endpoint).json()['versions'][0]['is_current'])
        response = self.client.get(f'{self.endpoint}{release.pk}/download/')
        self.assertEqual(b''.join(response.streaming_content), buffer.getvalue())

    def test_preflight_failure_happens_before_any_website_write(self):
        before = (self.root / 'index.html').read_bytes()
        with patch.object(publish.LocalPublisher, 'preflight', side_effect=publish.PublishError('目標不一致')):
            response = self.upload()
        job = FrontendDeployment.objects.get(pk=response.json()['deployment']['id'])
        self.assertEqual(job.status, 'failed')
        self.assertIn('目標不一致', job.message)
        self.assertEqual((self.root / 'index.html').read_bytes(), before)
        self.assertIsNone(job.backup_id)

    def test_backup_failure_prevents_website_write(self):
        before = (self.root / 'index.html').read_bytes()
        with patch('API.frontend_publish.snapshot', side_effect=OSError('private backup failure')):
            self.upload()
        self.assertEqual(FrontendDeployment.objects.get().status, 'failed')
        self.assertEqual((self.root / 'index.html').read_bytes(), before)

    def test_failed_write_restores_original_files_and_does_not_claim_success(self):
        before = (self.root / 'index.html').read_bytes()
        original = publish.LocalPublisher.write
        failed = False

        def write(provider, name, body, headers):
            nonlocal failed
            if name == 'index.html' and not failed:
                failed = True
                raise OSError('single write failure')
            return original(provider, name, body, headers)

        with patch.object(publish.LocalPublisher, 'write', write):
            self.upload()
        self.assertEqual(FrontendDeployment.objects.get().status, 'failed')
        self.assertEqual((self.root / 'index.html').read_bytes(), before)
        self.assertFalse(any(v['is_current'] for v in self.client.get(self.endpoint).json()['versions']))

    def test_waits_for_cdn_and_rolls_back_on_cdn_failure(self):
        before = (self.root / 'index.html').read_bytes()
        calls = []

        def invalidate(provider):
            calls.append(FrontendDeployment.objects.get().status)
            if len(calls) == 1:
                self.assertEqual(calls[-1], 'invalidating')
                self.assertFalse(FrontendRelease.objects.filter(is_current=True).exists())
                raise OSError('CDN failed')

        with patch.object(publish.LocalPublisher, 'invalidate', invalidate):
            self.upload()
        self.assertEqual(FrontendDeployment.objects.get().status, 'failed')
        self.assertEqual((self.root / 'index.html').read_bytes(), before)
        self.assertEqual(len(calls), 2)

    def test_missing_configuration_blocks_publication_without_storing_build(self):
        with patch('API.frontend_publish.target_configuration', return_value=(None, '尚未設定發布位置')):
            self.assertEqual(self.upload().status_code, 503)
        self.assertFalse(FrontendRelease.objects.exists())

    def test_active_job_blocks_a_second_publication(self):
        with patch('API.frontend_publish.start_deployment'):
            first = self.upload()
            second = self.upload()
        self.assertEqual((first.status_code, second.status_code), (202, 409))
        self.assertEqual(FrontendDeployment.objects.count(), 1)
        self.assertEqual(FrontendDeployment.objects.get().status, 'queued')

    def test_full_3000_file_multipart_build_is_accepted(self):
        files = [SimpleUploadedFile('index.html', html())] + [SimpleUploadedFile(f'app-{i}.js', b'x') for i in range(2999)]
        paths = ['index.html'] + [f'assets/app-{i}.js' for i in range(2999)]
        with patch('API.frontend_publish.start_deployment'):
            response = self.client.post(self.endpoint, {'files': files, 'paths': paths}, format='multipart', **self.csrf)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(FrontendDeployment.objects.count(), 1)

    def test_last_successful_release_can_recover_after_failed_rollback(self):
        first = self.upload(html('B'), script=b'B javascript')
        good_release = FrontendDeployment.objects.get(pk=first.json()['deployment']['id']).release_id
        original_write = publish.LocalPublisher.write
        calls = 0

        def fail_after_one_write(provider, name, body, headers):
            nonlocal calls
            calls += 1
            if calls >= 2:
                raise OSError('publication and rollback unavailable')
            return original_write(provider, name, body, headers)

        with patch.object(publish.LocalPublisher, 'write', fail_after_one_write):
            self.upload(html('C'), script=b'C javascript')
        self.assertEqual((self.root/'assets/app.js').read_bytes(), b'C javascript')
        self.assertFalse(any(item['is_current'] for item in self.client.get(self.endpoint).json()['versions']))
        restored = self.client.post(f'{self.endpoint}{good_release}/restore/', **self.csrf)
        self.assertEqual(restored.status_code, 202)
        job = FrontendDeployment.objects.get(pk=restored.json()['deployment']['id'])
        self.assertEqual(job.status, 'succeeded', job.message)
        self.assertEqual((self.root/'index.html').read_bytes(), html('B'))
        self.assertEqual((self.root/'assets/app.js').read_bytes(), b'B javascript')

    def test_trusted_backup_restores_non_utf8_legacy_html(self):
        old = b'<html>legacy original \xff</html>'
        (self.root/'index.html').write_bytes(old)
        response = self.upload()
        backup_id = FrontendDeployment.objects.get(pk=response.json()['deployment']['id']).backup_id
        restored = self.client.post(f'{self.endpoint}{backup_id}/restore/', **self.csrf)
        job = FrontendDeployment.objects.get(pk=restored.json()['deployment']['id'])
        self.assertEqual(job.status, 'succeeded', job.message)
        self.assertEqual((self.root/'index.html').read_bytes(), old)

    @skipUnlessDBFeature('has_select_for_update')
    def test_two_concurrent_requests_create_only_one_active_job(self):
        from django.db import connections
        barrier = Barrier(2)

        def request():
            client = APIClient()
            client.force_authenticate(user=self.admin)
            barrier.wait(timeout=10)
            try:
                return client.post(self.endpoint, {'files': [SimpleUploadedFile('index.html', html())],
                                                  'paths': ['index.html']}, format='multipart').status_code
            finally:
                connections['default'].close()

        with patch('API.frontend_publish.start_deployment'), ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(lambda _: request(), range(2)))
        self.assertEqual(statuses, [202, 409])
        self.assertEqual(FrontendDeployment.objects.count(), 1)

    def test_permission_csrf_and_tenant_boundary(self):
        files = {'files': [SimpleUploadedFile('index.html', html())], 'paths': ['index.html']}
        self.assertEqual(self.client.post(self.endpoint, files, format='multipart').status_code, 403)
        self.assertEqual(self.client.get(self.endpoint.replace('flashfalcon', 'snowland')).status_code, 404)
        staff = get_user_model().objects.create_user(username='ordinary-staff', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.endpoint).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.endpoint).status_code, 403)
        self.assertFalse(FrontendDeployment.objects.exists())


class S3PublicationContractTests(SimpleTestCase):
    def setUp(self):
        self.s3, self.cdn = Mock(), Mock()
        self.enterContext(patch('API.frontend_publish.boto3.client', side_effect=lambda name, **kwargs: self.s3 if name == 's3' else self.cdn))
        self.target = dict(mode='s3', bucket='snowland-web', owner='799381135280', distribution='E1234567890', prefix='', origin='https://snowland.tw', region='ap-northeast-1')
        self.cdn.get_distribution.return_value = {'Distribution': {
            'ARN': 'arn:aws:cloudfront::799381135280:distribution/E1234567890',
            'DistributionConfig': {'Enabled': True, 'Aliases': {'Items': ['snowland.tw']}, 'DefaultCacheBehavior': {'TargetOriginId': 'web'},
                                   'Origins': {'Items': [{'Id': 'web', 'DomainName': 'snowland-web.s3.ap-northeast-1.amazonaws.com', 'OriginPath': ''}]}},
        }}

    def test_verified_bucket_owner_and_cloudfront_origin(self):
        provider = publish.S3Publisher(self.target)
        provider.preflight()
        self.s3.head_bucket.assert_called_once_with(Bucket='snowland-web', ExpectedBucketOwner='799381135280')
        self.cdn.get_distribution.return_value['Distribution']['DistributionConfig']['Origins']['Items'][0]['DomainName'] = 'other-bucket.s3.amazonaws.com'
        with self.assertRaises(publish.PublishError):
            provider.preflight()
        self.s3.upload_fileobj.assert_not_called()

    def test_waits_until_invalidation_has_completed(self):
        provider = publish.S3Publisher(self.target)
        self.cdn.create_invalidation.return_value = {'Invalidation': {'Id': 'INVALIDATE1', 'Status': 'InProgress'}}
        self.cdn.get_invalidation.return_value = {'Invalidation': {'Id': 'INVALIDATE1', 'Status': 'Completed'}}
        with patch('API.frontend_publish.time.sleep'):
            provider.invalidate()
        self.cdn.get_invalidation.assert_called_once_with(DistributionId='E1234567890', Id='INVALIDATE1')

    def test_s3_write_preserves_header_contract_without_object_acl(self):
        provider = publish.S3Publisher(self.target)
        body = BytesIO(b'<html>new</html>')
        provider.write('index.html', body, publish.object_headers('index.html'))
        args = self.s3.upload_fileobj.call_args
        self.assertEqual(args.args[1:], ('snowland-web', 'index.html'))
        self.assertEqual(args.kwargs['ExtraArgs']['ExpectedBucketOwner'], '799381135280')
        self.assertEqual(args.kwargs['ExtraArgs']['CacheControl'], 'no-cache, no-store, must-revalidate')
        self.assertNotIn('ACL', args.kwargs['ExtraArgs'])

    def test_prefixed_custom_django_static_files_cannot_be_overwritten_or_deleted(self):
        self.target['prefix'] = 'site'
        self.s3.get_paginator.return_value.paginate.return_value = [{
            'Contents': [{'Key': 'site/index.html'}, {'Key': 'site/django-assets/admin.css'}, {'Key': 'site/assets/app.js'}],
        }]
        with override_settings(STATIC_URL='https://snowland.tw/site/django-assets/'):
            provider = publish.S3Publisher(self.target)
            self.assertEqual(provider.names(), {'index.html', 'assets/app.js'})
            with self.assertRaises(publish.PublishError):
                provider.write('django-assets/admin.css', BytesIO(b'bad'), {})
            with self.assertRaises(publish.PublishError):
                provider.delete('django-assets/admin.css')
        self.s3.upload_fileobj.assert_not_called()
        self.s3.delete_object.assert_not_called()

    def test_replacing_large_build_does_not_accumulate_unrestorable_assets(self):
        objects = {'index.html'} | {f'assets/old-{i}.js' for i in range(1600)} | {f'assets/new-{i}.js' for i in range(1600)}
        desired = {'index.html'} | {f'assets/new-{i}.js' for i in range(1600)}
        self.s3.get_paginator.return_value.paginate.side_effect = lambda **options: [{'Contents': [{'Key': name} for name in objects]}]
        self.s3.delete_object.side_effect = lambda Key, **options: objects.remove(Key)
        provider = publish.S3Publisher(self.target)
        self.assertGreater(len(provider.names()), publish.MAX_FILES)
        publish.cleanup(provider, desired)
        self.assertEqual(provider.names(), desired)
        self.assertLessEqual(len(provider.names()), publish.MAX_FILES)


class FrontendTargetConfigurationTests(SimpleTestCase):
    def setUp(self):
        self.enterContext(override_settings(DEBUG=False, FRONTEND_URL='https://snowland.tw', SNOWLAND_PRIVATE_MEDIA_BUCKET='private-bucket'))
        self.environment = {
            'SNOWLAND_FRONTEND_BUCKET': 'website-bucket',
            'SNOWLAND_FRONTEND_BUCKET_OWNER': '799381135280',
            'SNOWLAND_FRONTEND_DISTRIBUTION_ID': 'E1234567890',
        }

    def test_missing_config_is_not_ready_and_does_not_guess_a_media_bucket(self):
        with patch.dict('os.environ', {}, clear=True):
            target, reason = publish.target_configuration()
        self.assertIsNone(target)
        self.assertIn('尚未完成', reason)

    def test_private_bucket_or_django_static_prefix_is_rejected(self):
        with patch.dict('os.environ', {**self.environment, 'SNOWLAND_FRONTEND_BUCKET': 'private-bucket'}, clear=True):
            self.assertIsNone(publish.target_configuration()[0])
        with override_settings(STATIC_URL='https://snowland.tw/django-assets/'), patch.dict('os.environ', {**self.environment, 'SNOWLAND_FRONTEND_PREFIX': 'django-assets'}, clear=True):
            self.assertIsNone(publish.target_configuration()[0])
            self.assertFalse(publish.valid_path('django-assets/admin.css'))

    def test_explicit_production_configuration_and_no_local_mode_in_production(self):
        with override_settings(SNOWLAND_FRONTEND_LOCAL_ROOT='ignored-local-path'), patch.dict('os.environ', self.environment, clear=True):
            target, reason = publish.target_configuration()
        self.assertEqual(target['mode'], 's3')
        self.assertEqual(target['bucket'], 'website-bucket')
        self.assertEqual(reason, '')
