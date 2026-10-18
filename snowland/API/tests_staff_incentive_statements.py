from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Coach import tests_staff_incentives as fixtures
from Coach.models import StaffIncentiveStatement
from Coach.staff_incentives import adjust_staff_incentive
from Client.models import Client
from Resorts.models import Campus


class StaffIncentiveStatementApiTests(TestCase):
    url = '/api/admin/snowland/staff-incentive-statements/'

    def setUp(self):
        fixtures.StaffIncentiveCalculationTests.setUp(self)
        self.hq = User.objects.create_superuser('bonus-hq', 'bonus-hq@example.test', 'QA-only')
        self.api = APIClient()
        self.api.force_authenticate(self.hq)
        self.data = {'user': self.employee.pk, 'campus': self.campus.pk, 'month': '2026-01-01'}

    def calculate(self):
        result = self.api.post(self.url + 'calculate/', self.data, format='json')
        self.assertEqual(result.status_code, 200, getattr(result, 'data', result.content))
        return result.data['data']

    def ack(self, detail):
        return {'accepted': True, 'expected_updated_at': self.api.get(detail).data['updated_at']}

    def test_calculate_adjust_confirm_record_payment_and_retrieve_snapshot(self):
        row = self.calculate()
        detail = f"{self.url}{row['id']}/"
        self.assertEqual(row['earned_amount'], 250)
        self.assertEqual(row['currency'], 'TWD')
        adjusted = self.api.post(detail + 'adjust/', {'amount': -30, 'note': 'QA 調整'}, format='json')
        self.assertEqual(adjusted.status_code, 200, adjusted.data)
        self.assertEqual(adjusted.data['data']['total_amount'], 220)
        self.assertEqual(self.api.post(detail + 'confirm/', self.ack(detail), format='json').status_code, 200)
        self.assertEqual(self.api.post(detail + 'record-paid/', self.ack(detail), format='json').status_code, 200)
        final = self.api.get(detail)
        self.assertEqual(final.status_code, 200)
        self.assertEqual(final.data['status'], 'paid')
        self.assertEqual(final.data['total_amount'], 220)
        self.assertEqual(final.data['confirmed_by'], self.hq.pk)
        self.assertEqual(final.data['paid_by'], self.hq.pk)
        for operation, body in [('adjust/', {'amount': 1, 'note': 'QA'}), ('recalculate/', {})]:
            self.assertEqual(self.api.post(detail + operation, body, format='json').status_code, 400)
        self.assertEqual(self.api.delete(detail).status_code, 400)

    def test_arbitrary_create_patch_and_confirm_without_acknowledgement_are_rejected(self):
        row = self.calculate()
        detail = f"{self.url}{row['id']}/"
        self.assertEqual(self.api.post(self.url, self.data, format='json').status_code, 405)
        self.assertEqual(self.api.patch(detail, {'total_amount': 999}, format='json').status_code, 405)
        for payload in [{}, {'accepted': False}]:
            self.assertEqual(self.api.post(detail + 'confirm/', payload, format='json').status_code, 400)
        self.assertEqual(self.api.post(detail + 'record-paid/', {'accepted': True}, format='json').status_code, 400)

    def test_invalid_month_and_adjustment_leave_existing_statement_unchanged(self):
        row = self.calculate()
        detail = f"{self.url}{row['id']}/"
        for value in ['2026-01-02', 'bad', None, True]:
            response = self.api.post(self.url + 'calculate/', {**self.data, 'month': value}, format='json')
            self.assertEqual(response.status_code, 400, getattr(response, 'data', response.content))
        for value in [True, 'NaN', 1.5]:
            self.assertEqual(self.api.post(detail + 'adjust/', {'amount': value, 'note': 'QA'}, format='json').status_code, 400)
        self.assertEqual(self.api.get(detail).data['total_amount'], 250)
        self.assertEqual(StaffIncentiveStatement.objects.count(), 1)

    def test_other_company_or_selected_campus_cannot_read_calculate_or_delete(self):
        row = self.calculate()
        other = Client.objects.create(name='Other bonus', internal_code='other-bonus')
        foreign = Campus.objects.create(client=other, name='Foreign', code='foreign')
        self.assertEqual(self.api.get(f"/api/admin/other-bonus/staff-incentive-statements/{row['id']}/").status_code, 404)
        response = self.api.post(self.url + 'calculate/', {**self.data, 'campus': foreign.pk}, format='json')
        self.assertEqual(response.status_code, 404)
        other_campus = Campus.objects.create(client=self.client_tenant, name='B', code='b')
        self.assertEqual(self.api.get(f"{self.url}{row['id']}/", HTTP_X_CAMPUS_ID=str(other_campus.pk)).status_code, 404)
        self.assertEqual(self.api.post(self.url + 'calculate/', self.data, format='json', HTTP_X_CAMPUS_ID=str(other_campus.pk)).status_code, 404)
        self.assertEqual(self.api.delete(f"{self.url}{row['id']}/", HTTP_X_CAMPUS_ID=str(other_campus.pk)).status_code, 404)

    def test_staff_without_payroll_permission_cannot_access_statements(self):
        row = self.calculate()
        self.api.force_authenticate(self.employee)
        for path in [self.url, f"{self.url}{row['id']}/"]:
            self.assertEqual(self.api.get(path).status_code, 403)
        self.assertEqual(self.api.post(self.url + 'calculate/', self.data, format='json').status_code, 403)

    def test_confirm_and_record_payment_are_idempotent_and_draft_deletion_is_allowed(self):
        row = self.calculate()
        detail = f"{self.url}{row['id']}/"
        self.assertEqual(self.api.delete(detail).status_code, 204)
        self.assertFalse(StaffIncentiveStatement.objects.exists())
        row = self.calculate()
        detail = f"{self.url}{row['id']}/"
        for action, field in [('confirm/', 'confirmed_at'), ('record-paid/', 'paid_at')]:
            payload = self.ack(detail)
            first = self.api.post(detail + action, payload, format='json')
            second = self.api.post(detail + action, payload, format='json')
            self.assertEqual(first.status_code, 200, first.data)
            self.assertEqual(second.data['data'][field], first.data['data'][field])

    def test_cookie_authenticated_writes_require_csrf(self):
        from django.test import Client as BrowserClient
        import json
        browser = BrowserClient(enforce_csrf_checks=True)
        browser.force_login(self.hq)
        self.assertEqual(browser.post(self.url + 'calculate/', json.dumps(self.data), content_type='application/json').status_code, 403)
        self.assertEqual(browser.get(self.url).status_code, 200)
        response = browser.post(self.url + 'calculate/', json.dumps(self.data), content_type='application/json', HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200, response.content)

    def test_stale_page_cannot_confirm_an_unseen_changed_amount(self):
        row = self.calculate()
        detail = f"{self.url}{row['id']}/"
        old = self.ack(detail)
        statement = StaffIncentiveStatement.objects.get(pk=row['id'])
        adjust_staff_incentive(statement, amount=500, note='QA 另一位管理員更新')
        response = self.api.post(detail + 'confirm/', old, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        statement.refresh_from_db()
        self.assertEqual(statement.status, 'draft')
        self.assertEqual(statement.total_amount, 750)
