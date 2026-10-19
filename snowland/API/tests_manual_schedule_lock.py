from datetime import time

from django.test import TestCase

from API import tests_order_assignment_scope as fixtures
from booking.models import Booking, OrderRevision, Reservation
from booking.scheduler import assign_coachs


class ManualScheduleLockTests(TestCase):
    setUp = fixtures.OrderAssignmentScopeTests.setUp
    coach = fixtures.OrderAssignmentScopeTests.coach

    def lock_original(self, status='manually_assigned'):
        first, alternative = self.coach(), self.coach()
        first.coachresort_set.update(assignment_score=100)
        alternative.coachresort_set.update(assignment_score=0)
        self.reservation.preferred_coach = first
        self.reservation.status = status
        self.reservation.save()
        self.booking.is_scheduled = True
        self.booking.save()
        return first, alternative

    def new_reservation(self, coach=None, start=time(9), end=time(13)):
        reservation = Reservation.objects.create(group=self.group, resort=self.resort,
            course_type=self.kind, course_template=self.template, max_ability_level='no_exp',
            preferred_coach=coach, is_preferred_coach=bool(coach), status='created')
        Booking.objects.create(reservation=reservation, date=self.booking.date,
            start_time=start, end_time=end, course_template=self.template)
        return reservation

    def assert_original(self, coach, status='manually_assigned'):
        self.reservation.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, coach.pk)
        self.assertEqual(self.reservation.status, status)
        self.assertTrue(self.booking.is_scheduled)

    def test_manual_assignment_is_unchanged_even_if_explicitly_in_scheduler_batch(self):
        first, alternative = self.lock_original()
        success, report = assign_coachs([self.reservation])
        self.assertTrue(success, report)
        self.assert_original(first)

    def test_new_customer_preference_cannot_displace_manual_assignment(self):
        first, alternative = self.lock_original()
        new = self.new_reservation(first)
        success, report = assign_coachs([new])
        self.assertFalse(success, report)
        self.assert_original(first)
        new.refresh_from_db()
        self.assertEqual(new.status, 'created')
        self.assertFalse(new.bookings.get().is_scheduled)

    def test_existing_automatic_assignment_can_still_move_for_customer_preference(self):
        first, alternative = self.lock_original('auto_assigned')
        new = self.new_reservation(first)
        success, report = assign_coachs([new])
        self.assertTrue(success, report)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, alternative.pk)
        new.refresh_from_db()
        self.assertEqual(new.preferred_coach_id, first.pk)
        self.assertTrue(new.bookings.get().is_scheduled)

    def test_completed_and_form_filled_history_are_not_reassigned(self):
        for status in ('completed', 'form_filled'):
            with self.subTest(status=status):
                first, alternative = self.lock_original(status)
                success, report = assign_coachs([self.reservation])
                self.assertTrue(success, report)
                self.assert_original(first, status)

    def test_form_filled_lesson_still_reserves_its_coach(self):
        first, alternative = self.lock_original('form_filled')
        new = self.new_reservation(first)
        success, report = assign_coachs([new])
        self.assertFalse(success, report)
        self.assert_original(first, 'form_filled')

    def test_rescheduling_another_line_does_not_shuffle_manual_sibling(self):
        first, alternative = self.lock_original()
        second = self.new_reservation(start=time(13), end=time(17))
        second.preferred_coach = alternative
        second.status = 'auto_assigned'
        second.save()
        second.bookings.update(is_scheduled=True)
        result = self.api.put(self.url, {'action': 'schedule', 'reservation_updates': [
            {'reservation_id': second.pk, 'coach_id': None},
        ]}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assert_original(first)
        second.refresh_from_db()
        self.assertIsNotNone(second.preferred_coach_id)
        self.assertTrue(second.bookings.get().is_scheduled)

    def test_terminal_lines_in_a_batch_are_not_reopened(self):
        self.coach()
        for status in ('cancelled', 'deleted'):
            with self.subTest(status=status):
                self.reservation.status = status
                self.reservation.save()
                success, report = assign_coachs([self.reservation])
                self.assertTrue(success, report)
                self.reservation.refresh_from_db()
                self.booking.refresh_from_db()
                self.assertEqual(self.reservation.status, status)
                self.assertIsNone(self.reservation.preferred_coach_id)
                self.assertFalse(self.booking.is_scheduled)

    def test_remove_save_then_explicit_schedule_reassigns_without_fake_edit(self):
        first, alternative = self.lock_original()
        saved = self.api.put(self.url, {'action': 'save', 'reservation_updates': [
            {'reservation_id': self.reservation.pk, 'coach_id': None},
        ]}, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, 'created')
        self.assertIsNone(self.reservation.preferred_coach_id)
        retried = self.api.put(self.url, {'action': 'schedule'}, format='json')
        self.assertEqual(retried.status_code, 200, retried.data)
        self.reservation.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertIsNotNone(self.reservation.preferred_coach_id)
        self.assertTrue(self.booking.is_scheduled)

    def test_unchanged_auto_sibling_is_not_shuffled_by_retrying_an_unassigned_line(self):
        first, alternative = self.lock_original('auto_assigned')
        second = self.new_reservation(start=time(13), end=time(17))
        result = self.api.put(self.url, {'action': 'schedule'}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assert_original(first, 'auto_assigned')
        second.refresh_from_db()
        self.assertIsNotNone(second.preferred_coach_id)
        self.assertTrue(second.bookings.get().is_scheduled)

    def test_retry_failure_keeps_unscheduled_course_payment_and_history_unchanged(self):
        coach = self.coach()
        coach.languages = ['en']
        coach.save()
        result = self.api.put(self.url, {'action': 'schedule', 'payment_status': 'paid'}, format='json')
        self.assertEqual(result.status_code, 400, result.data)
        self.reservation.refresh_from_db()
        self.booking.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.reservation.status, 'created')
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.booking.is_scheduled)
        self.assertEqual(self.payment.status, 'pending')
        self.assertFalse(OrderRevision.objects.filter(group=self.group).exists())
