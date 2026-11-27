from datetime import time

from django.test import TestCase

from API import tests_order_assignment_scope as assignment_fixtures
from Coach.models import CoachLeaveRequest
from booking.models import Booking, OrderRevision, Reservation, ReservationGroup


class ManualAssignmentConflictTests(TestCase):
    setUp = assignment_fixtures.OrderAssignmentScopeTests.setUp
    coach = assignment_fixtures.OrderAssignmentScopeTests.coach

    def assign(self, coach, **extra):
        return self.api.put(self.url, {
            'action': 'save', 'payment_status': 'paid',
            'reservation_updates': [{'reservation_id': self.reservation.pk, 'coach_id': coach.pk}],
            **extra,
        }, format='json')

    def assert_unchanged(self):
        self.reservation.refresh_from_db()
        self.booking.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.booking.is_scheduled)
        self.assertEqual(self.payment.status, 'pending')
        self.assertFalse(OrderRevision.objects.filter(group=self.group).exists())

    def assert_candidate(self, coach, reason=None):
        response = self.api.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        result = response.data['data']['reservations'][0]
        self.assertEqual(result['candidate_status'], 'ok')
        if reason:
            self.assertNotIn(coach.pk, {row['id'] for row in result['available_coaches']})
            unavailable = {row['id']: row['reason_codes'] for row in result['unavailable_coaches']}
            self.assertEqual(unavailable[coach.pk], [reason])
        else:
            self.assertIn(coach.pk, {row['id'] for row in result['available_coaches']})

    def test_form_filled_conflict_across_campuses_and_resorts_blocks_picker_and_save(self):
        coach = self.coach()
        # A coach can serve two campuses, but not teach both at the same time.
        coach.campuses.add(self.other_campus)
        coach.coachresort_set.create(resort=self.other_resort)
        self.booking.start_time, self.booking.end_time = time(8), time(12)
        self.booking.save(update_fields=['start_time', 'end_time'])
        other = Reservation.objects.create(
            group=ReservationGroup.objects.create(client=self.tenant, campus=self.other_campus),
            resort=self.other_resort, preferred_coach=coach, status='form_filled',
        )
        occupied = Booking.objects.create(reservation=other, date=self.booking.date,
                                          start_time=time(11), end_time=time(15), is_scheduled=True)
        self.assert_candidate(coach, 'schedule_conflict')
        response = self.assign(coach)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['reason_codes'], ['schedule_conflict'])
        self.assert_unchanged()

        occupied.start_time = time(12)
        occupied.save(update_fields=['start_time'])
        self.assert_candidate(coach)
        response = self.assign(coach)
        self.assertEqual(response.status_code, 200, response.data)
        self.assert_candidate(coach)  # Its own scheduled booking is skipped by the picker.

    def test_unscheduled_cancelled_deleted_and_archived_bookings_do_not_occupy(self):
        coach = self.coach()
        other = Reservation.objects.create(group=self.group, resort=self.resort, preferred_coach=coach,
                                           status='form_filled')
        slot = Booking.objects.create(reservation=other, date=self.booking.date,
                                      start_time=time(9), end_time=time(13))
        self.assert_candidate(coach)

        slot.is_scheduled = True
        slot.save(update_fields=['is_scheduled'])
        for status in ('cancelled', 'deleted'):
            with self.subTest(status=status):
                other.status = status
                other.save(update_fields=['status'])
                self.assert_candidate(coach)
        other.status = 'form_filled'
        other.is_deleted = True
        other.save(update_fields=['status', 'is_deleted'])
        self.assert_candidate(coach)
        response = self.assign(coach)
        self.assertEqual(response.status_code, 200, response.data)

    def test_approved_leave_is_rejected_but_cancelled_leave_does_not_block(self):
        coach = self.coach()
        leave = CoachLeaveRequest.objects.create(coach=coach, start_date=self.booking.date,
                                                 end_date=self.booking.date, status='approved', reason='QA')
        self.assert_candidate(coach, 'on_leave')
        response = self.assign(coach)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['reason_codes'], ['on_leave'])
        self.assert_unchanged()
        leave.status = 'cancelled'
        leave.save(update_fields=['status'])
        self.assert_candidate(coach)
        response = self.assign(coach)
        self.assertEqual(response.status_code, 200, response.data)

    def test_overlapping_lessons_in_one_reservation_are_rejected(self):
        coach = self.coach()
        Booking.objects.create(reservation=self.reservation, date=self.booking.date,
                               start_time=time(12), end_time=time(15))
        self.assert_candidate(coach, 'schedule_conflict')
        response = self.assign(coach)
        self.assertEqual(response.status_code, 400, response.data)
        self.assert_unchanged()
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=True).exists())

    def test_two_reservations_cannot_take_the_same_coach_in_one_save(self):
        coach = self.coach()
        second = Reservation.objects.create(group=self.group, resort=self.resort, status='created',
            course_type=self.kind, course_template=self.template, max_ability_level='no_exp')
        slot = Booking.objects.create(reservation=second, date=self.booking.date,
                                      start_time=time(10), end_time=time(14))
        response = self.assign(coach, reservation_updates=[
            {'reservation_id': self.reservation.pk, 'coach_id': coach.pk},
            {'reservation_id': second.pk, 'coach_id': coach.pk},
        ])
        self.assertEqual(response.status_code, 400, response.data)
        self.assert_unchanged()
        second.refresh_from_db()
        slot.refresh_from_db()
        self.assertIsNone(second.preferred_coach_id)
        self.assertFalse(slot.is_scheduled)

    def test_adjacent_lessons_are_allowed_and_passive_coach_waits_for_confirmation(self):
        coach = self.coach()
        coach.availability_status = 'passive'
        coach.save(update_fields=['availability_status'])
        Booking.objects.create(reservation=self.reservation, date=self.booking.date,
                               start_time=time(13), end_time=time(15))
        response = self.assign(coach)
        self.assertEqual(response.status_code, 200, response.data)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, 'pending_coach_confirmation')
        self.assertEqual(self.reservation.preferred_coach_id, coach.pk)
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=False).exists())

    def test_removing_passive_coach_returns_to_unscheduled_state(self):
        coach = self.coach()
        self.reservation.preferred_coach = coach
        self.reservation.status = 'pending_coach_confirmation'
        self.reservation.save()
        self.booking.is_scheduled = True
        self.booking.save()
        response = self.api.put(self.url, {'action': 'save', 'reservation_updates': [
            {'reservation_id': self.reservation.pk, 'coach_id': None},
        ]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.reservation.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.reservation.status, 'created')
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.booking.is_scheduled)

    def test_cancelled_or_deleted_reservation_cannot_be_reassigned(self):
        coach = self.coach()
        for status in ('cancelled', 'deleted'):
            with self.subTest(status=status):
                self.reservation.status = status
                self.reservation.save(update_fields=['status'])
                response = self.assign(coach)
                self.assertEqual(response.status_code, 400, response.data)
                self.assert_unchanged()

    def test_duplicate_reservation_updates_are_rejected_not_last_write_wins(self):
        coach = self.coach()
        response = self.assign(coach, reservation_updates=[
            {'reservation_id': self.reservation.pk, 'coach_id': coach.pk},
            {'reservation_id': self.reservation.pk, 'coach_id': None},
        ])
        self.assertEqual(response.status_code, 400, response.data)
        self.assert_unchanged()

    def test_conflict_uses_proposed_times_and_rolls_back_the_entire_save(self):
        coach = self.coach()
        occupied = Reservation.objects.create(group=self.group, resort=self.resort,
                                               preferred_coach=coach, status='manually_assigned')
        Booking.objects.create(reservation=occupied, date=self.booking.date,
                               start_time=time(15), end_time=time(18), is_scheduled=True)
        response = self.assign(coach, booking_updates=[{
            'booking_id': self.booking.pk, 'start_time': '13:00', 'end_time': '17:00',
        }])
        self.assertEqual(response.status_code, 400, response.data)
        self.assert_unchanged()
        self.assertEqual((self.booking.start_time, self.booking.end_time), (time(9), time(13)))

    def test_editing_one_form_filled_lesson_preserves_occupancy_of_its_unchanged_sibling(self):
        coach = self.coach()
        occupied = Reservation.objects.create(group=self.group, resort=self.resort,
                                               preferred_coach=coach, status='form_filled')
        edited = Booking.objects.create(reservation=occupied, date=self.booking.date,
                                         start_time=time(13), end_time=time(17), is_scheduled=True)
        unchanged = Booking.objects.create(reservation=occupied, date=self.booking.date,
                                            start_time=time(9), end_time=time(13), is_scheduled=True)
        self.assert_candidate(coach, 'schedule_conflict')
        response = self.assign(coach, booking_updates=[{
            'booking_id': edited.pk, 'start_time': '14:00', 'end_time': '18:00',
        }])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['reason_codes'], ['schedule_conflict'])
        self.assert_unchanged()
        edited.refresh_from_db()
        unchanged.refresh_from_db()
        self.assertEqual(edited.start_time, time(13))
        self.assertTrue(unchanged.is_scheduled)

    def test_removal_in_same_batch_releases_coach_for_another_reservation(self):
        coach = self.coach()
        self.reservation.preferred_coach = coach
        self.reservation.status = 'manually_assigned'
        self.reservation.save()
        self.booking.is_scheduled = True
        self.booking.save()
        replacement = Reservation.objects.create(group=self.group, resort=self.resort, status='created',
            course_type=self.kind, course_template=self.template, max_ability_level='no_exp')
        slot = Booking.objects.create(reservation=replacement, date=self.booking.date,
                                      start_time=time(9), end_time=time(13))
        response = self.assign(coach, reservation_updates=[
            {'reservation_id': self.reservation.pk, 'coach_id': None},
            {'reservation_id': replacement.pk, 'coach_id': coach.pk},
        ])
        self.assertEqual(response.status_code, 200, response.data)
        self.reservation.refresh_from_db()
        self.booking.refresh_from_db()
        replacement.refresh_from_db()
        slot.refresh_from_db()
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.booking.is_scheduled)
        self.assertEqual(replacement.preferred_coach_id, coach.pk)
        self.assertTrue(slot.is_scheduled)
