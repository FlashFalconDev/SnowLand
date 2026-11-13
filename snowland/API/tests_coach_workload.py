from datetime import time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Client.models import Client
from Coach.models import Coach, CoachCourseLevel, CoachLeaveRequest, CoachResort
from Coursekit.models import CourseTemplate
from Resorts.models import Campus, Resorts
from booking.models import Booking, Payment, Reservation, ReservationGroup, SharedCourseClass


class CoachWorkloadTests(TestCase):
    url = '/api/admin/snowland/bookings/coach-workload/'

    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.today = timezone.localdate()
        self.day = self.today + timedelta(days=2)
        self.booking_1.date = self.day
        self.booking_1.save(update_fields=['date'])
        self.empty_coach = self.make_coach('QA 零堂教練')
        self.empty_coach.auto_assignment_enabled = False
        self.empty_coach.save(update_fields=['auto_assignment_enabled'])
        self.second_campus = Campus.objects.create(client=self.client_tenant, name='QA 西校區', code='west')
        self.second_resort = Resorts.objects.create(client=self.client_tenant, name='west', display_name='QA 西雪場')
        self.second_campus.resorts.add(self.second_resort)
        self.outside_coach = self.make_coach('QA 西校區教練', campus=self.second_campus)
        CoachResort.objects.create(coach=self.coach, resort=self.resort, resort_priority=2, assignment_score=4)
        CoachCourseLevel.objects.create(coach=self.coach, course_type=self.course_type,
                                       ability_levels=['entry', 'level3'], price_level='Lv2', course_order=3)
        self.hq = User.objects.create_superuser('qa-workload-hq', password='local-qa-only')
        self.api = APIClient()
        self.api.force_authenticate(self.hq)

    def make_coach(self, name, campus=None):
        coach = Coach.objects.create(client=self.client_tenant, name=name)
        coach.campuses.add(campus or self.campus)
        return coach

    def add_lesson(self, *, coach=None, campus=None, resort=None, day=None, starts=12, ends=13,
                   status='auto_assigned', specified=False, payment=None, shared=None,
                   name='QA 滑雪課程', is_scheduled=True):
        group = ReservationGroup.objects.create(client=self.client_tenant, campus=campus or self.campus)
        reservation = Reservation.objects.create(
            group=group, resort=resort or self.resort, course_type=self.course_type,
            preferred_coach=coach or self.coach, status=status, is_preferred_coach=specified,
            shared_course_class=shared, number_of_people=1,
        )
        if payment:
            Payment.objects.create(reservation_group=group, status=payment)
        return Booking.objects.create(
            reservation=reservation, date=day or self.day, start_time=time(starts), end_time=time(ends),
            course_name=name, is_scheduled=is_scheduled,
        )

    def make_staff(self, role, permissions):
        user = User.objects.create_user(f'qa-workload-{role}')
        profile = user.userprofile
        profile.is_manager = True
        profile.manager_client = self.client_tenant
        profile.role = role
        profile.admin_permissions = permissions
        profile.save()
        profile.campuses.add(self.campus)
        return user

    def get_report(self, start=None, end=None, resort=None, campus='all'):
        params = {'start': start or self.day.isoformat(), 'end': end or self.day.isoformat()}
        if resort is not None:
            params['resort_id'] = resort
        response = self.api.get(self.url, params, HTTP_X_CAMPUS_ID=str(campus))
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['data']

    def test_status_totals_zero_roster_and_current_settings(self):
        self.add_lesson(starts=12, ends=14, specified=True)
        self.add_lesson(starts=14, ends=15, status='pending_coach_confirmation', payment='unpaid')
        for status in ('created', 'cancelled', 'deleted', 'auto_assignment_failed'):
            self.add_lesson(status=status)
        for payment in ('expired', 'refunded'):
            self.add_lesson(payment=payment)
        self.add_lesson(is_scheduled=False)
        self.add_lesson(starts=14, ends=14)
        self.add_lesson(name='QA 雪地攝影')
        self.add_lesson(day=self.day + timedelta(days=1))
        report = self.get_report(campus=self.campus.pk)
        first, second = report['coaches']
        self.assertEqual(first['id'], self.coach.pk)
        self.assertEqual((first['lesson_count'], first['assigned_seconds'], first['completed_seconds'],
                          first['pending_seconds'], first['specified_seconds']), (3, 18000, 7200, 3600, 7200))
        self.assertEqual(first['settings']['resorts'][0]['weight'], 4)
        self.assertEqual(first['settings']['courses'][0]['ability_levels'], ['level1', 'level3'])
        self.assertEqual(second['id'], self.empty_coach.pk)
        self.assertEqual(second['assigned_seconds'], 0)
        self.assertFalse(second['settings']['auto_assignment_enabled'])

    def test_shared_class_counts_once_and_completed_takes_precedence(self):
        template = CourseTemplate.objects.create(course_type=self.course_type, name='QA 團體班', duration_hours=1, max_capacity=6)
        shared = SharedCourseClass.objects.create(
            client=self.client_tenant, campus=self.campus, resort=self.resort, template=template,
            date=self.day, start_time=time(12), end_time=time(13), status='ready', ability_level='no_exp',
        )
        self.add_lesson(shared=shared, status='pending_coach_confirmation')
        self.add_lesson(shared=shared, status='auto_assigned')
        self.add_lesson(shared=shared, status='completed')
        row = self.get_report()['coaches'][0]
        self.assertEqual((row['lesson_count'], row['assigned_seconds'], row['completed_seconds'],
                          row['pending_seconds']), (2, 10800, 10800, 0))

    def test_scope_filter_retains_history_and_uses_latest_payment(self):
        self.add_lesson(coach=self.outside_coach, campus=self.second_campus, resort=self.second_resort)
        self.add_lesson(coach=self.outside_coach)
        paid_then_refunded = self.add_lesson(payment='paid')
        Payment.objects.create(reservation_group=paid_then_refunded.reservation.group, status='refunded')
        foreign = Client.objects.create(name='QA Foreign', internal_code='qa-foreign')
        foreign_coach = Coach.objects.create(client=foreign, name='Foreign name')
        foreign_coach.campuses.add(self.campus)
        self.add_lesson(coach=foreign_coach)
        result = self.get_report(campus=self.campus.pk)
        rows = {row['id']: row for row in result['coaches']}
        self.assertNotIn(foreign_coach.pk, rows)
        self.assertEqual(rows[self.coach.pk]['assigned_seconds'], 7200)
        self.assertEqual(rows[self.outside_coach.pk]['assigned_seconds'], 3600)
        self.assertIsNone(rows[self.outside_coach.pk]['settings'])
        self.assertIsNone(rows[self.outside_coach.pk]['leave_days'])
        self.assertEqual([resort['id'] for resort in result['resorts']], [self.resort.pk])
        west_report = self.get_report(resort=self.second_resort.pk)
        self.assertEqual([(row['id'], row['assigned_seconds']) for row in west_report['coaches']],
                         [(self.outside_coach.pk, 3600)])

    def test_manager_date_limit_and_permissions(self):
        manager = self.make_staff('campus_manager', ['scheduling'])
        self.api.force_authenticate(manager)
        self.add_lesson(day=self.today + timedelta(days=11))
        report = self.get_report(start=self.today - timedelta(days=1), end=self.today + timedelta(days=20))
        self.assertEqual(report['start'], self.today.isoformat())
        self.assertEqual(report['end'], (self.today + timedelta(days=10)).isoformat())
        self.assertEqual(report['coaches'][0]['assigned_seconds'], 7200)
        self.assertTrue(all(row['settings'] is None for row in report['coaches']))
        self.assertFalse(self.get_report(start=self.today - timedelta(days=3), end=self.today - timedelta(days=1))['has_visible_dates'])
        self.assertEqual(self.api.get(self.url, {'start': self.day, 'end': self.day,
                                                'resort_id': self.second_resort.pk}).status_code, 400)
        self.assertEqual(self.api.get(self.url, {'start': self.day, 'end': self.day},
                                      HTTP_X_CAMPUS_ID=str(self.second_campus.pk)).status_code, 403)
        self.api.force_authenticate(self.coach_user)
        self.assertEqual(self.api.get(self.url, {'start': self.day, 'end': self.day}).status_code, 403)

    def test_leave_days_are_clipped_deduplicated_and_private(self):
        for offset in (-1, 0):
            CoachLeaveRequest.objects.create(coach=self.empty_coach, start_date=self.day + timedelta(days=offset),
                                             end_date=self.day + timedelta(days=1), status='approved',
                                             reason='PRIVATE QA REASON')
        CoachLeaveRequest.objects.create(coach=self.empty_coach, start_date=self.day + timedelta(days=2),
                                         end_date=self.day + timedelta(days=2), status='pending')
        report = self.get_report(end=self.day + timedelta(days=2))
        row = next(coach for coach in report['coaches'] if coach['id'] == self.empty_coach.pk)
        self.assertEqual(row['leave_days'], 2)
        self.assertNotIn('PRIVATE QA REASON', str(report))

    def test_invalid_or_excessive_range_and_resort_return_400(self):
        for params in ({}, {'start': 'bad', 'end': self.day},
                       {'start': self.day, 'end': self.day - timedelta(days=1)},
                       {'start': self.day, 'end': self.day + timedelta(days=366)},
                       {'start': self.day, 'end': self.day, 'resort_id': '9' * 25}):
            with self.subTest(params=params):
                self.assertEqual(self.api.get(self.url, params).status_code, 400)
