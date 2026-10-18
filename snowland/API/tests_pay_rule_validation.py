from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Coach.models import CoachPayRule
from Coach.payroll import calculate_payroll_statement


class PayRuleValidationTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.api = APIClient()
        self.api.force_authenticate(User.objects.create_superuser('qa-rules', 'qa-rules@example.test', 'QA-only'))
        self.rule = CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000)
        self.url = f'/api/admin/snowland/coach-pay-rules/{self.rule.pk}/'

    def test_referral_percentage_outside_zero_to_one_hundred_is_rejected_without_mutation(self):
        for value in ['-0.01', '100.01']:
            response = self.api.patch(self.url, {'referral_percent': value}, format='json')
            self.assertEqual(response.status_code, 400, (value, response.data))
            self.rule.refresh_from_db()
            self.assertEqual(self.rule.referral_percent, 10)

    def test_assistance_hours_cannot_be_negative(self):
        response = self.api.patch(self.url, {'assistance_hour_factor': '-0.01'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.rule.refresh_from_db()
        self.assertEqual(str(self.rule.assistance_hour_factor), '0.50')

    def test_zero_and_percentage_boundaries_are_valid(self):
        for value in ['0', '100']:
            response = self.api.patch(self.url, {'referral_percent': value, 'assistance_hour_factor': '0', 'hourly_rate': 0}, format='json')
            self.assertEqual(response.status_code, 200, response.data)

    def test_edit_retains_identity_and_can_disable_without_creating_a_second_rule(self):
        response = self.api.patch(self.url, {'hourly_rate': 1500, 'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.hourly_rate, 1500)
        self.assertFalse(self.rule.is_active)
        self.assertEqual(CoachPayRule.objects.filter(coach=self.coach).count(), 1)

    def test_legacy_invalid_rule_blocks_calculation_instead_of_silently_skipping_pay(self):
        for changes in [{'referral_percent': -1}, {'referral_percent': 101}, {'assistance_hour_factor': -1}]:
            CoachPayRule.objects.filter(pk=self.rule.pk).update(referral_percent=10, assistance_hour_factor='0.5')
            CoachPayRule.objects.filter(pk=self.rule.pk).update(**changes)
            with self.assertRaisesMessage(ValueError, '薪資規則'):
                calculate_payroll_statement(coach=self.coach, campus=self.campus,
                    period_start=self.booking_1.date, period_end=self.booking_2.date)
            self.assertFalse(self.coach.payroll_statements.exists())

    def test_browser_rate_changes_require_csrf_issued_by_rule_read(self):
        from django.test import Client as BrowserClient
        browser = BrowserClient(enforce_csrf_checks=True); browser.force_login(User.objects.get(username='qa-rules'))
        self.assertEqual(browser.patch(self.url, {'hourly_rate':1500}, content_type='application/json').status_code, 403)
        self.assertEqual(browser.get(self.url).status_code, 200)
        response = browser.patch(self.url, {'hourly_rate':1500}, content_type='application/json', HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200, response.content)
        self.rule.refresh_from_db(); self.assertEqual(self.rule.hourly_rate, 1500)

    def calculate(self):
        return calculate_payroll_statement(coach=self.coach,campus=self.campus,
            period_start=self.booking_1.date,period_end=self.booking_2.date)

    def test_ambiguous_legacy_rules_do_not_silently_pick_first_or_change_existing_draft(self):
        statement = self.calculate()
        before = list(statement.lines.values_list('pk','total_amount'))
        amount = statement.total_amount
        CoachPayRule.objects.create(coach=self.coach,discipline='snowboard',certification_level='Lv3',hourly_rate=3000)
        with self.assertRaisesMessage(ValueError,'多筆啟用'):
            self.calculate()
        statement.refresh_from_db()
        self.assertEqual(statement.total_amount,amount)
        self.assertEqual(list(statement.lines.values_list('pk','total_amount')),before)

    def test_new_conflicting_active_rule_is_rejected_without_creating_it(self):
        response = self.api.post('/api/admin/snowland/coach-pay-rules/',{
            'coach':self.coach.pk,'discipline':'snowboard','certification_level':'Lv3','hourly_rate':3000,'is_active':True},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(CoachPayRule.objects.filter(coach=self.coach).count(),1)

    def test_inactive_rule_can_be_saved_then_enabled_only_after_old_rule_is_disabled(self):
        other = CoachPayRule.objects.create(coach=self.coach,discipline='snowboard',certification_level='Lv3',hourly_rate=2000,is_active=False)
        url = f'/api/admin/snowland/coach-pay-rules/{other.pk}/'
        self.assertEqual(self.api.patch(url,{'is_active':True},format='json').status_code,400)
        other.refresh_from_db(); self.assertFalse(other.is_active)
        self.assertEqual(self.api.patch(self.url,{'is_active':False},format='json').status_code,200)
        self.assertEqual(self.api.patch(url,{'is_active':True},format='json').status_code,200)
        self.assertEqual(self.calculate().course_pay,8000)

    def test_specific_course_rule_overrides_generic_without_conflict(self):
        response = self.api.post('/api/admin/snowland/coach-pay-rules/',{
            'coach':self.coach.pk,'course_type':self.course_type.pk,'discipline':'snowboard','certification_level':'Lv3','hourly_rate':1500},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(self.calculate().course_pay,6000)

    def test_ambiguous_specific_rules_cannot_fall_back_to_generic(self):
        for level in ['Lv2','Lv3']:
            CoachPayRule.objects.create(coach=self.coach,course_type=self.course_type,discipline='snowboard',certification_level=level,hourly_rate=2000)
        with self.assertRaisesMessage(ValueError,'多筆啟用'):
            self.calculate()
        self.assertFalse(self.coach.payroll_statements.exists())

    def test_deleting_rule_keeps_calculated_payroll_snapshot_and_failed_recalculation_intact(self):
        statement = self.calculate()
        before = list(statement.lines.values_list('pk', 'total_amount'))
        amount = statement.total_amount
        response = self.api.delete(self.url)
        self.assertEqual(response.status_code, 204, response.data)
        self.assertFalse(CoachPayRule.objects.filter(pk=self.rule.pk).exists())
        with self.assertRaisesMessage(ValueError, '尚未設定薪資規則'):
            self.calculate()
        statement.refresh_from_db()
        self.assertEqual(statement.total_amount, amount)
        self.assertEqual(list(statement.lines.values_list('pk', 'total_amount')), before)

    def test_browser_rule_deletion_requires_csrf_and_does_not_delete_on_rejection(self):
        from django.test import Client as BrowserClient
        browser = BrowserClient(enforce_csrf_checks=True)
        browser.force_login(User.objects.get(username='qa-rules'))
        self.assertEqual(browser.delete(self.url).status_code, 403)
        self.assertTrue(CoachPayRule.objects.filter(pk=self.rule.pk).exists())
        self.assertEqual(browser.get(self.url).status_code, 200)
        response = browser.delete(self.url, HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(CoachPayRule.objects.filter(pk=self.rule.pk).exists())

    def test_different_work_types_can_each_have_an_active_rule(self):
        response = self.api.post('/api/admin/snowland/coach-pay-rules/', {
            'coach': self.coach.pk, 'discipline': 'ski', 'hourly_rate': 2000,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(CoachPayRule.objects.filter(coach=self.coach, is_active=True).count(), 2)
        self.assertEqual(self.calculate().course_pay, 4000)

    def test_changing_specific_rule_to_conflicting_generic_preserves_original_rule(self):
        other = CoachPayRule.objects.create(
            coach=self.coach, course_type=self.course_type, discipline='snowboard',
            certification_level='Lv3', hourly_rate=2000,
        )
        response = self.api.patch(f'/api/admin/snowland/coach-pay-rules/{other.pk}/', {
            'course_type': None,
        }, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        other.refresh_from_db()
        self.assertEqual(other.course_type_id, self.course_type.pk)
        self.assertEqual(other.hourly_rate, 2000)
        self.assertEqual(self.calculate().course_pay, 8000)
