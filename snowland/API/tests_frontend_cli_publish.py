import hashlib
import secrets
import stat
import struct
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from API import frontend_cli_publish as cli
from API import frontend_publish as publish
from API.tests_frontend_publish import html
from Client.models import Client, FrontendDeployment, FrontendRelease


def archive_bytes(entries=None):
    if entries is None:
        entries = [('index.html', html()), ('assets/app.js', b'new script')]
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        for path, body in entries:
            archive.writestr(path, body)
    return buffer.getvalue()


def digest(token):
    return hashlib.sha256(token.encode('ascii')).hexdigest()


class FrontendCliPublishTests(TransactionTestCase):
    web = '/api/admin/flashfalcon/frontend-releases/'
    endpoint = f'{web}cli/publish/'

    def setUp(self):
        self.platform, _ = Client.objects.get_or_create(internal_code='flashfalcon', defaults={'name': 'FlashFalcon'})
        self.school, _ = Client.objects.get_or_create(internal_code='snowland', defaults={'name': 'SnowLand'})
        self.token = secrets.token_hex(32)
        self.old_token = secrets.token_hex(32)
        self.env = self.enterContext(patch.dict('os.environ', {
            cli.CURRENT_TOKEN_DIGEST: digest(self.token), cli.PREVIOUS_TOKEN_DIGEST: '',
        }))
        self.client = APIClient(enforce_csrf_checks=True)
        self.auth = {'HTTP_AUTHORIZATION': 'Bearer ' + self.token}
        self.storage = FileSystemStorage(location=self.enterContext(TemporaryDirectory()))
        self.target = {'mode': 'local', 'root': self.storage.location, 'label': 'test'}
        self.config = self.enterContext(patch('API.frontend_publish.target_configuration', return_value=(self.target, '')))
        self.enterContext(patch('API.frontend_cli_publish.release_storage', return_value=self.storage))
        self.enterContext(patch('API.frontend_releases.release_storage', return_value=self.storage))
        self.start = self.enterContext(patch('API.frontend_publish.start_deployment'))

    def upload(self, body=None, key=None, auth=None, url=None):
        upload = SimpleUploadedFile('dist.zip', archive_bytes() if body is None else body, 'application/zip')
        return self.client.post(url or self.endpoint, {'archive': upload}, format='multipart',
                                HTTP_IDEMPOTENCY_KEY=str(uuid4()) if key is None else str(key),
                                **(self.auth if auth is None else auth))

    def job(self, request_id, auth=None):
        return self.client.get(f'{self.web}cli/jobs/{request_id}/', **(self.auth if auth is None else auth))

    def assert_no_release_objects(self):
        self.assertFalse(FrontendRelease.objects.exists())
        self.assertFalse(any(path.is_file() for path in Path(self.storage.location).rglob('*')))

    def test_bearer_required_for_upload_and_lookup(self):
        for auth in ({}, {'HTTP_AUTHORIZATION': 'Bearer ' + secrets.token_hex(32)},
                     {'HTTP_AUTHORIZATION': 'Basic ' + self.token}, {'HTTP_AUTHORIZATION': 'Bearer'}):
            with self.subTest(scheme_present=bool(auth)):
                self.assertEqual(self.upload(auth=auth).status_code, 401)
                self.assertEqual(self.job(uuid4(), auth=auth).status_code, 401)
        self.assert_no_release_objects()

    def test_missing_or_invalid_current_digest_disables_both_routes_even_with_previous(self):
        self.env[cli.PREVIOUS_TOKEN_DIGEST] = digest(self.token)
        for value in (None, '', 'malformed'):
            if value is None:
                self.env.pop(cli.CURRENT_TOKEN_DIGEST, None)
            else:
                self.env[cli.CURRENT_TOKEN_DIGEST] = value
            self.assertEqual(self.upload().status_code, 404)
            self.assertEqual(self.job(uuid4()).status_code, 404)
        self.assert_no_release_objects()

    def test_previous_token_can_submit_and_both_rotation_slots_share_job_identity(self):
        self.env[cli.PREVIOUS_TOKEN_DIGEST] = digest(self.old_token)
        previous = {'HTTP_AUTHORIZATION': 'Bearer ' + self.old_token}
        response = self.upload(auth=previous)
        self.assertEqual(response.status_code, 202)
        request_id = response.json()['request_id']
        self.assertEqual(self.job(request_id).status_code, 200)
        self.assertEqual(self.job(request_id, auth=previous).status_code, 200)
        del self.env[cli.PREVIOUS_TOKEN_DIGEST]
        self.assertEqual(self.job(request_id, auth=previous).status_code, 401)

    def test_scoped_to_exact_and_active_flashfalcon(self):
        for code in ('snowland', 'FlashFalcon'):
            self.assertEqual(self.upload(url=self.endpoint.replace('flashfalcon', code)).status_code, 404)
        self.platform.is_active = False
        self.platform.save(update_fields=['is_active'])
        self.assertEqual(self.upload().status_code, 404)
        self.assertEqual(self.job(uuid4()).status_code, 404)
        self.assert_no_release_objects()

    def test_neither_session_nor_login_jwt_authorizes_cli_routes(self):
        admin = get_user_model().objects.create_superuser(username='cli-session-admin')
        self.client.force_login(admin)
        self.assertEqual(self.client.get(self.web).status_code, 200)
        self.assertEqual(self.upload(auth={}).status_code, 401)
        self.assertEqual(self.job(uuid4(), auth={}).status_code, 401)
        jwt = str(AccessToken.for_user(admin))
        self.assertEqual(self.upload(auth={'HTTP_AUTHORIZATION': 'Bearer ' + jwt}).status_code, 401)

    def test_cli_bearer_has_no_web_release_or_admin_permissions(self):
        self.assertEqual(self.client.get(self.web, **self.auth).status_code, 403)
        self.assertEqual(self.client.get(f'{self.web}5/download/', **self.auth).status_code, 403)
        self.assertEqual(self.client.post(f'{self.web}5/restore/', **self.auth).status_code, 403)
        self.assertIn(self.client.get('/api/admin/flashfalcon/me/', **self.auth).status_code, (401, 403))
        self.assertEqual(self.client.get(self.endpoint, **self.auth).status_code, 405)
        self.assertEqual(self.client.get(f'{self.web}cli/jobs/', **self.auth).status_code, 404)
        self.assertEqual(self.client.post(f'{self.web}cli/jobs/{uuid4()}/', **self.auth).status_code, 405)

    def test_job_lookup_excludes_web_and_other_clients(self):
        release = FrontendRelease.objects.create(client=self.platform, filename='build.zip', archive_name='unused',
                                                sha256='a' * 64, size=1)
        web = FrontendDeployment.objects.create(client=self.platform, release=release)
        other = FrontendDeployment.objects.create(client=self.school, release=release, cli_request_id=uuid4())
        for key in (web.pk, other.cli_request_id, uuid4()):
            self.assertEqual(self.job(key).status_code, 404)

    def test_exact_replay_reuses_existing_job_even_if_target_is_now_unavailable(self):
        key = uuid4()
        first = self.upload(key=key)
        self.config.return_value = (None, 'test unavailable')
        second = self.upload(key=key)
        self.assertEqual((first.status_code, second.status_code), (202, 202))
        self.assertEqual(first.json(), second.json())
        self.assertEqual(self.job(key).json(), first.json())
        self.assertIn('no-store', second['Cache-Control'])
        self.assertEqual(FrontendRelease.objects.count(), 1)
        self.assertEqual(FrontendDeployment.objects.count(), 1)
        self.start.assert_called_once()

    def test_same_key_with_changed_bytes_is_distinct_conflict(self):
        key = uuid4()
        self.assertEqual(self.upload(key=key).status_code, 202)
        different = archive_bytes([('index.html', html('other'))])
        response = self.upload(body=different, key=key)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'idempotency_conflict')
        self.assertEqual(FrontendRelease.objects.count(), 1)
        self.assertEqual(len(list(Path(self.storage.location).rglob('*.zip'))), 1)
        self.start.assert_called_once()

    def test_active_web_job_conflicts_without_storing_an_archive(self):
        web = APIClient()
        web.force_login(get_user_model().objects.create_superuser(username='web-publisher'))
        first = web.post(self.web, {'files': SimpleUploadedFile('index.html', html()), 'paths': ['index.html']}, format='multipart')
        self.assertEqual(first.status_code, 202)
        key = uuid4()
        response = self.upload(key=key)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'publication_in_progress')
        self.assertEqual(self.job(key).status_code, 404)
        self.assertEqual(FrontendRelease.objects.count(), 1)
        self.assertEqual(len(list(Path(self.storage.location).rglob('*.zip'))), 1)
        self.start.assert_called_once()

    def test_active_cli_job_also_blocks_web_publication(self):
        self.assertEqual(self.upload().status_code, 202)
        web = APIClient()
        web.force_login(get_user_model().objects.create_superuser(username='web-publisher'))
        response = web.post(self.web, {'files': SimpleUploadedFile('index.html', html()),
                                      'paths': ['index.html']}, format='multipart')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(FrontendDeployment.objects.count(), 1)

    def test_queue_failure_cleans_only_archive_created_inside_request(self):
        with patch('API.frontend_publish.queue_publication', side_effect=IntegrityError), self.assertLogs('django.request', level='ERROR'):
            self.client.raise_request_exception = False
            self.assertEqual(self.upload().status_code, 500)
        self.assert_no_release_objects()
        self.assertEqual(self.upload().status_code, 202)
        job = FrontendDeployment.objects.get()
        job.status = 'succeeded'
        job.save(update_fields=['status'])
        with patch('API.frontend_publish.queue_publication', side_effect=IntegrityError), self.assertLogs('django.request', level='ERROR'):
            self.assertEqual(self.upload().status_code, 500)
        self.assertTrue(self.storage.exists(job.release.archive_name))

    def test_requires_uuid_and_exactly_one_multipart_archive(self):
        self.assertEqual(self.upload(key='not-a-uuid').status_code, 400)
        self.assertEqual(self.upload(key='').status_code, 400)
        headers = {**self.auth, 'HTTP_IDEMPOTENCY_KEY': str(uuid4())}
        one = SimpleUploadedFile('dist.zip', archive_bytes(), 'application/zip')
        two = SimpleUploadedFile('dist.zip', archive_bytes(), 'application/zip')
        self.assertEqual(self.client.post(self.endpoint, {'archive': [one, two]}, format='multipart', **headers).status_code, 400)
        one.seek(0)
        self.assertEqual(self.client.post(self.endpoint, {'archive': one, 'extra': 'field'}, format='multipart', **headers).status_code, 400)
        self.assertEqual(self.client.post(self.endpoint, {'archive': 'text'}, format='json', **headers).status_code, 415)
        self.assert_no_release_objects()

    def test_rejects_bad_paths_types_and_foreign_builds(self):
        symlink = ZipInfo('assets/link.js')
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        invalid = [
            [('dist/index.html', html())], [('index.html', html(identity='Other'))], [('index.html', b'<meta name>')],
            [('index.html', html()), ('assets/App.js', b'x'), ('Assets/app2.js', b'x')],
            [('index.html', html()), ('assets/App.js', b'x'), ('assets/app.js', b'x')],
            [('index.html', html()), ('assets.js', b'x'), ('assets.js/foo.js', b'x')],
        ] + [[('index.html', html()), (name, body)] for name, body in (
            ('../app.js', b'x'), ('/app.js', b'x'), ('C:/app.js', b'x'),
            ('static/app.js', b'x'), ('api/', b''), ('private_frontend_releases/app.css', b'x'),
            ('test.zip', b'x'), ('test.php', b'x'), ('test.exe', b'x'), ('test.py', b'x'),
            ('nested.png', b'prefix' + archive_bytes()), ('assets/app.png', b'MZ executable'),
            ('script.js', b'#!/bin/sh'), (symlink, b'../external.js'),
        )]
        for i, entries in enumerate(invalid):
            with self.subTest(zip_case=i):
                self.assertEqual(self.upload(archive_bytes(entries)).status_code, 400)
        # ZipFile writes platform-normalized names on Windows. Insert the raw
        # separator into both the local and central ZIP headers for this case.
        body = archive_bytes([('index.html', html()), ('assets@app.js', b'x')])
        self.assertEqual(self.upload(body.replace(b'assets@app.js', b'assets\\app.js')).status_code, 400)
        self.assert_no_release_objects()
        self.start.assert_not_called()

    def test_rejects_protected_custom_static_prefix(self):
        self.target['prefix'] = 'site'
        with override_settings(STATIC_URL='https://example.test/site/custom-static/'):
            self.assertEqual(self.upload(archive_bytes([('index.html', html()), ('custom-static/app.js', b'x')])).status_code, 400)
        self.assert_no_release_objects()

    def test_rejects_corrupt_crc_encrypted_and_non_zip_bytes(self):
        buffer = BytesIO()
        with ZipFile(buffer, 'w') as archive:
            archive.writestr('index.html', html())
            archive.writestr('assets/app.js', b'uncompressed asset')
        raw = buffer.getvalue()
        encrypted = bytearray(raw)
        central_dir = raw.index(b'PK\x01\x02')
        struct.pack_into('<H', encrypted, central_dir + 8, 1)
        for body in (b'not a zip', raw[:-4], raw.replace(b'uncompressed asset', b'uncompressed crash'), bytes(encrypted)):
            self.assertEqual(self.upload(body).status_code, 400)
        self.assert_no_release_objects()

    def test_rejects_compressed_expanded_file_count_and_member_size_limits(self):
        for field, value, expected in (('MAX_ARCHIVE_BYTES', 8, 413), ('MAX_FILES', 1, 400),
                                       ('MAX_BYTES', 8, 400), ('MAX_FILE_BYTES', 8, 400)):
            module = cli if field == 'MAX_ARCHIVE_BYTES' else publish
            with self.subTest(limit=field), patch.object(module, field, value):
                self.assertEqual(self.upload().status_code, expected)
        self.assert_no_release_objects()

    def test_accepts_real_build_asset_shapes_and_directory_entries(self):
        body = archive_bytes([('index.html', html()), ('assets/', b''), ('assets/雪.PNG', b'image'),
                              ('assets/app.css', b'css'), ('_redirects', b'/* /index.html 200')])
        self.assertEqual(self.upload(body).status_code, 202)

    def mock_aws(self):
        self.config.return_value = ({'mode': 's3', 'bucket': 'cli-website-test', 'owner': '123456789012',
                                    'distribution': 'ETEST1234567', 'prefix': '', 'origin': 'https://example.test',
                                    'region': 'ap-northeast-1'}, '')
        objects = {'index.html': b'<html>original</html>', 'old.js': b'old', 'static/internal.css': b'protected'}
        s3, cdn = Mock(), Mock()
        self.enterContext(patch('API.frontend_publish.boto3.client', side_effect=lambda name, **kwargs: {'s3': s3, 'cloudfront': cdn}[name]))
        s3.get_paginator.return_value.paginate.side_effect = lambda **kwargs: [{'Contents': [{'Key': key} for key in objects]}]
        s3.get_object.side_effect = lambda Key, **kwargs: {'Body': BytesIO(objects[Key])}
        s3.upload_fileobj.side_effect = lambda body, bucket, key, **kwargs: objects.update({key: body.read()})
        s3.delete_object.side_effect = lambda Key, **kwargs: objects.pop(Key)
        cdn.get_distribution.return_value = {'Distribution': {
            'ARN': 'arn:aws:cloudfront::123456789012:distribution/ETEST1234567',
            'DistributionConfig': {'Enabled': True, 'Aliases': {'Items': ['example.test']},
                                   'DefaultCacheBehavior': {'TargetOriginId': 'web'},
                                   'Origins': {'Items': [{'Id': 'web', 'DomainName': 'cli-website-test.s3.amazonaws.com'}]}},
        }}
        cdn.create_invalidation.return_value = {'Invalidation': {'Status': 'Completed'}}
        self.start.side_effect = publish.run_deployment
        return objects, s3, cdn

    def test_success_through_s3_and_cloudfront_contract(self):
        objects, s3, cdn = self.mock_aws()
        response = self.upload()
        self.assertEqual(response.status_code, 202)
        job = self.job(response.json()['request_id']).json()['deployment']
        self.assertEqual(job['status'], 'succeeded')
        self.assertEqual(objects, {'index.html': html(), 'assets/app.js': b'new script', 'static/internal.css': b'protected'})
        self.assertTrue(FrontendRelease.objects.get(pk=job['release_id']).is_current)
        self.assertIsNotNone(job['backup_id'])
        s3.head_bucket.assert_called_once()
        cdn.create_invalidation.assert_called_once()

    def test_cdn_failure_restores_site_and_records_failed(self):
        objects, _, cdn = self.mock_aws()
        before = objects.copy()
        cdn.create_invalidation.side_effect = [OSError('test CDN failure'), {'Invalidation': {'Status': 'Completed'}}]
        with self.assertLogs('API.frontend_publish', level='ERROR'):
            response = self.upload()
        status = self.job(response.json()['request_id']).json()['deployment']['status']
        self.assertEqual(status, 'failed')
        self.assertEqual(objects, before)
        self.assertEqual(cdn.create_invalidation.call_count, 2)
        self.assertFalse(FrontendRelease.objects.filter(is_current=True).exists())

    def test_credentials_are_removed_before_upload_processing_and_never_logged(self):
        wrong = secrets.token_hex(32)
        with self.assertLogs(level='WARNING') as captured:
            response = self.upload(auth={'HTTP_AUTHORIZATION': 'Bearer ' + wrong})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(self.upload(body=b'bad').status_code, 400)
        text = '\n'.join(captured.output) + response.content.decode()
        self.assertFalse(wrong in text or self.token in text or 'HTTP_AUTHORIZATION' in text)
        valid = self.upload()
        self.assertFalse('HTTP_AUTHORIZATION' in valid.wsgi_request.META)
        self.assertFalse('Authorization' in valid.wsgi_request.headers)
