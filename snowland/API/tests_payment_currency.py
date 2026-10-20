from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client


class PaymentCurrencySettingsTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.user = User.objects.create_superuser('currency-hq', 'currency-hq@example.test', 'test-password')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/admin/snowland/payment-settings/'

    def test_headquarters_can_save_and_reload_jpy_rate_without_changing_twd_prices(self):
        initial = self.api.get(self.url)
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.data['data']['currency_settings'], {'jpy_enabled': False, 'jpy_per_twd': ''})
        saved = self.api.put(self.url, {'currency_settings': {'jpy_enabled': True, 'jpy_per_twd': '4.5'}}, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        reloaded = self.api.get(self.url)
        self.assertEqual(reloaded.data['data']['currency_settings'], {'jpy_enabled': True, 'jpy_per_twd': '4.50000000'})

    def test_invalid_rate_never_partially_changes_bank_or_previous_currency_settings(self):
        self.api.put(self.url, {'bank_name': '原本銀行', 'currency_settings': {'jpy_enabled': True, 'jpy_per_twd': '4.5'}}, format='json')
        for rate in ['', '0', '-1', 'NaN', 'Infinity', '1e9', '4.123456789', '1000000000', True, 4.5, {}, []]:
            with self.subTest(rate=rate):
                response = self.api.put(self.url, {'bank_name': '不該寫入', 'currency_settings': {'jpy_enabled': True, 'jpy_per_twd': rate}}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                current = self.api.get(self.url).data['data']
                self.assertEqual(current['bank_name'], '原本銀行')
                self.assertEqual(current['currency_settings']['jpy_per_twd'], '4.50000000')

    def test_old_settings_client_does_not_clear_new_rate_and_other_tenant_is_independent(self):
        self.api.put(self.url, {'currency_settings': {'jpy_enabled': True, 'jpy_per_twd': '4.5'}}, format='json')
        self.assertEqual(self.api.put(self.url, {'bank_name': '更新名稱'}, format='json').status_code, 200)
        self.assertEqual(self.api.get(self.url).data['data']['currency_settings']['jpy_per_twd'], '4.50000000')
        Client.objects.create(name='Other', internal_code='other-currency')
        other = self.api.get('/api/admin/other-currency/payment-settings/')
        self.assertEqual(other.status_code, 200, other.data)
        self.assertEqual(other.data['data']['currency_settings'], {'jpy_enabled': False, 'jpy_per_twd': ''})

    def test_campus_manager_cannot_change_company_currency_settings(self):
        manager = User.objects.create_user('currency-manager', 'currency-manager@example.test', 'test-password')
        profile = manager.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = ['payment_settings']
        profile.save()
        self.api.force_authenticate(manager)
        response = self.api.put(self.url, {'currency_settings': {'jpy_enabled': True, 'jpy_per_twd': '4.5'}}, format='json')
        self.assertEqual(response.status_code, 403, response.data)

    def test_enabled_value_must_be_boolean_and_disabling_requires_no_rate(self):
        bad = self.api.put(self.url, {'currency_settings': {'jpy_enabled': 'false', 'jpy_per_twd': '4.5'}}, format='json')
        self.assertEqual(bad.status_code, 400)
        off = self.api.put(self.url, {'currency_settings': {'jpy_enabled': False, 'jpy_per_twd': ''}}, format='json')
        self.assertEqual(off.status_code, 200, off.data)
        self.assertEqual(off.data['data']['currency_settings'], {'jpy_enabled': False, 'jpy_per_twd': ''})

    def test_jpy_account_cannot_be_used_as_a_twd_account(self):
        from booking.models import ReservationGroup
        from booking.operations import resolve_payment_account
        response = self.api.post('/api/admin/snowland/payment-accounts/', {
            'name': '日幣測試帳戶', 'currency': 'JPY', 'bank_name': 'QA銀行', 'bank_branch': 'QA分行',
            'account_number': 'QA-NOT-REAL', 'account_holder': 'QA戶名',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['currency'], 'JPY')
        group = ReservationGroup.objects.create(client=self.tenant, user=self.user)
        self.assertIsNone(resolve_payment_account(group))
        self.assertEqual(resolve_payment_account(group, currency='JPY').pk, response.data['id'])

    def test_public_currency_choices_require_both_enabled_rate_and_complete_account(self):
        from Resorts.models import PaymentCurrencySettings, PaymentAccount
        public = APIClient()
        url = '/booking/snowland/api/currency-options/'
        self.assertEqual(public.get(url).data['currencies'], [{'code':'TWD','rate':'1.00000000'}])
        config = PaymentCurrencySettings.objects.create(client=self.tenant,jpy_enabled=True,jpy_per_twd='4.5')
        self.assertEqual(len(public.get(url).data['currencies']),1)
        bank = PaymentAccount.objects.create(client=self.tenant,name='QA日幣',currency='JPY',bank_name='QA銀行',bank_branch='QA分行',account_number='QA-ONLY',account_holder='QA戶名')
        enabled = public.get(url)
        self.assertEqual(enabled.status_code,200,enabled.data)
        self.assertEqual(enabled.data['currencies'],[{'code':'TWD','rate':'1.00000000'},{'code':'JPY','rate':'4.50000000'}])
        self.assertNotIn('QA-ONLY',str(enabled.data))
        bank.is_active=False;bank.save()
        self.assertEqual(len(public.get(url).data['currencies']),1)

    def test_used_account_currency_cannot_be_relabelled(self):
        from Resorts.models import PaymentAccount
        from booking.models import Payment, ReservationGroup
        bank=PaymentAccount.objects.create(client=self.tenant,name='QA已使用',bank_name='QA銀行',bank_branch='QA分行',account_number='QA-ONLY',account_holder='QA戶名')
        group=ReservationGroup.objects.create(client=self.tenant,user=self.user)
        Payment.objects.create(reservation_group=group,payment_account=bank,status='unpaid')
        response=self.api.patch(f'/api/admin/snowland/payment-accounts/{bank.pk}/',{'currency':'JPY'},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(self.api.get(f'/api/admin/snowland/payment-accounts/{bank.pk}/').data['currency'],'TWD')
