from unittest.mock import patch
import json
import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from Client.models import Client
from booking import tests_payment_expiry_race as fixtures
from booking.models import Payment
from booking.payment_access import payment_access_token


class LegacyPaymentPageTests(TestCase):
    def setUp(self):
        fixtures.PaymentExpiryRaceTests.setUp(self)
        self.payment.expires_at = timezone.now() + timezone.timedelta(days=1)
        self.payment.save(update_fields=['expires_at'])
        self.client.force_login(self.group.user)
        self.url = '/booking/snowland/payment/'

    def read(self, **params):
        return self.client.get(self.url, {'reservation_group': self.group.pk, **params})

    def test_real_url_resolves_its_tenant_and_reuses_bank_info_without_ip_lookup(self):
        with patch('requests.get') as lookup:
            response = self.read()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'QA-ONLY-ACCOUNT')
        self.assertEqual(response.context['total_amount'], self.reservation.payment_amount)
        lookup.assert_not_called()

    def test_latest_paid_or_refunded_attempt_cannot_render_payment_controls(self):
        for state in ('paid', 'refunded'):
            with self.subTest(state=state):
                latest = Payment.objects.create(reservation_group=self.group, user=self.group.user, status=state)
                response = self.read()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['payment_status'], state)
                self.assertNotContains(response, 'onclick="confirmBankTransfer()"')
                self.assertContains(response, '付款成功' if state == 'paid' else '已退款')
                latest.refresh_from_db()
                self.assertEqual(latest.status, state)

    def test_new_unpaid_after_collection_requires_review_not_another_payment(self):
        self.payment.status = 'paid'
        self.payment.save(update_fields=['status'])
        Payment.objects.create(reservation_group=self.group, status='unpaid')
        response = self.read()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['payment_status'], 'payment_records_review')
        self.assertContains(response, '請勿再次付款')
        self.assertNotContains(response, 'onclick="confirmBankTransfer()"')

    def test_invalid_foreign_inactive_and_unauthorized_orders_remain_hidden(self):
        for group_id in ('', 'not-a-number', '-1', str(10**40)):
            self.assertEqual(self.read(reservation_group=group_id).status_code, 404)
        Client.objects.create(name='Other', internal_code='other')
        self.assertEqual(self.client.get('/booking/other/payment/', {'reservation_group': self.group.pk}).status_code, 404)
        self.assertEqual(self.client.get('/booking/missing/payment/', {'reservation_group': self.group.pk}).status_code, 404)
        stranger = User.objects.create_user('legacy-payment-stranger')
        self.client.force_login(stranger)
        self.assertEqual(self.read().status_code, 404)
        self.group.client.is_active = False
        self.group.client.save(update_fields=['is_active'])
        self.client.force_login(self.group.user)
        self.assertEqual(self.read().status_code, 404)

    def test_signed_guest_paid_page_needs_its_token_and_does_not_require_owner_email(self):
        self.group.user = None
        self.group.save(update_fields=['user'])
        self.payment.status = 'paid'
        self.payment.save(update_fields=['status'])
        self.client.logout()
        self.assertEqual(self.read().status_code, 404)
        self.assertEqual(self.read(access_token='invalid').status_code, 404)
        response = self.read(access_token=payment_access_token(self.group))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '付款成功')
        self.assertNotContains(response, 'onclick="confirmBankTransfer()"')

    def test_expired_read_does_not_mutate_payment_or_reservation_and_post_is_not_accepted(self):
        self.payment.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        self.payment.save(update_fields=['expires_at'])
        response = self.read()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['payment_status'], 'expired')
        self.assertNotContains(response, 'onclick="confirmBankTransfer()"')
        self.payment.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(self.payment.status, 'unpaid')
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertEqual(self.client.post(self.url, {'reservation_group': self.group.pk}).status_code, 405)

    def test_payment_script_uses_safe_json_and_paid_continuation_is_existing_member_page(self):
        unpaid = self.read()
        content = unpaid.content.decode()
        config = re.search(r'<script id="payment-data" type="application/json">(.*?)</script>', content, re.S)
        self.assertIsNotNone(config, 'payment config must not embed Python Decimal/list representations in JavaScript')
        data = json.loads(config.group(1))
        self.assertEqual(data['reservation_group_pk'], str(self.group.pk))
        self.assertEqual(data['paymentStatus'], 'unpaid')
        self.assertNotIn('currentUser.email', content)
        self.assertNotIn('/api/rebind_order/', content)
        self.assertNotIn('accountSelector', content)
        self.payment.status = 'paid'
        self.payment.save(update_fields=['status'])
        paid = self.read()
        self.assertContains(paid, f'href="/snowland/membership/orders/{self.group.pk}"')
        self.assertContains(paid, '查看會員訂單')

    def test_signed_guest_continuation_never_offers_automatic_order_transfer(self):
        self.group.user = None
        self.group.save(update_fields=['user'])
        self.payment.status = 'paid'
        self.payment.save(update_fields=['status'])
        self.client.logout()
        response = self.read(access_token=payment_access_token(self.group))
        self.assertContains(response, '不會自動綁定會員')
        self.assertContains(response, 'href="/snowland/booking"')
        self.assertNotContains(response, '查看會員訂單')
        self.assertNotContains(response, '/api/rebind_order/')

    def test_payment_styles_are_self_contained_behind_frontend_proxy(self):
        response = self.read()
        self.assertContains(response, 'min-height:48px')
        self.assertContains(response, '@media(max-width:600px)')
        self.assertContains(response, 'aria-live="polite"')
        self.assertNotContains(response, '/static/booking.css')
        self.assertNotContains(response, 'unpkg.com')
