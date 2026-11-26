from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from botocore.exceptions import ClientError
from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Coach.models import Coach
from Control.models import TenantStaffMembership
from Resorts.models import Campus
from booking.models import Booking, CourseAlbumAsset, MemberDetail, Payment, Reservation, ReservationGroup


class CourseAlbumManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = Client.objects.create(name='Album School', internal_code='album-school')
        cls.other_school = Client.objects.create(name='Other School', internal_code='other-school')
        cls.campus = Campus.objects.create(client=cls.school, name='Album Campus', code='album')
        cls.other_campus = Campus.objects.create(client=cls.school, name='Other Campus', code='other')
        cls.coach, cls.replacement = [cls.make_coach(name) for name in ('album-coach', 'album-replacement')]
        cls.manager = cls.make_manager('album-manager', cls.school, 'hq_admin')
        cls.assistant = cls.make_manager('album-assistant', cls.school, 'assistant')
        cls.foreign_manager = cls.make_manager('foreign-manager', cls.other_school, 'hq_admin')
        cls.campus_manager = cls.make_manager('campus-manager', cls.school, 'campus_manager')
        cls.campus_manager.tenant_staff_memberships.get().campuses.add(cls.other_campus)
        cls.owner = User.objects.create_user('album-member')
        group = ReservationGroup.objects.create(client=cls.school, campus=cls.campus, user=cls.owner)
        reservation = Reservation.objects.create(group=group, preferred_coach=cls.coach, status='completed')
        cls.booking = Booking.objects.create(
            reservation=reservation, date=timezone.localdate() - timedelta(days=1),
            start_time='09:00', end_time='12:00',
        )
        cls.member = MemberDetail.objects.create(reservation=reservation, user=cls.owner)
        Payment.objects.create(reservation_group=group, status='pending', payment_method='TT')
        cls.coach_url = f'/api/admin/album-school/coach/course-albums/{cls.booking.pk}/'
        cls.manager_url = f'/api/admin/album-school/course-albums/{cls.booking.pk}/'
        cls.member_url = '/booking/album-school/api/course-albums/'

    @classmethod
    def make_coach(cls, name):
        user = User.objects.create_user(name)
        TenantStaffMembership.objects.create(user=user, client=cls.school, is_coach=True)
        return Coach.objects.create(user=user, client=cls.school, name=name)

    @staticmethod
    def make_manager(name, client, role):
        user = User.objects.create_user(name)
        TenantStaffMembership.objects.create(user=user, client=client, is_manager=True, role=role)
        return user

    def setUp(self):
        self.enterContext(override_settings(PRIVATE_COURSE_MEDIA_ROOT=self.enterContext(TemporaryDirectory())))
        self.api = APIClient()
        self.api.force_authenticate(self.coach.user)
        content = BytesIO()
        Image.new('RGB', (4, 4)).save(content, format='PNG')
        self.png = content.getvalue()

    def post_file(self, name='photo.png', data=None, content_type='image/png'):
        return self.api.post(self.coach_url, {
            'file': SimpleUploadedFile(name, self.png if data is None else data, content_type=content_type),
        }, format='multipart')

    def upload_photo(self):
        result = self.post_file()
        self.assertEqual(result.status_code, 201, result.data)
        return result.data['data']

    def delete_asset(self, route, asset_id):
        return self.api.delete(f'{route}?asset_id={asset_id}')

    def test_current_uploader_deletes_file_and_tags_and_repeats_safely(self):
        uploaded = self.upload_photo()
        asset = CourseAlbumAsset.objects.get(pk=uploaded['id'])
        name, storage = asset.file.name, asset.file.storage
        self.assertTrue(storage.exists(name))
        self.assertTrue(self.api.get(self.coach_url).data['data']['assets'][0]['can_delete'])
        tag = {'asset_id': asset.pk, 'member_id': self.member.pk, 'tagged': True}
        self.assertEqual(self.api.patch(self.coach_url, tag, format='json').status_code, 200)

        self.api.force_authenticate(self.owner)
        self.assertEqual(self.api.get(self.member_url).data['albums'][0]['assets'][0]['tagged_member_ids'], [self.member.pk])
        preview = self.api.get(uploaded['url'])
        self.assertEqual(preview.status_code, 200)
        preview.close()
        self.assertEqual(self.delete_asset(self.coach_url, asset.pk).status_code, 403)

        self.api.force_authenticate(self.coach.user)
        self.assertEqual(self.delete_asset(self.coach_url, asset.pk).status_code, 204)
        self.assertEqual(self.delete_asset(self.coach_url, asset.pk).status_code, 204)
        self.assertEqual(self.api.get(self.coach_url).data['data']['assets'], [])
        self.assertEqual(self.api.patch(self.coach_url, tag, format='json').status_code, 404)
        self.assertFalse(storage.exists(name))
        self.assertFalse(self.member.tagged_course_assets.exists())
        audit = LogEntry.objects.get(object_id=str(asset.pk), action_flag=DELETION)
        self.assertEqual(audit.user, self.coach.user)
        self.assertIn(f'堂次 {self.booking.pk}', audit.change_message)

        self.api.force_authenticate(self.owner)
        self.assertEqual(self.api.get(self.member_url).data['albums'], [])
        self.assertEqual(self.api.get(uploaded['url']).status_code, 404)
        self.assertEqual(self.api.patch(self.member_url, tag, format='json').status_code, 404)

    def test_reassigned_upload_cannot_be_deleted_by_either_coach(self):
        asset_id = self.upload_photo()['id']
        Reservation.objects.filter(pk=self.booking.reservation_id).update(preferred_coach=self.replacement)
        self.assertEqual(self.delete_asset(self.coach_url, asset_id).status_code, 404)
        self.api.force_authenticate(self.replacement.user)
        self.assertFalse(self.api.get(self.coach_url).data['data']['assets'][0]['can_delete'])
        self.assertEqual(self.delete_asset(self.coach_url, asset_id).status_code, 403)
        self.assertTrue(CourseAlbumAsset.objects.filter(pk=asset_id).exists())

    def test_manager_with_evaluation_scope_can_preview_and_delete_any_asset(self):
        uploaded = self.upload_photo()
        Reservation.objects.filter(pk=self.booking.reservation_id).update(preferred_coach=None)
        self.api.force_authenticate(self.manager)
        response = self.api.get(self.manager_url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['data']['assets'][0]['can_delete'])
        preview = self.api.get(uploaded['url'])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(b''.join(preview.streaming_content), self.png)
        self.assertEqual(self.api.post(self.manager_url, {}, format='json').status_code, 405)
        self.assertEqual(self.delete_asset(self.manager_url, uploaded['id']).status_code, 204)
        self.assertEqual(self.delete_asset(self.manager_url, uploaded['id']).status_code, 204)
        self.assertEqual(LogEntry.objects.get(object_id=str(uploaded['id']), action_flag=DELETION).user, self.manager)

    def test_delete_blocks_other_tenants_campuses_and_readonly_staff(self):
        asset_id = self.upload_photo()['id']
        self.api.force_authenticate(self.foreign_manager)
        self.assertEqual(self.delete_asset(self.manager_url, asset_id).status_code, 403)
        foreign_url = self.manager_url.replace('/album-school/', '/other-school/')
        self.assertEqual(self.delete_asset(foreign_url, asset_id).status_code, 404)

        self.api.force_authenticate(self.campus_manager)
        self.assertEqual(self.delete_asset(self.manager_url, asset_id).status_code, 404)
        self.api.force_authenticate(self.assistant)
        self.assertFalse(self.api.get(self.manager_url).data['data']['assets'][0]['can_delete'])
        self.assertEqual(self.delete_asset(self.manager_url, asset_id).status_code, 403)

        self.api.force_authenticate(self.manager)
        other_booking = Booking.objects.create(
            reservation=self.booking.reservation, date=self.booking.date, start_time='13:00', end_time='15:00',
        )
        wrong_booking = self.manager_url.replace(f'/{self.booking.pk}/', f'/{other_booking.pk}/')
        self.assertEqual(self.delete_asset(wrong_booking, asset_id).status_code, 404)
        self.assertTrue(CourseAlbumAsset.objects.filter(pk=asset_id).exists())

    def test_coach_delete_can_be_disabled_for_a_tenant(self):
        asset_id = self.upload_photo()['id']
        module = ModuleInfo.objects.create(module_sid='booking', module_name='Booking')
        ModuleSetting.objects.create(
            client=self.school, module=module, settings={'course_album_coach_delete_enabled': False},
        )
        self.assertFalse(self.api.get(self.coach_url).data['data']['assets'][0]['can_delete'])
        self.assertEqual(self.delete_asset(self.coach_url, asset_id).status_code, 403)
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.delete_asset(self.manager_url, asset_id).status_code, 204)

    def test_storage_failure_preserves_asset_and_tags_for_retry(self):
        asset = CourseAlbumAsset.objects.get(pk=self.upload_photo()['id'])
        asset.tagged_members.add(self.member)
        with patch.object(asset.file.storage, 'delete', side_effect=ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}}, 'DeleteObject',
        )), self.assertLogs('API.learning_views', level='ERROR') as log:
            response = self.delete_asset(self.coach_url, asset.pk)
        self.assertEqual(response.status_code, 503, response.data)
        self.assertIn('重試', response.data['msg'])
        self.assertIn(f'asset={asset.pk}', log.output[0])
        self.assertTrue(self.member.tagged_course_assets.filter(pk=asset.pk).exists())
        self.assertTrue(asset.file.storage.exists(asset.file.name))
        self.assertFalse(LogEntry.objects.filter(object_id=str(asset.pk), action_flag=DELETION).exists())
        self.assertEqual(self.delete_asset(self.coach_url, asset.pk).status_code, 204)

    def test_heic_heif_extension_mime_and_disguised_content_get_named_help(self):
        heic_header = b'\x00\x00\x00\x14ftypisom\x00\x00\x00\x00heic'
        for name, content_type, data in (
            ('camera.HEIC', 'application/octet-stream', self.png),
            ('camera.heif', 'image/png', b''),
            ('camera.jpg', 'image/heic', self.png),
            ('camera.png', 'image/heif', self.png),
            ('disguised.mp4', 'video/mp4', heic_header),
        ):
            with self.subTest(name=name, mime=content_type):
                result = self.post_file(name, data, content_type)
                self.assertEqual(result.status_code, 400, result.data)
                self.assertIn(name, result.data['msg'])
                self.assertIn('HEIC 格式暫不支援', result.data['msg'])
                self.assertIn('最相容', result.data['msg'])
                self.assertIn('JPG', result.data['msg'])
        self.assertFalse(CourseAlbumAsset.objects.exists())

    def test_unsupported_or_disguised_files_get_named_format_errors(self):
        for name, content_type, data in (
            ('fake.jpg', 'image/jpeg', b'plain text'),
            ('fake.mp4', 'video/mp4', b'\x00\x00\x00\x10ftypjunk\x00\x00\x00\x00'),
            ('fake.webm', 'video/webm', b'\x1aE\xdf\xa3\x8b\x42\x82\x88matroska'),
        ):
            with self.subTest(name=name):
                result = self.post_file(name, data, content_type)
                self.assertEqual(result.status_code, 400, result.data)
                self.assertIn(name, result.data['msg'])
                self.assertIn('JPEG、PNG、WebP', result.data['msg'])
        self.assertFalse(CourseAlbumAsset.objects.exists())

    def test_video_types_and_size_limits_apply_to_each_file(self):
        for name, mime, header in (
            ('movie.mp4', 'video/mp4', b'\x00\x00\x00\x10ftypisom\x00\x00\x00\x00'),
            ('movie.mov', 'video/quicktime', b'\x00\x00\x00\x10ftypqt  \x00\x00\x00\x00'),
            ('movie.webm', 'video/webm', b'\x1aE\xdf\xa3\x87\x42\x82\x84webm'),
        ):
            with self.subTest(name=name):
                with override_settings(COURSE_MEDIA_MAX_VIDEO_BYTES=len(header)):
                    result = self.post_file(name, header, mime)
                    self.assertEqual(result.status_code, 201, result.data)
                    self.assertEqual(result.data['data']['type'], 'video')
                    preview = self.api.get(result.data['data']['url'])
                    self.assertEqual(preview['Content-Type'], mime)
                    preview.close()
                    oversized = self.post_file(name, header + b'0', mime)
                    self.assertEqual(oversized.status_code, 400, oversized.data)
                    self.assertIn(f'「{name}」：影片不可超過', oversized.data['msg'])
        with override_settings(COURSE_MEDIA_MAX_PHOTO_BYTES=len(self.png) - 1):
            result = self.post_file()
        self.assertEqual(result.status_code, 400, result.data)
        self.assertIn('「photo.png」：照片不可超過', result.data['msg'])
        self.assertEqual(CourseAlbumAsset.objects.count(), 3)
