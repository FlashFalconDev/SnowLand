from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import StaffIncentiveRule
from Control.models import UserProfile
from Resorts.models import Campus


class StaffIncentiveRuleTests(TestCase):
    url = '/api/admin/snowland/staff-incentive-rules/'

    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.other = Client.objects.create(name='Other', internal_code='other')
        self.a = Campus.objects.create(client=self.tenant, name='A', code='a')
        self.b = Campus.objects.create(client=self.tenant, name='B', code='b')
        self.foreign = Campus.objects.create(client=self.other, name='Other', code='other')
        self.hq = User.objects.create_superuser('incentive-hq', 'incentive-hq@example.test', 'QA-only')
        self.manager = self.staff('manager', self.tenant, self.a, ['payroll'])
        self.employee = self.staff('employee', self.tenant, self.a, [])
        self.outside_employee = self.staff('outside', self.other, self.foreign, ['payroll'])
        self.api = APIClient()
        self.api.force_authenticate(self.hq)

    def staff(self, name, tenant, campus, permissions):
        user = User.objects.create_user(name, f'{name}@example.test', 'QA-only')
        profile = UserProfile.objects.get(user=user)
        profile.is_manager = True
        profile.manager_client = tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = permissions
        profile.save()
        profile.campuses.add(campus)
        user.refresh_from_db()
        return user

    def data(self, **changes):
        return {'user': self.employee.pk, 'campus': self.a.pk,
                'completed_order_percent': '2.50', 'is_active': True, **changes}

    def test_create_edit_reload_and_disable_without_duplicate(self):
        response = self.api.post(self.url, self.data(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        detail = f"{self.url}{response.data['id']}/"
        self.assertEqual(self.api.patch(detail, {'completed_order_percent': '3.25', 'is_active': False}, format='json').status_code, 200)
        stored = self.api.get(detail)
        self.assertEqual(stored.status_code, 200)
        self.assertEqual(stored.data['completed_order_percent'], '3.25')
        self.assertFalse(stored.data['is_active'])
        self.assertEqual(StaffIncentiveRule.objects.count(), 1)

    def test_invalid_percentages_do_not_create_data(self):
        for value in ['-0.01', '100.01', 'NaN', 'Infinity', True, '1.001']:
            response = self.api.post(self.url, self.data(completed_order_percent=value), format='json')
            self.assertEqual(response.status_code, 400, (value, response.data))
        self.assertFalse(StaffIncentiveRule.objects.exists())

    def test_zero_and_one_hundred_percent_are_supported(self):
        for value in ['0', '100']:
            response = self.api.post(self.url, self.data(completed_order_percent=value), format='json')
            self.assertEqual(response.status_code, 201, response.data)
            StaffIncentiveRule.objects.get(pk=response.data['id']).delete()

    def test_duplicate_employee_campus_is_explained_not_server_error(self):
        self.assertEqual(self.api.post(self.url, self.data(), format='json').status_code, 201)
        response = self.api.post(self.url, self.data(), format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(StaffIncentiveRule.objects.count(), 1)

    def test_rejects_other_company_unassigned_inactive_and_nonstaff_users(self):
        ordinary = User.objects.create_user('ordinary')
        inactive = self.staff('inactive', self.tenant, self.a, [])
        inactive.is_active = False
        inactive.save(update_fields=['is_active'])
        for changes in [{'user': self.outside_employee.pk}, {'campus': self.foreign.pk},
                        {'campus': self.b.pk}, {'user': ordinary.pk}, {'user': inactive.pk}]:
            response = self.api.post(self.url, self.data(**changes), format='json')
            self.assertEqual(response.status_code, 400, (changes, response.data))
        self.assertFalse(StaffIncentiveRule.objects.exists())

    def test_campus_manager_can_only_manage_current_scope(self):
        a = StaffIncentiveRule.objects.create(user=self.employee, campus=self.a, completed_order_percent=2)
        self.employee.userprofile.campuses.add(self.b)
        b = StaffIncentiveRule.objects.create(user=self.employee, campus=self.b, completed_order_percent=4)
        self.api.force_authenticate(self.manager)
        rows = self.api.get(self.url)
        self.assertEqual(rows.status_code, 200, rows.data)
        self.assertEqual([row['id'] for row in rows.data['data']['list']], [a.pk])
        self.assertEqual(self.api.get(f'{self.url}{b.pk}/').status_code, 404)
        self.assertEqual(self.api.patch(f'{self.url}{a.pk}/', {'campus': self.b.pk}, format='json').status_code, 403)
        a.refresh_from_db()
        self.assertEqual(a.campus_id, self.a.pk)

    def test_members_and_staff_without_payroll_permission_cannot_read_or_write(self):
        for actor in [User.objects.create_user('member'), self.employee]:
            self.api.force_authenticate(actor)
            self.assertEqual(self.api.get(self.url).status_code, 403)
            self.assertEqual(self.api.post(self.url, self.data(), format='json').status_code, 403)

    def test_cross_company_rule_is_not_readable_or_mutable(self):
        rule = StaffIncentiveRule.objects.create(user=self.outside_employee, campus=self.foreign)
        detail = f'{self.url}{rule.pk}/'
        self.assertEqual(self.api.get(detail).status_code, 404)
        self.assertEqual(self.api.patch(detail, {'completed_order_percent': 5}, format='json').status_code, 404)
        self.assertEqual(self.api.delete(detail).status_code, 404)

    def test_browser_writes_require_csrf_issued_by_safe_read(self):
        from django.test import Client as BrowserClient
        import json
        browser = BrowserClient(enforce_csrf_checks=True)
        browser.force_login(self.hq)
        self.assertEqual(browser.post(self.url, json.dumps(self.data()), content_type='application/json').status_code, 403)
        self.assertEqual(browser.get(self.url).status_code, 200)
        token = browser.cookies['csrftoken'].value
        response = browser.post(self.url, json.dumps(self.data()), content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201, response.content)
        detail = f"{self.url}{response.json()['id']}/"
        self.assertEqual(browser.delete(detail).status_code, 403)
        self.assertEqual(browser.delete(detail, HTTP_X_CSRFTOKEN=token).status_code, 204)

    def test_employee_choices_are_scoped_without_exposing_contact_information(self):
        self.api.force_authenticate(self.manager)
        result = self.api.get(self.url + 'employees/')
        self.assertEqual(result.status_code, 200, result.data)
        data = result.data['data']
        self.assertEqual(data['campuses'], [{'id': self.a.pk, 'name': 'A'}])
        self.assertEqual({row['id'] for row in data['employees']}, {self.employee.pk, self.manager.pk})
        for row in data['employees']:
            self.assertEqual(row['campus_ids'], [self.a.pk])
            self.assertEqual(set(row), {'id', 'name', 'campus_ids'})

    def test_headquarters_selected_campus_cannot_be_ignored_on_write(self):
        self.employee.userprofile.campuses.add(self.b)
        response = self.api.post(self.url, self.data(campus=self.b.pk), format='json', HTTP_X_CAMPUS_ID=str(self.a.pk))
        self.assertEqual(response.status_code, 403, response.data)
        self.assertFalse(StaffIncentiveRule.objects.exists())

    def test_departed_employee_rule_can_be_disabled_but_not_reenabled(self):
        rule = StaffIncentiveRule.objects.create(user=self.employee, campus=self.a, completed_order_percent=2)
        self.employee.is_active = False
        self.employee.save(update_fields=['is_active'])
        detail = f'{self.url}{rule.pk}/'
        response = self.api.patch(detail, {'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.api.patch(detail, {'is_active': True}, format='json').status_code, 400)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)

    def test_disabled_campus_rule_can_be_disabled_without_changing_identity(self):
        rule = StaffIncentiveRule.objects.create(user=self.employee, campus=self.a, completed_order_percent=2)
        self.a.is_active = False
        self.a.save(update_fields=['is_active'])
        detail = f'{self.url}{rule.pk}/'
        response = self.api.patch(detail, {'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.api.patch(detail, {'is_active': True}, format='json').status_code, 400)
