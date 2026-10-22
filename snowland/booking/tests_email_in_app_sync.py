from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from booking import tests_participant_notifications as fixtures
from booking.management.commands.process_snowland_jobs import Command
from booking.models import NotificationDelivery
from booking.operations import schedule_group_notifications


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailInAppSyncTests(TestCase):
    setUp = fixtures.ParticipantNotificationTests.setUp
    template = fixtures.ParticipantNotificationTests.template
    jobs = fixtures.ParticipantNotificationTests.jobs
    complete = fixtures.ParticipantNotificationTests.complete
    url = '/booking/snowland/api/member-notifications/'

    def api(self, user):
        api = APIClient(); api.force_authenticate(user)
        return api

    def test_email_success_syncs_once_to_owner_adult_parent_with_own_read_state(self):
        template = self.template()
        self.jobs(); self.jobs()
        self.assertEqual(len(mail.outbox), 3)
        mirrors = template.deliveries.filter(payload__has_key='in_app_mirror_of')
        self.assertEqual(mirrors.count(), 3)
        self.assertEqual(set(mirrors.values_list('recipient', flat=True)), {str(user.pk) for user in [self.owner, self.adult, self.parent]})
        parent = self.api(self.parent)
        response = parent.get(self.url)
        self.assertEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertTrue(row['active'])
        self.assertNotIn('ORGANIZER-NAME-ONLY', row['body'])
        self.assertEqual(parent.post(f"{self.url}{row['id']}/read/").status_code, 200)
        self.assertEqual(parent.get(self.url).data['unread_count'], 0)
        self.assertEqual(self.api(self.adult).get(self.url).data['unread_count'], 1)
        self.assertEqual(self.api(self.owner).post(f"{self.url}{row['id']}/read/").status_code, 404)

    def test_unrelated_same_email_account_never_receives_or_claims_notice(self):
        stranger = User.objects.create_user('qa-same-email-stranger', self.adult.email)
        self.template(); self.jobs()
        self.assertEqual(self.api(stranger).get(self.url).data['count'], 0)
        self.assertFalse(NotificationDelivery.objects.filter(recipient=str(stranger.pk)).exists())

    def test_related_shared_email_deduplicates_mail_but_keeps_individual_safe_inboxes(self):
        self.adult.email = self.owner.email; self.adult.save(update_fields=['email'])
        self.template(); self.jobs()
        self.assertEqual(len(mail.outbox), 2)
        owner = self.api(self.owner).get(self.url).data['results'][0]
        adult = self.api(self.adult).get(self.url).data['results'][0]
        self.assertIn('ORGANIZER-NAME-ONLY', owner['body'])
        self.assertNotIn('ORGANIZER-NAME-ONLY', adult['body'])
        self.assertNotEqual(owner['id'], adult['id'])

    def test_admin_queue_identifies_synced_delivery_as_in_app_not_another_email(self):
        from API.admin_serializers import NotificationDeliveryAdminSerializer
        template = self.template(); self.jobs()
        source = template.deliveries.get(recipient=self.adult.email)
        mirror = template.deliveries.get(recipient=str(self.adult.pk))
        self.assertEqual(NotificationDeliveryAdminSerializer(source).data['channel'], 'email')
        result = NotificationDeliveryAdminSerializer(mirror).data
        self.assertEqual(result['channel'], 'in_app')
        self.assertTrue(result['email_synced'])

    def test_missing_documents_only_syncs_to_responsible_parent(self):
        self.complete(self.member)
        self.template(event='missing_documents'); self.jobs()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.api(self.parent).get(self.url).data['count'], 1)
        self.assertEqual(self.api(self.adult).get(self.url).data['count'], 0)
        self.assertEqual(self.api(self.owner).get(self.url).data['count'], 0)

    def test_order_contact_can_differ_from_owner_account_but_financial_notice_stays_owner_only(self):
        self.payment.DataJSON = {'contact': {'email': 'qa-contact@example.test'}}
        self.payment.save(update_fields=['DataJSON'])
        template = self.template(event='payment_confirmed')
        schedule_group_notifications(self.group, 'payment_confirmed'); self.jobs()
        self.assertEqual(mail.outbox[0].to, ['qa-contact@example.test'])
        self.assertEqual(self.api(self.owner).get(self.url).data['count'], 1)
        self.assertEqual(self.api(self.parent).get(self.url).data['count'], 0)
        self.assertEqual(template.deliveries.filter(payload__has_key='in_app_mirror_of').count(), 1)

    def test_failed_transport_and_dry_run_do_not_publish_successful_in_app_copy(self):
        template = self.template()
        self.jobs(dry_run=True)
        self.assertFalse(template.deliveries.exists())
        with patch('booking.management.commands.process_snowland_jobs.send_mail', return_value=0):
            self.jobs()
        self.assertFalse(template.deliveries.filter(payload__has_key='in_app_mirror_of').exists())
        self.assertEqual(template.deliveries.filter(status='failed').count(), 3)

    def test_original_snapshot_and_read_flag_survive_template_change_and_resync(self):
        template = self.template(); self.jobs()
        source = template.deliveries.get(recipient=self.adult.email)
        client = self.api(self.adult)
        row = client.get(self.url).data['results'][0]
        client.post(f"{self.url}{row['id']}/read/")
        template.body = 'QA changed'; template.channel = 'line'; template.save()
        Command._sync_email_in_app(source, 'QA changed', 'QA changed', timezone.now())
        result = client.get(self.url)
        self.assertEqual(result.data['count'], 1)
        self.assertEqual(result.data['results'][0]['body'], row['body'])
        self.assertEqual(result.data['unread_count'], 0)

    def test_guardian_revocation_and_cancelled_course_apply_to_synced_history(self):
        self.template(); self.jobs()
        parent = self.api(self.parent)
        row = parent.get(self.url).data['results'][0]
        self.reservation.status = 'cancelled'; self.reservation.save(update_fields=['status'])
        cancelled = parent.get(self.url).data['results'][0]
        self.assertFalse(cancelled['active'])
        self.assertNotIn(self.group.line_group_url, cancelled['body'])
        for child in self.children:
            child.guardian = None; child.save(update_fields=['guardian'])
        self.assertEqual(parent.get(self.url).data['count'], 0)
        self.assertEqual(parent.post(f"{self.url}{row['id']}/read/").status_code, 404)
