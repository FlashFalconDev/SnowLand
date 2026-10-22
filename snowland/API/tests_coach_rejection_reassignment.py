from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Coach.models import Coach, CoachCourseLevel, CoachLeaveRequest, CoachResort
from Resorts.models import Campus
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

    def manually_reassigned_course(self):
        replacement = self.alternative()
        replacement.auto_assignment_enabled = False
        replacement.user = User.objects.create_user('replacement-coach', email='replacement@example.test')
        replacement.save(update_fields=['auto_assignment_enabled', 'user'])
        profile = replacement.user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        self.reservation.language = 'zh'
        self.reservation.max_ability_level = 'level3'
        self.reservation.save(update_fields=['language', 'max_ability_level'])
        original_times = list(self.reservation.bookings.order_by('pk').values_list(
            'id', 'date', 'start_time', 'end_time', 'course_type', 'course_name'))
        original_prices = (self.reservation.course_fee, self.reservation.coach_fee, self.reservation.discount_amount)
        rejected = self.reject()
        self.assertIn('行政', rejected.data['msg'])
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=True).exists())
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('reassign-hq', 'reassign-hq@example.test', 'QA-only'))
        result = admin.put(f'/api/admin/snowland/orders/{self.group.pk}/', {
            'action': 'save', 'reservation_updates': [{'reservation_id': self.reservation.pk, 'coach_id': replacement.pk}],
        }, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, replacement.pk)
        self.assertEqual(self.reservation.status, 'manually_assigned')
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=False).exists())
        self.assertEqual(list(self.reservation.bookings.order_by('pk').values_list(
            'id', 'date', 'start_time', 'end_time', 'course_type', 'course_name')), original_times)
        self.assertEqual((self.reservation.course_fee, self.reservation.coach_fee, self.reservation.discount_amount), original_prices)
        self.assertEqual(list(self.group.payments.values_list('status', flat=True)), ['paid'])
        self.assertTrue(self.reservation.rejected_coaches.filter(pk=self.coach.pk).exists())
        return replacement

    def test_reject_then_hq_manual_assignment_moves_all_lessons_between_coach_views(self):
        replacement = self.manually_reassigned_course()
        for path in ('my-courses/', 'my-calendar/', 'pending/'):
            response = self.api.get('/api/admin/snowland/coach/' + path)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['data']['list'], [])
        other = APIClient()
        other.force_authenticate(replacement.user)
        courses = other.get('/api/admin/snowland/coach/my-courses/')
        self.assertEqual(courses.status_code, 200, courses.data)
        self.assertEqual([row['id'] for row in courses.data['data']['list']], [self.reservation.pk])
        self.assertEqual(courses.data['data']['list'][0]['status'], 'manually_assigned')
        self.assertEqual(len(courses.data['data']['list'][0]['bookings']), 2)
        calendar = other.get('/api/admin/snowland/coach/my-calendar/')
        self.assertEqual(calendar.status_code, 200, calendar.data)
        self.assertEqual({row['id'] for row in calendar.data['data']['list']}, {self.booking_1.pk, self.booking_2.pk})
        self.assertEqual(other.get('/api/admin/snowland/coach/pending/').data['data']['list'], [])

    def test_previous_coach_cannot_use_old_confirmation_or_admin_save_to_undo_reassignment(self):
        replacement = self.manually_reassigned_course()
        for action in ('accept', 'reject'):
            response = self.api.post(self.url, {'action': action}, format='json')
            self.assertEqual(response.status_code, 404, response.data)
        response = self.api.put(f'/api/admin/snowland/orders/{self.group.pk}/', {
            'action': 'save', 'payment_status': 'pending',
            'reservation_updates': [{'reservation_id': self.reservation.pk, 'coach_id': self.coach.pk}],
        }, format='json')
        self.assertEqual(response.status_code, 403, response.data)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, replacement.pk)
        self.assertEqual(list(self.group.payments.values_list('status', flat=True)), ['paid'])

    def test_wrong_campus_manager_cannot_manually_reassign_rejected_course_or_change_payment(self):
        replacement = self.alternative()
        replacement.auto_assignment_enabled = False
        replacement.save(update_fields=['auto_assignment_enabled'])
        self.reject()
        other_campus = Campus.objects.create(client=self.client_tenant, code='other-campus', name='其他校區')
        user = User.objects.create_user('wrong-campus-manager')
        profile = user.userprofile
        profile.is_manager = True
        profile.manager_client = self.client_tenant
        profile.role = 'campus_manager'
        profile.save()
        profile.campuses.add(other_campus)
        manager = APIClient()
        manager.force_authenticate(user)
        self.assertEqual(manager.get(f'/api/admin/snowland/orders/{self.group.pk}/').status_code, 404)
        response = manager.put(f'/api/admin/snowland/orders/{self.group.pk}/', {
            'action': 'save', 'payment_status': 'pending',
            'reservation_updates': [{'reservation_id': self.reservation.pk, 'coach_id': replacement.pk}],
        }, format='json')
        self.assertEqual(response.status_code, 403, response.data)
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.reservation.bookings.filter(is_scheduled=True).exists())
        self.assertEqual(list(self.group.payments.values_list('status', flat=True)), ['paid'])
