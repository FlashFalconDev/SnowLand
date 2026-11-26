from datetime import date, datetime, time, timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Client.models import Client, ModuleInfo, ModuleSetting
from Coach.models import Coach, CoachPayRule, PayrollStatement
from Coach.payroll import calculate_payroll_statement
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from booking.models import Booking, Reservation, ReservationGroup, SharedCourseClass


class CoachCourseSummaryTests(TestCase):
    url = '/api/admin/snowland/coach/my-courses/summary/'

    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.coach.schedule_visibility = 'full'
        self.coach.save(update_fields=['schedule_visibility'])
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        self.api = APIClient()
        self.api.force_authenticate(self.coach_user)

        self.ski = CourseType.objects.create(
            category=CourseCategory.objects.create(client=self.client_tenant, name='雙板'), name='初階',
        )
        self.full_day = CourseTemplate.objects.create(
            course_type=self.course_type, name='全天', duration_hours=6, payroll_hours=5,
        )
        self.half_day = CourseTemplate.objects.create(
            course_type=self.ski, name='半天', duration_hours=4, payroll_hours=3,
        )
        self.reservation.course_template = self.full_day
        self.reservation.save(update_fields=['course_template'])
        self.booking_1.date = date(2026, 12, 1)
        self.booking_2.date = date(2026, 12, 2)
        for booking in (self.booking_1, self.booking_2):
            booking.end_time = time(15)
            booking.save(update_fields=['date', 'end_time'])

    def add_lesson(self, day, *, template=None, status='completed', group=None, coach=None,
                   shared_class=None, coach_fee=0, is_preferred_coach=False, end=time(13)):
        reservation = Reservation.objects.create(
            group=group or self.group, resort=self.resort, preferred_coach=coach or self.coach,
            course_type=template.course_type if template else self.course_type,
            course_template=template, status=status, shared_course_class=shared_class,
            coach_fee=coach_fee, is_preferred_coach=is_preferred_coach,
        )
        return Booking.objects.create(
            reservation=reservation, date=day, start_time=time(9), end_time=end, is_scheduled=True,
        )

    def summary(self, **params):
        response = self.api.get(self.url, params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.json()['data']

    def assert_discipline(self, totals, discipline, *, hours, count, amount):
        self.assertEqual(totals['disciplines'][discipline], {
            'hours': hours, 'specified_count': count, 'specified_amount': amount,
        })

    def test_actual_and_estimates_use_the_same_rules_as_payroll(self):
        CoachPayRule.objects.create(
            coach=self.coach, discipline='snowboard', hourly_rate=1000, specified_fee=400, referral_percent=0,
        )
        CoachPayRule.objects.create(
            coach=self.coach, discipline='snowboard', effective_from=date(2026, 12, 2),
            certification_level='new', hourly_rate=1000, specified_fee=900, referral_percent=0,
        )
        CoachPayRule.objects.create(
            coach=self.coach, discipline='ski', hourly_rate=1000, specified_fee=650, referral_percent=0,
        )
        CoachPayRule.objects.create(
            coach=self.coach, discipline='ski', course_type=self.ski, effective_from=date(2026, 12, 20),
            hourly_rate=1000, specified_fee=800, referral_percent=0,
        )
        self.add_lesson(date(2026, 12, 8), template=self.half_day, coach_fee=100)
        custom = CourseTemplate.objects.create(
            course_type=self.ski, name='自訂', duration_hours=4, payroll_hours=Decimal('2.75'),
        )
        self.add_lesson(date(2026, 12, 21), template=custom, coach_fee=100, status='manually_assigned')

        summary = self.summary(month='2026-12')
        self.assertEqual(summary['mode'], 'payroll')
        self.assertEqual(summary['actual']['total_hours'], 13)
        self.assert_discipline(summary['actual'], 'snowboard', hours=10, count=1, amount=400)
        self.assert_discipline(summary['actual'], 'ski', hours=3, count=1, amount=650)
        self.assertEqual(summary['estimated']['total_hours'], 2.75)
        self.assert_discipline(summary['estimated'], 'snowboard', hours=0, count=0, amount=0)
        self.assert_discipline(summary['estimated'], 'ski', hours=2.75, count=1, amount=800)
        self.assertFalse(PayrollStatement.objects.exists())

        statement = calculate_payroll_statement(
            coach=self.coach, campus=self.campus, period_start=date(2026, 12, 1), period_end=date(2026, 12, 31),
        )
        self.assertEqual(sum(line.quantity for line in statement.lines.filter(line_type='course')), 13)
        self.assertEqual(statement.specified_fees, 1050)
        for discipline in ('snowboard', 'ski'):
            totals = summary['actual']['disciplines'][discipline]
            lines = statement.lines.filter(metadata__discipline=discipline)
            self.assertEqual(sum(line.quantity for line in lines.filter(line_type='course')), totals['hours'])
            specified = lines.filter(line_type='specified')
            self.assertEqual(specified.count(), totals['specified_count'])
            self.assertEqual(sum(line.total_amount for line in specified), totals['specified_amount'])

    def test_shared_course_hours_count_once_with_completed_taking_precedence(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, specified_fee=400)
        day = date(2026, 12, 21)
        shared = SharedCourseClass.objects.create(
            client=self.client_tenant, campus=self.campus, resort=self.resort, template=self.full_day,
            date=day, start_time=time(9), end_time=time(15), ability_level='level1',
        )
        for status in ('manually_assigned', 'completed', 'completed'):
            group = ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus, user=self.user)
            self.add_lesson(day, template=self.full_day, shared_class=shared, coach_fee=100, group=group, status=status)
        summary = self.summary(month='2026-12')
        self.assert_discipline(summary['actual'], 'snowboard', hours=15, count=3, amount=1200)
        self.assert_discipline(summary['estimated'], 'snowboard', hours=0, count=1, amount=400)

    def test_month_boundary_and_visible_window_use_taipei_dates(self):
        self.add_lesson(date(2026, 11, 30), template=self.half_day)
        self.add_lesson(date(2026, 12, 11), template=self.half_day, status='manually_assigned')
        self.add_lesson(date(2026, 12, 12), template=self.half_day, status='manually_assigned')
        self.add_lesson(date(2027, 1, 1), template=self.half_day, status='manually_assigned')
        self.coach.schedule_visibility = 'recent_10_days'
        self.coach.save(update_fields=['schedule_visibility'])
        before_midnight = datetime(2026, 11, 30, 15, 59, tzinfo=timezone.utc)
        midnight = datetime(2026, 11, 30, 16, tzinfo=timezone.utc)
        with patch('django.utils.timezone.now', return_value=before_midnight):
            november = self.summary()
        with patch('django.utils.timezone.now', return_value=midnight):
            december = self.summary()
            january = self.summary(month='2027-01')
        self.assertEqual((november['month'], november['actual']['total_hours']), ('2026-11', 3))
        self.assertEqual((december['month'], december['actual']['total_hours']), ('2026-12', 10))
        self.assert_discipline(december['estimated'], 'ski', hours=3, count=0, amount=0)
        self.assertEqual(january['estimated']['total_hours'], 0)

    def test_scope_ignores_other_coaches_other_tenants_and_inactive_bookings(self):
        other_coach = Coach.objects.create(client=self.client_tenant, name='其他教練')
        other_tenant = Client.objects.create(internal_code='other', name='其他租戶')
        other_group = ReservationGroup.objects.create(client=other_tenant, user=self.user)
        day = date(2026, 12, 6)
        self.add_lesson(day, template=self.half_day, coach=other_coach, coach_fee=100)
        self.add_lesson(day, template=self.half_day, group=other_group, coach_fee=100)
        self.add_lesson(day, template=self.half_day, status='cancelled')
        self.add_lesson(day, template=self.half_day, status='deleted')
        archived = self.add_lesson(day, template=self.half_day)
        archived.is_deleted = True
        archived.save(update_fields=['is_deleted'])
        summary = self.summary(month='2026-12', coach_id=other_coach.pk)
        self.assertEqual(summary['actual']['total_hours'], 10)
        self.assertEqual(summary['estimated']['total_hours'], 0)
        self.assertEqual(self.api.get(self.url.replace('/snowland/', '/other/')).status_code, 403)
        self.api.force_authenticate(User.objects.create_superuser('hq-summary'))
        self.assertEqual(self.api.get(self.url).status_code, 403)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.get(self.url).status_code, 403)

    def test_missing_or_ambiguous_fee_rules_leave_hours_and_report_unresolved_groups(self):
        day = date(2026, 12, 8)
        self.add_lesson(day, template=self.half_day, coach_fee=100, status='auto_assigned')
        self.add_lesson(day, template=self.half_day, is_preferred_coach=True)
        for level in ('L1', 'L2'):
            CoachPayRule.objects.create(
                coach=self.coach, discipline='ski', hourly_rate=1000, specified_fee=650, certification_level=level,
            )
        summary = self.summary(month='2026-12')
        self.assert_discipline(summary['actual'], 'ski', hours=3, count=0, amount=0)
        self.assert_discipline(summary['estimated'], 'ski', hours=3, count=0, amount=0)
        self.assertEqual(summary['actual']['unresolved_specified_count'], 1)
        self.assertEqual(summary['estimated']['unresolved_specified_count'], 1)

    def test_blank_template_hours_follow_schedule_and_zero_is_respected(self):
        fallback = CourseTemplate.objects.create(course_type=self.ski, name='時段', duration_hours=4)
        zero = CourseTemplate.objects.create(course_type=self.ski, name='零時數', duration_hours=4, payroll_hours=0)
        self.add_lesson(date(2026, 12, 3), template=fallback, end=time(13, 1))
        self.add_lesson(date(2026, 12, 4), template=zero)
        self.assert_discipline(self.summary(month='2026-12')['actual'], 'ski', hours=4.02, count=0, amount=0)

    def test_tenant_can_restore_scheduled_summary_and_invalid_month_is_rejected(self):
        module, _ = ModuleInfo.objects.get_or_create(module_sid='booking', defaults={'module_name': '預約'})
        other = Client.objects.create(internal_code='other', name='其他租戶')
        config = {'coach_course_payroll_summary_enabled': False}
        ModuleSetting.objects.create(client=other, module=module, settings=config)
        self.assertEqual(self.summary(month='2026-12')['mode'], 'payroll')
        ModuleSetting.objects.create(client=self.client_tenant, module=module, settings=config)
        self.assertEqual(self.summary(month='2026-12'), {'month': '2026-12', 'mode': 'scheduled'})
        for month in ('', '2026-1', '2026-13', '2026-12-01'):
            with self.subTest(month=month):
                self.assertEqual(self.api.get(self.url, {'month': month}).status_code, 400)
