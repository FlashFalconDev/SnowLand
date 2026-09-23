from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, CoachPayRule
from Coursekit.models import CourseCategory, CourseType
from Resorts.models import Campus, OperatingPolicy, PaymentAccount, Resorts
from booking.models import (
    Booking, CancellationRequest, CourseEvaluation, CourseMedia, MemberDetail, NotificationTemplate, Payment,
    Reservation, ReservationGroup, StaffBookingLink,
)
from booking.operations import calculate_refund, request_cancellation, resolve_payment_account, schedule_group_notifications
from Coach.payroll import add_payroll_adjustment, calculate_payroll_statement
from API.admin_serializers import OperatingPolicyAdminSerializer


class OperationsTests(TestCase):
    def setUp(self):
        self.client_tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.resort = Resorts.objects.create(client=self.client_tenant, name='tomamu-test', display_name='Tomamu')
        self.campus = Campus.objects.create(client=self.client_tenant, name='北海道校區', code='hokkaido')
        self.campus.resorts.add(self.resort)
        self.policy = OperatingPolicy.objects.create(
            client=self.client_tenant,
            cancellation_fee_percent=5,
            cancellation_rules=[
                {'days_before': 30, 'refund_percent': 100},
                {'days_before': 14, 'refund_percent': 80},
                {'days_before': 7, 'refund_percent': 50},
                {'days_before': 0, 'refund_percent': 0},
            ],
        )
        self.user = User.objects.create_user('student', email='student@example.com')
        self.coach_user = User.objects.create_user('coach', email='coach@example.com')
        self.coach = Coach.objects.create(client=self.client_tenant, user=self.coach_user, name='教練 A')
        self.coach.campuses.add(self.campus)
        self.category = CourseCategory.objects.create(client=self.client_tenant, name='單板')
        self.course_type = CourseType.objects.create(category=self.category, name='初階')
        self.group = ReservationGroup.objects.create(
            client=self.client_tenant, campus=self.campus, user=self.user,
            referral_user=self.coach_user, name='測試訂單', marketing_source='朋友介紹', source_country='TW',
        )
        self.reservation = Reservation.objects.create(
            group=self.group, resort=self.resort, course_type=self.course_type,
            preferred_coach=self.coach, status='completed', number_of_people=2,
            course_fee=10000, coach_fee=1000, discount_amount=1000,
        )
        self.booking_1 = Booking.objects.create(
            reservation=self.reservation, course_type='單板', course_name='初階',
            date=timezone.localdate() + timedelta(days=35), start_time=time(9), end_time=time(11), is_scheduled=True,
        )
        self.booking_2 = Booking.objects.create(
            reservation=self.reservation, course_type='單板', course_name='初階',
            date=timezone.localdate() + timedelta(days=36), start_time=time(9), end_time=time(11), is_scheduled=True,
        )

    def test_refund_uses_tier_then_subtracts_five_percent_handling_fee(self):
        values = calculate_refund(self.group)
        self.assertEqual(values['refund_percent'], 100)
        self.assertEqual(values['original_amount'], 10000)
        self.assertEqual(values['refund_amount'], 9500)

    def test_refund_rule_editor_rejects_duplicate_days_and_invalid_fee(self):
        serializer = OperatingPolicyAdminSerializer(self.policy, data={
            'cancellation_rules': [
                {'days_before': 30, 'refund_percent': 80},
                {'days_before': 30, 'refund_percent': 50},
            ],
            'cancellation_fee_percent': 101,
        }, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('cancellation_rules', serializer.errors)
        self.assertIn('cancellation_fee_percent', serializer.errors)

    def test_member_cancel_requires_owned_paid_order_and_bank_details(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='bank_transfer')
        url = f'/booking/{self.client_tenant.internal_code}/api/member-cancellations/{self.group.pk}/'
        stranger = APIClient()
        stranger.force_authenticate(user=User.objects.create_user('stranger'))
        self.assertEqual(stranger.get(url).status_code, 404)
        member = APIClient()
        member.force_authenticate(user=self.user)
        preview = member.get(url)
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.data['requires_bank_account'])
        self.assertEqual(member.post(url, {'reason': 'schedule'}, format='json').status_code, 400)
        submitted = member.post(url, {
            'reason': 'schedule', 'bank_name': 'Test Bank',
            'account_number': '123456', 'account_holder': 'Student',
        }, format='json')
        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(submitted.data['status'], 'requested')
        self.assertEqual(member.post(url, {'reason': 'schedule'}, format='json').status_code, 400)

    def test_bank_transfer_cancellation_requires_refund_bank(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='TT')
        with self.assertRaisesMessage(ValueError, '匯款訂單必須填寫'):
            request_cancellation(self.group, reason='schedule')

    def test_card_cancellation_does_not_require_refund_bank(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='credit_card')
        cancellation = request_cancellation(self.group, reason='schedule')
        self.assertEqual(cancellation.refund_amount, 9500)
        self.assertEqual(self.group.revisions.count(), 1)

    def test_staff_can_choose_configured_refund_rule(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='credit_card')
        cancellation = request_cancellation(self.group, reason='schedule', selected_rule_days_before=14)
        self.assertEqual(cancellation.calculation_mode, 'rule')
        self.assertEqual(cancellation.refund_percent, 80)
        self.assertEqual(cancellation.refund_amount, 7500)
        self.assertEqual(cancellation.selected_rule_days_before, 14)

    def test_staff_can_enter_special_refund_but_not_overpay(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='credit_card')
        with self.assertRaisesMessage(ValueError, '不可超過訂單金額'):
            request_cancellation(self.group, reason='weather', manual_refund_amount=10001)
        with self.assertRaisesMessage(ValueError, '不在目前營運規則中'):
            request_cancellation(self.group, reason='weather', selected_rule_days_before=99)
        cancellation = request_cancellation(self.group, reason='weather', manual_refund_amount=9800)
        self.assertEqual(cancellation.calculation_mode, 'manual')
        self.assertEqual(cancellation.refund_amount, 9800)
        self.assertEqual(cancellation.handling_fee_percent, 0)

    def test_payment_account_prefers_matching_resort_and_campus(self):
        fallback = PaymentAccount.objects.create(client=self.client_tenant, name='全域', is_default=True)
        matched = PaymentAccount.objects.create(client=self.client_tenant, name='北海道專用')
        matched.campuses.add(self.campus)
        matched.resorts.add(self.resort)
        self.assertEqual(resolve_payment_account(self.group), matched)
        matched.is_active = False
        matched.save()
        self.assertEqual(resolve_payment_account(self.group), fallback)

    def test_notifications_are_scheduled_for_matching_campus(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, DataJSON={'contact': {'email': 'student@example.com'}}
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='付款通知', event='payment_confirmed',
            channel='email', subject='付款完成', body='收到款項',
        )
        other = Campus.objects.create(client=self.client_tenant, name='其他校區', code='other')
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=other, name='不應發送', event='payment_confirmed',
            channel='email', subject='錯誤', body='錯誤',
        )
        deliveries = schedule_group_notifications(self.group, 'payment_confirmed')
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].recipient, 'student@example.com')

    def test_payroll_does_not_duplicate_per_reservation_fees_across_days(self):
        CoachPayRule.objects.create(
            coach=self.coach, discipline='snowboard', hourly_rate=1000,
            specified_fee=500, referral_percent=10, supervisor_allowance=300,
        )
        statement = calculate_payroll_statement(
            coach=self.coach, campus=self.campus,
            period_start=self.booking_1.date, period_end=self.booking_2.date,
        )
        self.assertEqual(statement.course_pay, 4000)
        self.assertEqual(statement.specified_fees, 500)
        self.assertEqual(statement.referral_commission, 900)
        self.assertEqual(statement.supervisor_allowance, 300)
        self.assertEqual(statement.total_amount, 5700)

    def test_manual_payroll_items_survive_recalculation_and_are_itemized(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
        args = dict(coach=self.coach, campus=self.campus, period_start=self.booking_1.date, period_end=self.booking_2.date)
        statement = calculate_payroll_statement(**args)
        add_payroll_adjustment(statement=statement, description='本月日文協助費', amount=1200)
        statement = calculate_payroll_statement(**args)
        self.assertEqual(statement.adjustment, 1200)
        self.assertEqual(statement.total_amount, 5200)
        self.assertEqual(statement.lines.filter(line_type='adjustment', description='本月日文協助費').count(), 1)

    def test_cross_tenant_pay_rule_is_rejected(self):
        other_tenant = Client.objects.create(name='Other', internal_code='other')
        other_coach = Coach.objects.create(client=other_tenant, name='外部教練')
        admin = User.objects.create_superuser('root', 'root@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.post('/api/admin/snowland/coach-pay-rules/', {
            'coach': other_coach.id, 'discipline': 'ski', 'hourly_rate': 1000,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_member_center_quick_rebook_only_returns_own_tenant_order(self):
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'quick_rebook_group_id': self.group.id,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['cart']), 1)
        self.assertEqual(response.data['cart'][0]['campusId'], self.campus.id)

        stranger = User.objects.create_user('stranger')
        api.force_authenticate(stranger)
        response = api.post('/booking/snowland/api/member-center/', {
            'quick_rebook_group_id': self.group.id,
        }, format='json')
        self.assertEqual(response.status_code, 404)

    def test_member_center_returns_real_orders_forms_and_learning_records(self):
        member = MemberDetail.objects.create(
            reservation=self.reservation,
            user=self.user,
            age_range='25-35y',
            snowboard_skills=['雪場S turn'],
        )
        evaluation = CourseEvaluation.objects.create(
            booking=self.booking_1,
            member=member,
            coach=self.coach,
            learning_progress={'before': '等級 1', 'after': '等級 2'},
            coach_notes='轉彎控制已有明顯進步。',
            completed_at=timezone.now(),
        )
        CourseMedia.objects.create(
            evaluation=evaluation,
            media_type='photo',
            url='https://example.com/lesson.jpg',
            is_public=True,
        )
        CourseMedia.objects.create(
            evaluation=evaluation,
            media_type='photo',
            url='https://example.com/private.jpg',
            is_public=False,
        )
        api = APIClient(); api.force_authenticate(self.user)

        response = api.get('/booking/snowland/api/member-center/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['member']['email'], 'student@example.com')
        self.assertEqual(response.data['orders'][0]['id'], self.group.id)
        self.assertEqual(response.data['orders'][0]['reservations'][0]['resort'], 'Tomamu')
        self.assertEqual(response.data['pre_course_forms'][0]['age_range'], '25-35y')
        self.assertEqual(response.data['learning_records'][0]['coach_notes'], '轉彎控制已有明顯進步。')
        self.assertEqual(response.data['learning_records'][0]['media'][0]['url'], 'https://example.com/lesson.jpg')
        self.assertEqual(len(response.data['learning_records'][0]['media']), 1)

    def test_member_email_registration_and_login_use_real_django_session(self):
        api = APIClient()
        registered = api.post('/booking/snowland/api/member-auth/', {
            'action': 'register',
            'email': 'new-member@example.com',
            'password': 'secure-pass-123',
        }, format='json')
        self.assertEqual(registered.status_code, 201)
        self.assertTrue(User.objects.get(email='new-member@example.com').check_password('secure-pass-123'))
        self.assertEqual(api.get('/booking/snowland/api/member-center/').status_code, 200)

        api.post('/control/api/logout/', {}, format='json')
        rejected = api.post('/booking/snowland/api/member-auth/', {
            'action': 'login', 'email': 'new-member@example.com', 'password': 'wrong-password',
        }, format='json')
        self.assertEqual(rejected.status_code, 400)
        logged_in = api.post('/booking/snowland/api/member-auth/', {
            'action': 'login', 'email': 'new-member@example.com', 'password': 'secure-pass-123',
        }, format='json')
        self.assertEqual(logged_in.status_code, 200)

    def test_staff_booking_link_resolves_only_before_use_and_expiry(self):
        link = StaffBookingLink.objects.create(
            client=self.client_tenant, campus=self.campus, created_by=self.coach_user,
            title='北海道櫃台', expires_at=timezone.now() + timedelta(days=1),
        )
        response = APIClient().get(f'/booking/snowland/api/staff-booking-link/{link.token}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['campus']['id'], self.campus.id)
        link.used_at = timezone.now(); link.save(update_fields=['used_at'])
        self.assertEqual(APIClient().get(f'/booking/snowland/api/staff-booking-link/{link.token}/').status_code, 404)

    def test_insurance_staff_can_complete_only_assigned_campus_record(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        staff = User.objects.create_user('insurance-staff')
        profile = staff.userprofile
        profile.is_manager = True
        profile.role = 'insurance'
        profile.admin_permissions = ['insurance_records']
        profile.save()
        profile.campuses.add(self.campus)
        api = APIClient(); api.force_authenticate(staff)
        response = api.post(f'/api/admin/snowland/insurance-records/{member.id}/complete/', {
            'field': 'insurance',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        member.refresh_from_db()
        self.assertIsNotNone(member.insurance_completed_at)

    def test_cancellation_state_cannot_skip_approval(self):
        cancellation = CancellationRequest.objects.create(
            group=self.group, reason='schedule', original_amount=10000, refund_amount=9500,
        )
        admin = User.objects.create_superuser('cancel-admin', 'cancel@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.post(f'/api/admin/snowland/cancellations/{cancellation.id}/process/', {
            'status': 'refunded',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_background_job_prepares_evaluations_for_completed_course(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        call_command('process_snowland_jobs')
        self.assertTrue(CourseEvaluation.objects.filter(booking=self.booking_1, member=member).exists())
        self.assertTrue(CourseEvaluation.objects.filter(booking=self.booking_2, member=member).exists())

    def test_order_console_prefers_customer_display_name_over_login_name(self):
        self.user.first_name = '小林'
        self.user.save(update_fields=['first_name'])
        admin = User.objects.create_superuser('display-admin', 'display@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.get('/api/admin/snowland/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['list'][0]['user_name'], '小林')
        search_response = api.get('/api/admin/snowland/orders/?search=小林')
        self.assertEqual(search_response.data['data']['total'], 1)
