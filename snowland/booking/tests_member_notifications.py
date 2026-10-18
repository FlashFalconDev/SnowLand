from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from unittest.mock import patch
from rest_framework.test import APIClient

from Client.models import Client
from booking.models import NotificationDelivery, Reservation
from booking import tests_participant_notifications as fixtures


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MemberNotificationTests(TestCase):
    url = '/booking/snowland/api/member-notifications/'
    setUp = fixtures.ParticipantNotificationTests.setUp
    template = fixtures.ParticipantNotificationTests.template
    jobs = fixtures.ParticipantNotificationTests.jobs

    def api(self, user):
        client = APIClient(); client.force_authenticate(user)
        return client

    def test_sent_in_app_notification_is_visible_only_to_recipient_and_keeps_original_content(self):
        template = self.template(channel='in_app')
        self.jobs()
        self.assertEqual(NotificationDelivery.objects.filter(template=template, status='sent').count(), 3)
        client = self.api(self.adult)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['unread_count'], 1)
        row = response.data['results'][0]
        self.assertIn(self.group.line_group_url, row['body'])
        self.assertNotIn('ORGANIZER-NAME-ONLY', row['body'])
        self.assertIsNone(row['read_at'])
        self.assertTrue(row['active'])
        template.body = 'CHANGED-TEMPLATE'; template.save(update_fields=['body'])
        self.assertEqual(client.get(self.url).data['results'][0]['body'], row['body'])
        stranger = User.objects.create_user('notice-stranger')
        self.assertEqual(self.api(stranger).get(self.url).data['count'], 0)
        self.assertEqual(APIClient().get(self.url).status_code, 401)

    def test_mark_read_is_owned_idempotent_and_tenant_scoped(self):
        template = self.template(channel='in_app'); self.jobs()
        delivery = NotificationDelivery.objects.get(template=template, recipient=str(self.adult.pk))
        endpoint = f'{self.url}{delivery.pk}/read/'
        client = self.api(self.adult)
        first = client.post(endpoint)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertIsNotNone(first.data['read_at'])
        self.assertEqual(client.post(endpoint).data['read_at'], first.data['read_at'])
        self.assertEqual(client.get(self.url).data['unread_count'], 0)
        self.assertEqual(self.api(self.parent).post(endpoint).status_code, 404)
        Client.objects.create(name='Other', internal_code='other')
        self.assertEqual(client.get('/booking/other/api/member-notifications/').data['count'], 0)
        self.assertEqual(client.post(f'/booking/other/api/member-notifications/{delivery.pk}/read/').status_code, 404)

    def test_cancelled_course_redacts_old_group_link_and_revoked_guardian_loses_notice_access(self):
        template = self.template(channel='in_app'); self.jobs()
        parent = self.api(self.parent)
        row = parent.get(self.url).data['results'][0]
        self.reservation.status = 'cancelled'; self.reservation.save(update_fields=['status'])
        archived = parent.get(self.url).data['results'][0]
        self.assertFalse(archived['active'])
        self.assertEqual(archived['line_group_url'], '')
        self.assertEqual(archived['action_path'], '')
        self.assertNotIn(self.group.line_group_url, archived['body'])
        for child in self.children:
            child.guardian = None; child.user = self.owner
            child.save(update_fields=['guardian', 'user'])
        self.assertEqual(parent.get(self.url).data['count'], 0)
        self.assertEqual(parent.post(f"{self.url}{row['id']}/read/").status_code, 404)

    def test_pagination_counts_only_this_users_sent_in_app_not_email_or_pending(self):
        template = self.template(event='pre_course', channel='in_app')
        for index in range(22):
            NotificationDelivery.objects.create(template=template, group=self.group, recipient=str(self.adult.pk), status='sent',
                scheduled_at=timezone.now(), sent_at=timezone.now(), payload={'in_app_subject': f'QA {index}', 'in_app_body': 'Saved body'})
        NotificationDelivery.objects.create(template=template, group=self.group, recipient=str(self.adult.pk), scheduled_at=timezone.now())
        client = self.api(self.adult)
        from booking.api_views import paid_class_group_url
        with patch('booking.api_views.paid_class_group_url', wraps=paid_class_group_url) as group_url:
            first = client.get(self.url).data
        self.assertEqual(group_url.call_count, 1)
        self.assertEqual(first['count'], 22)
        self.assertEqual(len(first['results']), 20)
        self.assertTrue(first['has_next'])
        second = client.get(self.url+'?page=2').data
        self.assertEqual(len(second['results']), 2)
        self.assertFalse({row['id'] for row in first['results']} & {row['id'] for row in second['results']})
        self.assertEqual(client.get(self.url+'?page=3').status_code, 404)

    def test_legacy_notice_without_snapshot_is_not_reconstructed_from_edited_template(self):
        template = self.template(channel='in_app')
        NotificationDelivery.objects.create(template=template, group=self.group, recipient=str(self.owner.pk), status='sent',
            scheduled_at=timezone.now(), sent_at=timezone.now(), payload={})
        row = self.api(self.owner).get(self.url).data['results'][0]
        self.assertTrue(row['legacy'])
        self.assertNotIn('ORGANIZER-NAME-ONLY', row['body'])
        self.assertIn('未保存', row['body'])

    def test_an_unrelated_deleted_course_in_order_does_not_hide_valid_learners_notice(self):
        self.template(channel='in_app'); self.jobs()
        Reservation.objects.create(group=self.group, status='deleted')
        self.assertEqual(self.api(self.adult).get(self.url).data['count'], 1)

    def test_mark_read_preserves_sent_body_and_does_not_touch_other_recipient(self):
        template = self.template(channel='in_app'); self.jobs()
        delivery = NotificationDelivery.objects.get(template=template, recipient=str(self.adult.pk))
        original = delivery.payload['in_app_body']
        self.api(self.adult).post(f'{self.url}{delivery.pk}/read/')
        delivery.refresh_from_db()
        self.assertEqual(delivery.payload['in_app_body'], original)
        self.assertIsNotNone(delivery.payload['read_at'])
        self.assertEqual(self.api(self.parent).get(self.url).data['unread_count'], 1)

    def test_old_payment_notice_preserves_receipt_but_not_group_link_after_order_cancelled(self):
        self.template(event='payment_confirmed', channel='in_app')
        self.jobs(); self.jobs()
        # Payment-confirmation normally queues through its event, not the reminder sweep.
        from booking.operations import schedule_group_notifications
        schedule_group_notifications(self.group, 'payment_confirmed')
        self.jobs(); self.jobs()
        client = self.api(self.owner)
        self.assertEqual(client.get(self.url).data['count'], 1)
        self.reservation.status = 'cancelled'; self.reservation.save(update_fields=['status'])
        row = client.get(self.url).data['results'][0]
        self.assertTrue(row['active'])  # The payment record remains the organizer's own history.
        self.assertNotIn(self.group.line_group_url, row['body'])
