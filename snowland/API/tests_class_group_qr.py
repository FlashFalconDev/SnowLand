from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings, Client as BrowserClient
from PIL import Image
from rest_framework.test import APIClient
from API import tests_operations as fixtures
from booking.models import ReservationGroup, Payment, MemberDetail
from Client.models import Client
from Resorts.models import Campus


class ClassGroupQRTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(PRIVATE_COURSE_MEDIA_ROOT=self.directory.name)
        self.settings_override.enable(); self.addCleanup(self.settings_override.disable)
        self.admin = User.objects.create_superuser('qr-hq', 'qr-hq@example.test', 'test')
        self.api = APIClient(); self.api.force_authenticate(self.admin)
        self.url = f'/api/admin/snowland/orders/{self.group.pk}/class-group-qr/'

    def image(self):
        buffer = BytesIO(); Image.new('RGB', (120, 120), 'white').save(buffer, format='PNG')
        return SimpleUploadedFile('group-qr.png', buffer.getvalue(), content_type='image/png')

    def test_upload_uses_private_file_and_returns_protected_url(self):
        response = self.api.post(self.url, {'file': self.image()}, format='multipart')
        self.assertEqual(response.status_code, 200, response.content)
        self.group.refresh_from_db()
        self.assertTrue(self.group.line_group_qr)
        self.assertIn('/class-group-qr/', response.data['data']['line_group_qr_url'])
        self.assertNotIn(self.directory.name, str(response.data))

    def uploaded(self):
        response = self.api.post(self.url, {'file': self.image()}, format='multipart')
        self.assertEqual(response.status_code, 200, response.content)
        return response.data['data']['line_group_qr_url']

    def reader(self, user):
        api = APIClient(); api.force_authenticate(user); return api

    def test_admin_preview_private_headers_and_anonymous_or_stranger_denied(self):
        url = self.uploaded()
        response = self.api.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        response.close()
        self.assertEqual(APIClient().get(url).status_code, 401)
        self.assertEqual(self.reader(self.coach_user).get(url).status_code, 404)
        self.assertEqual(self.reader(self.user).get(url).status_code, 404)

    def test_only_latest_paid_owner_bound_adult_and_guardian_can_read(self):
        url = self.uploaded()
        adult = User.objects.create_user('qr-adult'); parent = User.objects.create_user('qr-parent')
        member = MemberDetail.objects.create(reservation=self.reservation, user=adult, guardian=parent)
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        for user in [self.user, adult, parent]:
            response = self.reader(user).get(url)
            self.assertEqual(response.status_code, 200); response.close()
        member.guardian = None; member.user = self.user; member.save()
        self.assertEqual(self.reader(parent).get(url).status_code, 404)
        self.assertEqual(self.reader(adult).get(url).status_code, 404)
        Payment.objects.create(reservation_group=self.group, user=self.user, status='refunded')
        self.assertEqual(self.reader(self.user).get(url).status_code, 404)

    def test_cancelled_order_redacts_qr_from_owner_and_member_center(self):
        url = self.uploaded()
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        before = self.reader(self.user).get('/booking/snowland/api/member-center/').data
        self.assertEqual(before['orders'][0]['line_group_qr_url'], url)
        self.reservation.status = 'cancelled'; self.reservation.save()
        self.assertEqual(self.reader(self.user).get(url).status_code, 404)
        after = self.reader(self.user).get('/booking/snowland/api/member-center/').data
        self.assertEqual(after['orders'][0]['line_group_qr_url'], '')

    def test_upload_and_read_respect_campus_and_tenant(self):
        url = self.uploaded()
        other = Campus.objects.create(client=self.client_tenant, name='Other', code='other')
        self.assertEqual(self.api.post(self.url, {'file': self.image()}, format='multipart', HTTP_X_CAMPUS_ID=str(other.pk)).status_code, 404)
        self.assertEqual(self.api.get(url, HTTP_X_CAMPUS_ID=str(other.pk)).status_code, 404)
        Client.objects.create(name='Other', internal_code='other')
        self.assertEqual(self.api.get(url.replace('/snowland/', '/other/')).status_code, 404)
        self.assertEqual(self.reader(self.user).post(self.url, {'file': self.image()}, format='multipart').status_code, 403)

    def test_summary_roles_cannot_upload_or_read_private_qr(self):
        url = self.uploaded()
        for role in ['campus_manager', 'campus_principal']:
            user = User.objects.create_user('qr-'+role)
            profile = user.userprofile; profile.is_manager = True; profile.manager_client = self.client_tenant
            profile.role = role; profile.admin_permissions = ['orders']; profile.save(); profile.campuses.add(self.campus)
            self.assertEqual(self.reader(user).post(self.url, {'file': self.image()}, format='multipart').status_code, 403)
            self.assertEqual(self.reader(user).get(url).status_code, 404)

    def test_invalid_missing_video_svg_and_oversized_files_preserve_old_qr(self):
        url = self.uploaded(); self.group.refresh_from_db(); old_name = self.group.line_group_qr.name
        bad = [None, SimpleUploadedFile('fake.png', b'not an image'),
               SimpleUploadedFile('unsafe.svg', b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'),
               SimpleUploadedFile('fake.mp4', b'\x00\x00\x00\x20ftypisom' + b'x'*100),
               SimpleUploadedFile('large.png', b'x'*(5*1024*1024+1))]
        for upload in bad:
            response = self.api.post(self.url, {'file': upload} if upload else {}, format='multipart')
            self.assertEqual(response.status_code, 400, response.content)
            self.group.refresh_from_db(); self.assertEqual(self.group.line_group_qr.name, old_name)
        self.assertEqual(len([p for p in Path(self.directory.name).rglob('*') if p.is_file()]), 1)

    def test_replace_and_remove_clean_old_file_only_after_commit_and_keep_group_url(self):
        self.group.line_group_url = 'https://line.me/ti/g/QA-only'; self.group.save()
        first_url = self.uploaded(); self.group.refresh_from_db(); first_name = self.group.line_group_qr.name
        storage = self.group.line_group_qr.storage
        with self.captureOnCommitCallbacks(execute=True):
            second_url = self.uploaded()
        self.assertNotEqual(first_url, second_url)
        self.assertFalse(storage.exists(first_name))
        self.group.refresh_from_db(); second_name = self.group.line_group_qr.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.api.delete(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['line_group_qr_url'], '')
        self.assertFalse(storage.exists(second_name))
        self.group.refresh_from_db()
        self.assertEqual(self.group.line_group_url, 'https://line.me/ti/g/QA-only')

    def test_database_failure_cleans_new_file_and_preserves_previous_qr(self):
        self.uploaded(); self.group.refresh_from_db(); old_name = self.group.line_group_qr.name
        with patch.object(ReservationGroup, 'save', side_effect=RuntimeError('QA database failure')):
            with self.assertRaises(RuntimeError):
                self.api.post(self.url, {'file': self.image()}, format='multipart')
        self.group.refresh_from_db(); self.assertEqual(self.group.line_group_qr.name, old_name)
        self.assertEqual(len([p for p in Path(self.directory.name).rglob('*') if p.is_file()]), 1)

    def test_real_session_upload_requires_csrf_issued_by_order_detail(self):
        browser = BrowserClient(enforce_csrf_checks=True); browser.force_login(self.admin)
        self.assertEqual(browser.post(self.url, {'file': self.image()}).status_code, 403)
        response = browser.get(f'/api/admin/snowland/orders/{self.group.pk}/')
        self.assertEqual(response.status_code, 200)
        token = browser.cookies['csrftoken'].value
        response = browser.post(self.url, {'file': self.image()}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.content)

    def test_order_deletion_cleans_qr_after_commit(self):
        self.uploaded(); self.group.refresh_from_db()
        storage, name = self.group.line_group_qr.storage, self.group.line_group_qr.name
        with self.captureOnCommitCallbacks(execute=True):
            self.group.delete()
        self.assertFalse(storage.exists(name))

    def test_old_file_cleanup_failure_never_deletes_committed_new_picture(self):
        self.uploaded(); self.group.refresh_from_db()
        old_name = self.group.line_group_qr.name; storage = self.group.line_group_qr.storage
        with patch.object(type(storage), 'delete', side_effect=OSError('QA cleanup failure')):
            with self.captureOnCommitCallbacks(execute=True):
                self.uploaded()
        self.group.refresh_from_db()
        self.assertNotEqual(self.group.line_group_qr.name, old_name)
        self.assertTrue(storage.exists(self.group.line_group_qr.name))
