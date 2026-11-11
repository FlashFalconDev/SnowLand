import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from API.recruitment import RecruitmentThrottle
from Client.models import Client, RecruitmentApplication
from Control.models import TenantStaffMembership
from Resorts.models import Campus


PDF = b'%PDF-1.4\n% Synthetic recruitment attachment\n%%EOF\n'


class RecruitmentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.files = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(PRIVATE_COURSE_MEDIA_ROOT=Path(self.files)))
        self.enterContext(patch.object(RecruitmentThrottle, 'rate', '1000/min'))
        self.school = Client.objects.create(internal_code='recruit-a', name='Recruit A')
        self.other_school = Client.objects.create(internal_code='recruit-b', name='Recruit B')
        self.public = APIClient()
        self.console = APIClient()
        self.console.force_login(User.objects.create_superuser('recruit-admin', 'admin@example.test', 'test'))
        self.public_url = '/booking/recruit-a/api/recruitment/'
        self.console_url = '/api/admin/recruit-a/recruitment/'
        self.settings_url = self.console_url + 'settings/'
        self.fields = [
            {'id': 'name', 'label': '姓名', 'type': 'short', 'required': True},
            {'id': 'bio', 'label': '自我介紹', 'type': 'long', 'required': False},
            {'id': 'level', 'label': '程度', 'type': 'single', 'required': True, 'options': ['初級', '進階']},
            {'id': 'sports', 'label': '項目', 'type': 'multiple', 'required': True, 'options': ['單板', '雙板']},
            {'id': 'cv', 'label': '履歷', 'type': 'file', 'required': True, 'formats': ['pdf'], 'max_mb': 1},
        ]

    def configure(self, fields=None, enabled=True, revision=None):
        return self.console.put(self.settings_url, {
            'enabled': enabled,
            'fields': self.fields if fields is None else fields,
            'revision': revision if revision is not None else self.console.get(self.settings_url).data['revision'],
        }, format='json')

    def payload(self, **changes):
        return {
            'submission_id': str(uuid4()),
            'revision': self.public.get(self.public_url).data.get('revision', 'old'),
            'answers': json.dumps({'name': 'QA 應徵者', 'bio': '有滑雪經驗', 'level': '進階', 'sports': ['單板', '雙板']}),
            'file_cv': SimpleUploadedFile('合成履歷.pdf', PDF, 'application/pdf'),
            **changes,
        }

    def submit(self, **changes):
        return self.public.post(self.public_url, self.payload(**changes), format='multipart')

    def test_draft_stays_private_and_publishing_preserves_order(self):
        self.assertEqual(self.public.get(self.public_url).data, {'enabled': False})
        self.assertEqual(self.configure(enabled=False).status_code, 200)
        self.assertEqual(self.public.get(self.public_url).data, {'enabled': False})
        self.assertEqual(self.submit().status_code, 503)
        self.assertEqual(self.configure(fields=self.fields[::-1]).status_code, 200)
        self.assertEqual(self.public.get(self.public_url).data['fields'], self.fields[::-1])
        self.assertEqual(self.public.get('/booking/recruit-b/api/recruitment/').data, {'enabled': False})

    def test_settings_validate_schema_and_detect_stale_edits(self):
        revision = self.console.get(self.settings_url).data['revision']
        for invalid in ([], [self.fields[0]] * 2, [{**self.fields[2], 'options': ['重複', '重複']}],
                        [{**self.fields[4], 'formats': ['zip']}], [{**self.fields[4], 'max_mb': 11}]):
            self.assertEqual(self.configure(fields=invalid).status_code, 400)
        self.assertEqual(self.configure().status_code, 200)
        self.assertEqual(self.configure(revision=revision).status_code, 409)

    def test_save_once_and_keep_the_original_questions(self):
        self.assertEqual(self.configure().status_code, 200)
        original = self.payload()
        first = self.public.post(self.public_url, original, format='multipart')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(self.configure(fields=[{**self.fields[0], 'label': '新題目'}]).status_code, 200)
        retry = self.payload(submission_id=original['submission_id'], revision=original['revision'])
        self.assertEqual(self.public.post(self.public_url, retry, format='multipart').status_code, 200)
        self.assertEqual(self.submit(revision=original['revision']).status_code, 409)
        self.assertEqual(self.submit(submission_id=original['submission_id']).status_code, 409)
        application = RecruitmentApplication.objects.get()
        self.assertEqual(application.fields, self.fields)
        self.assertEqual(len(list(Path(self.files).rglob('*.pdf'))), 1)
        detail = self.console.get(f'{self.console_url}{application.pk}/').data
        self.assertEqual(detail['answers']['sports'], ['單板', '雙板'])
        self.assertEqual(detail['attachments']['cv']['name'], '合成履歷.pdf')
        self.assertNotIn('path', detail['attachments']['cv'])
        self.assertEqual(self.console.get(self.console_url).data['count'], 1)

    def test_required_answers_file_content_and_size_are_checked(self):
        self.assertEqual(self.configure().status_code, 200)
        no_answers = self.submit(answers='{}')
        self.assertEqual(no_answers.status_code, 400)
        self.assertEqual(set(no_answers.data['fields']), {'name', 'level', 'sports'})
        bad_choices = self.submit(answers=json.dumps({'name': 'QA', 'level': '其他', 'sports': ['單板', '單板']}))
        self.assertEqual(set(bad_choices.data['fields']), {'level', 'sports'})
        for upload in (SimpleUploadedFile('cv.pdf', b'<html>not a PDF</html>'),
                       SimpleUploadedFile('cv.pdf', PDF + b'x' * 1048576)):
            result = self.submit(file_cv=upload)
            self.assertEqual(result.status_code, 400)
            self.assertIn('cv', result.data['fields'])
        without_attachment = self.payload()
        del without_attachment['file_cv']
        result = self.public.post(self.public_url, without_attachment, format='multipart')
        self.assertEqual(result.status_code, 400)
        self.assertIn('cv', result.data['fields'])
        self.assertFalse(RecruitmentApplication.objects.exists())
        self.assertFalse(list(Path(self.files).rglob('*.pdf')))

    def test_failed_database_write_cleans_saved_attachment(self):
        self.assertEqual(self.configure().status_code, 200)
        with patch('API.recruitment.RecruitmentApplication.objects.create', side_effect=RuntimeError('QA')):
            with self.assertRaises(RuntimeError):
                self.submit()
        self.assertFalse(list(Path(self.files).rglob('*.pdf')))
        self.assertFalse(RecruitmentApplication.objects.exists())

    def test_download_requires_recruitment_permission_and_matching_school(self):
        self.assertEqual(self.configure().status_code, 200)
        self.assertEqual(self.submit().status_code, 201)
        application = RecruitmentApplication.objects.get()
        suffix = f'{application.pk}/attachments/cv/'
        response = self.console.get(self.console_url + suffix)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), PDF)
        self.assertTrue(response['Content-Disposition'].startswith('attachment;'))
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(self.console.get(self.console_url + 'invalid/attachments/cv/').status_code, 404)
        self.assertEqual(self.console.get('/api/admin/recruit-b/recruitment/' + suffix).status_code, 404)
        self.assertEqual(self.public.get(self.console_url + suffix).status_code, 403)

        worker = User.objects.create_user('recruit-worker')
        profile = TenantStaffMembership.objects.create(
            user=worker, client=self.school, is_manager=True, admin_permissions=['site_about'], all_campuses=True,
        )
        worker_api = APIClient()
        worker_api.force_login(worker)
        self.assertEqual(worker_api.get(self.console_url + suffix).status_code, 403)
        profile.admin_permissions = ['recruitment']
        profile.all_campuses = False
        profile.save()
        profile.campuses.add(Campus.objects.create(client=self.school, name='QA campus'))
        self.assertEqual(worker_api.get(self.console_url + suffix).status_code, 403)
        profile.all_campuses = True
        profile.save()
        permitted = worker_api.get(self.console_url + suffix)
        self.assertEqual(permitted.status_code, 200)
        self.assertEqual(b''.join(permitted.streaming_content), PDF)

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=True, ALLOWED_HOSTS=['127.0.0.1'])
    def test_recruitment_rejects_local_bypass_without_a_logged_in_session(self):
        response = self.public.get(self.console_url, HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(username='local-dev-admin', is_superuser=True).exists())
