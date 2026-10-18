from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from API import tests_payroll_review as fixtures
from Coach.models import PayrollDocumentSettings, PayrollStatement
from Coach.payroll_documents import document_digest
from Coach.payroll_review import publish_statement, confirm_statement


def png(color='black'):
    stream = BytesIO(); Image.new('RGB', (160, 60), color).save(stream, format='PNG')
    return stream.getvalue()


class PayrollDocumentTests(TestCase):
    def setUp(self):
        fixtures.PayrollReviewTests.setUp(self)
        self.root = TemporaryDirectory(); self.addCleanup(self.root.cleanup)
        self.settings_override = override_settings(PRIVATE_COURSE_MEDIA_ROOT=self.root.name)
        self.settings_override.enable(); self.addCleanup(self.settings_override.disable)
        self.document_settings = PayrollDocumentSettings.objects.create(client=self.client_tenant,
            title='QA 報酬單', body='QA 測試條文，非正式文件。<script>不應執行</script>', is_active=True)
        self.settings_url = '/api/admin/snowland/payroll-statements/document-settings/'

    def confirm(self):
        statement = publish_statement(self.statement, self.deadline)
        self.statement = confirm_statement(statement, self.coach_user, str(statement.review_token))
        self.api.force_authenticate(self.coach_user)

    def upload(self, data=None, content=None):
        payload = {'signer_name':'QA 本人', 'accepted':'true', 'document_digest':document_digest(self.statement.document_snapshot),
            'file':SimpleUploadedFile('qa.png', png() if content is None else content, content_type='image/png')}
        payload.update(data or {})
        return self.api.post(self.coach_url+'signature/', payload, format='multipart')

    def test_confirmation_generates_immutable_document_snapshot_and_digest(self):
        self.confirm()
        original = deepcopy(self.statement.document_snapshot)
        self.assertEqual(original['total_amount'], 1000)
        self.assertEqual(original['lines'][0]['total_amount'], 1000)
        PayrollDocumentSettings.objects.filter(pk=self.document_settings.pk).update(body='QA changed')
        self.coach.name = 'QA renamed'; self.coach.save(update_fields=['name'])
        self.api.force_authenticate(self.hq)
        response = self.api.post(self.admin_url+'document/')
        self.assertEqual(response.status_code, 200, response.data)
        self.statement.refresh_from_db()
        self.assertEqual(self.statement.document_snapshot, original)
        self.assertEqual(response.data['data']['document_digest'], document_digest(original))

    def test_private_signature_and_identical_retry_preserve_timestamp_file_and_snapshot(self):
        self.confirm()
        for attempt in range(2):
            response = self.upload()
            self.assertEqual(response.status_code, 200, response.data)
            self.statement.refresh_from_db()
            if attempt == 0:
                old = (self.statement.signature_file.name, self.statement.signed_at)
            self.assertEqual((self.statement.signature_file.name, self.statement.signed_at), old)
            self.assertNotIn('signature_file', response.data['data'])
        self.assertEqual(len(list(Path(self.root.name).rglob('*.png'))), 1)
        url = response.data['data']['signature_file_url']
        image = self.api.get(url)
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image['Cache-Control'], 'private, no-store')
        self.assertEqual(b''.join(image.streaming_content), png())
        image.close()
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.get(url).status_code, 403)
        self.api.force_authenticate(self.hq)
        admin = self.api.get(self.admin_url).data
        admin_image = self.api.get(admin['signature_file_url'])
        self.assertEqual(admin_image.status_code, 200)
        admin_image.close()

    def test_invalid_file_consent_or_stale_document_never_saves_signature(self):
        self.confirm()
        for kwargs in [{'content':b'not a PNG'}, {'data':{'accepted':'false'}}, {'data':{'document_digest':'0'*64}}, {'data':{'signer_name':''}}]:
            response = self.upload(**kwargs)
            self.assertEqual(response.status_code, 400, response.data)
            self.statement.refresh_from_db(); self.assertFalse(self.statement.signature_file)
            self.assertIsNone(self.statement.signed_at)
        self.assertFalse(list(Path(self.root.name).rglob('*.png')))

    def test_signed_document_cannot_be_overwritten(self):
        self.confirm(); self.assertEqual(self.upload().status_code, 200)
        self.statement.refresh_from_db(); name = self.statement.signature_file.name
        self.assertEqual(self.upload(content=png('blue')).status_code, 400)
        self.statement.refresh_from_db()
        self.assertEqual(self.statement.signature_file.name, name)
        self.assertEqual(self.statement.signer_name, 'QA 本人')

    def test_missing_template_keeps_confirmation_but_requires_explicit_later_generation(self):
        self.document_settings.is_active = False; self.document_settings.save()
        self.confirm(); self.assertFalse(self.statement.document_snapshot)
        self.assertEqual(self.upload(data={'document_digest':'0'*64}).status_code, 400)
        self.api.force_authenticate(self.hq)
        self.assertEqual(self.api.post(self.admin_url+'document/').status_code, 409)
        self.document_settings.is_active = True; self.document_settings.save()
        response = self.api.post(self.admin_url+'document/')
        self.assertEqual(response.status_code, 200, response.data)

    def test_settings_require_content_and_preserve_tenant_on_save(self):
        response = self.api.post(self.settings_url, {'is_active':True,'body':' '}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        response = self.api.post(self.settings_url, {'body':'QA 新版內容'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.document_settings.refresh_from_db()
        self.assertEqual(self.document_settings.body, 'QA 新版內容')
        self.assertEqual(self.document_settings.client, self.client_tenant)

    def test_database_failure_cleans_uncommitted_signature_file(self):
        self.confirm()
        original_save = PayrollStatement.save
        def fail(instance, *args, **kwargs):
            if instance.signed_at:
                raise RuntimeError('QA fail signature write')
            return original_save(instance, *args, **kwargs)
        with patch.object(PayrollStatement, 'save', fail):
            with self.assertRaisesMessage(RuntimeError, 'QA fail signature write'):
                self.upload()
        self.statement.refresh_from_db(); self.assertIsNone(self.statement.signed_at)
        self.assertFalse(list(Path(self.root.name).rglob('*.png')))

    def test_deleted_qa_statement_removes_private_file_only_after_commit(self):
        self.confirm(); self.upload(); self.statement.refresh_from_db()
        name, storage = self.statement.signature_file.name, self.statement.signature_file.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.statement.delete()
            self.assertTrue(storage.exists(name))
        self.assertFalse(storage.exists(name))

    def test_campus_payroll_staff_cannot_change_company_document_content(self):
        profile = self.user.userprofile
        profile.is_manager = True; profile.role = 'campus_staff'; profile.manager_client = self.client_tenant
        profile.admin_permissions = ['payroll']; profile.save(); profile.campuses.add(self.campus)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.get(self.settings_url).status_code, 200)
        self.assertEqual(self.api.post(self.settings_url, {'body':'QA forbidden'}, format='json').status_code, 403)
        self.document_settings.refresh_from_db(); self.assertNotEqual(self.document_settings.body, 'QA forbidden')

    def test_coach_list_uses_coach_private_image_route_not_admin_route(self):
        self.confirm(); self.upload()
        response = self.api.get('/api/admin/snowland/coach/payroll/')
        url = response.data['data']['list'][0]['signature_file_url']
        image = self.api.get(url)
        self.assertEqual(image.status_code, 200, url)
        self.assertIn('/coach/payroll/', url)
        image.close()

    def test_real_session_signature_requires_csrf_from_authorized_page(self):
        from django.test import Client as BrowserClient
        self.confirm()
        browser = BrowserClient(enforce_csrf_checks=True); browser.force_login(self.coach_user)
        data = {'signer_name':'QA 本人','accepted':'true','document_digest':document_digest(self.statement.document_snapshot),
            'file':SimpleUploadedFile('qa.png',png(),content_type='image/png')}
        self.assertEqual(browser.post(self.coach_url+'signature/',data).status_code, 403)
        self.statement.refresh_from_db(); self.assertIsNone(self.statement.signed_at)
        response = browser.get(self.coach_url)
        self.assertEqual(response.status_code, 200)
        token = browser.cookies['csrftoken'].value
        data['file'] = SimpleUploadedFile('qa.png',png(),content_type='image/png')
        self.assertEqual(browser.post(self.coach_url+'signature/',data,HTTP_X_CSRFTOKEN=token).status_code, 200)
