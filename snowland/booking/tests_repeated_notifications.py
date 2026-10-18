from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from API.admin_serializers import NotificationTemplateAdminSerializer
from booking import tests_participant_notifications as fixtures
from booking.models import NotificationDelivery
from booking.operations import schedule_group_notifications


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RepeatedNotificationTests(TestCase):
    setUp = fixtures.ParticipantNotificationTests.setUp
    template = fixtures.ParticipantNotificationTests.template
    jobs = fixtures.ParticipantNotificationTests.jobs
    complete = fixtures.ParticipantNotificationTests.complete

    def first_reminders(self, interval=2):
        template = self.template('missing_documents')
        template.days_before = 0
        template.repeat_interval_days = interval
        template.save()
        self.jobs()
        self.assertEqual(template.deliveries.filter(status='sent').count(), 4)
        self.assertEqual(template.deliveries.filter(payload__has_key='in_app_mirror_of').count(), 2)
        return template

    def age_notices(self, template, days):
        template.deliveries.filter(status='sent').update(sent_at=timezone.now()-timedelta(days=days))

    def test_default_does_not_repeat_old_templates(self):
        template = self.first_reminders(0)
        self.age_notices(template, 10)
        self.jobs()
        self.assertEqual(template.deliveries.count(), 4)
        self.assertEqual(len(mail.outbox), 2)

    def test_interval_due_only_once_per_responsible_account(self):
        template = self.first_reminders()
        self.age_notices(template, 1)
        self.jobs()
        self.assertEqual(template.deliveries.count(), 4)
        self.age_notices(template, 2)
        self.jobs(); self.jobs()
        self.assertEqual(template.deliveries.count(), 8)
        self.assertEqual(template.deliveries.filter(status='sent').count(), 8)
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual({notice.recipient for notice in template.deliveries.all()}, {self.adult.email, self.parent.email, str(self.adult.pk), str(self.parent.pk)})

    def test_complete_documents_or_disable_repetition_cancels_queued_repeat(self):
        template = self.first_reminders()
        self.age_notices(template, 2)
        pending = schedule_group_notifications(self.group, 'missing_documents')
        self.assertEqual(len(pending), 2)
        self.complete(self.member)
        template.repeat_interval_days = 0
        template.save()
        self.jobs()
        self.assertEqual(template.deliveries.filter(status='cancelled').count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_missed_intervals_do_not_catch_up_with_many_messages(self):
        template = self.first_reminders()
        self.age_notices(template, 20)
        self.jobs(); self.jobs(); self.jobs()
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual(template.deliveries.count(), 8)

    def test_dry_run_does_not_create_due_repeats(self):
        template = self.first_reminders()
        self.age_notices(template, 2)
        self.jobs(dry_run=True)
        self.assertEqual(template.deliveries.count(), 4)
        self.assertEqual(len(mail.outbox), 2)

    def test_cancelled_course_stops_repeat(self):
        template = self.first_reminders()
        self.age_notices(template, 2)
        self.reservation.status = 'cancelled'
        self.reservation.save(update_fields=['status'])
        self.jobs()
        self.assertEqual(template.deliveries.count(), 4)

    def test_increasing_interval_postpones_already_queued_repeat(self):
        template = self.first_reminders()
        self.age_notices(template, 2)
        pending = schedule_group_notifications(self.group, 'missing_documents')
        self.assertEqual(len(pending), 2)
        template.repeat_interval_days = 7
        template.save()
        self.jobs()
        self.assertEqual(len(mail.outbox), 2)
        for notice in pending:
            notice.refresh_from_db()
            self.assertEqual(notice.status, 'scheduled')
            self.assertGreater(notice.scheduled_at, timezone.now()+timedelta(days=4))

    def test_completing_only_adults_documents_keeps_parent_reminder(self):
        template = self.first_reminders()
        self.age_notices(template, 2)
        self.complete(self.member)
        self.jobs()
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(mail.outbox[-1].to, [self.parent.email])

    def test_refund_stops_repeat_and_past_course_is_not_reminded(self):
        template = self.first_reminders()
        self.age_notices(template, 2)
        self.payment.status = 'refunded'
        self.payment.save(update_fields=['status'])
        self.jobs()
        self.assertEqual(template.deliveries.count(), 4)
        self.payment.status = 'paid'; self.payment.save(update_fields=['status'])
        self.booking.date = timezone.localdate()-timedelta(days=1)
        self.booking.save(update_fields=['date'])
        self.jobs()
        self.assertEqual(template.deliveries.count(), 4)

    def test_repeat_interval_serializer_bounds_and_event_restriction(self):
        base = {'name': 'QA repeat', 'event': 'missing_documents', 'channel': 'in_app', 'body': 'QA', 'repeat_interval_days': 2}
        context = {'request': SimpleNamespace(tenant=self.tenant)}
        valid = NotificationTemplateAdminSerializer(data=base, context=context)
        self.assertTrue(valid.is_valid(), valid.errors)
        template = valid.save()
        self.assertEqual(template.repeat_interval_days, 2)
        for value in [-1, 366, 'not-a-number', None]:
            serializer = NotificationTemplateAdminSerializer(template, data={'repeat_interval_days': value}, partial=True, context=context)
            self.assertFalse(serializer.is_valid(), value)
            self.assertIn('repeat_interval_days', serializer.errors)
        serializer = NotificationTemplateAdminSerializer(template, data={'event': 'payment_confirmed'}, partial=True, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn('repeat_interval_days', serializer.errors)

    def test_failed_notification_does_not_bypass_failure_policy_as_repeat(self):
        template = self.template('missing_documents')
        template.repeat_interval_days = 1
        template.save()
        with patch('booking.management.commands.process_snowland_jobs.send_mail', side_effect=RuntimeError('QA offline')):
            self.jobs(); self.jobs()
        self.assertEqual(template.deliveries.filter(status='failed').count(), 2)
        self.assertEqual(template.deliveries.count(), 2)
