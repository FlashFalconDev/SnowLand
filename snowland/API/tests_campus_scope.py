from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client
from Control.models import UserProfile
from Resorts.models import Campus, OperatingPolicy, Resorts
from booking.models import ReservationGroup


class CampusScopeApiTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.other_tenant = Client.objects.create(name='Other', internal_code='other')
        self.resort_a = Resorts.objects.create(client=self.tenant, name='a', display_name='A 雪場')
        self.resort_b = Resorts.objects.create(client=self.tenant, name='b', display_name='B 雪場')
        self.other_resort = Resorts.objects.create(client=self.other_tenant, name='other', display_name='外部雪場')
        self.campus_a = Campus.objects.create(client=self.tenant, name='A 校區', code='a')
        self.campus_b = Campus.objects.create(client=self.tenant, name='B 校區', code='b')
        self.campus_a.resorts.add(self.resort_a)
        self.campus_b.resorts.add(self.resort_b)
        OperatingPolicy.objects.create(client=self.tenant)
        self.superuser = User.objects.create_superuser('root', 'root@example.com', 'test-password')
        self.manager = User.objects.create_user('manager', 'manager@example.com', 'test-password')
        self.profile = UserProfile.objects.get(user=self.manager)
        self.profile.is_manager = True
        self.profile.role = 'campus_manager'
        self.profile.admin_permissions = ['orders', 'resorts', 'campuses']
        self.profile.save()
        self.profile.campuses.add(self.campus_a)
        self.manager.refresh_from_db()

    def authenticated(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_headquarters_can_list_all_and_filter_one_campus(self):
        client = self.authenticated(self.superuser)
        response = client.get('/api/admin/snowland/campuses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 2)

        response = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data['data']['list']], [self.resort_a.id])

    def test_campus_manager_is_limited_to_assigned_campus(self):
        client = self.authenticated(self.manager)
        response = client.get('/api/admin/snowland/campuses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data['data']['list']], [self.campus_a.id])

        forbidden = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID=str(self.campus_b.id))
        self.assertEqual(forbidden.status_code, 403)

    def test_cannot_attach_other_tenant_resort(self):
        client = self.authenticated(self.superuser)
        response = client.post('/api/admin/snowland/campuses/', {
            'name': '錯誤校區', 'code': 'invalid', 'resort_ids': [self.other_resort.id],
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_campus_with_orders_cannot_be_deleted(self):
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='訂單')
        client = self.authenticated(self.superuser)
        response = client.delete(f'/api/admin/snowland/campuses/{self.campus_a.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Campus.objects.filter(pk=self.campus_a.id).exists())

    def test_admin_me_returns_scope_context(self):
        client = self.authenticated(self.manager)
        response = client.get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['role'], 'campus_manager')
        self.assertFalse(response.data['data']['can_view_all_campuses'])
        self.assertEqual(response.data['data']['assigned_campus_ids'], [self.campus_a.id])

    def test_order_list_respects_selected_campus(self):
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='A order')
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_b, name='B order')
        client = self.authenticated(self.superuser)
        response = client.get('/api/admin/snowland/orders/', HTTP_X_CAMPUS_ID=str(self.campus_b.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 1)
        self.assertEqual(response.data['data']['list'][0]['name'], 'B order')

    def test_dashboard_respects_campus_scope_and_shows_breakdowns(self):
        ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_a, name='A order', marketing_source='Google'
        )
        ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_b, name='B order', marketing_source='朋友介紹'
        )
        client = self.authenticated(self.superuser)
        response = client.get('/api/admin/snowland/dashboard/', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['stats']['orders'], 1)
        self.assertEqual(response.data['data']['campus_summary'][0]['name'], 'A 校區')
        self.assertEqual(response.data['data']['marketing_sources'][0]['name'], 'Google')
