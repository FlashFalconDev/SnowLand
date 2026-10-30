from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from Client.models import Client
from Control.models import TenantStaffMembership
from Resorts.models import Campus


class TenantMembershipTests(TestCase):
    def setUp(self):
        self.a = Client.objects.create(name='School A', internal_code='school-a')
        self.b = Client.objects.create(name='School B', internal_code='school-b')
        self.user = User.objects.create_user('shared', 'shared@example.test', 'test-password')
        self.ca = Campus.objects.create(client=self.a, name='A', code='a')
        self.cb = Campus.objects.create(client=self.b, name='B', code='b')
        self.pa = TenantStaffMembership.objects.create(user=self.user, client=self.a, is_manager=True,
            role='campus_manager', admin_permissions=['orders'])
        self.pa.campuses.add(self.ca)
        self.pb = TenantStaffMembership.objects.create(user=self.user, client=self.b, is_manager=True,
            role='hq_admin', admin_permissions=['staff','cms'])
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_same_login_has_independent_roles_permissions_and_campuses(self):
        a=self.api.get('/api/admin/school-a/me/')
        b=self.api.get('/api/admin/school-b/me/')
        self.assertEqual(a.status_code,200,a.data)
        self.assertEqual(b.status_code,200,b.data)
        self.assertEqual(a.data['data']['role'],'campus_manager')
        self.assertEqual(a.data['data']['permissions'],['orders'])
        self.assertEqual(a.data['data']['assigned_campus_ids'],[self.ca.pk])
        self.assertEqual(b.data['data']['role'],'hq_admin')
        self.assertEqual(b.data['data']['permissions'],['staff','cms'])
        self.assertEqual(self.api.get('/api/admin/school-a/staff/').status_code,403)
        self.assertEqual(self.api.get('/api/admin/school-b/orders/').status_code,403)

    def test_revocation_in_one_school_never_changes_other_school(self):
        result=self.api.post(f'/api/admin/school-b/customers/{self.user.pk}/permission/',
            {'is_manager':False,'is_coach':False,'role':'','permissions':[],'campus_ids':[]},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(self.api.get('/api/admin/school-b/me/').status_code,403)
        self.assertEqual(self.api.get('/api/admin/school-a/me/').status_code,200)
        self.pa.refresh_from_db()
        self.assertEqual(self.pa.admin_permissions,['orders'])

    def test_school_cannot_grant_platform_administration(self):
        result=self.api.post(f'/api/admin/school-b/customers/{self.user.pk}/permission/',
            {'is_superuser':True,'is_manager':True,'role':'hq_admin','permissions':['staff'],'campus_ids':[]},format='json')
        self.assertEqual(result.status_code,403,result.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)

    def test_exact_email_can_find_other_school_identity_without_its_roles(self):
        other=User.objects.create_user('other-staff','other@example.test','qa-password')
        old=other.userprofile;old.is_manager=True;old.manager_client=self.a;old.role='hq_admin';old.save()
        unfiltered=self.api.get('/api/admin/school-b/staff/').data['data']['list']
        self.assertNotIn(other.pk,[row['id'] for row in unfiltered])
        partial=self.api.get('/api/admin/school-b/staff/',{'q':'other@'}).data['data']['list']
        self.assertNotIn(other.pk,[row['id'] for row in partial])
        found=self.api.get('/api/admin/school-b/staff/',{'q':'other@example.test','invite':'1'}).data['data']['list']
        target=next(row for row in found if row['id']==other.pk)
        self.assertFalse(target['is_manager']);self.assertEqual(target['role'],'')
        self.assertEqual(target['permissions'],[])

    def test_cms_authority_uses_current_school_before_permission_selection(self):
        self.assertEqual(self.api.get('/api/admin/school-b/site-content/').status_code,200)
        self.assertEqual(self.api.get('/api/admin/school-a/site-content/').status_code,403)

    def test_same_login_has_independent_coach_profiles_and_school_calendar(self):
        from Coach.models import Coach
        from django.db import IntegrityError,transaction
        a=Coach.objects.create(user=self.user,client=self.a,name='A coach',website_enabled=True)
        b=Coach.objects.create(user=self.user,client=self.b,name='B coach',website_enabled=True)
        a.campuses.add(self.ca);b.campuses.add(self.cb)
        for membership in [self.pa,self.pb]:
            membership.is_coach=True;membership.save()
        self.assertEqual(self.api.get('/api/admin/school-a/coach/my-courses/').status_code,200)
        self.assertEqual(self.api.get('/api/admin/school-b/coach/my-courses/').status_code,200)
        for code,coach in [('school-a',a),('school-b',b)]:
            response=self.api.get('/booking/'+code+'/api/website-coaches/')
            self.assertEqual([row['id'] for row in response.data['data']['list']],[coach.pk])
        self.assertEqual(self.api.get('/booking/school-a/api/coach-bookings/',{'coach_id':b.pk}).status_code,404)
        self.assertEqual(self.api.get('/booking/api/website-coaches/').status_code,404)
        with self.assertRaises(IntegrityError),transaction.atomic():
            Coach.objects.create(user=self.user,client=self.a,name='duplicate')

    def test_maintenance_command_requires_school_and_does_not_modify_others(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from io import StringIO
        other=User.objects.create_user('command-user',email='command@example.test')
        call_command('set_user_permission',other.email,client='school-a',manager=True,stdout=StringIO())
        call_command('set_user_permission',other.email,client='school-b',coach=True,stdout=StringIO())
        a=TenantStaffMembership.objects.get(user=other,client=self.a)
        b=TenantStaffMembership.objects.get(user=other,client=self.b)
        self.assertTrue(a.is_manager);self.assertFalse(a.is_coach)
        self.assertFalse(b.is_manager);self.assertTrue(b.is_coach)
        other.userprofile.refresh_from_db();self.assertFalse(other.userprofile.is_manager)
        with self.assertRaises(CommandError):
            call_command('set_user_permission',other.email,client='not-a-school',manager=True,stdout=StringIO())
