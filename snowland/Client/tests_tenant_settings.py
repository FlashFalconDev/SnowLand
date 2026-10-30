from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from Client.models import Client, ModuleInfo, ModuleSetting
from Client.tenant_settings import gateway_settings
from Control.models import TenantStaffMembership


class TenantSettingsTests(TestCase):
    def setUp(self):
        self.a=Client.objects.create(name='SnowLand',internal_code='snowland',logo_url='https://example.test/a.png')
        self.b=Client.objects.create(name='Second school',internal_code='school-b',google_oauth_client_id='second.apps.googleusercontent.com')
        self.api=APIClient()

    def test_public_identity_is_live_and_never_returns_private_settings(self):
        self.a.bank_account_number='private';self.a.sales='private';self.a.save()
        result=self.api.get('/booking/snowland/api/client-info/')
        self.assertEqual(result.status_code,200)
        self.assertEqual(set(result.data),{'internal_code','name','logo_url','google_client_id','booking_enabled'})
        self.a.name='Renamed school';self.a.save()
        self.assertEqual(self.api.get('/booking/snowland/api/client-info/').data['name'],'Renamed school')
        self.assertEqual(self.api.get('/booking/school-b/api/client-info/').data['google_client_id'],'second.apps.googleusercontent.com')

    def test_expiry_only_warns_and_does_not_disable_existing_school(self):
        self.a.service_end_date=timezone.now()-timedelta(days=1);self.a.save()
        self.assertIn('尚未停用',self.a.service_status)
        self.assertEqual(self.api.get('/booking/snowland/api/client-info/').status_code,200)
        self.a.is_active=False;self.a.save()
        self.assertEqual(self.api.get('/booking/snowland/api/client-info/').status_code,404)

    @override_settings(NEWEBPAY_MERCHANT_ID='legacy-id',NEWEBPAY_HASH_KEY='qa-key',NEWEBPAY_HASH_IV='qa-iv')
    def test_new_school_never_borrows_legacy_gateway(self):
        self.assertEqual(gateway_settings(self.a)['MerchantID'],'legacy-id')
        self.assertIsNone(gateway_settings(self.b))
        self.b.payment_env_prefix='SCHOOL_B'
        with patch.dict('os.environ',{'SCHOOL_B_MERCHANT_ID':'b-id','SCHOOL_B_HASH_KEY':'b-key','SCHOOL_B_HASH_IV':'b-iv'}):
            self.assertEqual(gateway_settings(self.b)['MerchantID'],'b-id')
        self.assertIsNone(gateway_settings(self.b))

    def test_disabled_school_module_limits_even_an_authorized_school_admin(self):
        user=User.objects.create_user('staff','staff@example.test','test-password')
        TenantStaffMembership.objects.create(user=user,client=self.a,is_manager=True,role='hq_admin',admin_permissions=['orders','staff'])
        module=ModuleInfo.objects.create(module_sid='orders',module_name='Orders')
        ModuleSetting.objects.create(client=self.a,module=module,is_active=False)
        self.api.force_authenticate(user)
        self.assertEqual(self.api.get('/api/admin/snowland/orders/').status_code,403)
        response=self.api.get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertNotIn('orders',response.data['data']['permissions'])

    def test_get_cannot_edit_public_school_configuration(self):
        self.assertEqual(self.api.post('/booking/school-b/api/client-info/',{'name':'changed'}).status_code,405)
        self.b.refresh_from_db();self.assertEqual(self.b.name,'Second school')

    def test_platform_only_configuration_and_model_validation(self):
        from django.contrib.admin.sites import AdminSite
        from django.core.exceptions import ValidationError
        from Client.admin import ClientAdmin
        from django.test import RequestFactory
        staff=User.objects.create_user('tenant-admin',is_staff=True)
        request=RequestFactory().get('/admin/');request.user=staff
        admin=ClientAdmin(Client,AdminSite())
        self.assertFalse(admin.has_view_permission(request,self.a))
        self.assertFalse(admin.has_change_permission(request,self.a))
        for code in ['auth','has space','a/b']:
            self.a.internal_code=code
            with self.assertRaises(ValidationError):self.a.clean()
        self.a.internal_code='school-a';self.a.payment_env_prefix='bad-prefix'
        with self.assertRaises(ValidationError):self.a.clean()

    def test_global_module_off_is_enforced_without_school_override(self):
        from Client.tenant_settings import module_enabled
        ModuleInfo.objects.create(module_sid='booking',module_name='Booking',is_active=False)
        self.assertFalse(module_enabled(self.a,'booking'))
        self.assertFalse(self.api.get('/booking/snowland/api/client-info/').data['booking_enabled'])

    def test_payment_prefix_cannot_be_accidentally_reused_by_a_second_school(self):
        from django.db import IntegrityError,transaction
        self.a.payment_env_prefix='SCHOOL_A';self.a.save()
        self.b.payment_env_prefix='SCHOOL_A'
        with self.assertRaises(IntegrityError),transaction.atomic():self.b.save()

    @override_settings(SNOWLAND_PUBLIC_PAYMENT_URL='https://booking.example.test/snowland/payment')
    def test_shared_site_links_keep_each_school_path(self):
        from booking.payment_access import school_payment_base_url
        self.assertEqual(school_payment_base_url(self.b),'https://booking.example.test/school-b/payment')
        with override_settings(SNOWLAND_PUBLIC_PAYMENT_URL='https://attacker.test/unknown/payment'):
            with self.assertRaises(ValueError):school_payment_base_url(self.b)
