from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Coach.models import Coach, CoachCourseLevel, CoachLeaveRequest, CoachResort
from booking.models import Booking, Payment, Reservation, ReservationGroup


class CoachRejectionReassignmentTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.reservation.status = 'pending_coach_confirmation'
        self.reservation.save()
        self.coach.availability_status = 'passive'
        self.coach.save()
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save()
        self.day = timezone.localdate() + timedelta(days=2)
        self.booking_1.date = self.day
        self.booking_1.save()
        self.booking_2.date = self.day + timedelta(days=1)
        self.booking_2.save()
        Payment.objects.create(reservation_group=self.group, status='paid')
        self.api = APIClient()
        self.api.force_authenticate(self.coach_user)
        self.url = f'/api/admin/snowland/coach/confirm/{self.reservation.pk}/'

    def alternative(self, status='active'):
        coach = Coach.objects.create(client=self.client_tenant, name='QA替代教練', languages=['zh'], availability_status=status)
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(coach=coach, course_type=self.course_type,
            ability_levels=['level6'], price_level='Lv1')
        return coach

    def reject(self):
        result = self.api.post(self.url, {'action': 'reject'}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.reservation.refresh_from_db()
        self.assertTrue(self.reservation.rejected_coaches.filter(pk=self.coach.pk).exists())
        self.assertNotIn('True', result.data['msg'])
        self.assertNotIn('False', result.data['msg'])
        return result

    def test_real_reject_reassigns_all_lessons_to_available_alternative(self):
        coach = self.alternative()
        result = self.reject()
        self.assertEqual(self.reservation.preferred_coach_id, coach.pk)
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=False).exists())
        self.assertIn('重新安排', result.data['msg'])
        self.assertEqual(self.api.get('/api/admin/snowland/coach/pending/').data['data']['list'], [])

    def test_passive_alternative_gets_pending_confirmation_not_false_acceptance(self):
        coach = self.alternative('passive')
        result = self.reject()
        self.assertEqual(self.reservation.preferred_coach_id, coach.pk)
        self.assertEqual(self.reservation.status, 'pending_coach_confirmation')
        self.assertIn('等待', result.data['msg'])

    def test_no_alternative_leaves_rejection_saved_and_requires_admin(self):
        result = self.reject()
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=True).exists())
        self.assertIn('行政', result.data['msg'])

    def test_approved_leave_on_one_day_does_not_partially_assign_other_day(self):
        coach = self.alternative()
        CoachLeaveRequest.objects.create(coach=coach, start_date=self.day + timedelta(days=1),
            end_date=self.day + timedelta(days=1), status='approved', reason='QA')
        result = self.reject()
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=True).exists())
        self.assertIn('行政', result.data['msg'])

    def test_completed_or_form_filled_occupancy_is_not_double_booked(self):
        coach = self.alternative()
        other = Reservation.objects.create(group=ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus),
            preferred_coach=coach, resort=self.resort, status='completed')
        Booking.objects.create(reservation=other, date=self.day, start_time='09:00', end_time='11:00', is_scheduled=True)
        for status in ('completed', 'form_filled'):
            with self.subTest(status=status):
                other.status = status
                other.save()
                self.reservation.preferred_coach = self.coach
                self.reservation.status = 'pending_coach_confirmation'
                self.reservation.save()
                self.reservation.bookings.update(is_scheduled=True)
                self.reject()
                self.assertIsNone(self.reservation.preferred_coach_id)
                self.assertFalse(self.reservation.bookings.filter(is_scheduled=True).exists())

    def test_cancelled_old_preference_does_not_reserve_alternative_forever(self):
        coach = self.alternative()
        other = Reservation.objects.create(group=ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus),
            preferred_coach=coach, is_preferred_coach=True, resort=self.resort, status='cancelled')
        Booking.objects.create(reservation=other, date=self.day, start_time='09:00', end_time='11:00', is_scheduled=True)
        self.reject()
        self.assertEqual(self.reservation.preferred_coach_id, coach.pk)
        other.refresh_from_db()
        self.assertEqual(other.status, 'cancelled')

    def test_coach_opted_out_of_automatic_assignment_is_not_used(self):
        coach = self.alternative()
        coach.auto_assignment_enabled = False
        coach.save()
        self.reject()
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=True).exists())

    def test_resort_permission_does_not_grant_another_campus_assignment(self):
        coach = self.alternative()
        coach.campuses.clear()
        self.reject()
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=True).exists())
