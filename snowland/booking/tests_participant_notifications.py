from datetime import time, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from Client.models import Client
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from booking.legal_documents import get_current_waiver
from booking.models import Booking, MemberDetail, MemberProfile, NotificationDelivery, NotificationTemplate, Payment, Reservation, ReservationGroup
from booking.operations import schedule_group_notifications


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ParticipantNotificationTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.owner = User.objects.create_user('notification-owner', 'owner@example.test')
        self.adult = User.objects.create_user('notification-adult', 'adult@example.test')
        self.parent = User.objects.create_user('notification-parent', 'parent@example.test')
        self.group = ReservationGroup.objects.create(client=self.tenant, user=self.owner, name='ORGANIZER-NAME-ONLY', line_group_url='https://line.me/ti/g/QA-FAKE')
        self.reservation = Reservation.objects.create(group=self.group, status='auto_assigned', number_of_people=3)
        self.booking = Booking.objects.create(reservation=self.reservation, date=timezone.localdate()+timedelta(days=1), start_time=time(9), end_time=time(12))
        self.member = MemberDetail.objects.create(reservation=self.reservation, user=self.adult)
        self.children = [MemberDetail.objects.create(reservation=self.reservation, guardian=self.parent) for _ in range(2)]
        self.payment = Payment.objects.create(reservation_group=self.group, user=self.owner, status='paid', expires_at=timezone.now()+timedelta(days=3))

    def template(self, event='line_group', channel='email'):
        return NotificationTemplate.objects.create(client=self.tenant, name=f'{event} {channel}', event=event,
            channel=channel, subject='QA reminder', body='{customer_name}|{line_group_url}|{payment_url}', days_before=3)

    def jobs(self, dry_run=False):
        call_command('process_snowland_jobs', stdout=StringIO(), dry_run=dry_run)

    def complete(self, member):
        member.insurance_data = {'full_name': 'QA Only', 'birth_date': '1990-01-01', 'id_number': 'QA-ID', 'phone': 'QA-PHONE'}
        member.insurance_completed_at = member.waiver_completed_at = timezone.now()
        member.waiver_signature = 'Original signature'
        member.waiver_document_version = get_current_waiver(self.tenant)['version']
        member.save()

    def test_group_invite_and_pre_course_target_owner_adult_parent_once_each(self):
        for event in ['line_group', 'pre_course']:
            template = self.template(event)
            scheduled = schedule_group_notifications(self.group, event)
            self.assertEqual({item.recipient for item in scheduled}, {'owner@example.test', 'adult@example.test', 'parent@example.test'})
            self.assertEqual(schedule_group_notifications(self.group, event), [])
            self.assertEqual(NotificationDelivery.objects.filter(template=template).count(), 3)
        self.jobs(); self.jobs()
        self.assertEqual(len(mail.outbox), 6)
        for message in mail.outbox:
            if message.to != [self.owner.email]:
                self.assertNotIn('ORGANIZER-NAME-ONLY', message.body)
                self.assertNotIn('payment_token', message.body)

    def test_payment_confirmation_remains_organizer_only(self):
        self.template('payment_confirmed')
        scheduled = schedule_group_notifications(self.group, 'payment_confirmed')
        self.assertEqual([item.recipient for item in scheduled], [self.owner.email])

    def test_missing_documents_only_reminds_account_responsible_for_incomplete_students(self):
        template = self.template('missing_documents')
        self.complete(self.member)
        self.complete(self.children[0])
        scheduled = schedule_group_notifications(self.group, 'missing_documents')
        self.assertEqual([item.recipient for item in scheduled], [self.parent.email])
        self.complete(self.children[1])
        self.jobs()
        self.assertEqual(NotificationDelivery.objects.get(template=template).status, 'cancelled')
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    def test_missing_seat_or_unbound_student_reminds_organizer_not_other_members(self):
        self.template('missing_documents')
        for member in [self.member, *self.children]:
            self.complete(member)
        self.reservation.number_of_people = 4
        self.reservation.save(update_fields=['number_of_people'])
        scheduled = schedule_group_notifications(self.group, 'missing_documents')
        self.assertEqual([item.recipient for item in scheduled], [self.owner.email])

    def test_cancelled_or_removed_guardian_is_rechecked_before_send(self):
        template = self.template()
        schedule_group_notifications(self.group, 'line_group')
        for member in self.children:
            member.guardian = None; member.user = self.owner
            member.save(update_fields=['guardian', 'user'])
        self.jobs()
        self.assertEqual(NotificationDelivery.objects.get(template=template, recipient=self.parent.email).status, 'cancelled')
        self.assertEqual({message.to[0] for message in mail.outbox}, {self.owner.email, self.adult.email})

    def test_latest_refund_prevents_queued_course_messages_even_when_old_payment_is_paid(self):
        template = self.template()
        schedule_group_notifications(self.group, 'line_group')
        Payment.objects.create(reservation_group=self.group, user=self.owner, status='refunded')
        self.jobs()
        self.assertFalse(NotificationDelivery.objects.filter(template=template).exclude(status='cancelled').exists())
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    def test_line_uses_bound_profile_id_and_parent_receives_one_mock_push_for_two_children(self):
        template = self.template(channel='line')
        for user, suffix in [(self.adult, 'a'), (self.parent, 'b')]:
            MemberProfile.objects.create(user=user, line_user_id='U'+suffix*32)
        with patch('chatbooking.line.LineMessagingClient') as line:
            self.jobs(); self.jobs()
        self.assertEqual(NotificationDelivery.objects.filter(template=template, status='sent').count(), 2)
        self.assertEqual(line.return_value.push.call_count, 2)
        self.assertEqual({call.args[0] for call in line.return_value.push.call_args_list}, {'U'+'a'*32, 'U'+'b'*32})
        self.assertTrue(all('ORGANIZER-NAME-ONLY' not in call.args[1] for call in line.return_value.push.call_args_list))

    def test_dry_run_does_not_create_deliveries_or_send(self):
        self.template()
        self.jobs(dry_run=True)
        self.assertFalse(NotificationDelivery.objects.exists())
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    def test_email_change_cancels_old_destination_and_uses_current_bound_account(self):
        template = self.template()
        schedule_group_notifications(self.group, 'line_group')
        self.adult.email = 'new-adult@example.test'; self.adult.save(update_fields=['email'])
        self.jobs()
        self.assertEqual(NotificationDelivery.objects.get(template=template, recipient='adult@example.test').status, 'cancelled')
        self.assertEqual({message.to[0] for message in mail.outbox}, {self.owner.email, self.parent.email, self.adult.email})

    def test_parent_cancelled_course_is_not_notified_even_if_another_course_in_order_is_active(self):
        template = self.template()
        schedule_group_notifications(self.group, 'line_group')
        later = Reservation.objects.create(group=self.group, status='auto_assigned', number_of_people=1)
        Booking.objects.create(reservation=later, date=timezone.localdate()+timedelta(days=10), start_time=time(9), end_time=time(12))
        self.reservation.status = 'cancelled'; self.reservation.save(update_fields=['status'])
        self.jobs()
        for user in [self.adult, self.parent]:
            self.assertEqual(NotificationDelivery.objects.get(template=template, recipient=user.email).status, 'cancelled')
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    def test_course_restrictions_and_advance_date_use_each_recipients_actual_course(self):
        category = CourseCategory.objects.create(client=self.tenant, name='QA')
        course_type = CourseType.objects.create(category=category, name='QA')
        first = CourseTemplate.objects.create(course_type=course_type, name='First', duration_hours=3)
        second = CourseTemplate.objects.create(course_type=course_type, name='Second', duration_hours=3)
        self.reservation.course_template = first; self.reservation.save(update_fields=['course_template'])
        later = Reservation.objects.create(group=self.group, course_template=second, status='auto_assigned')
        date = timezone.localdate()+timedelta(days=10)
        Booking.objects.create(reservation=later, date=date, start_time=time(9), end_time=time(12))
        self.member.reservation = later; self.member.save(update_fields=['reservation'])
        template = self.template()
        schedule_group_notifications(self.group, 'line_group')
        delivery = NotificationDelivery.objects.get(template=template, recipient=self.adult.email)
        self.assertEqual(timezone.localtime(delivery.scheduled_at).date(), date-timedelta(days=3))
        template.course_templates.add(first)
        schedule_group_notifications(self.group, 'line_group')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'cancelled')

    def test_shared_email_deduplicates_and_inactive_account_is_excluded(self):
        template = self.template()
        self.parent.email = self.adult.email.upper(); self.parent.save(update_fields=['email'])
        scheduled = schedule_group_notifications(self.group, 'line_group')
        self.assertEqual({item.recipient for item in scheduled}, {self.owner.email, self.adult.email})
        self.adult.is_active = self.parent.is_active = False
        self.adult.save(update_fields=['is_active']); self.parent.save(update_fields=['is_active'])
        self.jobs()
        self.assertEqual(NotificationDelivery.objects.get(template=template, recipient=self.adult.email).status, 'cancelled')
        self.assertEqual([message.to for message in mail.outbox], [[self.owner.email]])

    def test_malformed_legacy_contact_data_falls_back_without_500(self):
        self.template()
        self.payment.DataJSON = ['legacy invalid shape']; self.payment.save(update_fields=['DataJSON'])
        self.assertEqual(len(schedule_group_notifications(self.group, 'line_group')), 3)

    def test_dry_run_does_not_mutate_existing_stale_delivery(self):
        template = self.template()
        schedule_group_notifications(self.group, 'line_group')
        self.adult.is_active = False; self.adult.save(update_fields=['is_active'])
        self.jobs(dry_run=True)
        self.assertEqual(NotificationDelivery.objects.get(template=template, recipient=self.adult.email).status, 'scheduled')
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    def test_organizer_missing_documents_uses_incomplete_course_not_earlier_complete_course(self):
        self.template('missing_documents')
        for member in [self.member, *self.children]:
            self.complete(member)
        later = Reservation.objects.create(group=self.group, status='auto_assigned', number_of_people=1)
        date = timezone.localdate()+timedelta(days=10)
        Booking.objects.create(reservation=later, date=date, start_time=time(9), end_time=time(12))
        MemberDetail.objects.create(reservation=later, user=self.owner)
        scheduled = schedule_group_notifications(self.group, 'missing_documents')
        self.assertEqual([item.recipient for item in scheduled], [self.owner.email])
        self.assertEqual(timezone.localtime(scheduled[0].scheduled_at).date(), date-timedelta(days=3))

    def test_email_transport_failure_is_recorded_failed_not_claimed_sent(self):
        template = self.template()
        with patch('booking.management.commands.process_snowland_jobs.send_mail', side_effect=RuntimeError('QA transport offline')):
            self.jobs()
        self.assertEqual(NotificationDelivery.objects.filter(template=template, status='failed').count(), 3)
        self.assertFalse(NotificationDelivery.objects.filter(template=template, status='sent').exists())

    def test_zero_messages_reported_by_transport_is_failed_not_sent(self):
        template = self.template()
        with patch('booking.management.commands.process_snowland_jobs.send_mail', return_value=0):
            self.jobs()
        self.assertEqual(NotificationDelivery.objects.filter(template=template, status='failed').count(), 3)
        self.assertFalse(NotificationDelivery.objects.filter(template=template, status='sent').exists())

    def test_recipient_course_dates_use_one_local_day_even_across_midnight(self):
        from booking.notification_recipients import course_notification_recipients
        today = timezone.localdate()
        template = self.template()
        with patch('booking.notification_recipients.timezone.localdate', side_effect=[today, today+timedelta(days=2)]) as clock:
            recipients = course_notification_recipients(self.group, template)
        self.assertEqual(len(recipients), 3)
        self.assertEqual(clock.call_count, 1)

    def test_stale_worker_candidate_is_rechecked_and_not_sent_twice(self):
        from booking.management.commands.process_snowland_jobs import Command
        self.template()
        delivery = schedule_group_notifications(self.group, 'line_group')[0]
        command = Command()
        now = timezone.now()
        self.assertEqual(command._deliver_due(delivery.pk, now, False), (1, 0))
        self.assertEqual(command._deliver_due(delivery.pk, now, False), (0, 0))
        self.assertEqual(len(mail.outbox), 1)

    def test_stale_worker_candidate_does_not_send_cancelled_failed_or_future_notice(self):
        from booking.management.commands.process_snowland_jobs import Command
        template = self.template()
        command = Command()
        now = timezone.now()
        for status, scheduled_at in [('cancelled', now), ('failed', now), ('scheduled', now+timedelta(days=1))]:
            delivery = NotificationDelivery.objects.create(template=template, group=self.group,
                recipient=self.owner.email, status=status, scheduled_at=scheduled_at)
            self.assertEqual(command._deliver_due(delivery.pk, now, False), (0, 0))
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    def test_stale_worker_candidate_deleted_after_scan_is_ignored(self):
        from booking.management.commands.process_snowland_jobs import Command
        self.template()
        delivery = schedule_group_notifications(self.group, 'line_group')[0]
        delivery_id = delivery.pk
        delivery.delete()
        self.assertEqual(Command()._deliver_due(delivery_id, timezone.now(), False), (0, 0))
