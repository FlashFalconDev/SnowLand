from datetime import time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Control.models import UserProfile
from Resorts.models import Campus, EquipmentAssistanceTimeSlot, OperatingPolicy, PaymentAccount, Resorts
from Coach.models import Coach
from Coursekit.models import CourseCategory, CourseType
from booking.models import Booking, MemberDetail, NotificationTemplate, Payment, Reservation, ReservationGroup


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

    def test_coach_manager_can_read_form_choices_but_not_edit_resorts(self):
        self.profile.admin_permissions = ['coaches']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)

        resorts = client.get('/api/admin/snowland/resorts/')
        self.assertEqual(resorts.status_code, 200)
        self.assertEqual([item['id'] for item in resorts.data['data']['list']], [self.resort_a.id])
        self.assertEqual(client.get('/api/admin/snowland/course-categories/').status_code, 200)
        self.assertEqual(client.get('/api/admin/snowland/course-types/').status_code, 200)
        self.assertEqual(client.post('/api/admin/snowland/resorts/', {'name': '不應新增'}, format='json').status_code, 403)

    def test_coach_creation_assigns_campus_and_rejects_other_campus(self):
        self.profile.admin_permissions = ['coaches']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/coaches/'

        created = client.post(url, {'name': '道東新教練'}, format='json')
        self.assertEqual(created.status_code, 201)
        coach = Coach.objects.get(name='道東新教練')
        self.assertEqual(list(coach.campuses.values_list('id', flat=True)), [self.campus_a.id])
        self.assertEqual(created.data['data']['campus_ids'], [self.campus_a.id])
        self.assertTrue(created.data['data']['can_manage'])

        denied = client.post(url, {'name': '越權教練', 'campus_ids_input': [self.campus_b.id]}, format='json')
        self.assertEqual(denied.status_code, 400)
        self.assertFalse(Coach.objects.filter(name='越權教練').exists())

        headquarters = self.authenticated(self.superuser)
        missing = headquarters.post(url, {'name': '未選校區'}, format='json')
        self.assertEqual(missing.status_code, 400)
        shared = headquarters.post(url, {
            'name': '共用教練', 'campus_ids_input': [self.campus_a.id, self.campus_b.id],
        }, format='json')
        self.assertEqual(shared.status_code, 201)
        self.assertCountEqual(shared.data['data']['campus_ids'], [self.campus_a.id, self.campus_b.id])

    def test_shared_coach_is_read_only_for_one_campus(self):
        self.profile.admin_permissions = ['coaches']
        self.profile.save(update_fields=['admin_permissions'])
        coach = Coach.objects.create(client=self.tenant, name='共用教練')
        coach.campuses.set([self.campus_a, self.campus_b])
        client = self.authenticated(self.manager)
        url = f'/api/admin/snowland/coaches/{coach.id}/'

        detail = client.get(url)
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.data['can_manage'])
        self.assertEqual(client.patch(url, {'name': '越權修改'}, format='json').status_code, 403)
        self.assertEqual(client.delete(url).status_code, 403)
        coach.refresh_from_db()
        self.assertEqual(coach.name, '共用教練')

    def test_coach_with_order_cannot_be_deleted(self):
        self.profile.admin_permissions = ['coaches']
        self.profile.save(update_fields=['admin_permissions'])
        coach = Coach.objects.create(client=self.tenant, name='已有課程教練')
        coach.campuses.add(self.campus_a)
        category = CourseCategory.objects.create(client=self.tenant, name='單板')
        course_type = CourseType.objects.create(category=category, name='一般課程')
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='測試訂單')
        Reservation.objects.create(group=group, resort=self.resort_a, course_type=course_type, preferred_coach=coach)

        response = self.authenticated(self.manager).delete(f'/api/admin/snowland/coaches/{coach.id}/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Coach.objects.filter(pk=coach.id).exists())

    def test_headquarters_can_list_all_and_filter_one_campus(self):
        client = self.authenticated(self.superuser)
        response = client.get('/api/admin/snowland/campuses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 2)

        response = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID='all')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['id'] for item in response.data['data']['list']}, {self.resort_a.id, self.resort_b.id})

        response = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data['data']['list']], [self.resort_a.id])

    def test_campus_manager_is_limited_to_assigned_campus(self):
        client = self.authenticated(self.manager)
        response = client.get('/api/admin/snowland/campuses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data['data']['list']], [self.campus_a.id])

        resorts = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID='all')
        self.assertEqual([item['id'] for item in resorts.data['data']['list']], [self.resort_a.id])

        create = client.post('/api/admin/snowland/campuses/', {'name': '未授權', 'code': 'denied'}, format='json')
        self.assertEqual(create.status_code, 403)

        forbidden = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID=str(self.campus_b.id))
        self.assertEqual(forbidden.status_code, 403)

    def test_schedule_limits_manager_to_ten_days_and_own_campus(self):
        today = timezone.localdate()
        for campus, resort, offset in (
            (self.campus_a, self.resort_a, 1),
            (self.campus_a, self.resort_a, 11),
            (self.campus_b, self.resort_b, 1),
        ):
            coach = Coach.objects.create(client=self.tenant, name=f'{campus.code}-{offset}')
            coach.campuses.add(campus)
            slot = EquipmentAssistanceTimeSlot.objects.create(
                resort=resort, label=f'協助-{campus.code}-{offset}',
                start_time=time(8), end_time=time(8, 30),
            )
            group = ReservationGroup.objects.create(client=self.tenant, campus=campus, name=f'{campus.code}-{offset}')
            Payment.objects.create(reservation_group=group, status='paid')
            reservation = Reservation.objects.create(
                group=group, resort=resort, preferred_coach=coach,
                status='manually_assigned', equipment='purchaseAssistanceTime',
                equipment_assistance_time_slot=slot,
            )
            Booking.objects.create(
                reservation=reservation, date=today + timedelta(days=offset),
                start_time=time(9), end_time=time(11),
                course_type='單板', course_name='測試課程', is_scheduled=True,
            )

        self.profile.admin_permissions = ['scheduling']
        self.profile.save(update_fields=['admin_permissions'])
        url = '/api/admin/snowland/bookings/'
        manager = self.authenticated(self.manager)
        response = manager.get(url, {'start': today.isoformat(), 'end': (today + timedelta(days=30)).isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 2)
        self.assertEqual({item['date'] for item in response.data['data']['list']},
                         {(today + timedelta(days=1)).isoformat()})
        self.assertEqual(len(response.data['data']['daily_summary']), 11)
        self.assertEqual(response.data['data']['daily_summary'][0]['total_coaches'], 2)

        beyond = manager.get(url, {'start': (today + timedelta(days=11)).isoformat(),
                                   'end': (today + timedelta(days=20)).isoformat()})
        self.assertEqual(beyond.status_code, 200)
        self.assertEqual(beyond.data['data']['list'], [])

        principal = User.objects.create_user('principal')
        principal_profile = principal.userprofile
        principal_profile.is_manager = True
        principal_profile.role = 'campus_principal'
        principal_profile.admin_permissions = ['scheduling']
        principal_profile.save()
        principal_profile.campuses.add(self.campus_a)
        principal_response = self.authenticated(principal).get(
            url, {'start': today.isoformat(), 'end': (today + timedelta(days=30)).isoformat()})
        self.assertEqual(principal_response.status_code, 200)
        self.assertEqual(principal_response.data['data']['total'], 4)

    def test_notification_templates_cannot_cross_campus_or_change_company_default(self):
        self.profile.admin_permissions = ['notifications']
        self.profile.save(update_fields=['admin_permissions'])
        url = '/api/admin/snowland/notification-templates/'
        own = NotificationTemplate.objects.create(client=self.tenant, campus=self.campus_a, name='A 提醒', event='pre_course', channel='email', body='A')
        other = NotificationTemplate.objects.create(client=self.tenant, campus=self.campus_b, name='B 提醒', event='pre_course', channel='email', body='B')
        global_template = NotificationTemplate.objects.create(client=self.tenant, name='總部提醒', event='pre_course', channel='email', body='全部')
        client = self.authenticated(self.manager)

        listed = client.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual({row['id'] for row in listed.data['data']['list']}, {own.id, global_template.id})
        payload = {'name': '新增提醒', 'event': 'pre_course', 'channel': 'email', 'body': '內容'}
        self.assertEqual(client.post(url, {**payload, 'campus': self.campus_a.id}, format='json').status_code, 201)
        self.assertEqual(client.post(url, {**payload, 'campus': self.campus_b.id}, format='json').status_code, 403)
        self.assertEqual(client.post(url, {**payload, 'campus': None}, format='json').status_code, 403)
        self.assertEqual(client.patch(f'{url}{own.id}/', {'campus': self.campus_b.id}, format='json').status_code, 403)
        self.assertEqual(client.patch(f'{url}{global_template.id}/', {'name': '越權'}, format='json').status_code, 404)
        self.assertEqual(client.delete(f'{url}{global_template.id}/').status_code, 404)
        self.assertEqual(client.get(f'{url}{other.id}/').status_code, 404)

        headquarters = self.authenticated(self.superuser)
        scoped = headquarters.get(url, HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual({row['campus'] for row in scoped.data['data']['list']}, {self.campus_a.id, None})
        self.assertNotIn(other.id, {row['id'] for row in scoped.data['data']['list']})
        self.assertEqual(headquarters.post(url, {**payload, 'campus': self.campus_b.id}, format='json', HTTP_X_CAMPUS_ID=str(self.campus_a.id)).status_code, 403)

    def test_cannot_attach_other_tenant_resort(self):
        client = self.authenticated(self.superuser)
        response = client.post('/api/admin/snowland/campuses/', {
            'name': '錯誤校區', 'code': 'invalid', 'resort_ids': [self.other_resort.id],
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_campus_manager_cannot_create_payment_account_for_other_campus(self):
        self.profile.admin_permissions = ['payment_settings']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/payment-accounts/'

        for data in (
            {'name': '其他校區帳戶', 'campus_ids': [self.campus_b.id]},
            {'name': '其他雪場帳戶', 'campus_ids': [self.campus_a.id], 'resort_ids': [self.resort_b.id]},
            {'name': '全公司帳戶'},
        ):
            response = client.post(url, data, format='json')
            self.assertEqual(response.status_code, 400)

        self.assertFalse(PaymentAccount.objects.filter(client=self.tenant).exists())

    def test_campus_manager_can_create_payment_account_for_own_campus(self):
        self.profile.admin_permissions = ['payment_settings']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        response = client.post('/api/admin/snowland/payment-accounts/', {
            'name': 'A 校區帳戶',
            'campus_ids': [self.campus_a.id],
            'resort_ids': [self.resort_a.id],
        }, format='json')
        self.assertEqual(response.status_code, 201)
        account = PaymentAccount.objects.get(client=self.tenant)
        self.assertEqual(list(account.campuses.values_list('id', flat=True)), [self.campus_a.id])
        self.assertEqual(list(account.resorts.values_list('id', flat=True)), [self.resort_a.id])

    def test_payment_account_resort_must_belong_to_selected_campus(self):
        client = self.authenticated(self.superuser)
        response = client.post('/api/admin/snowland/payment-accounts/', {
            'name': '錯配帳戶',
            'campus_ids': [self.campus_a.id],
            'resort_ids': [self.resort_b.id],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PaymentAccount.objects.filter(client=self.tenant).exists())

        valid = client.post('/api/admin/snowland/payment-accounts/', {
            'name': '跨校區共用帳戶',
            'campus_ids': [self.campus_a.id, self.campus_b.id],
            'resort_ids': [self.resort_b.id],
        }, format='json')
        self.assertEqual(valid.status_code, 201)

    def test_campus_manager_cannot_modify_shared_payment_account(self):
        self.profile.admin_permissions = ['payment_settings']
        self.profile.save(update_fields=['admin_permissions'])
        account = PaymentAccount.objects.create(client=self.tenant, name='共用帳戶')
        account.campuses.add(self.campus_a, self.campus_b)
        client = self.authenticated(self.manager)
        response = client.patch(f'/api/admin/snowland/payment-accounts/{account.id}/', {
            'name': '擅自修改',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        account.refresh_from_db()
        self.assertEqual(account.name, '共用帳戶')

        deleted = client.delete(f'/api/admin/snowland/payment-accounts/{account.id}/')
        self.assertEqual(deleted.status_code, 403)
        self.assertTrue(PaymentAccount.objects.filter(pk=account.id).exists())

    def test_campus_manager_cannot_modify_company_operating_policy(self):
        client = self.authenticated(self.manager)
        policy = OperatingPolicy.objects.get(client=self.tenant, campus__isnull=True)
        response = client.patch(f'/api/admin/snowland/operating-policies/{policy.id}/', {
            'unpaid_hold_days': 9,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        policy.refresh_from_db()
        self.assertEqual(policy.unpaid_hold_days, 3)

        deleted = client.delete(f'/api/admin/snowland/operating-policies/{policy.id}/')
        self.assertEqual(deleted.status_code, 403)
        self.assertTrue(OperatingPolicy.objects.filter(pk=policy.id).exists())

    def test_campus_manager_can_modify_own_operating_policy(self):
        policy = OperatingPolicy.objects.create(client=self.tenant, campus=self.campus_a)
        client = self.authenticated(self.manager)
        response = client.patch(f'/api/admin/snowland/operating-policies/{policy.id}/', {
            'unpaid_hold_days': 5,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        policy.refresh_from_db()
        self.assertEqual(policy.unpaid_hold_days, 5)

    def test_campus_manager_cannot_change_company_payment_settings(self):
        self.profile.admin_permissions = ['payment_settings']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/payment-settings/'
        self.assertEqual(client.get(url).status_code, 200)
        response = client.put(url, {'bank_name': '擅自修改'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.tenant.refresh_from_db()
        self.assertNotEqual(self.tenant.bank_name, '擅自修改')

        headquarters = self.authenticated(self.superuser)
        response = headquarters.put(url, {'bank_name': '總部銀行'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.bank_name, '總部銀行')

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

    def test_coach_only_admin_me_lists_only_coach_campuses(self):
        coach_user = User.objects.create_user('campus-coach', 'coach@example.test', 'test-password')
        coach_profile = coach_user.userprofile
        coach_profile.is_coach = True
        coach_profile.save(update_fields=['is_coach'])
        coach = Coach.objects.create(client=self.tenant, user=coach_user, name='A 教練')
        coach.campuses.add(self.campus_a)

        response = self.authenticated(coach_user).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['data']['can_view_all_campuses'])
        self.assertEqual(response.data['data']['assigned_campus_ids'], [self.campus_a.id])
        self.assertEqual([item['id'] for item in response.data['data']['campuses']], [self.campus_a.id])

    def test_order_list_respects_selected_campus(self):
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='A order')
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_b, name='B order')
        client = self.authenticated(self.superuser)
        response = client.get('/api/admin/snowland/orders/', HTTP_X_CAMPUS_ID=str(self.campus_b.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 1)
        self.assertEqual(response.data['data']['list'][0]['name'], 'B order')

    def test_campus_manager_cannot_complete_other_campus_order(self):
        other_order = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_b, name='B order')
        response = self.authenticated(self.manager).post(
            f'/api/admin/snowland/orders/{other_order.pk}/complete-course/',
            {'reservation_id': 1}, format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_campus_manager_order_info_is_ten_day_read_only_summary(self):
        today = timezone.localdate()
        member = User.objects.create_user('student', 'private@example.com', 'test-password')
        created = []
        for campus, resort, offset in (
            (self.campus_a, self.resort_a, 1),
            (self.campus_a, self.resort_a, 11),
            (self.campus_b, self.resort_b, 1),
        ):
            group = ReservationGroup.objects.create(client=self.tenant, campus=campus, user=member, name=f'訂單-{offset}')
            reservation = Reservation.objects.create(group=group, resort=resort, number_of_people=1)
            Booking.objects.create(
                reservation=reservation, date=today + timedelta(days=offset),
                start_time=time(9), end_time=time(11), course_type='單板', course_name='上午班',
            )
            created.append(group)
        later_reservation = Reservation.objects.create(
            group=created[0], resort=self.resort_a, number_of_people=7,
        )
        Booking.objects.create(
            reservation=later_reservation, date=today + timedelta(days=12),
            start_time=time(9), end_time=time(11), course_type='雙板', course_name='未來課程',
        )

        client = self.authenticated(self.manager)
        response = client.get('/api/admin/snowland/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 1)
        item = response.data['data']['list'][0]
        self.assertEqual(item['id'], created[0].id)
        self.assertEqual(item['number_of_people'], 1)
        self.assertEqual(item['course_dates'], [(today + timedelta(days=1)).isoformat()])
        self.assertEqual(len(item['sessions']), 1)
        self.assertNotIn('private@example.com', str(item))
        for forbidden in ('user_email', 'total_fee', 'payment_status', 'bank_account', 'revisions'):
            self.assertNotIn(forbidden, item)

        self.assertEqual(client.get('/api/admin/snowland/orders/', {'search': 'private@example.com'}).data['data']['total'], 0)
        self.assertEqual(client.get('/api/admin/snowland/orders/', {'search': item['sn']}).data['data']['total'], 1)
        self.assertEqual(client.get('/api/admin/snowland/orders/', {'payment_status': 'paid'}).data['data']['total'], 1)

        detail = client.get(f'/api/admin/snowland/orders/{created[0].id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('user_email', detail.data['data'])
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{created[1].id}/').status_code, 404)
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{created[2].id}/').status_code, 404)
        self.assertEqual(client.patch(f'/api/admin/snowland/orders/{created[0].id}/', {'payment_status': 'paid'}, format='json').status_code, 403)
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{created[0].id}/refund-preview/').status_code, 403)

    def test_campus_principal_sees_all_own_campus_dates_but_only_partial_order_info(self):
        today = timezone.localdate()
        principal = User.objects.create_user('principal', 'principal@example.com', 'test-password')
        profile = principal.userprofile
        profile.is_manager = True
        profile.role = 'campus_principal'
        profile.admin_permissions = ['orders']
        profile.save()
        profile.campuses.add(self.campus_a)
        customer = User.objects.create_user('private-customer', 'private@example.com', 'test-password')
        customer.first_name = '小雪'
        customer.save(update_fields=['first_name'])
        groups = []
        for campus, resort, offset in (
            (self.campus_a, self.resort_a, 1),
            (self.campus_a, self.resort_a, 11),
            (self.campus_b, self.resort_b, 1),
        ):
            group = ReservationGroup.objects.create(client=self.tenant, campus=campus, user=customer)
            reservation = Reservation.objects.create(group=group, resort=resort, number_of_people=2)
            MemberDetail.objects.create(reservation=reservation, age_range='7-12y')
            Booking.objects.create(
                reservation=reservation, date=today + timedelta(days=offset),
                start_time=time(9), end_time=time(11), course_type='單板', course_name='上午班',
            )
            groups.append(group)

        client = self.authenticated(principal)
        response = client.get('/api/admin/snowland/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['id'] for item in response.data['data']['list']}, {groups[0].id, groups[1].id})
        item = next(item for item in response.data['data']['list'] if item['id'] == groups[1].id)
        self.assertEqual(item['student_alias'], '小雪')
        self.assertEqual(item['course_dates'], [(today + timedelta(days=11)).isoformat()])
        self.assertEqual(item['number_of_people'], 2)
        self.assertEqual(item['sessions'][0]['age_ranges'], ['兒童7-12y'])
        for forbidden in ('user_email', 'total_fee', 'payment_status', 'bank_account', 'revisions'):
            self.assertNotIn(forbidden, item)
        self.assertEqual(client.get('/api/admin/snowland/orders/', {'search': 'private@example.com'}).data['data']['total'], 0)
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{groups[2].id}/').status_code, 404)
        self.assertEqual(client.patch(f'/api/admin/snowland/orders/{groups[0].id}/', {'payment_status': 'paid'}, format='json').status_code, 403)
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{groups[0].id}/refund-preview/').status_code, 403)

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
