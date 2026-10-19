from django.test import TestCase
from rest_framework.test import APIClient
from API import tests_multi_campus_membership as fixtures
from API.admin_permissions import ROLE_DEFAULT_PERMISSIONS
from Coach.models import Coach
from booking.models import Payment, Reservation


class DualRoleCampusTests(TestCase):
    def setUp(self):
        fixtures.MultiCampusMembershipTests.setUp(self)
        self.user=self.staff['campus_manager']
        profile=self.user.userprofile;profile.is_coach=True;profile.save()
        profile.campuses.set([self.campuses['a']])
        self.coach=Coach.objects.create(client=self.tenant,user=self.user,name='QA兼任教練')
        self.coach.campuses.add(self.campuses['b'])
        Reservation.objects.filter(group__in=[self.groups['b',2],self.groups['b',11]]).update(preferred_coach=self.coach)
        for group in self.groups.values():Payment.objects.create(reservation_group=group,status='paid')
        self.session=APIClient();self.assertTrue(self.session.login(username='campus_manager',password='qa-only'))
        self.hq_api=APIClient();self.hq_api.force_authenticate(self.hq)

    def me(self):
        result=self.session.get('/api/admin/snowland/me/');self.assertEqual(result.status_code,200,result.data)
        return result.data['data']

    def own_ids(self):
        result=self.session.get('/api/admin/snowland/coach/my-courses/',HTTP_X_CAMPUS_ID=str(self.campuses['a'].pk))
        self.assertEqual(result.status_code,200,result.data)
        self.assertNotIn('QA-PRIVATE-MULTI',str(result.data))
        return {row['group_id'] for row in result.data['data']['list']}

    def change_role(self,manager,coach):
        result=self.hq_api.post(f'/api/admin/snowland/customers/{self.user.pk}/permission/',{
            'is_manager':manager,'is_coach':coach,'role':'campus_manager' if manager else '',
            'campus_ids':[self.campuses['a'].pk] if manager else [],
            'permissions':ROLE_DEFAULT_PERMISSIONS['campus_manager'] if manager else [],
        },format='json')
        self.assertEqual(result.status_code,200,result.data)

    def test_dual_role_manager_scope_does_not_expand_to_coach_campus(self):
        me=self.me();self.assertTrue(me['is_manager']);self.assertTrue(me['is_coach'])
        self.assertEqual([row['id'] for row in me['campuses']],[self.campuses['a'].pk])
        orders=self.session.get('/api/admin/snowland/orders/')
        self.assertEqual(orders.status_code,200,orders.data)
        self.assertEqual({row['id'] for row in orders.data['data']['list']},{self.groups['a',2].pk})
        self.assertEqual(self.session.get('/api/admin/snowland/orders/',HTTP_X_CAMPUS_ID=str(self.campuses['b'].pk)).status_code,403)
        self.assertEqual(self.own_ids(),{self.groups['b',2].pk})

    def test_manager_revocation_preserves_only_coach_access_in_existing_session(self):
        self.change_role(False,True)
        me=self.me();self.assertFalse(me['is_manager']);self.assertTrue(me['is_coach']);self.assertEqual(me['role'],'coach')
        self.assertEqual([row['id'] for row in me['campuses']],[self.campuses['b'].pk]);self.assertEqual(me['permissions'],[])
        self.assertEqual(self.session.get('/api/admin/snowland/orders/').status_code,403)
        self.assertEqual(self.own_ids(),{self.groups['b',2].pk})

    def test_coach_revocation_preserves_only_manager_access(self):
        self.change_role(True,False)
        me=self.me();self.assertTrue(me['is_manager']);self.assertFalse(me['is_coach'])
        self.assertEqual(self.session.get('/api/admin/snowland/coach/my-courses/').status_code,403)
        self.assertEqual(self.session.get('/api/admin/snowland/orders/').status_code,200)
        self.assertTrue(Coach.objects.filter(pk=self.coach.pk).exists(),'Removing access must not delete historical coach records')

    def test_disabled_manager_campus_falls_back_to_personal_coach_but_hq_keeps_history(self):
        url=f'/api/admin/snowland/campuses/{self.campuses["a"].pk}/'
        self.assertEqual(self.hq_api.patch(url,{'is_active':False},format='json').status_code,200)
        me=self.me();self.assertFalse(me['is_manager']);self.assertTrue(me['is_coach'])
        self.assertEqual([row['id'] for row in me['campuses']],[self.campuses['b'].pk])
        self.assertEqual(self.session.get('/api/admin/snowland/orders/').status_code,403)
        self.assertEqual(self.own_ids(),{self.groups['b',2].pk})
        history=self.hq_api.get(f'/api/admin/snowland/orders/{self.groups["a",2].pk}/')
        self.assertEqual(history.status_code,200,history.data)
        public=APIClient().get('/booking/snowland/api/resorts/')
        self.assertEqual(public.status_code,200,public.data)
        self.assertNotIn(self.resorts['a'].name,[row['name'] for row in public.data])
        self.assertEqual(self.hq_api.patch(url,{'is_active':True},format='json').status_code,200)
        self.assertTrue(self.me()['is_manager']);self.assertEqual(self.session.get('/api/admin/snowland/orders/').status_code,200)
