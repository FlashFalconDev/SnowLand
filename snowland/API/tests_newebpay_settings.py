import json
from unittest.mock import patch

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Client.models import Client
from Control.models import TenantStaffMembership
from Resorts.models import Campus
from booking.Newebpay import sha256_hash
from booking.models import NewebpayMerchant, Payment


@override_settings(SNOWLAND_NEWEBPAY_SANDBOX_ENABLED=True)
class NewebpaySettingsTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.tenant = self.client_tenant
        self.tenant.internal_code = 'qa-pay'
        self.tenant.bank_name = 'QA Bank'
        self.tenant.bank_branch = 'QA Branch'
        self.tenant.bank_account_number = 'QA-ONLY'
        self.tenant.bank_account_holder = 'QA'
        self.tenant.save()
        self.group.source_country = 'TW'
        self.group.save(update_fields=['source_country'])
        self.payment = Payment.objects.create(reservation_group=self.group)
        self.hq = User.objects.create_superuser('qa-pay-hq')
        self.admin = APIClient()
        self.admin.force_authenticate(self.hq)
        self.member = APIClient()
        self.member.force_authenticate(self.user)
        self.settings_url = '/api/admin/qa-pay/newebpay-settings/'
        self.order_url = f'/api/admin/qa-pay/orders/{self.group.pk}/card-payment/'
        self.info_url = '/booking/qa-pay/api/payment-info/'
        self.pay_url = '/booking/qa-pay/api/process-payment/'
        self.form = {'merchant_id': 'QA_MERCHANT', 'hash_key': 'Q' * 32, 'hash_iv': 'A' * 16,
                     'environment': 'sandbox', 'enabled': False}
        self.master = patch.dict('os.environ', {'SNOWLAND_NEWEBPAY_CREDENTIAL_KEY': Fernet.generate_key().decode()})
        self.master.start()
        self.addCleanup(self.master.stop)

    def set_shop(self, form=None, enable=True):
        result = self.admin.put(self.settings_url, form or self.form, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertFalse(result.data['data']['enabled'])
        if enable:
            enabled = self.admin.put(self.settings_url, {'enabled': True}, format='json')
            self.assertEqual(enabled.status_code, 200, enabled.data)
        return result

    def test_write_only_and_tenant_scoped_settings(self):
        initial = self.admin.get(self.settings_url)
        self.assertEqual(initial.status_code, 200, initial.data)
        self.assertFalse(initial.data['data']['configured'])
        self.set_shop()
        saved = NewebpayMerchant.objects.get()
        serialized = str(self.admin.get(self.settings_url).data)
        for secret in (self.form['hash_key'], self.form['hash_iv'], self.form['merchant_id']):
            self.assertNotIn(secret, serialized)
            self.assertNotIn(secret, saved.encrypted_credentials)
        other = Client.objects.create(name='QA Other', internal_code='qa-other')
        response = self.admin.get(f'/api/admin/{other.internal_code}/newebpay-settings/')
        self.assertFalse(response.data['data']['configured'])

    def test_fails_closed_without_master_key_or_while_incomplete(self):
        with patch.dict('os.environ', {'SNOWLAND_NEWEBPAY_CREDENTIAL_KEY': 'invalid'}):
            result = self.admin.put(self.settings_url, self.form, format='json')
            self.assertEqual(result.status_code, 400)
        bad = {**self.form, 'hash_iv': 'wrong'}
        self.assertEqual(self.admin.put(self.settings_url, bad, format='json').status_code, 400)
        self.assertEqual(self.admin.put(self.settings_url, {'enabled': True}, format='json').status_code, 400)
        self.assertFalse(NewebpayMerchant.objects.exists())

    def test_sandbox_cannot_be_activated_when_disabled_by_installation(self):
        with self.settings(SNOWLAND_NEWEBPAY_SANDBOX_ENABLED=False):
            self.set_shop(enable=False)
            result = self.admin.put(self.settings_url, {'enabled': True}, format='json')
        self.assertEqual(result.status_code, 400)
        self.assertFalse(NewebpayMerchant.objects.get().enabled)

    def test_order_requires_explicit_enable_and_pins_merchant_revision(self):
        self.assertEqual(self.admin.put(self.order_url, {'enabled': True}, format='json').status_code, 409)
        self.set_shop()
        payload = {'reservation_group_id': self.group.pk, 'payment_type': 'newebpay'}
        self.assertEqual(self.member.post(self.pay_url, payload, format='json').status_code, 400)
        self.assertEqual(self.member.get(self.info_url, {'reservation_group': self.group.pk}).data['payment_methods'], ['bank_transfer'])
        self.assertEqual(self.admin.put(self.order_url, {'enabled': True}, format='json').status_code, 200)
        self.assertIn('newebpay', self.member.get(self.info_url, {'reservation_group': self.group.pk}).data['payment_methods'])
        result = self.member.post(self.pay_url, payload, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertIn('https://ccore.newebpay.com/', result.data['html'])
        self.group.refresh_from_db()
        merchant = self.group.newebpay_merchant
        self.assertIsNotNone(merchant)
        self.assertEqual(self.admin.put(self.order_url, {'enabled': False}, format='json').status_code, 409)
        bank_attempt = self.member.post(self.pay_url, {**payload, 'payment_type': 'bank_transfer', 'sender_account': '12345'}, format='json')
        self.assertEqual(bank_attempt.status_code, 409)

        # Rotate to a different revision. Old signed notifications still settle the old order.
        self.set_shop({**self.form, 'merchant_id': 'QA_REPLACEMENT'})
        result = {
            'MerchantID': self.form['merchant_id'], 'MerchantOrderNo': str(self.group.pk),
            'Amt': self.reservation.payment_amount, 'TradeNo': 'QA-TEST-ONLY',
        }
        key, iv = self.form['hash_key'], self.form['hash_iv']
        info = AES.new(key.encode(), AES.MODE_CBC, iv=iv.encode()).encrypt(
            pad(json.dumps({'Status': 'SUCCESS', 'Result': result}).encode(), 32)
        ).hex()
        signed = {'MerchantID': result['MerchantID'], 'TradeInfo': info, 'TradeSha': sha256_hash(info, key, iv)}
        route = '/call_back/NewebPay/?client_code=qa-pay&merchant_revision='
        self.assertEqual(self.client.post(route + str(NewebpayMerchant.objects.latest('pk').pk), signed).status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'unpaid')
        self.assertEqual(self.client.post(route + str(merchant.pk), signed).status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'paid')

    def test_unauthorized_users_cannot_configure_or_enable_an_order(self):
        self.set_shop()
        self.assertEqual(self.member.get(self.settings_url).status_code, 403)
        self.assertEqual(self.member.put(self.order_url, {'enabled': True}, format='json').status_code, 403)
        self.group.refresh_from_db()
        self.assertIsNone(self.group.newebpay_override)

    def test_customer_service_only_opens_own_campus_order(self):
        self.set_shop()
        self.group.reservations.update(status='auto_assigned')
        staff = User.objects.create_user('qa-pay-support')
        profile = TenantStaffMembership.objects.create(
            user=staff, client=self.tenant, is_manager=True, role='assistant',
            admin_permissions=['order_edit', 'payment_accounts'], all_campuses=False,
        )
        profile.campuses.add(self.campus)
        self.admin.force_authenticate(staff)
        self.assertEqual(self.admin.get(self.settings_url).status_code, 403)
        self.assertEqual(self.admin.put(self.order_url, {'enabled': True}, format='json').status_code, 200)
        self.assertEqual(self.admin.put(self.order_url, {'enabled': False}, format='json').status_code, 200)
        self.assertEqual(self.admin.put(self.order_url, ['invalid'], format='json').status_code, 400)
        self.payment.status = 'paid'
        self.payment.save(update_fields=['status'])
        self.assertEqual(self.admin.put(self.order_url, {'enabled': True}, format='json').status_code, 409)
        self.group.campus = Campus.objects.create(client=self.tenant, name='QA Outside', code='qa-outside')
        self.group.save(update_fields=['campus'])
        self.assertEqual(self.admin.get(self.order_url).status_code, 404)
