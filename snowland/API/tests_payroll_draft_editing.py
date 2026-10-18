from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Coach.models import CoachPayRule, PayrollLine, PayrollStatement
from Coach.payroll import add_payroll_adjustment, calculate_payroll_statement
from Resorts.models import Campus


class PayrollDraftEditingTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.admin = User.objects.create_superuser('qa-payroll-hq', 'qa-payroll-hq@example.test', 'QA-only')
        self.api = APIClient(); self.api.force_authenticate(self.admin)
        self.statement = PayrollStatement.objects.create(coach=self.coach, campus=self.campus,
            period_start=self.booking_1.date, period_end=self.booking_2.date, course_pay=1000, total_amount=1000)
        self.line = add_payroll_adjustment(statement=self.statement, description='QA allowance', amount=200)
        self.url = f'/api/admin/snowland/payroll-statements/{self.statement.pk}/'
        self.edit = self.url+f'adjustments/{self.line.pk}/edit/'
        self.remove = self.url+f'adjustments/{self.line.pk}/remove/'

    def test_edit_and_remove_recalculate_totals_without_duplicate_lines(self):
        response = self.api.post(self.edit, {'description': 'QA revised', 'amount': -100}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['total_amount'], 900)
        self.assertEqual(response.data['data']['adjustment'], -100)
        self.line.refresh_from_db(); self.assertEqual(self.line.description, 'QA revised')
        self.assertEqual(self.statement.lines.count(), 1)
        response = self.api.post(self.remove, {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['total_amount'], 1000)
        self.assertEqual(response.data['data']['adjustment'], 0)
        self.assertFalse(PayrollLine.objects.filter(pk=self.line.pk).exists())

    def test_invalid_or_excessive_deduction_does_not_mutate(self):
        for amount in [-1001, '1.5', True, 0, 10000001, None]:
            response = self.api.post(self.edit, {'description': 'QA invalid', 'amount': amount}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.line.refresh_from_db(); self.statement.refresh_from_db()
            self.assertEqual(self.line.total_amount, 200)
            self.assertEqual(self.statement.total_amount, 1200)

    def test_removing_positive_adjustment_cannot_make_existing_deductions_negative(self):
        add_payroll_adjustment(statement=self.statement, description='QA deduction', amount=-1150)
        response = self.api.post(self.remove, {}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.statement.refresh_from_db()
        self.assertEqual(self.statement.total_amount, 50)
        self.assertEqual(self.statement.lines.count(), 2)

    def test_confirmed_and_paid_are_locked_for_edit_remove_delete_and_recalculate(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000)
        for status in ['confirmed', 'paid']:
            self.statement.status = status; self.statement.save(update_fields=['status'])
            self.assertEqual(self.api.post(self.edit, {'description': 'QA', 'amount': 100}, format='json').status_code, 400)
            self.assertEqual(self.api.post(self.remove, {}, format='json').status_code, 400)
            self.assertEqual(self.api.delete(self.url).status_code, 400)
            with self.assertRaisesMessage(ValueError, '已確認或已發放'):
                calculate_payroll_statement(coach=self.coach, campus=self.campus,
                    period_start=self.statement.period_start, period_end=self.statement.period_end)
            self.statement.refresh_from_db(); self.line.refresh_from_db()
            self.assertEqual(self.statement.total_amount, 1200)
            self.assertEqual(self.line.total_amount, 200)

    def test_course_or_other_statement_lines_cannot_be_edited(self):
        course = PayrollLine.objects.create(statement=self.statement, line_type='course', description='QA course', total_amount=1000)
        other = PayrollStatement.objects.create(coach=self.coach, campus=self.campus,
            period_start=self.booking_1.date.replace(year=self.booking_1.date.year+1),
            period_end=self.booking_2.date.replace(year=self.booking_2.date.year+1))
        foreign = PayrollLine.objects.create(statement=other, line_type='adjustment', description='QA other', total_amount=100)
        for line in [course, foreign]:
            response = self.api.post(self.url+f'adjustments/{line.pk}/edit/', {'description': 'QA', 'amount': 10}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(self.api.post(self.url+f'adjustments/{line.pk}/remove/', {}, format='json').status_code, 400)

    def test_member_and_coach_cannot_manage_salary(self):
        for user in [self.user, self.coach_user]:
            self.api.force_authenticate(user)
            self.assertEqual(self.api.post(self.edit, {'description': 'QA', 'amount': 10}, format='json').status_code, 403)
            self.assertEqual(self.api.post(self.remove, {}, format='json').status_code, 403)
            self.assertEqual(self.api.delete(self.url).status_code, 403)

    def test_selected_other_campus_cannot_edit_or_delete(self):
        other = Campus.objects.create(client=self.client_tenant, name='QA other', code='qa-other')
        headers = {'HTTP_X_CAMPUS_ID': str(other.pk)}
        self.assertEqual(self.api.post(self.edit, {'description': 'QA', 'amount': 10}, format='json', **headers).status_code, 404)
        self.assertEqual(self.api.post(self.remove, {}, format='json', **headers).status_code, 404)
        self.assertEqual(self.api.delete(self.url, **headers).status_code, 404)

    def test_delete_draft_only_removes_statement_and_lines_not_courses(self):
        reservation_id = self.reservation.pk
        self.assertEqual(self.api.delete(self.url).status_code, 204)
        self.assertFalse(PayrollStatement.objects.filter(pk=self.statement.pk).exists())
        self.assertFalse(PayrollLine.objects.filter(pk=self.line.pk).exists())
        self.assertTrue(self.reservation.__class__.objects.filter(pk=reservation_id).exists())

    def test_general_patch_and_post_cannot_bypass_financial_operations(self):
        self.assertEqual(self.api.patch(self.url, {'total_amount': 9999, 'status': 'paid'}, format='json').status_code, 405)
        self.assertEqual(self.api.post('/api/admin/snowland/payroll-statements/', {'total_amount': 9999}, format='json').status_code, 405)

    def test_recalculation_preserves_edited_manual_line(self):
        self.api.post(self.edit, {'description': 'QA revised', 'amount': -100}, format='json')
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
        result = calculate_payroll_statement(coach=self.coach, campus=self.campus,
            period_start=self.statement.period_start, period_end=self.statement.period_end)
        self.assertEqual(result.course_pay, 4000)
        self.assertEqual(result.total_amount, 3900)
        self.assertEqual(result.lines.filter(line_type='adjustment').count(), 1)
