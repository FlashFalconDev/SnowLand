from datetime import date, time, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client, SiteContent
from Coach.models import Coach, CoachPayRule, PayrollStatement
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from Resorts.models import Campus, EquipmentAssistanceTimeSlot, OperatingPolicy, PaymentAccount, Resorts
from booking.models import (
    Booking, CancellationRequest, CourseEvaluation, CourseMedia, MemberDetail, NotificationDelivery, NotificationTemplate, Payment,
    Reservation, ReservationGroup, StaffBookingLink,
)
from booking.operations import calculate_refund, request_cancellation, resolve_payment_account, schedule_group_notifications, record_order_revision
from booking.payment_access import PAYMENT_LINK_MAX_AGE, can_access_payment, payment_access_token, payment_url_for_group
from booking.legal_documents import get_current_waiver
from Coach.payroll import add_payroll_adjustment, calculate_payroll_statement
from booking.tasks import auto_cancel_unpaid_reservations
from booking.views import payment as legacy_payment
from API.admin_serializers import CoachAdminSerializer, CourseEvaluationAdminSerializer, NotificationTemplateAdminSerializer, OperatingPolicyAdminSerializer


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

    def test_order_detail_keeps_history_beyond_list_preview_limit(self):
        for version in range(21):
            record_order_revision(self.group, reason=f'Version {version + 1}')
        api = APIClient()
        api.force_authenticate(User.objects.create_superuser('history-hq', 'history-hq@example.test', 'test-password'))
        detail = api.get(f'/api/admin/snowland/orders/{self.group.pk}/')
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(len(detail.data['data']['revisions']), 21)
        self.assertEqual(detail.data['data']['revisions'][-1]['version'], 1)
        listed = api.get('/api/admin/snowland/orders/').data['data']['list'][0]
        self.assertEqual(len(listed['revisions']), 20)
        self.assertNotIn('snapshot', listed['revisions'][0])

    def test_order_revision_difference_preserves_zero_baseline_and_old_snapshots(self):
        self.reservation.course_fee = 0
        self.reservation.coach_fee = 0
        self.reservation.discount_amount = 0
        self.reservation.save()
        initial = record_order_revision(self.group, change_type='create')
        self.assertEqual(initial.difference_amount, 0)
        self.reservation.course_fee = 3000
        self.reservation.save()
        increased = record_order_revision(self.group)
        self.assertEqual(increased.difference_amount, 3000)
        self.reservation.course_fee = 0
        self.reservation.save()
        decreased = record_order_revision(self.group)
        self.assertEqual(decreased.difference_amount, -3000)
        self.reservation.course_fee = 2000
        self.reservation.save()
        explicit_zero = record_order_revision(self.group, previous_total=0)
        self.assertEqual(explicit_zero.difference_amount, 2000)
        initial.refresh_from_db()
        self.assertEqual(initial.snapshot['reservations'][0]['payable'], 0)
        self.assertEqual(list(self.group.revisions.order_by('version').values_list('version', flat=True)), [1, 2, 3, 4])
        api = APIClient()
        api.force_authenticate(User.objects.create_superuser('revision-hq', 'revision-hq@example.test', 'test-password'))
        response = api.get(f'/api/admin/snowland/orders/{self.group.pk}/revisions/')
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['data']['list']
        self.assertEqual([row['difference_amount'] for row in rows], [2000, -3000, 3000, 0])
        self.assertEqual(rows[-1]['snapshot']['reservations'][0]['payable'], 0)
        self.coach.name = 'Renamed coach'
        self.coach.save(update_fields=['name'])
        detail = api.get(f'/api/admin/snowland/orders/{self.group.pk}/')
        self.assertEqual(detail.status_code, 200, detail.data)
        history = detail.data['data']['revisions']
        self.assertEqual(history[-1]['snapshot']['reservations'][0]['coach_name'], '教練 A')
        self.assertEqual(history[-1]['snapshot']['reservations'][0]['resort_name'], 'Tomamu')
        listed = api.get('/api/admin/snowland/orders/').data['data']['list'][0]
        self.assertNotIn('snapshot', listed['revisions'][0])
        api.force_authenticate(self.user)
        self.assertEqual(api.get(f'/api/admin/snowland/orders/{self.group.pk}/revisions/').status_code, 403)

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

    def test_member_center_tracks_paid_cancellation_review_and_refund(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid', payment_method='credit_card',
        )
        member = APIClient()
        member.force_authenticate(user=self.user)
        cancellation_url = f'/booking/{self.client_tenant.internal_code}/api/member-cancellations/{self.group.pk}/'
        center_url = f'/booking/{self.client_tenant.internal_code}/api/member-center/'

        requested = member.post(cancellation_url, {'reason': 'schedule'}, format='json')
        self.assertEqual(requested.status_code, 201, requested.data)
        order = next(row for row in member.get(center_url).data['orders'] if row['id'] == self.group.pk)
        self.assertEqual(order['cancellation']['status'], 'requested')
        self.assertEqual(order['cancellation']['original_amount'], 10000)
        self.assertEqual(order['cancellation']['refund_amount'], 9500)

        admin = APIClient()
        admin.force_authenticate(user=User.objects.create_superuser('cancel-reviewer', 'reviewer@example.test', 'test-password'))
        process_url = f'/api/admin/snowland/cancellations/{requested.data["id"]}/process/'
        approved = admin.post(process_url, {'status': 'approved'}, format='json')
        self.assertEqual(approved.status_code, 200, approved.data)
        order = next(row for row in member.get(center_url).data['orders'] if row['id'] == self.group.pk)
        self.assertEqual(order['payment_status'], 'paid')
        self.assertEqual(order['cancellation']['status'], 'approved')
        self.assertEqual(order['cancellation']['refund_amount'], 9500)

        refunded = admin.post(process_url, {'status': 'refunded'}, format='json')
        self.assertEqual(refunded.status_code, 200, refunded.data)
        order = next(row for row in member.get(center_url).data['orders'] if row['id'] == self.group.pk)
        self.assertEqual(order['payment_status'], 'refunded')
        self.assertEqual(order['cancellation']['status'], 'refunded')

    def test_rejected_cancellation_can_be_submitted_again(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid', payment_method='credit_card',
        )
        member = APIClient()
        member.force_authenticate(user=self.user)
        cancellation_url = f'/booking/{self.client_tenant.internal_code}/api/member-cancellations/{self.group.pk}/'
        first = member.post(cancellation_url, {'reason': 'schedule'}, format='json')
        self.assertEqual(first.status_code, 201, first.data)

        admin = APIClient()
        admin.force_authenticate(user=User.objects.create_superuser('reject-reviewer', 'reject@example.test', 'test-password'))
        process_url = f'/api/admin/snowland/cancellations/{first.data["id"]}/process/'
        rejected = admin.post(process_url, {'status': 'rejected'}, format='json')
        self.assertEqual(rejected.status_code, 200, rejected.data)
        self.assertEqual(member.get(cancellation_url).data['request_status'], 'rejected')

        second = member.post(cancellation_url, {'reason': 'health'}, format='json')
        self.assertEqual(second.status_code, 201, second.data)
        self.assertNotEqual(second.data['id'], first.data['id'])
        self.assertEqual(CancellationRequest.objects.get(pk=first.data['id']).status, 'rejected')

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

    def test_payment_account_does_not_use_another_resorts_account(self):
        other_resort = Resorts.objects.create(client=self.client_tenant, name='qa-other-resort', display_name='其他雪場')
        wrong = PaymentAccount.objects.create(client=self.client_tenant, name='其他雪場專用', is_default=True)
        wrong.campuses.add(self.campus)
        wrong.resorts.add(other_resort)
        fallback = PaymentAccount.objects.create(client=self.client_tenant, name='全公司通用')
        self.assertEqual(resolve_payment_account(self.group), fallback)

    def test_configured_account_reaches_modern_and_legacy_payment_pages(self):
        self.client.force_login(self.user)
        account = PaymentAccount.objects.create(
            client=self.client_tenant, name='北海道收款', bank_name='測試銀行',
            bank_branch='北海道分行', account_number='QA-ACCOUNT-001', account_holder='測試戶名',
        )
        account.campuses.add(self.campus)
        account.resorts.add(self.resort)
        modern = self.client.get(
            f'/booking/{self.client_tenant.internal_code}/api/payment-info/',
            {'reservation_group': self.group.pk},
        )
        self.assertEqual(modern.status_code, 200)
        self.assertEqual(modern.json()['bank_info']['bank_account_number'], 'QA-ACCOUNT-001')
        self.assertIn('bank_transfer', modern.json()['payment_methods'])

        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        Payment.objects.create(reservation_group=self.group, user=self.user, status='unpaid')
        request = RequestFactory().get('/booking/snowland/payment/', {'reservation_group': self.group.pk})
        request.user = self.user
        request.tenant = self.client_tenant
        request.client_code = self.client_tenant.internal_code
        with patch('booking.views.requests.get', side_effect=RuntimeError('offline')):
            legacy = legacy_payment(request, client_code=self.client_tenant.internal_code)
        self.assertEqual(legacy.status_code, 200)
        self.assertIn('QA-ACCOUNT-001', legacy.content.decode())
        self.assertNotIn('123-456-789012', legacy.content.decode())

    def test_legacy_payment_page_hides_member_order_from_other_users(self):
        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        url = f'/booking/{self.client_tenant.internal_code}/payment/'

        for user in (User.objects.create_user('payment-stranger'), None):
            request = RequestFactory().get(url, {'reservation_group': self.group.pk})
            request.user = user or SimpleNamespace(id=None, is_authenticated=False)
            request.tenant = self.client_tenant
            request.client_code = self.client_tenant.internal_code
            with self.assertRaises(Http404):
                legacy_payment(request, client_code=self.client_tenant.internal_code)

        request = RequestFactory().get(url, {'reservation_group': self.group.pk})
        request.user = self.user
        request.tenant = self.client_tenant
        request.client_code = self.client_tenant.internal_code
        self.assertEqual(legacy_payment(request, client_code=self.client_tenant.internal_code).status_code, 200)

    def test_guest_payment_requires_order_specific_signed_link(self):
        guest_group = ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus, source_country='TW')
        Reservation.objects.create(group=guest_group, resort=self.resort, status='completed', course_fee=5000)
        Payment.objects.create(reservation_group=guest_group, status='unpaid')
        PaymentAccount.objects.create(
            client=self.client_tenant, name='測試收款', is_default=True,
            bank_name='測試銀行', bank_branch='測試分行', account_number='QA-001', account_holder='測試戶名',
        )
        info_url = '/booking/snowland/api/payment-info/'
        pay_url = '/booking/snowland/api/process-payment/'
        guest = APIClient()
        self.assertEqual(guest.get(info_url, {'reservation_group': 'not-a-number'}).status_code, 404)
        self.assertEqual(guest.get(info_url, {'reservation_group': guest_group.pk}).status_code, 404)
        self.assertEqual(guest.post(pay_url, {
            'reservation_group_id': guest_group.pk, 'payment_type': 'bank_transfer', 'sender_account': '12345',
        }, format='json').status_code, 404)
        link = payment_url_for_group('https://example.test/payment', guest_group)
        self.assertIn('access_token=', link)
        token = payment_access_token(guest_group)
        with patch('django.core.signing.time.time', return_value=1_700_000_000):
            expiring_token = payment_access_token(guest_group)
        with patch('django.core.signing.time.time', return_value=1_700_000_000 + PAYMENT_LINK_MAX_AGE + 1):
            self.assertFalse(can_access_payment(guest_group, None, expiring_token))
        self.assertEqual(guest.get(info_url, {
            'reservation_group': guest_group.pk, 'access_token': payment_access_token(self.group),
        }).status_code, 404)
        self.assertEqual(guest.get(info_url, {
            'reservation_group': guest_group.pk, 'access_token': token + 'x',
        }).status_code, 404)
        self.assertEqual(guest.get(info_url, {
            'reservation_group': guest_group.pk, 'access_token': token,
        }).status_code, 200)
        paid = guest.post(pay_url, {
            'reservation_group_id': guest_group.pk, 'payment_type': 'bank_transfer',
            'sender_account': '12345', 'access_token': token,
        }, format='json')
        self.assertEqual(paid.status_code, 200, paid.data)
        self.assertEqual(Payment.objects.get(reservation_group=guest_group).bank_account, '12345')

        request = RequestFactory().get('/booking/snowland/payment/', {'reservation_group': guest_group.pk})
        request.user = SimpleNamespace(id=None, is_authenticated=False)
        request.tenant = self.client_tenant
        request.client_code = self.client_tenant.internal_code
        with self.assertRaises(Http404):
            legacy_payment(request, client_code=self.client_tenant.internal_code)

        visitor = User.objects.create_user('guest-link-visitor', email='guest-link-visitor@example.test')
        self.client.force_login(visitor)
        old_url = '/booking/api/process_payment/'
        old_body = {
            'reservation_group_pk': guest_group.pk, 'paymentType': 'TT', 'senderAccount': '12345',
        }
        self.assertEqual(self.client.post(old_url, old_body, content_type='application/json').status_code, 404)
        old_body['access_token'] = token
        self.assertEqual(self.client.post(old_url, old_body, content_type='application/json').status_code, 200)

    def test_legacy_payment_api_uses_authenticated_order_owner_not_body_user(self):
        PaymentAccount.objects.create(client=self.client_tenant, name='QA合法收款設定', is_default=True,
            bank_name='QA銀行', bank_branch='QA分行', account_number='QA-ONLY', account_holder='QA戶名')
        payment = Payment.objects.create(reservation_group=self.group, user=self.user, status='unpaid')
        stranger = User.objects.create_user('payment-api-stranger', email='stranger@example.test')
        url = '/booking/api/process_payment/'
        body = {
            'reservation_group_pk': self.group.pk,
            'paymentType': 'TT',
            'senderAccount': '12345',
            'user': {'id': self.user.pk},
        }

        self.client.force_login(stranger)
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 404)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'unpaid')

        self.client.force_login(self.user)
        body['user'] = {'id': stranger.pk}
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.user, self.user)

        payment.status = 'paid'
        payment.save(update_fields=['status'])
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'paid')

        self.client.logout()
        self.assertEqual(self.client.post(url, body, content_type='application/json', HTTP_JWT='unverified|student@example.com').status_code, 401)

    def test_each_campus_order_returns_its_own_bank_account_and_amount(self):
        self.client.force_login(self.user)
        first_account = PaymentAccount.objects.create(
            client=self.client_tenant, name='北海道收款', bank_name='測試銀行 A',
            bank_branch='A 分行', account_number='QA-ACCOUNT-A', account_holder='測試戶名 A',
        )
        first_account.campuses.add(self.campus)
        first_account.resorts.add(self.resort)
        other_campus = Campus.objects.create(client=self.client_tenant, name='道東校區', code='east')
        other_resort = Resorts.objects.create(client=self.client_tenant, name='furano-test', display_name='Furano')
        other_campus.resorts.add(other_resort)
        second_account = PaymentAccount.objects.create(
            client=self.client_tenant, name='道東收款', bank_name='測試銀行 B',
            bank_branch='B 分行', account_number='QA-ACCOUNT-B', account_holder='測試戶名 B',
        )
        second_account.campuses.add(other_campus)
        second_account.resorts.add(other_resort)
        other_group = ReservationGroup.objects.create(
            client=self.client_tenant, campus=other_campus, user=self.user, source_country='TW',
        )
        Reservation.objects.create(group=other_group, resort=other_resort, course_fee=5000)

        payment_url = f'/booking/{self.client_tenant.internal_code}/api/payment-info/'
        first = self.client.get(payment_url, {'reservation_group': self.group.pk})
        second = self.client.get(payment_url, {'reservation_group': other_group.pk})
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()['bank_info']['bank_account_number'], 'QA-ACCOUNT-A')
        self.assertEqual(second.json()['bank_info']['bank_account_number'], 'QA-ACCOUNT-B')
        self.assertEqual(first.json()['total_amount'], 10000)
        self.assertEqual(second.json()['total_amount'], 5000)
        self.assertEqual(first.json()['payment_methods'], ['bank_transfer'])
        self.assertEqual(second.json()['payment_methods'], ['bank_transfer'])

    def test_incomplete_account_cannot_accept_bank_transfer(self):
        self.client.force_login(self.user)
        PaymentAccount.objects.create(client=self.client_tenant, name='資料未填完', bank_name='測試銀行')
        info = self.client.get(
            f'/booking/{self.client_tenant.internal_code}/api/payment-info/',
            {'reservation_group': self.group.pk},
        )
        self.assertEqual(info.status_code, 200)
        self.assertNotIn('bank_transfer', info.json()['payment_methods'])
        submit = self.client.post(
            f'/booking/{self.client_tenant.internal_code}/api/process-payment/',
            {'reservation_group_id': self.group.pk, 'payment_type': 'bank_transfer', 'sender_account': '12345'},
            content_type='application/json',
        )
        self.assertEqual(submit.status_code, 400)
        self.assertFalse(Payment.objects.filter(reservation_group=self.group, status='pending').exists())

    def test_unpaid_order_stays_active_until_configured_expiration(self):
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            created_at=timezone.now() - timedelta(days=2),
            expires_at=timezone.now() + timedelta(days=1),
        )
        Payment.objects.filter(pk=payment.pk).update(created_at=timezone.now() - timedelta(days=2))
        auto_cancel_unpaid_reservations()
        payment.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(payment.status, 'unpaid')
        self.assertEqual(self.reservation.status, 'completed')

    def test_coach_schedule_visibility_default_and_full_setting(self):
        today = timezone.localdate()
        for offset in (-1, 10, 11):
            Booking.objects.create(
                reservation=self.reservation, course_type='單板', course_name='初階',
                date=today + timedelta(days=offset), start_time=time(9),
                end_time=time(11), is_scheduled=True,
            )
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        def visible_dates(path):
            response = api.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['data']['visibility_mode'],
                             'full' if self.coach.schedule_visibility == 'full' else 'recent_10_days')
            items = response.data['data']['list']
            if path.endswith('my-courses/'):
                return {booking['date'] for item in items for booking in item['bookings']}
            return {item['date'] for item in items}

        courses_url = '/api/admin/snowland/coach/my-courses/'
        calendar_url = '/api/admin/snowland/coach/my-calendar/'
        restricted = {(today + timedelta(days=offset)).isoformat() for offset in (-1, 10)}
        for path in (courses_url, calendar_url):
            self.assertEqual(visible_dates(path), restricted)
        future_only = api.get(courses_url, {'date_from': (today + timedelta(days=11)).isoformat()})
        self.assertEqual(future_only.status_code, 200)
        self.assertEqual(future_only.data['data']['list'], [])

        self.coach.schedule_visibility = 'full'
        self.coach.save(update_fields=['schedule_visibility'])
        all_dates = {(today + timedelta(days=offset)).isoformat() for offset in (-1, 10, 11, 35, 36)}
        for path in (courses_url, calendar_url):
            self.assertEqual(visible_dates(path), all_dates)

    def test_coach_can_confirm_future_booking_not_yet_visible_in_schedule(self):
        self.reservation.status = 'pending_coach_confirmation'
        self.reservation.save(update_fields=['status'])
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        pending = api.get('/api/admin/snowland/coach/pending/')
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.data['data']['visibility_mode'], 'all_pending')
        self.assertEqual(pending.data['data']['total'], 1)
        self.assertEqual(
            {booking['date'] for booking in pending.data['data']['list'][0]['bookings']},
            {(timezone.localdate() + timedelta(days=offset)).isoformat() for offset in (35, 36)},
        )

        for path in ('/api/admin/snowland/coach/my-courses/', '/api/admin/snowland/coach/my-calendar/'):
            response = api.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['data']['list'], [])

    def test_coach_order_views_expose_only_student_alias_and_lesson_details(self):
        self.user.first_name = '小雪'
        self.user.last_name = '私密姓氏'
        self.user.save(update_fields=['first_name', 'last_name'])
        self.reservation.status = 'pending_coach_confirmation'
        self.reservation.save(update_fields=['status'])
        self.booking_1.date = timezone.localdate() + timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
        MemberDetail.objects.create(reservation=self.reservation, age_range='7-12y')
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        for path in ('coach/pending/', 'coach/my-courses/'):
            response = api.get(f'/api/admin/snowland/{path}')
            self.assertEqual(response.status_code, 200)
            item = response.data['data']['list'][0]
            self.assertEqual(item['user_name'], '小雪')
            if path == 'coach/my-courses/':
                self.assertEqual(item['course_category'], '單板')
            self.assertEqual(item['age_ranges'], ['兒童7-12y'])
            self.assertEqual(item['language_label'], '中文')
            self.assertNotIn('total_fee', item)
            self.assertNotIn('student@example.com', str(item))
            self.assertNotIn('私密姓氏', str(item))

        calendar = api.get('/api/admin/snowland/coach/my-calendar/')
        self.assertEqual(calendar.status_code, 200)
        self.assertEqual(calendar.data['data']['list'][0]['user_name'], '小雪')

    def test_coach_cannot_reject_a_completed_course(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        self.coach.schedule_visibility = 'full'
        self.coach.save(update_fields=['schedule_visibility'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        response = api.post(
            f'/api/admin/snowland/coach/confirm/{self.reservation.id}/',
            {'action': 'reject'}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        courses = api.get('/api/admin/snowland/coach/my-courses/')
        self.assertEqual(courses.status_code, 200)
        item = courses.data['data']['list'][0]
        self.assertEqual(item['status'], 'completed')
        self.assertTrue(all(booking['is_scheduled'] for booking in item['bookings']))

    def test_coach_can_accept_pending_course_but_cannot_reject_it_after_accepting(self):
        self.reservation.status = 'pending_coach_confirmation'
        self.reservation.save(update_fields=['status'])
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        self.coach.schedule_visibility = 'full'
        self.coach.save(update_fields=['schedule_visibility'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)
        url = f'/api/admin/snowland/coach/confirm/{self.reservation.id}/'

        self.assertEqual(api.post(url, {'action': 'accept'}, format='json').status_code, 200)
        self.assertEqual(api.post(url, {'action': 'reject'}, format='json').status_code, 400)
        courses = api.get('/api/admin/snowland/coach/my-courses/')
        self.assertEqual(courses.status_code, 200)
        self.assertEqual(courses.data['data']['list'][0]['status'], 'manually_assigned')

    def test_coach_cannot_view_or_confirm_another_tenants_order(self):
        other_tenant = Client.objects.create(name='Other', internal_code='other')
        other_resort = Resorts.objects.create(client=other_tenant, name='other', display_name='Other Resort')
        assistance_slot = EquipmentAssistanceTimeSlot.objects.create(
            resort=other_resort, label='裝備協助', start_time=time(8), end_time=time(8, 30),
        )
        other_group = ReservationGroup.objects.create(client=other_tenant, user=self.user)
        other_reservation = Reservation.objects.create(
            group=other_group, preferred_coach=self.coach,
            resort=other_resort, equipment='purchaseAssistanceTime',
            equipment_assistance_time_slot=assistance_slot,
            status='pending_coach_confirmation', number_of_people=1,
        )
        Booking.objects.create(
            reservation=other_reservation, date=timezone.localdate() + timedelta(days=1),
            start_time=time(9), end_time=time(11), is_scheduled=True,
        )
        Payment.objects.create(reservation_group=other_group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        for path in ('coach/pending/', 'coach/my-courses/', 'coach/my-calendar/'):
            response = api.get(f'/api/admin/snowland/{path}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['data']['list'], [])
        response = api.post(
            f'/api/admin/snowland/coach/confirm/{other_reservation.id}/',
            {'action': 'accept'}, format='json',
        )
        self.assertEqual(response.status_code, 404)

    def test_coach_leave_counts_only_snowland_courses(self):
        leave_date = timezone.localdate() + timedelta(days=7)
        self.reservation.status = 'manually_assigned'
        self.reservation.save(update_fields=['status'])
        self.booking_1.date = leave_date
        self.booking_1.save(update_fields=['date'])
        other_tenant = Client.objects.create(name='Other', internal_code='other')
        other_group = ReservationGroup.objects.create(client=other_tenant, user=self.user)
        other_reservation = Reservation.objects.create(
            group=other_group, preferred_coach=self.coach, status='manually_assigned',
        )
        Booking.objects.create(
            reservation=other_reservation, date=leave_date,
            start_time=time(9), end_time=time(11), is_scheduled=True,
        )
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        response = api.post('/api/admin/snowland/coach/apply-leave/', {
            'start_date': leave_date.isoformat(),
            'end_date': leave_date.isoformat(),
            'reason': '請假測試',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['affected_count'], 1)
        leaves = api.get('/api/admin/snowland/coach/my-leaves/')
        self.assertEqual(leaves.status_code, 200)
        self.assertEqual(leaves.data['data']['list'][0]['affected_count'], 1)

    def test_coach_schedule_visibility_serializer_rejects_invalid_value(self):
        self.assertEqual(self.coach.schedule_visibility, 'ten_days')
        serializer = CoachAdminSerializer(self.coach, data={'schedule_visibility': 'anything'}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('schedule_visibility', serializer.errors)

    def test_unpaid_order_expires_after_configured_deadline(self):
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        auto_cancel_unpaid_reservations()
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'expired')

    def test_scheduled_job_releases_expired_unpaid_reservation(self):
        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        call_command('process_snowland_jobs', '--dry-run')
        payment.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(payment.status, 'unpaid')
        self.assertEqual(self.reservation.status, 'auto_assigned')
        call_command('process_snowland_jobs')
        payment.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(payment.status, 'expired')
        self.assertEqual(self.reservation.status, 'cancelled')

    def test_expired_payment_attempt_does_not_cancel_paid_order(self):
        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        protected_payment = Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        expired_attempt = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        call_command('process_snowland_jobs')
        self.reservation.refresh_from_db()
        expired_attempt.refresh_from_db()
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertEqual(expired_attempt.status, 'expired')
        protected_payment.status = 'pending'
        protected_payment.save(update_fields=['status'])
        second_attempt = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        call_command('process_snowland_jobs')
        self.reservation.refresh_from_db()
        second_attempt.refresh_from_db()
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertEqual(second_attempt.status, 'expired')

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

    def test_order_and_payment_confirmations_ignore_course_advance_days(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user,
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        for event in ('order_created', 'payment_confirmed'):
            NotificationTemplate.objects.create(
                client=self.client_tenant, campus=self.campus, name=f'{event} 通知', event=event,
                channel='email', subject='確認通知', body='已成立', days_before=3,
            )
            before = timezone.now()
            delivery = schedule_group_notifications(self.group, event)[0]
            self.assertLessEqual(before, delivery.scheduled_at)
            self.assertLessEqual(delivery.scheduled_at, timezone.now())

    def test_order_confirmation_template_saves_as_immediate(self):
        serializer = NotificationTemplateAdminSerializer(
            data={
                'name': '訂單確認', 'campus': self.campus.pk, 'event': 'order_created',
                'channel': 'email', 'subject': '訂單成立', 'body': '已收到訂單', 'days_before': 3,
            },
            context={'request': SimpleNamespace(tenant=self.client_tenant)},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.save().days_before, 0)

    def test_active_shared_class_notice_requires_payment_link_and_deliverable_channel(self):
        base = {
            'name': '成班付款', 'campus': self.campus.pk, 'event': 'shared_class_ready',
            'channel': 'email', 'subject': '請付款', 'body': '請付款', 'days_before': 3,
            'is_active': True,
        }
        context = {'request': SimpleNamespace(tenant=self.client_tenant)}
        missing_link = NotificationTemplateAdminSerializer(data=base, context=context)
        self.assertFalse(missing_link.is_valid())
        self.assertIn('body', missing_link.errors)

        in_app = NotificationTemplateAdminSerializer(
            data={**base, 'channel': 'in_app', 'body': '請付款：{payment_url}'}, context=context,
        )
        self.assertFalse(in_app.is_valid())
        self.assertIn('channel', in_app.errors)

        valid = NotificationTemplateAdminSerializer(
            data={**base, 'body': '請付款：{payment_url}'}, context=context,
        )
        self.assertTrue(valid.is_valid(), valid.errors)
        notice = valid.save()
        self.assertEqual(notice.days_before, 0)

        removing_link = NotificationTemplateAdminSerializer(
            notice, data={'body': '請付款'}, partial=True, context=context,
        )
        self.assertFalse(removing_link.is_valid())
        self.assertIn('body', removing_link.errors)

    def test_shared_class_notice_api_rejects_missing_payment_link(self):
        admin = User.objects.create_superuser('notification-admin', 'notification-admin@example.test', 'test-password')
        api = APIClient()
        api.force_authenticate(user=admin)
        response = api.post('/api/admin/snowland/notification-templates/', {
            'name': '成班付款', 'event': 'shared_class_ready', 'channel': 'email',
            'subject': '請付款', 'body': '您的團體班已成班', 'is_active': True,
        }, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('body', response.data)
        self.assertFalse(NotificationTemplate.objects.filter(name='成班付款').exists())

    def test_notification_template_only_matches_selected_course_template(self):
        matching = CourseTemplate.objects.create(course_type=self.course_type, name='符合課程', duration_hours=6)
        other = CourseTemplate.objects.create(course_type=self.course_type, name='其他課程', duration_hours=3)
        self.reservation.course_template = matching
        self.reservation.save(update_fields=['course_template'])
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='指定課程提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=3,
        )
        template.course_templates.add(other)
        self.assertEqual(schedule_group_notifications(self.group, 'pre_course'), [])
        template.course_templates.add(matching)
        self.assertEqual(len(schedule_group_notifications(self.group, 'pre_course')), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_disabled_template_cancels_queued_delivery_without_sending(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='停用提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=0,
        )
        delivery = NotificationDelivery.objects.create(
            template=template, group=self.group, recipient='student@example.com',
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        template.is_active = False
        template.save(update_fields=['is_active'])
        call_command('process_snowland_jobs')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'cancelled')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_course_restriction_change_cancels_queued_delivery(self):
        matching = CourseTemplate.objects.create(course_type=self.course_type, name='原課程', duration_hours=6)
        other = CourseTemplate.objects.create(course_type=self.course_type, name='其他課程', duration_hours=3)
        self.reservation.course_template = matching
        self.reservation.save(update_fields=['course_template'])
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='改課程提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=0,
        )
        template.course_templates.add(matching)
        delivery = NotificationDelivery.objects.create(
            template=template, group=self.group, recipient='student@example.com',
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        template.course_templates.set([other])
        call_command('process_snowland_jobs')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'cancelled')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reactivated_template_creates_one_new_delivery(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='重新啟用提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=0,
        )
        original = NotificationDelivery.objects.create(
            template=template, group=self.group, recipient='student@example.com',
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        template.is_active = False
        template.save(update_fields=['is_active'])
        call_command('process_snowland_jobs')
        original.refresh_from_db()
        self.assertEqual(original.status, 'cancelled')
        template.is_active = True
        template.save(update_fields=['is_active'])
        call_command('process_snowland_jobs')
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(template=template, group=self.group).count(), 3)
        self.assertEqual(NotificationDelivery.objects.filter(template=template, group=self.group, status='sent').count(), 2)
        self.assertEqual(NotificationDelivery.objects.filter(template=template, group=self.group, payload__has_key='in_app_mirror_of').count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_rescheduled_course_moves_unsent_reminder_without_duplicate(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='改期提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=3,
        )
        schedule_group_notifications(self.group, 'pre_course')
        delivery = NotificationDelivery.objects.get(group=self.group)
        original_time = delivery.scheduled_at
        self.booking_1.date += timedelta(days=2)
        self.booking_1.save(update_fields=['date'])
        self.booking_2.date += timedelta(days=2)
        self.booking_2.save(update_fields=['date'])
        schedule_group_notifications(self.group, 'pre_course')
        delivery.refresh_from_db()
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)
        self.assertEqual(delivery.scheduled_at, original_time + timedelta(days=2))

    def test_pre_course_reminder_waits_for_paid_order(self):
        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            DataJSON={'contact': {'email': 'student@example.com'}},
            expires_at=timezone.now() + timedelta(days=1),
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='課前提醒', event='pre_course',
            channel='email', subject='上課提醒', body='請準備裝備', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertFalse(NotificationDelivery.objects.filter(group=self.group).exists())
        payment.status = 'paid'
        payment.save(update_fields=['status'])
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_existing_pre_course_reminder_is_not_sent_before_payment(self):
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            DataJSON={'contact': {'email': 'student@example.com'}},
            expires_at=timezone.now() + timedelta(days=1),
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='課前提醒', event='pre_course',
            channel='email', subject='上課提醒', body='請準備裝備', days_before=3,
        )
        delivery = NotificationDelivery.objects.create(
            template=template, group=self.group, recipient='student@example.com',
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        call_command('process_snowland_jobs')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'scheduled')
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)
        payment.status = 'paid'
        payment.save(update_fields=['status'])
        call_command('process_snowland_jobs')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'scheduled')
        self.assertGreater(delivery.scheduled_at, timezone.now())
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_immediate_reminder_is_not_duplicated_on_repeated_job_runs(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='立即提醒', event='pre_course',
            channel='email', subject='上課提醒', body='請準備裝備', days_before=0,
        )
        call_command('process_snowland_jobs')
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 2)
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group, payload__has_key='in_app_mirror_of').count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_completed_documents_do_not_trigger_missing_documents_reminder(self):
        # This scenario has one fully documented learner, not an unfilled second seat.
        self.reservation.number_of_people = 1
        self.reservation.save(update_fields=['number_of_people'])
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        MemberDetail.objects.create(
            reservation=self.reservation, user=self.user,
            insurance_data={'full_name': '測試學員', 'birth_date': '1990-01-01', 'id_number': 'TEST123', 'phone': '0900000000'},
            insurance_completed_at=timezone.now(), waiver_signature='測試學員',
            waiver_document_version=get_current_waiver(self.client_tenant)['version'],
            waiver_completed_at=timezone.now(),
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='文件提醒', event='missing_documents',
            channel='email', subject='補資料', body='請完成課前資料', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertFalse(NotificationDelivery.objects.filter(group=self.group).exists())

    def test_missing_documents_reminder_is_scheduled_when_no_members_bound(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='文件提醒', event='missing_documents',
            channel='email', subject='補資料', body='請完成課前資料', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)

    def test_line_group_invitation_waits_for_link(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='群組邀請', event='line_group',
            channel='email', subject='上課群組', body='{line_group_url}', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertFalse(NotificationDelivery.objects.filter(group=self.group).exists())
        self.group.line_group_url = 'https://example.com/snowland-group'
        self.group.save(update_fields=['line_group_url'])
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_class_group_link_admin_to_paid_member_and_notification_queue(self):
        hq = User.objects.create_superuser('group-link-hq', 'group-link-hq@example.test', 'test-password')
        api = APIClient(); api.force_authenticate(hq)
        endpoint = f'/api/admin/snowland/orders/{self.group.pk}/class-group-link/'
        template = NotificationTemplate.objects.create(client=self.client_tenant, campus=self.campus,
            name='Class group', event='line_group', channel='email', subject='上課群組', body='{line_group_url}', days_before=3)
        link = 'https://line.me/ti/g/QA-TEST-NOT-A-REAL-GROUP'
        for invalid in ['javascript:alert(1)', 'http://line.me/ti/g/test', 'https://user:password@line.me/ti/g/test', 1, None, 'https://line.me/' + 'x'*500]:
            response = api.post(endpoint, {'line_group_url': invalid}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.group.refresh_from_db(); self.assertEqual(self.group.line_group_url, '')
        self.assertEqual(api.post(endpoint, {}, format='json').status_code, 400)
        self.assertEqual(api.post(endpoint, {'line_group_url': link}, format='json').status_code, 200)
        member_api = APIClient(); member_api.force_authenticate(self.user)
        self.assertEqual(member_api.get('/booking/snowland/api/member-center/').data['orders'][0]['line_group_url'], '')
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', DataJSON={})
        for _ in range(2):
            self.assertEqual(api.post(endpoint, {'line_group_url': link}, format='json').status_code, 200)
        deliveries = NotificationDelivery.objects.filter(template=template, group=self.group)
        self.assertEqual(deliveries.count(), 1)
        self.assertEqual(deliveries.get().recipient, self.user.email)
        self.assertEqual(timezone.localtime(deliveries.get().scheduled_at).date(), self.booking_1.date - timedelta(days=3))
        self.assertEqual(member_api.get('/booking/snowland/api/member-center/').data['orders'][0]['line_group_url'], link)
        self.assertEqual(member_api.post(endpoint, {'line_group_url': ''}, format='json').status_code, 403)
        self.reservation.status = 'cancelled'; self.reservation.save(update_fields=['status'])
        self.assertEqual(member_api.get('/booking/snowland/api/member-center/').data['orders'][0]['line_group_url'], '')
        self.assertEqual(api.post(endpoint, {'line_group_url': ''}, format='json').status_code, 200)
        self.assertEqual(deliveries.get().status, 'cancelled')
        self.assertEqual(len(mail.outbox), 0)

    def test_class_group_link_queue_failure_does_not_partially_save_link(self):
        hq = User.objects.create_superuser('group-link-atomic', 'atomic@example.test', 'test-password')
        api = APIClient(); api.force_authenticate(hq)
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        with patch('booking.operations.schedule_group_notifications', side_effect=RuntimeError('QA queue unavailable')):
            with self.assertRaises(RuntimeError):
                api.post(f'/api/admin/snowland/orders/{self.group.pk}/class-group-link/', {
                    'line_group_url': 'https://line.me/ti/g/QA-ATOMIC',
                }, format='json')
        self.group.refresh_from_db()
        self.assertEqual(self.group.line_group_url, '')

    def test_incomplete_course_does_not_trigger_evaluation_reminder(self):
        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='評量提醒', event='evaluation_due',
            channel='email', subject='填評量', body='請完成評量', days_before=0,
        )
        call_command('process_snowland_jobs')
        self.assertFalse(NotificationDelivery.objects.filter(group=self.group).exists())

    def test_completed_course_with_unfinished_evaluation_gets_reminder(self):
        MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='評量提醒', event='evaluation_due',
            channel='email', subject='填評量', body='請完成評量', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)

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

    def test_payroll_refuses_to_hide_completed_hours_without_pay_rule(self):
        with self.assertRaisesMessage(ValueError, '尚未設定薪資規則'):
            calculate_payroll_statement(
                coach=self.coach, campus=self.campus,
                period_start=self.booking_1.date, period_end=self.booking_2.date,
            )
        self.assertFalse(PayrollStatement.objects.filter(coach=self.coach, campus=self.campus).exists())

    def test_manual_payroll_items_survive_recalculation_and_are_itemized(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
        args = dict(coach=self.coach, campus=self.campus, period_start=self.booking_1.date, period_end=self.booking_2.date)
        statement = calculate_payroll_statement(**args)
        add_payroll_adjustment(statement=statement, description='本月日文協助費', amount=1200)
        statement = calculate_payroll_statement(**args)
        self.assertEqual(statement.adjustment, 1200)
        self.assertEqual(statement.total_amount, 5200)
        self.assertEqual(statement.lines.filter(line_type='adjustment', description='本月日文協助費').count(), 1)

    def test_payroll_rejects_overlapping_period_but_allows_same_period_recalculation(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
        start, end = self.booking_1.date, self.booking_2.date
        first = calculate_payroll_statement(coach=self.coach, campus=self.campus, period_start=start, period_end=end)
        recalculated = calculate_payroll_statement(coach=self.coach, campus=self.campus, period_start=start, period_end=end)
        self.assertEqual(recalculated.pk, first.pk)
        with self.assertRaisesMessage(ValueError, '結算期間不能重疊'):
            calculate_payroll_statement(coach=self.coach, campus=self.campus, period_start=end, period_end=end)
        self.assertEqual(PayrollStatement.objects.filter(coach=self.coach, campus=self.campus).count(), 1)

    def test_completed_course_cannot_change_time_or_coach_or_partially_update_payment(self):
        admin = User.objects.create_superuser('completion-lock-admin', 'completion-lock@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        payment = Payment.objects.create(reservation_group=self.group, user=self.user, status='pending')
        url = f'/api/admin/snowland/orders/{self.group.pk}/'
        new_date = self.booking_1.date + timedelta(days=1)
        changed_time = api.put(url, {
            'action': 'save', 'payment_status': 'paid',
            'booking_updates': [{'booking_id': self.booking_1.pk, 'date': str(new_date)}],
        }, format='json')
        self.assertEqual(changed_time.status_code, 400)
        self.assertIn('已完課', changed_time.data['msg'])
        payment.refresh_from_db(); self.booking_1.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        self.assertNotEqual(self.booking_1.date, new_date)

        another = Coach.objects.create(client=self.client_tenant, name='教練 B')
        another.campuses.add(self.campus)
        changed_coach = api.put(url, {
            'action': 'save', 'reservation_updates': [{'reservation_id': self.reservation.pk, 'coach_id': another.pk}],
        }, format='json')
        self.assertEqual(changed_coach.status_code, 400)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, self.coach.pk)

    def test_paid_scheduled_course_completion_creates_evaluations_and_payroll_hours(self):
        admin = User.objects.create_superuser('lifecycle-admin', 'lifecycle@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        group = ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus, user=self.user, name='閉環測試')
        reservation = Reservation.objects.create(
            group=group, resort=self.resort, course_type=self.course_type,
            preferred_coach=self.coach, status='manually_assigned', course_fee=10000,
        )
        yesterday = timezone.localdate() - timedelta(days=1)
        past = Booking.objects.create(reservation=reservation, course_type='單板', course_name='初階', date=yesterday, start_time=time(9), end_time=time(11), is_scheduled=True)
        future = Booking.objects.create(reservation=reservation, course_type='單板', course_name='初階', date=timezone.localdate() + timedelta(days=1), start_time=time(9), end_time=time(11), is_scheduled=True)
        member = MemberDetail.objects.create(reservation=reservation, user=self.user)
        payment = Payment.objects.create(reservation_group=group, user=self.user, status='pending', payment_method='bank_transfer')
        url = f'/api/admin/snowland/orders/{group.id}/complete-course/'
        payload = {'reservation_id': reservation.id}

        self.assertEqual(api.post(url, payload, format='json').status_code, 400)
        payment.status = 'paid'; payment.save(update_fields=['status'])
        self.assertEqual(api.post(url, payload, format='json').status_code, 400)
        self.assertEqual(CourseEvaluation.objects.filter(member=member, booking__reservation=reservation).count(), 0)

        future.date = yesterday; future.save(update_fields=['date'])
        schedule = api.get('/api/admin/snowland/bookings/', {'start': str(yesterday), 'end': str(yesterday)})
        self.assertEqual(schedule.status_code, 200)
        self.assertTrue(any(item['id'] == past.id for item in schedule.data['data']['list']))
        completed = api.post(url, payload, format='json')
        self.assertEqual(completed.status_code, 200, completed.data)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'completed')
        self.assertEqual(CourseEvaluation.objects.filter(member=member, booking__reservation=reservation).count(), 2)
        self.assertEqual(api.post(url, payload, format='json').status_code, 200)
        self.assertEqual(CourseEvaluation.objects.filter(member=member, booking__reservation=reservation).count(), 2)

        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
        payroll = api.post('/api/admin/snowland/payroll-statements/calculate/', {
            'coach': self.coach.id, 'campus': self.campus.id,
            'period_start': str(yesterday), 'period_end': str(yesterday),
        }, format='json')
        self.assertEqual(payroll.status_code, 200, payroll.data)
        self.assertEqual(payroll.data['data']['course_pay'], 4000)
        self.assertEqual(PayrollStatement.objects.get(coach=self.coach, campus=self.campus).lines.filter(line_type='course').count(), 2)

    def test_cross_tenant_pay_rule_is_rejected(self):
        other_tenant = Client.objects.create(name='Other', internal_code='other')
        other_coach = Coach.objects.create(client=other_tenant, name='外部教練')
        admin = User.objects.create_superuser('root', 'root@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.post('/api/admin/snowland/coach-pay-rules/', {
            'coach': other_coach.id, 'discipline': 'ski', 'hourly_rate': 1000,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_general_pay_rule_can_be_saved_without_course_type(self):
        admin = User.objects.create_superuser('payroll-admin', 'payroll@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.post('/api/admin/snowland/coach-pay-rules/', {
            'coach': self.coach.id, 'discipline': 'snowboard', 'hourly_rate': 1000,
            'specified_fee': 0, 'referral_percent': '0',
            'assistance_hour_factor': '0', 'supervisor_allowance': 0,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(CoachPayRule.objects.filter(coach=self.coach, course_type__isnull=True).exists())
        duplicate = api.post('/api/admin/snowland/coach-pay-rules/', {
            'coach': self.coach.id, 'discipline': 'snowboard', 'hourly_rate': 1200,
        }, format='json')
        self.assertEqual(duplicate.status_code, 400)
        updated = api.patch(f'/api/admin/snowland/coach-pay-rules/{response.data["id"]}/', {
            'hourly_rate': 1200,
        }, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(CoachPayRule.objects.get(pk=response.data['id']).hourly_rate, 1200)

    def test_member_center_quick_rebook_only_returns_own_tenant_order(self):
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'quick_rebook_group_id': self.group.id,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['cart']), 1)
        self.assertEqual(response.data['cart'][0]['campusId'], self.campus.id)
        self.assertEqual(response.data['cart'][0]['serviceType'], 'ski')

        self.category.service_type = 'photo'
        self.category.name = '自訂影像方案'
        self.category.save()
        photo = api.post('/booking/snowland/api/member-center/', {
            'quick_rebook_group_id': self.group.id,
        }, format='json')
        self.assertEqual(photo.data['cart'][0]['serviceType'], 'photo')
        member = api.get('/booking/snowland/api/member-center/')
        self.assertEqual(member.status_code, 200)
        self.assertEqual(member.data['orders'][0]['reservations'][0]['service_type'], 'photo')

        stranger = User.objects.create_user('stranger')
        api.force_authenticate(stranger)
        response = api.post('/booking/snowland/api/member-center/', {
            'quick_rebook_group_id': self.group.id,
        }, format='json')
        self.assertEqual(response.status_code, 404)

    def test_quick_rebook_preserves_customer_preference_not_auto_assignment(self):
        api=APIClient();api.force_authenticate(self.user)
        for preferred in [False,True]:
            self.reservation.preferred_coach=self.coach
            self.reservation.is_preferred_coach=preferred
            self.reservation.save()
            response=api.post('/booking/snowland/api/member-center/',{'quick_rebook_group_id':self.group.pk},format='json')
            self.assertEqual(response.status_code,200,response.data)
            item=response.data['cart'][0]
            self.assertEqual(item['coach'],self.coach.pk if preferred else 'any')
            self.assertEqual(item['coachName'],self.coach.name if preferred else '不指定')

    def test_quick_rebook_preserves_equipment_option_but_never_old_price(self):
        api=APIClient();api.force_authenticate(self.user)
        for stored,option in [('rentWithoutyourself','self_rent'),('ownWithoutAssistance','own_equipment'),('assistDuringCourse','class_time_help'),('purchaseAssistanceTime','extra_time_help')]:
            self.reservation.equipment=stored;self.reservation.save()
            response=api.post('/booking/snowland/api/member-center/',{'quick_rebook_group_id':self.group.pk},format='json')
            self.assertEqual(response.status_code,200,response.data)
            item=response.data['cart'][0]
            self.assertEqual(item['equipmentOption'],option)
            self.assertIsNone(item['totalPrice'])
            self.assertTrue(all(course['price'] is None for course in item['courses']))

    def test_quick_rebook_keeps_each_days_amended_template(self):
        half=CourseTemplate.objects.create(course_type=self.course_type,name='QA半天',duration_hours=3)
        full=CourseTemplate.objects.create(course_type=self.course_type,name='QA全天',duration_hours=6)
        self.reservation.course_template=half;self.reservation.save()
        self.booking_1.course_template=half;self.booking_1.save()
        self.booking_2.course_template=full;self.booking_2.save()
        api=APIClient();api.force_authenticate(self.user)
        response=api.post('/booking/snowland/api/member-center/',{'quick_rebook_group_id':self.group.pk},format='json')
        self.assertEqual(response.status_code,200,response.data)
        courses=response.data['cart'][0]['courses']
        self.assertEqual([row['courseTemplateId'] for row in courses],[half.pk,full.pk])
        self.assertEqual([row['durationHours'] for row in courses],[3,6])

    def test_quick_rebook_invalid_id_returns_400_not_500(self):
        api=APIClient();api.force_authenticate(self.user)
        for value in ['abc',0,-1,True,{'id':self.group.pk},'１']:
            response=api.post('/booking/snowland/api/member-center/',{'quick_rebook_group_id':value},format='json')
            self.assertEqual(response.status_code,400,response.data)

    def test_member_center_returns_real_orders_forms_and_learning_records(self):
        self.booking_1.date = timezone.localdate() - timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
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
        self.assertEqual(
            {media['url'] for media in response.data['learning_records'][0]['media']},
            {'https://example.com/lesson.jpg', 'https://example.com/private.jpg'},
        )

        stranger = User.objects.create_user('other-student')
        api.force_authenticate(stranger)
        self.assertEqual(api.get('/booking/snowland/api/member-center/').data['learning_records'], [])

    def test_member_can_complete_pre_course_form_and_waiver(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'update_pre_course_form',
            'member_id': member.id,
            'age_range': '25-35y',
            'snowboard_skills': ['雪場S turn'],
            'ski_skills': [],
            'insurance_data': {
                'full_name': '測試學員', 'birth_date': '1990-01-01',
                'id_number': 'TEST123', 'phone': '0900000000',
            },
            'waiver_agreed': True,
            'waiver_signature': '測試學員',
            'waiver_document_version': 'V0-2026-10-08',
            'media_consent': 'decline',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        member.refresh_from_db()
        self.assertIsNotNone(member.insurance_completed_at)
        self.assertIsNotNone(member.waiver_completed_at)
        self.assertEqual(member.waiver_signature, '測試學員')
        self.assertEqual(member.waiver_document_version, 'V0-2026-10-08')
        self.assertEqual(member.media_consent, 'decline')
        self.assertIn('SnowLand 滑雪運動安全聲明書', member.waiver_document_snapshot)

    def test_member_old_insurance_completion_without_details_is_not_complete(self):
        member = MemberDetail.objects.create(
            reservation=self.reservation,
            user=self.user,
            age_range='25-35y',
            insurance_completed_at=timezone.now(),
            insurance_data={},
        )
        api = APIClient(); api.force_authenticate(self.user)

        response = api.get('/booking/snowland/api/member-center/')

        self.assertEqual(response.status_code, 200)
        form = next(item for item in response.data['pre_course_forms'] if item['id'] == member.id)
        self.assertFalse(form['insurance_completed'])

    def test_old_minor_record_without_guardian_remains_incomplete_and_needs_reminder(self):
        from booking.management.commands.process_snowland_jobs import Command
        self.reservation.number_of_people = 1
        self.reservation.save(update_fields=['number_of_people'])
        member = MemberDetail.objects.create(
            reservation=self.reservation, user=self.user, age_range='7-12y',
            insurance_data={'full_name': 'QA 學員', 'birth_date': '2018-01-01', 'id_number': 'QA-ID', 'phone': 'QA-PHONE'},
            insurance_completed_at=timezone.now(), waiver_completed_at=timezone.now(),
            waiver_signature='QA 舊資料', waiver_document_version=get_current_waiver(self.client_tenant)['version'],
        )
        api = APIClient(); api.force_authenticate(self.user)
        form = api.get('/booking/snowland/api/member-center/').data['pre_course_forms'][0]
        self.assertFalse(form['insurance_completed'])
        self.assertFalse(form['waiver_completed'])
        self.assertTrue(Command._event_is_applicable(self.group, 'missing_documents'))
        member.insurance_data.update({'waiver_signer_role': 'guardian', 'guardian_name': 'QA 家長', 'guardian_relationship': '母親'})
        member.save(update_fields=['insurance_data'])
        self.assertFalse(Command._event_is_applicable(self.group, 'missing_documents'))

    def test_member_must_sign_current_waiver_version(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'update_pre_course_form',
            'member_id': member.id,
            'age_range': '25-35y',
            'insurance_data': {},
            'waiver_agreed': True,
            'waiver_signature': '測試學員',
            'waiver_document_version': 'OLD',
            'media_consent': 'decline',
        }, format='json')
        self.assertEqual(response.status_code, 409)

    def test_other_member_cannot_read_or_change_pre_course_form(self):
        member = MemberDetail.objects.create(
            reservation=self.reservation, user=self.user,
            insurance_data={'full_name': '原學員'},
        )
        other_user = User.objects.create_user('other-member', email='other@example.test')
        api = APIClient(); api.force_authenticate(other_user)

        own_center = api.get('/booking/snowland/api/member-center/')
        self.assertEqual(own_center.status_code, 200)
        self.assertEqual(own_center.data['pre_course_forms'], [])
        update = api.post('/booking/snowland/api/member-center/', {
            'action': 'update_pre_course_form',
            'member_id': member.id,
            'age_range': '25-35y',
            'insurance_data': {'full_name': '越權修改'},
        }, format='json')
        self.assertEqual(update.status_code, 404)
        member.refresh_from_db()
        self.assertEqual(member.insurance_data['full_name'], '原學員')

    def test_waiver_requires_media_choice_without_partial_form_save(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'update_pre_course_form',
            'member_id': member.id,
            'age_range': '25-35y',
            'insurance_data': {
                'full_name': '測試學員', 'birth_date': '1990-01-01',
                'id_number': 'TEST123', 'phone': '0900000000',
            },
            'waiver_agreed': True,
            'waiver_signature': '測試學員',
            'waiver_document_version': get_current_waiver(self.client_tenant)['version'],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        member.refresh_from_db()
        self.assertEqual(member.insurance_data, {})
        self.assertIsNone(member.insurance_completed_at)
        self.assertIsNone(member.waiver_completed_at)

    def test_updated_waiver_requires_new_signature_and_preserves_signed_snapshot(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        api = APIClient(); api.force_authenticate(self.user)
        url = '/booking/snowland/api/member-center/'
        original_version = get_current_waiver(self.client_tenant)['version']
        payload = {
            'action': 'update_pre_course_form',
            'member_id': member.id,
            'age_range': '25-35y',
            'insurance_data': {'birth_date': '1990-01-01'},
            'waiver_agreed': True,
            'waiver_signature': '測試學員',
            'waiver_document_version': original_version,
            'media_consent': 'decline',
        }
        self.assertEqual(api.post(url, payload, format='json').status_code, 200)
        member.refresh_from_db()
        original_snapshot = member.waiver_document_snapshot

        SiteContent.objects.create(
            client=self.client_tenant, content_type='page',
            location_key='membership.waiver', title='新版聲明書',
            body='新版法務條款內容', status='active',
            metadata={'version': 'V1-test', 'is_draft': False},
        )
        center = api.get(url)
        self.assertEqual(center.status_code, 200)
        self.assertEqual(center.data['waiver_document']['version'], 'V1-test')
        form = next(item for item in center.data['pre_course_forms'] if item['id'] == member.id)
        self.assertFalse(form['waiver_completed'])

        self.assertEqual(api.post(url, payload, format='json').status_code, 409)
        member.refresh_from_db()
        self.assertEqual(member.waiver_document_snapshot, original_snapshot)
        payload['waiver_document_version'] = 'V1-test'
        self.assertEqual(api.post(url, payload, format='json').status_code, 200)
        member.refresh_from_db()
        self.assertEqual(member.waiver_document_version, 'V1-test')
        self.assertEqual(member.waiver_document_snapshot, '新版法務條款內容')
        self.assertTrue(next(item for item in api.get(url).data['pre_course_forms'] if item['id'] == member.id)['waiver_completed'])

    def test_member_can_submit_course_satisfaction(self):
        self.booking_1.date = timezone.localdate() - timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(booking=self.booking_1, member=member, coach=self.coach)
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'submit_satisfaction',
            'evaluation_id': evaluation.id,
            'rating': 5,
            'feedback': '課程很清楚。',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.self_assessment['satisfaction_rating'], 5)
        self.assertEqual(evaluation.self_assessment['satisfaction_feedback'], '課程很清楚。')

    def test_admin_evaluation_flows_to_member_record_and_satisfaction(self):
        self.booking_1.date = timezone.localdate() - timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(
            booking=self.booking_1, member=member, coach=self.coach,
        )
        admin = User.objects.create_superuser('evaluation-admin', 'evaluation-admin@example.com', 'pw')
        admin_api = APIClient(); admin_api.force_authenticate(admin)
        updated = admin_api.patch(f'/api/admin/snowland/evaluations/{evaluation.id}/', {
            'coach_notes': '下次練習連續轉彎。',
            'learning_progress': {'煞車': '已完成', '轉彎': '持續練習'},
            'trail_names': 'Family Run',
            'completed_at': timezone.now().isoformat(),
        }, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)

        member_api = APIClient(); member_api.force_authenticate(self.user)
        records = member_api.get('/booking/snowland/api/member-center/')
        self.assertEqual(records.status_code, 200)
        self.assertEqual(len(records.data['learning_records']), 1)
        record = records.data['learning_records'][0]
        self.assertEqual(record['coach_notes'], '下次練習連續轉彎。')
        self.assertEqual(record['learning_progress']['轉彎'], '持續練習')
        self.assertEqual(record['trail_names'], ['Family Run'])

        rated = member_api.post('/booking/snowland/api/member-center/', {
            'action': 'submit_satisfaction', 'evaluation_id': evaluation.id,
            'rating': 5, 'feedback': '課程安排清楚。',
        }, format='json')
        self.assertEqual(rated.status_code, 200, rated.data)
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.self_assessment['satisfaction_rating'], 5)
        self.assertEqual(evaluation.self_assessment['satisfaction_feedback'], '課程安排清楚。')

        stranger = APIClient()
        stranger.force_authenticate(User.objects.create_user('other-evaluation-student'))
        self.assertEqual(stranger.get('/booking/snowland/api/member-center/').data['learning_records'], [])
        self.assertEqual(stranger.post('/booking/snowland/api/member-center/', {
            'action': 'submit_satisfaction', 'evaluation_id': evaluation.id, 'rating': 1,
        }, format='json').status_code, 404)

    def test_evaluation_rejects_invalid_media_without_saving_notes_or_completion(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(booking=self.booking_1, member=member, coach=self.coach)
        admin = User.objects.create_superuser('evaluation-media-admin', 'media-admin@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        url = f'/api/admin/snowland/evaluations/{evaluation.id}/'
        for media in (
            {'media_type': 'photo', 'url': 'not-a-url'},
            {'media_type': 'photo', 'url': 'ftp://example.com/photo.jpg'},
            {'media_type': 'document', 'url': 'https://example.com/photo.jpg'},
            {'media_type': 'photo'},
        ):
            with self.subTest(media=media):
                response = api.patch(url, {
                    'coach_notes': '不應部分儲存', 'completed_at': timezone.now().isoformat(),
                    'new_media': media,
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                evaluation.refresh_from_db()
                self.assertEqual(evaluation.coach_notes, '')
                self.assertIsNone(evaluation.completed_at)
                self.assertFalse(evaluation.media.exists())
        response = api.post(f'{url}media/', {'media_type': 'photo', 'url': 'not-a-url'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(evaluation.media.exists())

    def test_evaluation_saves_media_and_notes_together_for_member_without_public_exposure(self):
        self.booking_1.date = timezone.localdate() - timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(booking=self.booking_1, member=member, coach=self.coach)
        admin = User.objects.create_superuser('evaluation-media-owner', 'media-owner@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.patch(f'/api/admin/snowland/evaluations/{evaluation.id}/', {
            'coach_notes': '已能穩定煞車。', 'completed_at': timezone.now().isoformat(),
            'new_media': {'media_type': 'photo', 'url': 'https://example.com/lesson.jpg', 'is_public': False},
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.coach_notes, '已能穩定煞車。')
        self.assertIsNotNone(evaluation.completed_at)
        media = evaluation.media.get()
        self.assertEqual(media.uploaded_by_id, admin.id)
        self.assertFalse(media.is_public)
        api.force_authenticate(self.user)
        record = next(row for row in api.get('/booking/snowland/api/member-center/').data['learning_records'] if row['id'] == evaluation.id)
        self.assertEqual(record['media'][0]['url'], media.url)

    def test_evaluation_media_write_failure_rolls_back_notes_and_completion(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(booking=self.booking_1, member=member, coach=self.coach)
        admin = User.objects.create_superuser('evaluation-media-rollback', 'media-rollback@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        with patch('API.admin_serializers.CourseMedia.objects.create', side_effect=RuntimeError('media write failed')):
            with self.assertRaisesMessage(RuntimeError, 'media write failed'):
                api.patch(f'/api/admin/snowland/evaluations/{evaluation.id}/', {
                    'coach_notes': '不應部分儲存', 'completed_at': timezone.now().isoformat(),
                    'new_media': {'media_type': 'photo', 'url': 'https://example.com/lesson.jpg'},
                }, format='json')
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.coach_notes, '')
        self.assertIsNone(evaluation.completed_at)
        self.assertFalse(evaluation.media.exists())

    def test_admin_evaluation_list_identifies_order_course_and_location(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(
            booking=self.booking_1, member=member, coach=self.coach,
        )
        admin = User.objects.create_superuser('evaluation-list-admin', 'evaluation-list-admin@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)

        response = api.get('/api/admin/snowland/evaluations/')
        self.assertEqual(response.status_code, 200, response.data)
        row = next(item for item in response.data['data']['list'] if item['id'] == evaluation.id)
        self.assertEqual(row['order_number'], self.group.order_number)
        self.assertEqual(row['course_name'], '初階')
        self.assertEqual(row['campus_name'], '北海道校區')
        self.assertEqual(row['resort_name'], 'Tomamu')

        self.group.campus = None
        self.group.save(update_fields=['campus'])
        self.reservation.resort = None
        self.reservation.save(update_fields=['resort'])
        legacy_row = CourseEvaluationAdminSerializer(CourseEvaluation.objects.get(pk=evaluation.pk)).data
        self.assertEqual(legacy_row['campus_name'], '')
        self.assertEqual(legacy_row['resort_name'], '')

    def test_admin_cannot_mark_empty_evaluation_complete(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(booking=self.booking_1, member=member, coach=self.coach)
        admin = User.objects.create_superuser('evaluation-complete-admin', 'evaluation-complete-admin@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        url = f'/api/admin/snowland/evaluations/{evaluation.pk}/'

        empty = api.patch(url, {'completed_at': timezone.now().isoformat()}, format='json')
        self.assertEqual(empty.status_code, 400, empty.data)
        evaluation.refresh_from_db()
        self.assertIsNone(evaluation.completed_at)

        evaluation.coach_assessment = {'balance': 4}
        evaluation.save(update_fields=['coach_assessment'])
        hidden_only = api.patch(url, {'completed_at': timezone.now().isoformat()}, format='json')
        self.assertEqual(hidden_only.status_code, 400, hidden_only.data)
        evaluation.refresh_from_db()
        self.assertIsNone(evaluation.completed_at)

        filled = api.patch(url, {
            'coach_notes': '已能穩定煞車。', 'completed_at': timezone.now().isoformat(),
        }, format='json')
        self.assertEqual(filled.status_code, 200, filled.data)
        evaluation.refresh_from_db()
        self.assertIsNotNone(evaluation.completed_at)

        removed = api.patch(url, {'coach_notes': '  '}, format='json')
        self.assertEqual(removed.status_code, 400, removed.data)
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.coach_notes, '已能穩定煞車。')

    def test_member_cannot_rate_course_before_lesson_is_complete(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(
            booking=self.booking_1, member=member, coach=self.coach,
        )
        self.reservation.status = 'manually_assigned'
        self.reservation.save(update_fields=['status'])
        api = APIClient(); api.force_authenticate(self.user)

        self.assertEqual(api.get('/booking/snowland/api/member-center/').data['learning_records'], [])

        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'submit_satisfaction',
            'evaluation_id': evaluation.id,
            'rating': 5,
            'feedback': '課程很清楚。',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        evaluation.refresh_from_db()
        self.assertNotIn('satisfaction_rating', evaluation.self_assessment or {})

        self.booking_1.date = timezone.localdate() - timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'submit_satisfaction', 'evaluation_id': evaluation.id, 'rating': 5,
        }, format='json')
        self.assertEqual(response.status_code, 400)

        self.booking_1.date = timezone.localdate() + timedelta(days=35)
        self.booking_1.save(update_fields=['date'])
        self.reservation.status = 'completed'
        self.reservation.save(update_fields=['status'])
        self.assertEqual(api.get('/booking/snowland/api/member-center/').data['learning_records'], [])
        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'submit_satisfaction', 'evaluation_id': evaluation.id, 'rating': 5,
        }, format='json')
        self.assertEqual(response.status_code, 400)

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

    def test_member_registration_name_appears_after_login(self):
        api = APIClient()
        registered = api.post('/booking/snowland/api/member-auth/', {
            'action': 'register',
            'name': '測試會員',
            'email': 'named-member@example.com',
            'password': 'secure-pass-123',
        }, format='json')
        self.assertEqual(registered.status_code, 201)
        self.assertEqual(registered.data['member']['name'], '測試會員')
        self.assertEqual(User.objects.get(email='named-member@example.com').first_name, '測試會員')

        api.post('/control/api/logout/', {}, format='json')
        logged_in = api.post('/booking/snowland/api/member-auth/', {
            'action': 'login', 'email': 'named-member@example.com', 'password': 'secure-pass-123',
        }, format='json')
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(logged_in.data['member']['name'], '測試會員')

    def test_member_registration_rejects_invalid_explicit_name(self):
        for name in ('  ', 'user@example.com'):
            with self.subTest(name=name):
                response = APIClient().post('/booking/snowland/api/member-auth/', {
                    'action': 'register', 'name': name,
                    'email': 'invalid-name@example.com', 'password': 'secure-pass-123',
                }, format='json')
                self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='invalid-name@example.com').exists())

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
        profile.manager_client = self.client_tenant
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

    def test_insurance_list_has_one_row_per_member_for_multi_day_course(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        admin = User.objects.create_superuser('insurance-admin', 'insurance-admin@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)

        response = api.get('/api/admin/snowland/insurance-records/?status=missing')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 1)
        self.assertEqual(response.data['data']['list'][0]['id'], member.id)
        self.assertEqual(
            response.data['data']['list'][0]['sn'],
            f'{self.group.created_at:%Y%m%d}-{self.group.id:04d}',
        )

    def test_insurance_records_cannot_create_or_delete_member_details(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(booking=self.booking_1, member=member)
        admin = User.objects.create_superuser('insurance-admin', 'insurance-admin@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        url = '/api/admin/snowland/insurance-records/'

        self.assertEqual(api.delete(f'{url}{member.id}/').status_code, 405)
        self.assertEqual(api.post(url, {'age_range': '19-24y'}, format='json').status_code, 405)
        self.assertTrue(MemberDetail.objects.filter(pk=member.id).exists())
        self.assertTrue(CourseEvaluation.objects.filter(pk=evaluation.id).exists())

        updated = api.patch(f'{url}{member.id}/', {'age_range': '25-35y'}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        completed = api.post(f'{url}{member.id}/complete/', {'field': 'insurance'}, format='json')
        self.assertEqual(completed.status_code, 200, completed.data)
        member.refresh_from_db()
        self.assertEqual(member.age_range, '25-35y')
        self.assertIsNotNone(member.insurance_completed_at)

    def test_insurance_detail_returns_signed_record_without_exposing_it_in_list(self):
        from booking.legal_documents import get_current_waiver
        version = get_current_waiver(self.reservation.group.client)['version']
        member = MemberDetail.objects.create(
            reservation=self.reservation, user=self.user, age_range='7-12y',
            insurance_data={'full_name': 'QA 學員', 'id_number': 'QA-NOT-REAL',
                            'waiver_signer_role': 'guardian', 'guardian_name': 'QA 家長',
                            'guardian_relationship': '母親'},
            waiver_signature='QA 家長', waiver_document_version=version,
            waiver_document_snapshot='QA 測試條款', media_consent='decline',
            insurance_completed_at=timezone.now(), waiver_completed_at=timezone.now(),
        )
        api = APIClient()
        api.force_authenticate(User.objects.create_superuser('insurance-detail', password='pw'))
        url = '/api/admin/snowland/insurance-records/'
        row = api.get(url).data['data']['list'][0]
        self.assertNotIn('insurance_data', row)
        self.assertNotIn('waiver_document_snapshot', row)
        detail = api.get(f'{url}{member.id}/')
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['insurance_data'], member.insurance_data)
        self.assertEqual(detail.data['waiver_signature'], 'QA 家長')
        self.assertEqual(detail.data['waiver_document_snapshot'], 'QA 測試條款')
        self.assertEqual(detail.data['waiver_document_version'], version)
        self.assertFalse(detail.data['waiver_requires_resign'])
        self.assertEqual(detail.data['media_consent'], 'decline')
        self.assertEqual(api.get(url+'?status=missing').data['data']['total'], 0)
        self.assertEqual(api.get(url+'?status=completed').data['data']['total'], 1)
        MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        self.assertEqual(api.get(url+'?status=completed').data['data']['total'], 1)

    def test_insurance_detail_fields_cannot_overwrite_member_signature_or_personal_data(self):
        member = MemberDetail.objects.create(
            reservation=self.reservation, user=self.user,
            insurance_data={'full_name': 'QA 原學員'}, waiver_signature='QA 原簽名',
            waiver_document_snapshot='QA 原版本', waiver_document_version='QA-V1', media_consent='decline',
        )
        api = APIClient()
        api.force_authenticate(User.objects.create_superuser('insurance-readonly', password='pw'))
        response = api.patch(f'/api/admin/snowland/insurance-records/{member.id}/', {
            'insurance_data': {'full_name': '不應覆蓋'}, 'waiver_signature': '不應覆蓋',
            'waiver_document_snapshot': '不應覆蓋', 'waiver_document_version': 'QA-V2', 'media_consent': 'agree',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        member.refresh_from_db()
        self.assertEqual(member.insurance_data, {'full_name': 'QA 原學員'})
        self.assertEqual(member.waiver_signature, 'QA 原簽名')
        self.assertEqual(member.waiver_document_snapshot, 'QA 原版本')
        self.assertEqual(member.waiver_document_version, 'QA-V1')
        self.assertEqual(member.media_consent, 'decline')

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

    def test_schedule_console_prefers_customer_display_name_over_login_name(self):
        self.user.first_name = '小林'
        self.user.save(update_fields=['first_name'])
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        admin = User.objects.create_superuser('schedule-display-admin', 'schedule-display@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)

        response = api.get('/api/admin/snowland/bookings/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['list'][0]['user_name'], '小林')
        self.assertEqual(response.data['data']['list'][0]['order_number'], self.group.order_number)
        order_response = api.get('/api/admin/snowland/orders/')
        self.assertEqual(response.data['data']['list'][0]['sn'], order_response.data['data']['list'][0]['sn'])
