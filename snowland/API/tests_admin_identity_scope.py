from django.test import TestCase
from datetime import datetime, timezone as utc_timezone
from unittest.mock import patch

from API import tests_campus_scope as fixtures
from Coach.models import Coach
from booking.models import ReservationGroup


class AdminIdentityScopeTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)

    authenticated = fixtures.CampusScopeApiTests.authenticated

    def test_other_company_manager_is_not_presented_as_this_company_manager(self):
        self.profile.manager_client = self.other_tenant
        self.profile.save(update_fields=['manager_client'])
        response = self.authenticated(self.manager).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 403, response.data)

    def test_unassigned_manager_cannot_open_the_console(self):
        self.profile.manager_client = None
        self.profile.role = 'hq_admin'
        self.profile.save(update_fields=['manager_client', 'role'])
        response = self.authenticated(self.manager).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 403, response.data)

    def test_coach_flag_without_real_tenant_coach_cannot_open_the_console(self):
        self.profile.is_manager = False
        self.profile.is_coach = True
        self.profile.save(update_fields=['is_manager', 'is_coach'])
        api = self.authenticated(self.manager)
        self.assertEqual(api.get('/api/admin/snowland/me/').status_code, 403)
        Coach.objects.create(user=self.manager, client=self.other_tenant, name='Other coach')
        self.assertEqual(api.get('/api/admin/snowland/me/').status_code, 403)

    def test_other_company_manager_who_teaches_here_is_only_local_coach(self):
        self.profile.manager_client = self.other_tenant
        self.profile.is_coach = True
        self.profile.role = 'hq_admin'
        self.profile.admin_permissions = ['orders', 'resorts', 'payroll']
        self.profile.save()
        coach = Coach.objects.create(user=self.manager, client=self.tenant, name='Local coach')
        coach.campuses.add(self.campus_a)
        api = self.authenticated(self.manager)
        response = api.get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 200, response.data)
        user = response.data['data']
        self.assertFalse(user['is_manager'])
        self.assertTrue(user['is_coach'])
        self.assertEqual(user['role'], 'coach')
        self.assertEqual(user['permissions'], [])
        self.assertFalse(user['can_view_all_campuses'])
        self.assertEqual(user['assigned_campus_ids'], [self.campus_a.pk])
        self.assertEqual([row['id'] for row in user['campuses']], [self.campus_a.pk])
        self.assertEqual(api.get('/api/admin/snowland/orders/').status_code, 403)
        self.assertEqual(api.get('/api/admin/snowland/resorts/').status_code, 403)
        self.assertEqual(api.get('/api/admin/snowland/coach/my-courses/').status_code, 200)

    def test_local_manager_with_other_company_coach_has_no_local_coach_menu(self):
        self.profile.is_coach = True
        self.profile.save(update_fields=['is_coach'])
        Coach.objects.create(user=self.manager, client=self.other_tenant, name='Other coach')
        response = self.authenticated(self.manager).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 200, response.data)
        user = response.data['data']
        self.assertTrue(user['is_manager'])
        self.assertFalse(user['is_coach'])
        self.assertEqual(user['permissions'], ['orders', 'resorts', 'campuses'])
        self.assertEqual(user['role'], 'campus_manager')

    def test_superuser_remains_company_scoped_and_can_open_console(self):
        response = self.authenticated(self.superuser).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['data']['is_superuser'])
        self.assertTrue(response.data['data']['can_view_all_campuses'])
        self.assertEqual({row['id'] for row in response.data['data']['campuses']}, {self.campus_a.pk, self.campus_b.pk})

    def test_manager_without_active_campus_gets_a_clear_denial(self):
        self.profile.campuses.clear()
        response = self.authenticated(self.manager).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 403, response.data)

    def test_manager_without_active_campus_can_still_use_own_coach_role(self):
        self.profile.campuses.clear()
        self.profile.is_coach = True
        self.profile.save(update_fields=['is_coach'])
        coach = Coach.objects.create(user=self.manager, client=self.tenant, name='Local coach')
        coach.campuses.add(self.campus_b)
        response = self.authenticated(self.manager).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 200, response.data)
        user = response.data['data']
        self.assertFalse(user['is_manager'])
        self.assertTrue(user['is_coach'])
        self.assertEqual(user['permissions'], [])
        self.assertEqual(user['assigned_campus_ids'], [self.campus_b.pk])

    def test_manager_with_no_module_permissions_gets_clear_denial(self):
        self.profile.admin_permissions = []
        self.profile.save(update_fields=['admin_permissions'])
        response = self.authenticated(self.manager).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 403, response.data)

    def test_dashboard_recent_order_time_matches_taipei_day_boundary(self):
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='QA midnight')
        ReservationGroup.objects.filter(pk=group.pk).update(created_at=datetime(2026,10,15,16,10,tzinfo=utc_timezone.utc))
        with patch('API.admin_views.timezone.now', return_value=datetime(2026,10,15,16,30,tzinfo=utc_timezone.utc)):
            response = self.authenticated(self.superuser).get('/api/admin/snowland/dashboard/', {'period':'today'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['recent_orders'][0]['created_at'], '2026-10-16 00:10')
