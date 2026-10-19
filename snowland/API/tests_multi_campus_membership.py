from datetime import time, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from API.admin_permissions import ROLE_DEFAULT_PERMISSIONS
from Client.models import Client
from Resorts.models import Campus, Resorts
from Coursekit.models import CourseCategory, CourseType
from booking.models import ReservationGroup, Reservation, Booking, MemberDetail


class MultiCampusMembershipTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.other=Client.objects.create(name='Other',internal_code='other')
        self.campuses={};self.resorts={}
        for key in 'abc':
            campus=Campus.objects.create(client=self.tenant,name=f'{key}校區',code=key)
            resort=Resorts.objects.create(client=self.tenant,name=f'{key}resort',display_name=f'{key}雪場')
            campus.resorts.add(resort);self.campuses[key]=campus;self.resorts[key]=resort
        self.hq=User.objects.create_superuser('multi-hq',password='qa-only')
        self.staff={}
        for role in ('campus_manager','campus_principal'):
            user=User.objects.create_user(role,password='qa-only')
            profile=user.userprofile;profile.is_manager=True;profile.manager_client=self.tenant;profile.role=role;profile.admin_permissions=ROLE_DEFAULT_PERMISSIONS[role];profile.save()
            profile.campuses.set([self.campuses['a'],self.campuses['b']]);self.staff[role]=user
        self.kind=CourseType.objects.create(category=CourseCategory.objects.create(client=self.tenant,name='滑雪'),name='單板')
        self.groups={}
        for key in 'abc':
            for offset in (2,11):
                group=ReservationGroup.objects.create(client=self.tenant,campus=self.campuses[key],name='QA完整姓名不公開',order_number=f'QA-MULTI-{key}-{offset}')
                reservation=Reservation.objects.create(group=group,resort=self.resorts[key],course_type=self.kind,number_of_people=1,course_fee=10000,status='manually_assigned')
                Booking.objects.create(reservation=reservation,date=timezone.localdate()+timedelta(days=offset),start_time=time(9),end_time=time(12),course_type='單板')
                MemberDetail.objects.create(reservation=reservation,insurance_data={'passport_number':'QA-PRIVATE-MULTI'})
                self.groups[key,offset]=group

    def api(self,role='campus_principal'):
        api=APIClient();self.assertTrue(api.login(username=role,password='qa-only'));return api

    def ids(self,response):
        self.assertEqual(response.status_code,200,response.data)
        self.assertNotIn('QA-PRIVATE-MULTI',str(response.data))
        return {row['id'] for row in response.data['data']['list']}

    def change(self,user,campus_keys,manager=True):
        api=APIClient();api.force_authenticate(self.hq)
        return api.post(f'/api/admin/snowland/customers/{user.pk}/permission/',{'is_manager':manager,'is_coach':False,'role':'campus_principal','campus_ids':[self.campuses[key].pk for key in campus_keys],'permissions':ROLE_DEFAULT_PERMISSIONS['campus_principal']},format='json')

    def test_principal_union_then_single_scope_and_third_scope_denied(self):
        api=self.api()
        all_ids={group.pk for (key,_),group in self.groups.items() if key in 'ab'}
        self.assertEqual(self.ids(api.get('/api/admin/snowland/orders/')),all_ids)
        for key in 'ab':
            result=api.get('/api/admin/snowland/orders/',HTTP_X_CAMPUS_ID=str(self.campuses[key].pk))
            self.assertEqual(self.ids(result),{self.groups[key,offset].pk for offset in (2,11)})
        self.assertEqual(api.get('/api/admin/snowland/orders/',HTTP_X_CAMPUS_ID=str(self.campuses['c'].pk)).status_code,403)
        self.assertEqual(api.get(f'/api/admin/snowland/orders/{self.groups["c",2].pk}/').status_code,404)

    def test_manager_ten_day_boundary_applies_to_each_assigned_campus(self):
        api=self.api('campus_manager')
        self.assertEqual(self.ids(api.get('/api/admin/snowland/orders/')),{self.groups[key,2].pk for key in 'ab'})
        for key in 'ab':
            self.assertEqual(self.ids(api.get('/api/admin/snowland/orders/',HTTP_X_CAMPUS_ID=str(self.campuses[key].pk))),{self.groups[key,2].pk})
            self.assertEqual(api.get(f'/api/admin/snowland/orders/{self.groups[key,11].pk}/').status_code,404)

    def test_existing_session_loses_removed_campus_immediately(self):
        api=self.api();b=self.campuses['b'].pk
        self.assertEqual(api.get('/api/admin/snowland/orders/',HTTP_X_CAMPUS_ID=str(b)).status_code,200)
        self.assertEqual(self.change(self.staff['campus_principal'],'a').status_code,200)
        self.assertEqual(api.get('/api/admin/snowland/orders/',HTTP_X_CAMPUS_ID=str(b)).status_code,403)
        self.assertEqual(api.get(f'/api/admin/snowland/orders/{self.groups["b",2].pk}/').status_code,404)
        me=api.get('/api/admin/snowland/me/');self.assertEqual(me.status_code,200)
        self.assertEqual([row['id'] for row in me.data['data']['campuses']],[self.campuses['a'].pk])
        self.assertEqual(self.ids(api.get('/api/admin/snowland/orders/')),{self.groups['a',offset].pk for offset in (2,11)})

    def test_full_revocation_blocks_same_session_and_failed_foreign_assignment_is_atomic(self):
        api=self.api();user=self.staff['campus_principal']
        foreign=Campus.objects.create(client=self.other,name='不可指派',code='foreign')
        hq=APIClient();hq.force_authenticate(self.hq)
        response=hq.post(f'/api/admin/snowland/customers/{user.pk}/permission/',{'is_manager':True,'role':'campus_principal','campus_ids':[self.campuses['a'].pk,foreign.pk]},format='json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(set(user.userprofile.campuses.values_list('pk',flat=True)),{self.campuses[key].pk for key in 'ab'})
        self.assertEqual(self.change(user,'',manager=False).status_code,200)
        self.assertEqual(api.get('/api/admin/snowland/orders/').status_code,403)
        self.assertEqual(api.get('/api/admin/snowland/me/').status_code,403)

    def test_query_scope_cannot_expand_header_scope_or_grant_other_campus(self):
        api=self.api()
        response=api.get('/api/admin/snowland/orders/',{'campus_id':self.campuses['c'].pk},HTTP_X_CAMPUS_ID=str(self.campuses['b'].pk))
        self.assertEqual(self.ids(response),{self.groups['b',offset].pk for offset in (2,11)})
        self.assertEqual(api.get('/api/admin/snowland/orders/',{'campus_id':self.campuses['c'].pk}).status_code,403)
        self.assertEqual(api.patch(f'/api/admin/snowland/orders/{self.groups["a",2].pk}/',{'name':'不可越權寫入'},format='json').status_code,403)
        self.groups['a',2].refresh_from_db();self.assertEqual(self.groups['a',2].name,'QA完整姓名不公開')
