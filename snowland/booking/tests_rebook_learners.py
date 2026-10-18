from copy import deepcopy
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from booking import tests_participants as fixtures
from booking.models import MemberDetail, Reservation, ReservationGroup


class RebookLearnerTests(TestCase):
    def setUp(self):
        fixtures.MemberEnrollmentTests.setUp(self)
        self.source=fixtures.MemberEnrollmentTests.book(self)
        self.first,self.second=list(self.source.members.order_by('pk'))
        self.first.insurance_data={'full_name':'QA本人','id_number':'QA-PRIVATE-ID','birth_date':'1990-01-01','health_note':'QA-private'}
        self.first.age_range='25-35y';self.first.snowboard_skills=['雪場S turn']
        self.first.waiver_signature='QA-OLD-SIGNATURE';self.first.waiver_document_snapshot='QA-OLD-WAIVER'
        self.first.insurance_completed_at=timezone.now();self.first.waiver_completed_at=timezone.now()
        self.first.insurance_processing_status='insured';self.first.save()
        self.other=User.objects.create_user('qa-other-learner')
        self.second.user=self.other;self.second.insurance_data={'full_name':'QA其他成人','id_number':'OTHER-PRIVATE-ID'};self.second.save()

    def quick(self):
        result=self.api.post('/booking/snowland/api/member-center/',{'quick_rebook_group_id':self.source.group_id},format='json')
        self.assertEqual(result.status_code,200,result.data)
        return result.data['cart'][0]

    def payload(self):
        item=self.quick()
        item['courses'][0]['date']=str(timezone.localdate()+timedelta(days=30))
        return {'cart':[item],'accepted_policy':True,'contact':{'name':'QA訂購人','email':self.owner.email,'phone':'0900000000','messengerType':'line','messengerId':'qa-only','referralSource':'其他'}}

    def create(self,body,advanced=False):
        url='/booking/snowland/api/super-schedule/' if advanced else '/booking/snowland/api/create-reservation/'
        return self.api.post(url,body,format='json')

    def test_rebook_reference_has_only_authorized_count_not_private_data(self):
        item=self.quick()
        self.assertEqual(item['rebookSource'],{'reservationId':self.source.pk,'peopleCount':2,'learnerCount':1})
        for private in ['QA-PRIVATE-ID','OTHER-PRIVATE-ID','QA-OLD-SIGNATURE','QA-private']:
            self.assertNotIn(private,str(item))

    def test_new_order_copies_only_own_basic_preferences_and_resets_documents(self):
        result=self.create(self.payload());self.assertEqual(result.status_code,200,result.data)
        row=Reservation.objects.get(group_id=result.data['reservation_group_ids'][0])
        own,other=list(row.members.order_by('pk'))
        self.assertEqual(own.insurance_data,{'full_name':'QA本人'})
        self.assertEqual(own.age_range,'25-35y');self.assertEqual(list(own.snowboard_skills),['雪場S turn'])
        self.assertFalse(own.waiver_signature);self.assertFalse(own.waiver_document_snapshot)
        self.assertIsNone(own.waiver_completed_at);self.assertIsNone(own.insurance_completed_at)
        self.assertEqual(own.insurance_processing_status,'pending')
        self.assertEqual(other.insurance_data,{});self.assertNotEqual(other.user_id,self.other.pk)
        self.first.refresh_from_db();self.assertEqual(self.first.waiver_signature,'QA-OLD-SIGNATURE')

    def test_parent_keeps_own_child_management_but_not_other_adults_binding(self):
        self.first.user=None;self.first.guardian=self.owner;self.first.age_range='7-12y';self.first.save()
        result=self.create(self.payload());self.assertEqual(result.status_code,200,result.data)
        row=Reservation.objects.get(group_id=result.data['reservation_group_ids'][0])
        child,other=list(row.members.order_by('pk'))
        self.assertIsNone(child.user_id);self.assertEqual(child.guardian_id,self.owner.pk)
        self.assertEqual(child.age_range,'7-12y');self.assertEqual(child.insurance_data,{'full_name':'QA本人'})
        self.assertIsNone(other.guardian_id);self.assertNotEqual(other.user_id,self.other.pk)

    def test_foreign_owner_or_changed_count_never_half_creates_order(self):
        for mode in ['owner','people']:
            body=self.payload();before=ReservationGroup.objects.count();learners=MemberDetail.objects.count()
            if mode=='owner':
                self.source.group.user=self.other;self.source.group.save()
            else:
                body['cart'][0]['peopleCount']=1;body['cart'][0]['abilityLevelCounts']={'no_exp':1}
            result=self.create(body)
            self.assertEqual(result.status_code,400,result.data)
            self.assertEqual(ReservationGroup.objects.count(),before);self.assertEqual(MemberDetail.objects.count(),learners)
            self.source.group.user=self.owner;self.source.group.save()

    def test_guardian_permission_is_rechecked_at_submission(self):
        self.first.user=None;self.first.guardian=self.owner;self.first.save()
        body=self.payload();self.first.guardian=None;self.first.save()
        result=self.create(body);self.assertEqual(result.status_code,200,result.data)
        row=Reservation.objects.get(group_id=result.data['reservation_group_ids'][0])
        self.assertTrue(all(not member.insurance_data and not member.guardian_id for member in row.members.all()))

    def test_advanced_split_has_basic_preferences_per_day_not_old_signatures(self):
        body=self.payload();second=deepcopy(body['cart'][0]['courses'][0]);second['date']=str(timezone.localdate()+timedelta(days=31));body['cart'][0]['courses'].append(second)
        result=self.create(body,advanced=True);self.assertEqual(result.status_code,200,result.data)
        group=ReservationGroup.objects.get(pk=result.data['reservation_group_id'])
        self.assertEqual(group.reservations.count(),2)
        for row in group.reservations.all():
            own,other=list(row.members.order_by('pk'))
            self.assertEqual(own.insurance_data,{'full_name':'QA本人'});self.assertFalse(own.waiver_signature)
            self.assertEqual(other.insurance_data,{})

    def test_invalid_or_cross_company_source_is_rejected_in_both_booking_paths(self):
        from Client.models import Client
        foreign=ReservationGroup.objects.create(client=Client.objects.create(name='Other',internal_code='other'),user=self.owner)
        row=Reservation.objects.create(group=foreign,number_of_people=2)
        for reference in ['invalid',{}, {'reservationId':True},{'reservationId':row.pk}]:
            for advanced in [False,True]:
                body=self.payload();body['cart'][0]['rebookSource']=reference
                before=ReservationGroup.objects.count()
                result=self.create(body,advanced=advanced)
                self.assertEqual(result.status_code,400,result.data)
                self.assertEqual(ReservationGroup.objects.count(),before)

    def test_archived_learner_never_reappears_in_rebook_preferences(self):
        MemberDetail.all_objects.create(reservation=self.source,user=self.owner,is_active=False,age_range='7-12y',insurance_data={'full_name':'QA退出學員'})
        self.assertEqual(self.quick()['rebookSource']['learnerCount'],1)
        result=self.create(self.payload());self.assertEqual(result.status_code,200,result.data)
        row=Reservation.objects.get(group_id=result.data['reservation_group_ids'][0])
        self.assertEqual(row.members.count(),2)
        self.assertNotIn('QA退出學員',str(list(row.members.values_list('insurance_data',flat=True))))
