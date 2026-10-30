from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from Client.models import Client, ClientMemberProfile
from Client.memberships import member_profile
from booking.models import MemberProfile, ReservationGroup


class ClientMemberIsolationTests(TestCase):
    def setUp(self):
        self.a=Client.objects.create(name='A',internal_code='school-a')
        self.b=Client.objects.create(name='B',internal_code='school-b')
        self.user=User.objects.create_user('shared','shared@example.test','test-password',first_name='Shared identity')
        self.api=APIClient()
        self.api.force_authenticate(self.user)

    def test_same_login_gets_separate_profile_referral_and_line_status(self):
        pa=member_profile(self.user,self.a)
        pb=member_profile(self.user,self.b)
        pa.display_name='A name';pa.line_user_id='A-line';pa.save()
        a=self.api.get('/booking/school-a/api/member-center/')
        b=self.api.get('/booking/school-b/api/member-center/')
        self.assertEqual(a.status_code,200,a.data)
        self.assertEqual(b.status_code,200,b.data)
        self.assertEqual(a.data['member']['name'],'A name')
        self.assertEqual(b.data['member']['name'],'Shared identity')
        self.assertNotEqual(a.data['referral_code'],b.data['referral_code'])
        self.assertTrue(a.data['line_linked'])
        self.assertFalse(b.data['line_linked'])
        self.assertEqual(ClientMemberProfile.objects.filter(user=self.user).count(),2)

    def test_single_known_legacy_school_preserves_reference_without_copying_to_second(self):
        legacy=MemberProfile.objects.create(user=self.user,line_user_id='legacy-line')
        ReservationGroup.objects.create(user=self.user,client=self.a)
        a=member_profile(self.user,self.a)
        b=member_profile(self.user,self.b)
        self.assertEqual(a.referral_code,legacy.referral_code)
        self.assertEqual(a.line_user_id,'legacy-line')
        self.assertNotEqual(b.referral_code,legacy.referral_code)
        self.assertEqual(b.line_user_id,'')

    def test_ambiguous_legacy_line_is_never_automatically_shared(self):
        MemberProfile.objects.create(user=self.user,line_user_id='legacy-line')
        for client in [self.a,self.b]: ReservationGroup.objects.create(user=self.user,client=client)
        for client in [self.a,self.b]: self.assertEqual(member_profile(self.user,client).line_user_id,'')

    def test_unknown_or_inactive_school_cannot_establish_membership(self):
        self.b.is_active=False;self.b.save()
        for code in ['missing','school-b']:
            result=self.api.get(f'/booking/{code}/api/google-login/')
            self.assertEqual(result.status_code,404,result.data)
        self.assertFalse(ClientMemberProfile.objects.exists())

    def test_registered_member_without_orders_is_visible_only_in_own_school(self):
        from Control.models import TenantStaffMembership
        admin=User.objects.create_user('admin')
        for school in [self.a,self.b]:
            TenantStaffMembership.objects.create(user=admin,client=school,is_manager=True,role='hq_admin',admin_permissions=['customers'])
        member_profile(self.user,self.a).save()
        self.api.force_authenticate(admin)
        a=self.api.get('/api/admin/school-a/customers/')
        b=self.api.get('/api/admin/school-b/customers/')
        self.assertEqual(a.status_code,200,a.data)
        self.assertIn(self.user.pk,[row['id'] for row in a.data['data']['list']])
        self.assertNotIn(self.user.pk,[row['id'] for row in b.data['data']['list']])
