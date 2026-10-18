from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core import mail
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient
from booking import tests_participant_notifications as fixtures
from booking.class_group_qr import replace_group_qr
from booking.models import NotificationDelivery
from booking.operations import schedule_group_notifications


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GroupQRNotificationTests(TestCase):
    template = fixtures.ParticipantNotificationTests.template
    jobs = fixtures.ParticipantNotificationTests.jobs

    def setUp(self):
        fixtures.ParticipantNotificationTests.setUp(self)
        self.directory = TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        config = override_settings(PRIVATE_COURSE_MEDIA_ROOT=self.directory.name)
        config.enable(); self.addCleanup(config.disable)
        png = BytesIO(); Image.new('RGB', (120, 120), 'white').save(png, format='PNG')
        self.png = png.getvalue()
        self.group = replace_group_qr(self.group, SimpleUploadedFile('qr.png', self.png, content_type='image/png'))

    def test_group_mail_contains_private_inline_qr_without_public_image_url(self):
        self.template(); self.jobs()
        self.assertEqual(len(mail.outbox), 3)
        for message in mail.outbox:
            self.assertEqual(len(message.attachments), 1)
            image = message.attachments[0]
            self.assertEqual(image.get_content_type(), 'image/png')
            self.assertEqual(image.get_payload(decode=True), self.png)
            self.assertIn('cid:', message.alternatives[0][0])
            self.assertIn(f'href="{self.group.line_group_url}"', message.alternatives[0][0])
            self.assertNotIn(self.directory.name, str(message.alternatives))

    def test_qr_only_group_can_notify_and_show_qr_to_member_inbox(self):
        self.group.line_group_url = ''; self.group.save(update_fields=['line_group_url'])
        self.template(); self.jobs()
        self.assertEqual(len(mail.outbox), 3)
        api = APIClient(); api.force_authenticate(self.parent)
        response = api.get('/booking/snowland/api/member-notifications/')
        self.assertEqual(response.data['count'], 1)
        self.assertIn('/class-group-qr/', response.data['results'][0]['line_group_qr_url'])

    def test_legacy_whitespace_url_does_not_create_empty_html_links(self):
        self.group.line_group_url = ' '; self.group.save(update_fields=['line_group_url'])
        self.template(); self.jobs()
        self.assertEqual(len(mail.outbox), 3)
        self.assertNotIn('<a href="">', mail.outbox[0].alternatives[0][0])

    def test_mime_is_related_and_template_html_is_escaped(self):
        template = self.template()
        template.body = '<script>QA only</script>\n{customer_name}'; template.save()
        self.jobs()
        for message in mail.outbox:
            mime = message.message()
            self.assertEqual(mime.get_content_type(), 'multipart/related')
            html = message.alternatives[0][0]
            self.assertNotIn('<script>', html)
            self.assertIn('&lt;script&gt;', html)
            image = message.attachments[0]
            self.assertIn('cid:'+image['Content-ID'].strip('<>'), html)
            self.assertNotIn('/api/class-group-qr/', html)

    def test_jpeg_and_webp_uploads_keep_correct_inline_mime_types(self):
        self.template()
        for image_format, subtype in [('JPEG', 'jpeg'), ('WEBP', 'webp')]:
            with self.subTest(image_format=image_format):
                NotificationDelivery.objects.all().delete(); mail.outbox.clear()
                image = BytesIO(); Image.new('RGB', (120, 120), 'white').save(image, format=image_format)
                self.group = replace_group_qr(self.group, SimpleUploadedFile('qr', image.getvalue()))
                self.jobs()
                self.assertEqual(len(mail.outbox), 3)
                for message in mail.outbox:
                    self.assertEqual(message.attachments[0].get_content_type(), 'image/'+subtype)
                    self.assertEqual(message.attachments[0].get_payload(decode=True), image.getvalue())

    def test_repeated_jobs_send_once_and_parent_with_two_children_has_one_copy(self):
        template = self.template(); self.jobs(); self.jobs()
        self.assertEqual(len(mail.outbox), 3)
        copies = template.deliveries.filter(payload__has_key='in_app_mirror_of')
        self.assertEqual(copies.count(), 3)
        self.assertEqual(copies.filter(recipient=str(self.parent.pk)).count(), 1)
        self.assertEqual(set(row.payload['in_app_group_qr_name'] for row in copies), {self.group.line_group_qr.name})

    def test_scheduled_group_mail_uses_latest_qr_at_dispatch(self):
        template = self.template(); scheduled = schedule_group_notifications(self.group, 'line_group')
        self.assertEqual(len(scheduled), 3)
        png = BytesIO(); Image.new('RGB', (120, 120), 'black').save(png, format='PNG')
        replacement = png.getvalue()
        self.group = replace_group_qr(self.group, SimpleUploadedFile('new.png', replacement))
        self.jobs()
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual({message.attachments[0].get_payload(decode=True) for message in mail.outbox}, {replacement})

    def test_inbox_hides_changed_removed_or_cancelled_qr_without_sending_again(self):
        self.template(); self.jobs()
        api = APIClient(); api.force_authenticate(self.owner)
        endpoint = '/booking/snowland/api/member-notifications/'
        old = api.get(endpoint).data['results'][0]
        self.assertTrue(old['line_group_qr_url'])
        self.group = replace_group_qr(self.group, SimpleUploadedFile('new.png', self.png))
        self.assertEqual(api.get(endpoint).data['results'][0]['line_group_qr_url'], '')
        self.jobs(); self.assertEqual(len(mail.outbox), 3)
        self.group = replace_group_qr(self.group)
        self.assertEqual(api.get(endpoint).data['results'][0]['line_group_qr_url'], '')
        self.reservation.status = 'cancelled'; self.reservation.save()
        archived = api.get(endpoint).data['results'][0]
        self.assertFalse(archived['active']); self.assertEqual(archived['line_group_qr_url'], '')

    def test_missing_or_corrupt_file_fails_without_transport_or_inbox_copy(self):
        self.template()
        with self.group.line_group_qr.open('wb') as stream:
            stream.write(b'corrupt QA image')
        self.jobs()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(NotificationDelivery.objects.filter(status='failed').count(), 3)
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 0)
        NotificationDelivery.objects.all().delete()
        self.group.line_group_qr.storage.delete(self.group.line_group_qr.name)
        self.jobs()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(NotificationDelivery.objects.filter(status='failed').count(), 3)
        for row in NotificationDelivery.objects.all():
            self.assertNotIn(self.directory.name, row.error_message)

    def test_failed_mail_transport_does_not_create_successful_qr_inbox(self):
        self.template()
        with patch('booking.group_qr_notifications.EmailMultiAlternatives.send', side_effect=RuntimeError('QA send failed')):
            self.jobs()
        self.assertEqual(NotificationDelivery.objects.filter(status='failed').count(), 3)
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 0)

    def test_dry_run_or_refunded_order_does_not_send_qr(self):
        self.template(); self.jobs(dry_run=True)
        self.assertEqual(NotificationDelivery.objects.count(), 0)
        self.payment.status = 'refunded'; self.payment.save()
        self.jobs(); self.assertEqual(len(mail.outbox), 0)

    def test_direct_in_app_qr_notice_uses_protected_member_url(self):
        self.template(channel='in_app'); self.jobs()
        self.assertEqual(len(mail.outbox), 0)
        api = APIClient(); api.force_authenticate(self.parent)
        row = api.get('/booking/snowland/api/member-notifications/').data['results'][0]
        self.assertIn('/class-group-qr/', row['line_group_qr_url'])
        self.assertNotIn('信中附圖', row['body'])

    def test_removing_url_keeps_qr_only_group_notice_scheduled(self):
        self.template(); schedule_group_notifications(self.group, 'line_group')
        admin = User.objects.create_superuser('qr-notice-admin', 'qr-admin@example.test', 'test')
        api = APIClient(); api.force_authenticate(admin)
        response = api.post(f'/api/admin/snowland/orders/{self.group.pk}/class-group-link/', {'line_group_url': ''}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(NotificationDelivery.objects.filter(status='scheduled').count(), 3)
        self.assertEqual(NotificationDelivery.objects.filter(status='cancelled').count(), 0)

    def test_removing_only_qr_cancels_unusable_pending_group_notices(self):
        self.group.line_group_url = ''; self.group.save(update_fields=['line_group_url'])
        self.template(); schedule_group_notifications(self.group, 'line_group')
        admin = User.objects.create_superuser('qr-notice-admin', 'qr-admin@example.test', 'test')
        api = APIClient(); api.force_authenticate(admin)
        response = api.delete(f'/api/admin/snowland/orders/{self.group.pk}/class-group-qr/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(NotificationDelivery.objects.filter(status='scheduled').count(), 0)
        self.assertEqual(NotificationDelivery.objects.filter(status='cancelled').count(), 3)
