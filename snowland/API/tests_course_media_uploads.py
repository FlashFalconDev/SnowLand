from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from API import tests_coach_evaluations
from Resorts.models import Campus


class CourseMediaUploadTests(tests_coach_evaluations.CoachEvaluationTests):
    def setUp(self):
        super().setUp()
        self.media_dir = TemporaryDirectory(prefix='snowland-private-media-test-')
        self.addCleanup(self.media_dir.cleanup)
        override = override_settings(PRIVATE_COURSE_MEDIA_ROOT=self.media_dir.name)
        override.enable()
        self.addCleanup(override.disable)

    def photo(self):
        output = BytesIO()
        Image.new('RGB', (2, 2), 'blue').save(output, format='PNG')
        return SimpleUploadedFile('QA-photo.png', output.getvalue(), content_type='image/png')

    def upload(self, evaluation=None, file=None):
        return self.api.patch(f'{self.url}{(evaluation or self.own).id}/upload/',
                              {'file': file or self.photo()}, format='multipart')

    def test_upload_photo_is_private_and_owner_can_read_but_stranger_cannot(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 201, uploaded.data)
        media = self.own.media.get()
        self.assertFalse(media.is_public)
        self.assertTrue(media.file.name)
        url = uploaded.data['data']['url']
        owner = APIClient(); owner.force_authenticate(self.member)
        response = owner.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('image/png'))
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
        response.close()
        anonymous = APIClient()
        self.assertEqual(anonymous.get(url).status_code, 401)
        anonymous.force_authenticate(User.objects.create_user('media-stranger'))
        self.assertEqual(anonymous.get(url).status_code, 404)
        rows = owner.get('/booking/snowland/api/member-center/').data['learning_records']
        self.assertEqual(next(row for row in rows if row['id'] == self.own.id)['media'][0]['url'], url)

    def test_upload_cannot_access_other_coach_or_allow_invalid_or_oversized_files(self):
        self.assertEqual(self.upload(self.foreign).status_code, 404)
        bad = SimpleUploadedFile('fake.jpg', b'<html>not a photo</html>', content_type='image/jpeg')
        self.assertEqual(self.upload(file=bad).status_code, 400)
        with override_settings(COURSE_MEDIA_MAX_PHOTO_BYTES=10):
            self.assertEqual(self.upload().status_code, 400)
        self.assertFalse(self.own.media.exists())
        self.assertFalse([path for path in Path(self.media_dir.name).rglob('*') if path.is_file()])

    def test_order_owner_cannot_read_another_members_private_forms_evaluation_or_attachment(self):
        url = self.upload().data['data']['url']
        participant = User.objects.create_user('independently-bound-participant')
        learner = self.own.member
        learner.user = participant
        learner.insurance_data = {'full_name': 'Private learner', 'id_number': 'PRIVATE-ID'}
        learner.save(update_fields=['user', 'insurance_data'])
        organizer = APIClient()
        organizer.force_authenticate(self.member)
        center_url = '/booking/snowland/api/member-center/'
        center = organizer.get(center_url)
        self.assertEqual(center.status_code, 200)
        self.assertIn(self.own.booking.reservation.group_id, [order['id'] for order in center.data['orders']])
        self.assertNotIn(learner.pk, [form['id'] for form in center.data['pre_course_forms']])
        self.assertNotIn(self.own.pk, [record['id'] for record in center.data['learning_records']])
        self.assertEqual(organizer.post(center_url, {
            'action': 'update_pre_course_form', 'member_id': learner.pk,
            'age_range': '25-35y', 'insurance_data': {'full_name': 'Overwrite'},
        }, format='json').status_code, 404)
        self.assertEqual(organizer.post(center_url, {
            'action': 'submit_satisfaction', 'evaluation_id': self.own.pk, 'rating': 5,
        }, format='json').status_code, 404)
        response = organizer.get(url)
        response.close()
        self.assertEqual(response.status_code, 404)
        learner.refresh_from_db()
        self.assertEqual(learner.insurance_data['id_number'], 'PRIVATE-ID')

        own_client = APIClient()
        own_client.force_authenticate(participant)
        response = own_client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        own_center = own_client.get(center_url).data
        self.assertIn(learner.pk, [form['id'] for form in own_center['pre_course_forms']])
        self.assertIn(self.own.pk, [record['id'] for record in own_center['learning_records']])

    def test_only_current_guardian_can_read_private_attachment(self):
        url = self.upload().data['data']['url']
        guardian = User.objects.create_user('attachment-guardian')
        former_guardian = User.objects.create_user('former-attachment-guardian')
        learner = self.own.member
        learner.guardian = guardian
        learner.save(update_fields=['guardian'])
        client = APIClient()
        client.force_authenticate(guardian)
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        client.force_authenticate(former_guardian)
        self.assertEqual(client.get(url).status_code, 404)
        learner.guardian = former_guardian
        learner.save(update_fields=['guardian'])
        client.force_authenticate(guardian)
        self.assertEqual(client.get(url).status_code, 404)

    def test_video_range_request_and_invalid_range(self):
        # Container-signature fixture: this tests byte streaming, not playback.
        content = b'\x00\x00\x00\x18ftypisom' + b'\x00' * 100
        uploaded = self.upload(file=SimpleUploadedFile('QA-video.mp4', content, content_type='video/mp4'))
        self.assertEqual(uploaded.status_code, 201, uploaded.data)
        url = uploaded.data['data']['url']
        response = self.api.get(url, HTTP_RANGE='bytes=4-11')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response['Content-Range'], f'bytes 4-11/{len(content)}')
        self.assertEqual(b''.join(response.streaming_content), content[4:12])
        response.close()
        self.assertEqual(self.api.get(url, HTTP_RANGE='bytes=900-999').status_code, 416)

    def test_delete_evaluation_removes_private_attachment_after_commit(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 201, uploaded.data)
        path = Path(self.own.media.get().file.path)
        self.assertTrue(path.is_file())
        with self.captureOnCommitCallbacks(execute=True):
            self.own.delete()
        self.assertFalse(path.exists())

    def test_manager_download_respects_campus_and_superuser_selected_scope(self):
        url = self.upload().data['data']['url']
        other_campus = Campus.objects.create(client=self.tenant, name='Other', code='other')
        manager = User.objects.create_user('media-campus-manager')
        profile = manager.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = ['evaluations']
        profile.save()
        profile.campuses.add(other_campus)
        client = APIClient(); client.force_authenticate(manager)
        self.assertEqual(client.get(url).status_code, 404)
        profile.campuses.add(self.campus)
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        client.force_authenticate(User.objects.create_superuser('media-hq', password='pw'))
        self.assertEqual(client.get(url, HTTP_X_CAMPUS_ID=str(other_campus.pk)).status_code, 404)

    def test_storage_or_database_failure_leaves_no_attachment_or_orphan_file(self):
        with patch('booking.media_files.PrivateCourseMediaStorage.save', side_effect=OSError('QA storage offline')):
            response = self.upload()
        self.assertEqual(response.status_code, 503, response.data)
        from booking.media_files import save_course_upload
        with patch('booking.models.CourseMedia.save', side_effect=RuntimeError('QA database offline')):
            with self.assertRaises(RuntimeError):
                save_course_upload(self.own, self.coach_user, self.photo())
        self.assertFalse(self.own.media.exists())
        self.assertFalse([path for path in Path(self.media_dir.name).rglob('*') if path.is_file()])

    def test_rollback_does_not_remove_file_and_upload_limits_follow_settings(self):
        with override_settings(COURSE_MEDIA_MAX_PHOTO_BYTES=12345):
            limits = self.api.get(f'{self.url}{self.own.pk}/upload/')
        self.assertEqual(limits.status_code, 200, limits.data)
        self.assertEqual(limits.data['data']['photo_limit_bytes'], 12345)
        self.assertEqual(self.api.get(f'{self.url}{self.foreign.pk}/upload/').status_code, 404)
        self.assertEqual(self.upload().status_code, 201)
        path = Path(self.own.media.get().file.path)
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.own.delete()
                    raise RuntimeError('QA rollback')
            except RuntimeError:
                pass
        self.assertTrue(path.is_file())
