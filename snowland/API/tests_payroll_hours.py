from datetime import time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Coach.models import CoachPayRule
from Coach.payroll import add_payroll_adjustment, calculate_payroll_statement
from Coursekit.models import CourseTemplate
from booking.models import Booking, Reservation, SharedCourseClass


class PayrollHoursTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.template = CourseTemplate.objects.create(course_type=self.course_type, name='QA 全天', duration_hours=6)
        self.reservation.course_template = self.template
        self.reservation.save(update_fields=['course_template'])
        self.booking_1.end_time = time(15); self.booking_1.save(update_fields=['end_time'])
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
        self.admin = User.objects.create_superuser('qa-hours-hq', 'qa-hours-hq@example.test', 'QA-only')
        self.api = APIClient(); self.api.force_authenticate(self.admin)
        self.url = f'/api/admin/snowland/course-templates/{self.template.pk}/'

    def calculate(self):
        return calculate_payroll_statement(coach=self.coach, campus=self.campus,
            period_start=self.booking_1.date, period_end=self.booking_1.date)

    def test_null_preserves_legacy_scheduled_hours(self):
        statement = self.calculate()
        line = statement.lines.get(line_type='course')
        self.assertEqual(statement.course_pay, 6000)
        self.assertEqual(line.quantity, Decimal('6'))
        self.assertEqual(line.metadata['scheduled_hours'], '6')
        self.assertEqual(line.metadata['payroll_hours_source'], 'schedule')

    def test_full_day_five_payroll_hours_does_not_change_six_hour_schedule_or_customer_price(self):
        response = self.api.patch(self.url, {'payroll_hours': '5'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        statement = self.calculate()
        self.assertEqual(statement.course_pay, 5000)
        line = statement.lines.get(line_type='course')
        self.assertEqual(line.quantity, Decimal('5'))
        self.assertEqual(line.metadata['scheduled_hours'], '6')
        self.assertEqual(line.metadata['payroll_hours_source'], 'template')
        self.booking_1.refresh_from_db(); self.reservation.refresh_from_db(); self.template.refresh_from_db()
        self.assertEqual((self.booking_1.start_time, self.booking_1.end_time), (time(9), time(15)))
        self.assertEqual(self.template.duration_hours, 6)
        self.assertEqual(self.reservation.course_fee, 10000)

    def test_half_day_fractional_zero_and_reset_to_actual_hours(self):
        for value, expected in [('3', 3000), ('2.50', 2500), ('0', 0), (None, 6000)]:
            response = self.api.patch(self.url, {'payroll_hours': value}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(self.calculate().course_pay, expected)

    def test_invalid_hours_are_rejected_without_changing_template(self):
        for value in [-1, 25, '2.555', 'NaN', 'Infinity', True, 'bad']:
            response = self.api.patch(self.url, {'payroll_hours': value}, format='json')
            self.assertEqual(response.status_code, 400, (value, response.data))
            self.template.refresh_from_db(); self.assertIsNone(self.template.payroll_hours)

    def test_course_editor_without_payroll_permission_can_edit_name_but_not_hours(self):
        editor = User.objects.create_user('qa-course-editor')
        profile = editor.userprofile
        profile.is_manager = True; profile.manager_client = self.client_tenant
        profile.role = 'hq_admin'; profile.admin_permissions = ['course_types']; profile.save()
        self.api.force_authenticate(editor)
        self.assertEqual(self.api.patch(self.url, {'name': 'QA 改名'}, format='json').status_code, 200)
        response = self.api.patch(self.url, {'payroll_hours': '5'}, format='json')
        self.assertEqual(response.status_code, 403, response.data)
        self.assertFalse(self.api.get(self.url).data['can_manage_payroll_hours'])

    def test_other_tenant_cannot_change_hours(self):
        from Client.models import Client
        Client.objects.create(name='QA other', internal_code='other')
        response = self.api.patch(self.url.replace('/snowland/', '/other/'), {'payroll_hours': '5'}, format='json')
        self.assertEqual(response.status_code, 404, response.data)

    def test_confirmed_snapshot_does_not_change_when_template_changes(self):
        statement = self.calculate()
        statement.status = 'confirmed'; statement.save(update_fields=['status'])
        self.api.patch(self.url, {'payroll_hours': '5'}, format='json')
        statement.refresh_from_db()
        self.assertEqual(statement.course_pay, 6000)
        self.assertEqual(statement.lines.get(line_type='course').quantity, Decimal('6'))
        with self.assertRaisesMessage(ValueError, '已確認或已發放'):
            self.calculate()

    def test_recalculation_keeps_manual_adjustment_and_updates_hour_snapshot(self):
        statement = self.calculate()
        add_payroll_adjustment(statement=statement, description='QA 加給', amount=200)
        self.api.patch(self.url, {'payroll_hours': '5'}, format='json')
        statement = self.calculate()
        self.assertEqual(statement.total_amount, 5200)
        self.assertEqual(statement.adjustment, 200)
        self.assertEqual(statement.lines.filter(line_type='course').count(), 1)

    def test_shared_class_payroll_hours_are_counted_once_not_per_order(self):
        self.template.payroll_hours = Decimal('5'); self.template.save()
        shared = SharedCourseClass.objects.create(client=self.client_tenant, campus=self.campus, resort=self.resort,
            template=self.template, date=self.booking_1.date, start_time=time(9), end_time=time(15), ability_level='level1')
        self.reservation.shared_course_class = shared; self.reservation.save(update_fields=['shared_course_class'])
        other = Reservation.objects.create(group=self.group, course_type=self.course_type, course_template=self.template,
            preferred_coach=self.coach, shared_course_class=shared, status='completed')
        Booking.objects.create(reservation=other, date=self.booking_1.date, start_time=time(9), end_time=time(15), is_scheduled=True)
        statement = self.calculate()
        self.assertEqual(statement.course_pay, 5000)
        self.assertEqual(statement.lines.filter(line_type='course').count(), 1)
