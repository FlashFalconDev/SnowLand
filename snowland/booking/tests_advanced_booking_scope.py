from booking.tests_policy_support import checkout_policy_acknowledgement
from copy import deepcopy
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from booking import tests_pricing_modes as fixtures
from booking.models import ReservationGroup,Payment,MemberDetail
from Client.models import Client
from Coursekit.models import CourseCategory,CourseType,CourseTemplate
from Resorts.models import Campus,Resorts


class AdvancedBookingScopeTests(TestCase):
    def setUp(self):
        fixtures.PricingModeApiTests.setUp(self)
        self.campus=Campus.objects.create(client=self.client_record,name='QA校區',code='qa')
        self.campus.resorts.add(self.resort)
        self.resort.auto_scheduling_enabled=False;self.resort.save()
        self.url='/booking/snowland/api/super-schedule/'
        self.payload={**checkout_policy_acknowledgement(),'contact':{'name':'QA會員','email':'qa@example.test','phone':'0900000000','messengerType':'line','messengerId':'qa','referralSource':'其他'},'cart':[{'coach':'any','peopleCount':2,'abilityLevel':'no_exp','abilityLevelCounts':{'no_exp':2},'equipment':False,'equipmentOption':'own_equipment','language':'zh','resort':self.resort.name,'resortName':self.resort.display_name,'campusId':self.campus.pk,'courseCategory':'滑雪課程','courses':[{'date':str(timezone.localdate()+timedelta(days=20+i)),'courseTypeId':self.private_template.course_type_id,'courseTypeName':'QA課程','courseTemplateId':self.private_template.pk,'courseTemplateName':self.private_template.name,'durationHours':4,'timeSlotStart':'09:00','timeSlotEnd':'13:00'} for i in range(2)]}]}

    def test_anonymous_is_rejected_before_creating_any_order(self):
        self.api.force_authenticate(None)
        result=self.api.post(self.url,self.payload,format='json')
        self.assertEqual(result.status_code,401,result.data);self.assertEqual(ReservationGroup.objects.count(),0)

    def test_policy_and_marketing_source_are_required(self):
        for policy,source in [(False,'其他'),(True,'')]:
            body=deepcopy(self.payload);body['accepted_policy']=policy;body['contact']['referralSource']=source
            result=self.api.post(self.url,body,format='json')
            self.assertEqual(result.status_code,400,result.data);self.assertEqual(ReservationGroup.objects.count(),0)

    def test_success_preserves_campus_contact_source_learners_and_payment_policy(self):
        result=self.api.post(self.url,self.payload,format='json')
        self.assertEqual(result.status_code,200,result.data)
        group=ReservationGroup.objects.get(pk=result.data['reservation_group_id'])
        self.assertEqual(group.campus_id,self.campus.pk);self.assertEqual(group.marketing_source,'其他')
        self.assertEqual(group.booking_contact['phone'],'0900000000');self.assertIn('policy_accepted_at',group.booking_contact)
        self.assertEqual(group.reservations.count(),2);self.assertEqual(MemberDetail.objects.filter(reservation__group=group).count(),4)
        self.assertIsNotNone(group.payments.get().expires_at);self.assertEqual(group.revisions.count(),1)

    def test_foreign_course_or_resort_never_creates_order(self):
        other=Client.objects.create(name='Other',internal_code='other')
        resort=Resorts.objects.create(client=other,name='foreign-resort')
        kind=CourseType.objects.create(category=CourseCategory.objects.create(client=other,name='Foreign'),name='Foreign')
        template=CourseTemplate.objects.create(course_type=kind,name='Foreign',duration_hours=4,max_capacity=6)
        for changes in [{'resort':resort.name},{'template':template.pk,'type':kind.pk}]:
            body=deepcopy(self.payload)
            if 'resort' in changes:body['cart'][0]['resort']=changes['resort']
            else:body['cart'][0]['courses'][0].update(courseTypeId=changes['type'],courseTemplateId=changes['template'])
            result=self.api.post(self.url,body,format='json')
            self.assertEqual(result.status_code,400,result.data);self.assertEqual(ReservationGroup.objects.count(),0)

    def test_inactive_or_unassigned_campus_is_rejected(self):
        for state in ['inactive','unassigned']:
            self.campus.is_active=state!='inactive';self.campus.save()
            if state=='unassigned':self.campus.resorts.clear()
            result=self.api.post(self.url,self.payload,format='json')
            self.assertEqual(result.status_code,400,result.data);self.assertEqual(ReservationGroup.objects.count(),0)

    def test_multiple_cart_items_have_distinct_campus_groups(self):
        other_campus=Campus.objects.create(client=self.client_record,name='另一校區',code='qa2')
        other_campus.resorts.add(self.resort)
        body=deepcopy(self.payload);body['cart'].append(deepcopy(body['cart'][0]));body['cart'][1]['campusId']=other_campus.pk
        result=self.api.post(self.url,body,format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(set(ReservationGroup.objects.values_list('campus_id',flat=True)),{self.campus.pk,other_campus.pk})
        self.assertEqual(len(result.data['payment_urls']),2);self.assertEqual(Payment.objects.count(),2)

    def test_scheduling_failure_rolls_back_every_cart_group(self):
        from unittest.mock import patch
        self.resort.auto_scheduling_enabled=True;self.resort.save()
        body=deepcopy(self.payload);body['cart'].append(deepcopy(body['cart'][0]))
        with patch('booking.scheduler.assign_coachs',return_value=(False,{'error':'QA無可用教練'})):
            result=self.api.post(self.url,body,format='json')
        self.assertEqual(result.status_code,400,result.data);self.assertTrue(result.data['scheduling_failed'])
        self.assertEqual(ReservationGroup.objects.count(),0);self.assertEqual(Payment.objects.count(),0)
        self.assertEqual(MemberDetail.objects.count(),0)

    def test_shared_class_cannot_bypass_same_coach_flow(self):
        self.private_template.shared_class_enabled=True;self.private_template.save()
        result=self.api.post(self.url,self.payload,format='json')
        self.assertEqual(result.status_code,400,result.data);self.assertEqual(ReservationGroup.objects.count(),0)

    def test_advanced_discount_is_calculated_without_specified_coach_fee(self):
        from unittest.mock import patch
        from booking.api_views import calculate_cart_discount_summary
        body=deepcopy(self.payload);body['cart'][0]['coach']=999999
        with patch('booking.api_views.calculate_cart_discount_summary',wraps=calculate_cart_discount_summary) as pricing:
            result=self.api.post(self.url,body,format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(pricing.call_args.args[0][0]['coach'],'any')

    def test_malformed_cart_and_unpriced_added_hours_are_rejected(self):
        for cart in [{'bad':'shape'},[1],[{'resort':self.resort.name,'courses':[]}]]:
            result=self.api.post(self.url,{**self.payload,'cart':cart},format='json')
            self.assertEqual(result.status_code,400,result.data)
        body=deepcopy(self.payload);body['cart'][0]['courses'][0]['timeSlotEnd']='18:00'
        result=self.api.post(self.url,body,format='json')
        self.assertEqual(result.status_code,400,result.data);self.assertEqual(ReservationGroup.objects.count(),0)
