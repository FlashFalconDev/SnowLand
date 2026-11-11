
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, SiteContent
from Coach.models import Coach
from Control.models import TenantStaffMembership
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from Resorts.models import Campus, Resorts
from booking.models import ReservationGroup, StaffBookingLink
from django.utils import timezone


class ConsolePagePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = Client.objects.create(internal_code='console-a', name='甲校')
        cls.other = Client.objects.create(internal_code='console-b', name='乙校')
        cls.first = Campus.objects.create(client=cls.school, code='first', name='第一校區')
        cls.second = Campus.objects.create(client=cls.school, code='second', name='第二校區')
        cls.outside = Campus.objects.create(client=cls.other, code='outside', name='外校校區')
        cls.staff = get_user_model().objects.create_user('console-staff')
        cls.hq = get_user_model().objects.create_user('console-hq')
        TenantStaffMembership.objects.create(client=cls.school, user=cls.hq, is_manager=True, role='hq_admin')
        cls.profile = TenantStaffMembership.objects.create(
            client=cls.school, user=cls.staff, is_manager=True, role='assistant',
            all_campuses=False, admin_permissions=[],
        )
        cls.profile.campuses.set([cls.first])
        cls.order = ReservationGroup.objects.create(client=cls.school, campus=cls.first, user=cls.staff)
        cls.hidden_order = ReservationGroup.objects.create(client=cls.school, campus=cls.second, user=cls.staff)
        cls.url = '/api/admin/console-a/'

    def actor(self, permissions):
        self.profile.admin_permissions = permissions
        self.profile.save(update_fields=['admin_permissions'])
        client = APIClient()
        client.force_authenticate(self.staff)
        return client

    def test_order_pages_and_side_effects_use_distinct_grants(self):
        api = self.actor(['order_view'])
        url = self.url + 'orders/'
        self.assertEqual([row['id'] for row in api.get(url).data['data']['list']], [self.order.pk])
        self.assertEqual(api.get(url + f'{self.hidden_order.pk}/').status_code, 404)
        for path in ('orders/?workflow=payments', 'orders/?workflow=refunds', 'orders/export/', 'staff-booking-links/'):
            self.assertEqual(api.get(self.url + path).status_code, 403, path)

        api = self.actor(['order_payments'])
        detail = url + f'{self.order.pk}/'
        self.assertEqual(api.get(url + '?workflow=payments').status_code, 200)
        self.assertEqual(api.get(url).status_code, 403)
        self.assertEqual(api.patch(detail, {'payment_status': 'refunded'}, format='json').status_code, 403)
        self.assertEqual(api.patch(detail, {'payment_status': 'unpaid', 'action': 'schedule'}, format='json').status_code, 403)
        self.assertEqual(api.get(detail + 'refund-preview/').status_code, 403)

        api = self.actor(['order_refunds'])
        self.assertEqual(api.get(url + '?workflow=refunds').status_code, 200)
        self.assertEqual(api.get(self.url + 'cancellations/').status_code, 200)
        self.assertEqual(api.get(url + '?workflow=payments').status_code, 403)

        api = self.actor(['booking_links'])
        self.assertEqual(api.get(self.url + 'staff-booking-links/').status_code, 200)
        self.assertEqual(api.get(url).status_code, 403)

    def test_coach_booking_links_are_personal_and_campus_scoped(self):
        self.profile.is_manager = False
        self.profile.is_coach = True
        self.profile.save(update_fields=['is_manager', 'is_coach'])
        coach = Coach.objects.create(client=self.school, user=self.staff, name='QA 教練')
        coach.campuses.add(self.first)
        allowed = StaffBookingLink.objects.create(
            client=self.school, campus=self.first, created_by=self.staff, title='自己的連結', expires_at=timezone.now(),
        )
        other = StaffBookingLink.objects.create(
            client=self.school, campus=self.first, created_by=self.hq, title='別人的連結', expires_at=timezone.now(),
        )
        api = APIClient()
        api.force_authenticate(self.staff)
        url = self.url + 'staff-booking-links/'
        self.assertEqual([row['id'] for row in api.get(url).data['data']['list']], [allowed.pk])
        self.assertEqual(api.get(f'{url}{other.pk}/').status_code, 404)
        self.assertEqual(api.get(url, HTTP_X_CAMPUS_ID=str(self.second.pk)).status_code, 403)
        self.assertEqual(api.delete(f'{url}{allowed.pk}/').status_code, 403)
        self.assertEqual(api.get(self.url + 'orders/').status_code, 403)
        self.assertEqual(api.get('/api/admin/console-b/staff-booking-links/').status_code, 403)

    def test_coach_directory_and_leave_review_can_be_granted_separately(self):
        api = self.actor(['coach_leaves'])
        self.assertEqual(api.get(self.url + 'coach-leaves/').status_code, 200)
        self.assertEqual(api.get(self.url + 'coaches/').status_code, 403)
        api = self.actor(['coach_directory'])
        self.assertEqual(api.get(self.url + 'coaches/').status_code, 200)
        self.assertEqual(api.get(self.url + 'coach-leaves/').status_code, 403)

    def test_site_records_and_writes_are_scoped_to_the_granted_page(self):
        home = SiteContent.objects.create(client=self.school, location_key='homepage.hero', content_type='setting', title='Home')
        waiver = SiteContent.objects.create(client=self.school, location_key='membership.waiver', content_type='page', title='Waiver')
        gallery = SiteContent.objects.create(client=self.school, location_key='photography.gallery', content_type='media', title='Gallery')
        review = SiteContent.objects.create(client=self.school, location_key='homepage.reviews', content_type='review', title='Review')
        api = self.actor(['site_home'])
        url = self.url + 'site-content/'
        self.assertEqual({row['id'] for row in api.get(url).data['data']['list']}, {home.pk})
        self.assertEqual(api.get(url + f'{waiver.pk}/').status_code, 404)
        self.assertEqual(api.post(url, {'title': 'Blocked', 'body': 'QA waiver', 'location_key': 'membership.waiver', 'content_type': 'page'}, format='json').status_code, 403)
        self.assertEqual(api.get(url + 'waiver-current/').status_code, 403)
        self.assertEqual(self.actor(['course_documents']).get(url + 'waiver-current/').status_code, 200)
        self.assertEqual({row['id'] for row in self.actor(['site_media']).get(url).data['data']['list']}, {gallery.pk})
        self.assertEqual({row['id'] for row in self.actor(['site_reviews']).get(url).data['data']['list']}, {review.pk})

    def test_payroll_tabs_do_not_grant_other_financial_modules(self):
        endpoints = {
            'payroll_rules': 'coach-pay-rules/',
            'payroll_statements': 'payroll-statements/',
            'payroll_documents': 'payroll-statements/document-settings/',
            'staff_incentives': 'staff-incentive-rules/',
        }
        for grant in endpoints:
            api = self.actor([grant])
            for required, route in endpoints.items():
                with self.subTest(grant=grant, route=route):
                    self.assertEqual(api.get(self.url + route).status_code, 200 if required == grant else 403)

    def test_page_options_respect_permissions_tenant_and_campus(self):
        options = [
            ('payment_accounts', 'payment-accounts/scope-options/', ('campuses/', 'resorts/')),
            ('campuses', 'resorts/campus-options/', ('resorts/',)),
            ('notifications', 'notification-templates/course-options/', ('course-templates/', 'course-categories/')),
        ]
        fixtures = []
        for campus in (self.first, self.second, self.outside):
            resort = Resorts.objects.create(client=campus.client, name=campus.code, display_name=campus.name)
            campus.resorts.add(resort)
            category = CourseCategory.objects.create(client=campus.client, name=campus.code)
            course_type = CourseType.objects.create(category=category, name=campus.code)
            template = CourseTemplate.objects.create(course_type=course_type, name=campus.code, duration_hours=2)
            template.resorts.add(resort)
            fixtures.append((resort, template))
        resort, template = fixtures[0]
        template.resorts.add(fixtures[1][0])
        expected = {
            'payment_accounts': {
                'campuses': [{'id': self.first.pk, 'name': self.first.name, 'is_active': True, 'resort_ids': [resort.pk]}],
                'resorts': [{'id': resort.pk, 'display_name': resort.display_name}],
            },
            'campuses': {'list': [{'id': resort.pk, 'display_name': resort.display_name}], 'total': 1},
            'notifications': {'list': [{
                'id': template.pk, 'name': template.name, 'category_name': self.first.code,
                'resort_names': [resort.display_name],
            }], 'total': 1},
        }
        for grant, path, unrelated in options:
            with self.subTest(grant=grant):
                self.assertEqual(self.actor(['order_view']).get(self.url + path).status_code, 403)
                api = self.actor([grant])
                response = api.get(self.url + path, HTTP_X_CAMPUS_ID='all')
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['data'], expected[grant])
                self.assertEqual(api.get(self.url + path, HTTP_X_CAMPUS_ID=str(self.second.pk)).status_code, 403)
                self.assertEqual(api.get('/api/admin/console-b/' + path).status_code, 403)
                self.assertIn(api.post(self.url + path, {}, format='json').status_code, (403, 405))
                for route in unrelated:
                    self.assertEqual(api.get(self.url + route).status_code, 403, route)

    def test_booking_form_grant_cannot_read_or_change_bank_settings(self):
        api = self.actor(['booking_form_options'])
        path = self.url + 'payment-settings/'
        response = api.get(path + '?section=booking-form')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data['data']), {'messenger_options', 'referral_source_options'})
        self.assertEqual(api.get(path + '?section=accounts').status_code, 403)
        self.assertEqual(api.put(path, {'bank_account_number': '1234'}, format='json').status_code, 403)

    def test_tenant_can_save_page_and_campus_grants_without_affecting_other_tenant(self):
        other_membership = TenantStaffMembership.objects.create(
            client=self.other, user=self.staff, is_manager=True, role='marketing',
            all_campuses=True, admin_permissions=['analytics'],
        )
        admin = APIClient()
        admin.force_authenticate(self.hq)
        path = self.url + f'customers/{self.staff.pk}/permission/'
        payload = {
            'is_manager': True, 'role': 'assistant', 'permissions': ['order_view', 'coach_leaves'],
            'all_campuses': False, 'campus_ids': [self.first.pk],
        }
        self.assertEqual(admin.post(path, payload, format='json').status_code, 200)
        self.assertEqual(admin.post(path, {**payload, 'campus_ids': [self.outside.pk]}, format='json').status_code, 400)
        self.assertEqual(admin.post(path, {**payload, 'campus_ids': []}, format='json').status_code, 400)
        api = APIClient()
        api.force_authenticate(self.staff)
        identity = api.get(self.url + 'me/').data['data']
        self.assertEqual(set(identity['permissions']), {'order_view', 'coach_leaves'})
        self.assertFalse(identity['can_view_all_campuses'])
        self.assertEqual([campus['id'] for campus in identity['campuses']], [self.first.pk])
        self.assertEqual(api.get(self.url + 'orders/', HTTP_X_CAMPUS_ID=str(self.second.pk)).status_code, 403)
        self.assertEqual(api.get('/api/admin/console-b/me/').data['data']['permissions'], ['analytics'])
        other_membership.refresh_from_db()
        self.assertTrue(other_membership.all_campuses)

    def test_legacy_group_grants_are_expanded_until_a_new_selection_is_saved(self):
        api = self.actor(['orders', 'coaches', 'cms', 'reviews', 'payroll'])
        grants = set(api.get(self.url + 'me/').data['data']['permissions'])
        self.assertTrue({'order_view', 'order_edit', 'order_payments', 'order_refunds', 'order_export',
                         'booking_links', 'coach_directory', 'coach_leaves', 'course_documents',
                         'site_reviews', 'site_media', 'payroll_rules', 'payroll_statements'} <= grants)
