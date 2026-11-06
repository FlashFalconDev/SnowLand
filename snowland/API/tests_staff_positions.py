from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client
from Control.models import TenantStaffMembership
from Resorts.models import Campus


class StaffPositionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = Client.objects.create(internal_code='positions-a', name='QA A')
        cls.other = Client.objects.create(internal_code='positions-b', name='QA B')
        cls.first = Campus.objects.create(client=cls.school, code='first', name='QA First')
        cls.second = Campus.objects.create(client=cls.school, code='second', name='QA Second')
        user = get_user_model()
        cls.hq = user.objects.create_user('positions-hq')
        cls.worker = user.objects.create_user('positions-worker')
        cls.platform = user.objects.create_superuser('positions-platform', password='synthetic')
        for tenant in (cls.school, cls.other):
            TenantStaffMembership.objects.create(client=tenant, user=cls.hq, role='hq_admin',
                                                 is_manager=True, all_campuses=True, admin_permissions=['staff'])
        cls.other_membership = TenantStaffMembership.objects.create(
            client=cls.other, user=cls.worker, role='marketing',
            is_manager=True, all_campuses=True, admin_permissions=['analytics'],
        )
        cls.a = '/api/admin/positions-a/'
        cls.b = '/api/admin/positions-b/'
        cls.assignment = cls.a + f'customers/{cls.worker.pk}/permission/'

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.hq)

    def create_position(self, name, role='', permissions=(), campus_ids=(), root=None):
        data = {'name': name, 'role': role, 'permissions': list(permissions),
                'all_campuses': not campus_ids, 'campus_ids': list(campus_ids)}
        response = self.api.post((root or self.a) + 'staff-positions/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['data']

    def test_multi_position_inherits_pages_and_edits_propagate_within_tenant(self):
        order = self.create_position('訂單', 'campus_manager', ['order_view', 'order_refunds'], [self.first.pk])
        marketing = self.create_position('網站', 'web_editor', ['site_home', 'staff'])
        response = self.api.post(self.assignment, {'position_ids': [0, order['id'], marketing['id']]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        member = TenantStaffMembership.objects.get(client=self.school, user=self.worker)
        self.assertTrue(member.is_manager)
        self.assertTrue(member.is_coach)
        self.assertEqual(member.role, 'campus_manager')
        self.assertEqual(set(member.admin_permissions), {'order_view', 'site_home'})
        self.assertEqual(list(member.campuses.values_list('id', flat=True)), [self.first.pk])
        self.assertEqual(self.api.post(self.assignment, {'is_manager': False}, format='json').status_code, 409)
        path = self.a + f"staff-positions/{marketing['id']}/"
        self.assertEqual(self.api.delete(path).status_code, 400)
        changes = {**marketing['settings'], 'permissions': ['site_news']}
        self.assertEqual(self.api.put(path, changes, format='json').status_code, 200)
        member.refresh_from_db()
        self.assertEqual(set(member.admin_permissions), {'order_view', 'site_news'})
        self.other_membership.refresh_from_db()
        self.assertEqual(self.other_membership.admin_permissions, ['analytics'])
        self.assertEqual(self.api.post(self.assignment, {'position_ids': [0]}, format='json').status_code, 200)
        member.refresh_from_db()
        self.assertFalse(member.is_manager)
        self.assertTrue(member.is_coach)
        self.assertFalse(member.positions.exists())

    def test_cannot_combine_conflicting_scopes_or_assign_foreign_positions(self):
        first = self.create_position('校區一', 'campus_manager', ['order_view'], [self.first.pk])
        second = self.create_position('校區二', 'campus_manager', ['scheduling'], [self.second.pk])
        principal = self.create_position('校長', 'campus_principal', ['order_view'], [self.first.pk])
        outside = self.create_position('乙校', permissions=['analytics'], root=self.b)
        for ids in ([first['id'], second['id']], [first['id'], principal['id']], [outside['id']], [False]):
            with self.subTest(ids=ids):
                self.assertEqual(self.api.post(self.assignment, {'position_ids': ids}, format='json').status_code, 400)
                self.assertFalse(TenantStaffMembership.objects.filter(client=self.school, user=self.worker).exists())
        self.assertEqual(self.api.delete(self.a + f"staff-positions/{outside['id']}/").status_code, 404)

    def test_rejected_position_edit_does_not_change_existing_staff(self):
        first = self.create_position('校區訂單', 'campus_manager', ['order_view'], [self.first.pk])
        other = self.create_position('官網', 'web_editor', ['site_home'], [self.first.pk])
        ids = [first['id'], other['id']]
        self.assertEqual(self.api.post(self.assignment, {'position_ids': ids}, format='json').status_code, 200)
        details = {**other['settings'], 'campus_ids': [self.second.pk]}
        self.assertEqual(self.api.put(self.a + f"staff-positions/{other['id']}/", details, format='json').status_code, 400)
        member = TenantStaffMembership.objects.get(client=self.school, user=self.worker)
        self.assertEqual(list(member.campuses.values_list('pk', flat=True)), [self.first.pk])
        self.assertEqual(list(member.positions.get(pk=other['id']).campuses.values_list('pk', flat=True)), [self.first.pk])

    def test_only_platform_admin_changes_global_access_and_keeps_positions(self):
        position = self.create_position('網站', permissions=['site_home'])
        self.assertEqual(self.api.post(self.assignment, {'position_ids': [position['id']]}, format='json').status_code, 200)
        self.assertEqual(self.api.post(self.assignment, {'is_superuser': True}, format='json').status_code, 403)
        self.api.force_authenticate(self.worker)
        self.assertEqual(self.api.get(self.a + 'staff-positions/').status_code, 403)
        self.api.force_authenticate(self.platform)
        self.assertEqual(self.api.post(self.assignment, {'is_superuser': True, 'position_ids': []}, format='json').status_code, 400)
        self.assertEqual(self.api.post(self.assignment, {'is_superuser': True}, format='json').status_code, 200)
        member = TenantStaffMembership.objects.get(client=self.school, user=self.worker)
        self.assertEqual(list(member.positions.values_list('pk', flat=True)), [position['id']])

    def test_session_writes_require_same_origin_csrf(self):
        browser = APIClient(enforce_csrf_checks=True)
        browser.force_login(self.hq)
        url = self.a + 'staff-positions/'
        data = {'name': '測試職位', 'role': '', 'permissions': ['analytics'], 'all_campuses': True, 'campus_ids': []}
        self.assertEqual(browser.post(url, data, format='json').status_code, 403)
        self.assertEqual(browser.post(self.assignment, {'position_ids': [0]}, format='json').status_code, 403)
        self.assertEqual(browser.get(url).status_code, 200)
        csrf = browser.cookies['csrftoken'].value
        self.assertEqual(browser.post(url, data, format='json', HTTP_X_CSRFTOKEN=csrf).status_code, 201)
        self.assertEqual(browser.post(self.assignment, {'position_ids': [0]}, format='json', HTTP_X_CSRFTOKEN=csrf).status_code, 200)


class SnowlandPositionTemplateTests(TestCase):
    def test_seed_adds_editable_customer_templates_without_reassigning_employees(self):
        from importlib import import_module
        from types import SimpleNamespace

        from django.apps import apps
        from django.db import connection
        from Control.models import TenantStaffPosition

        seed = import_module('Control.migrations.0012_seed_snowland_staff_positions').seed_snowland_positions
        school = Client.objects.create(internal_code='snowland', name='SnowLand')
        other = Client.objects.create(internal_code='positions-other', name='Other tenant')
        first = Campus.objects.create(client=school, code='first', name='測試校區')
        second = Campus.objects.create(client=school, code='second', name='測試校區')
        Campus.objects.create(client=school, code='inactive', name='停用校區', is_active=False)
        Campus.objects.create(client=other, code='outside', name='外校')
        user = get_user_model().objects.create_user('preset-existing')
        membership = TenantStaffMembership.objects.create(
            client=school, user=user, role='assistant', is_manager=True,
            all_campuses=True, admin_permissions=['order_view'],
        )
        old_position = TenantStaffPosition.objects.create(
            client=school, name='行銷人員', role='marketing', permissions=['discounts'], all_campuses=True,
        )
        membership.positions.add(old_position)
        customized_preset = TenantStaffPosition.objects.create(
            client=school, name='行銷人員（預設）', role='marketing', permissions=['analytics', 'site_campaigns'],
            all_campuses=False,
        )
        customized_preset.campuses.add(first)

        schema = SimpleNamespace(connection=connection)
        seed(apps, schema)
        seed(apps, schema)

        self.assertEqual(list(membership.positions.all()), [old_position])
        membership.refresh_from_db()
        self.assertEqual(membership.admin_permissions, ['order_view'])
        self.assertEqual(school.staff_positions.count(), 9)
        self.assertFalse(other.staff_positions.exists())
        self.assertEqual(school.staff_positions.get(name='保險人員（預設）').permissions, ['insurance_records'])
        self.assertNotIn('order_refunds', school.staff_positions.get(name='行政小幫手（預設）').permissions)
        for campus in (first, second):
            principal = school.staff_positions.get(name=f'校區校長（測試校區／{campus.code}）')
            manager = school.staff_positions.get(name=f'校區主管（測試校區／{campus.code}）')
            self.assertEqual(list(principal.campuses.all()), [campus])
            self.assertEqual(list(manager.campuses.all()), [campus])
            self.assertFalse(principal.all_campuses)
            self.assertIn('analytics', principal.permissions)
            self.assertNotIn('payroll_statements', principal.permissions)
            self.assertNotIn('analytics', manager.permissions)
        customized_preset.refresh_from_db()
        self.assertEqual(customized_preset.permissions, ['analytics', 'site_campaigns'])
        self.assertEqual(list(customized_preset.campuses.all()), [first])
