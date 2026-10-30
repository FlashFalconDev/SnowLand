from copy import deepcopy
from datetime import date, timedelta
from django.test import TestCase
from Client.models import Client
from Coach.models import Coach
from Resorts.models import Campus
from booking import tests_pricing_modes as fixtures
from booking.api_views import CreateReservationAPI, compute_cart_item_pricing_authoritative
from booking.models import ReservationGroup, Reservation, Payment
from booking.scheduler import coach_matches_course_template
from booking.tests_policy_support import checkout_policy_acknowledgement

class TenantCoachSelectionTests(TestCase):
    def setUp(self):
        fixtures.PricingModeApiTests.setUp(self)
        self.other=Client.objects.create(name='Other school',internal_code='school-b')
        self.own=Coach.objects.create(client=self.client_record,name='Own coach')
        self.foreign=Coach.objects.create(client=self.other,name='Foreign private coach')
        campus=Campus.objects.create(client=self.client_record,name='QA',code='qa');campus.resorts.add(self.resort)
        self.resort.auto_scheduling_enabled=False;self.resort.save(update_fields=['auto_scheduling_enabled'])
        kind=self.private_template.course_type
        self.item={'coach':self.own.pk,'peopleCount':1,'abilityLevel':'no_exp','equipment':False,'equipmentOption':'own_equipment','language':'zh','resort':self.resort.name,'courseCategory':kind.category.name,'courses':[{'date':(date.today()+timedelta(days=35)).isoformat(),'courseTypeId':kind.pk,'courseTypeName':kind.name,'courseTemplateId':self.private_template.pk,'courseTemplateName':self.private_template.name,'durationHours':4,'timeSlotStart':'09:00','timeSlotEnd':'13:00'}]}

    def test_price_rejects_foreign_missing_and_unowned_coaches(self):
        unowned=Coach.objects.create(name='Unassigned legacy coach')
        params={'template_id':self.private_template.pk,'resort':self.resort.name,'people_count':1,'date':self.item['courses'][0]['date']}
        for coach_id in [self.foreign.pk,unowned.pk,999999]:
            response=self.api.get('/booking/snowland/api/calculate-price/',{**params,'coach_id':coach_id})
            self.assertEqual(response.status_code,400,response.data);self.assertNotIn(self.foreign.name,str(response.data))
        valid=self.api.get('/booking/snowland/api/calculate-price/',{**params,'coach_id':self.own.pk})
        self.assertEqual(valid.status_code,200,valid.data)

    def test_cart_price_rejects_foreign_coach(self):
        item=deepcopy(self.item);item['coach']=self.foreign.pk
        with self.assertRaisesRegex(ValueError,'此學校'):compute_cart_item_pricing_authoritative(item)
        self.assertGreater(compute_cart_item_pricing_authoritative(self.item)['course_fee'],0)

    def test_reservation_rejects_foreign_coach_before_writing(self):
        group=ReservationGroup.objects.create(client=self.client_record)
        item=deepcopy(self.item);item['coach']=self.foreign.pk
        with self.assertRaisesRegex(ValueError,'此學校'):CreateReservationAPI()._create_reservation(group,item)
        self.assertFalse(Reservation.objects.exists())
        own=CreateReservationAPI()._create_reservation(group,self.item)
        self.assertEqual(own.preferred_coach_id,self.own.pk)

    def test_full_submit_rejects_foreign_coach_without_order_or_payment(self):
        item=deepcopy(self.item);item['coach']=self.foreign.pk
        response=self.api.post('/booking/snowland/api/create-reservation/',{**checkout_policy_acknowledgement(),'cart':[item],'contact':{'name':'QA','email':'pricing@example.test','phone':'0900000000','messengerType':'line','messengerId':'local-qa','referralSource':'其他'}},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.assertFalse(ReservationGroup.objects.exists());self.assertFalse(Reservation.objects.exists());self.assertFalse(Payment.objects.exists())

    def test_template_guard_checks_school_before_optional_restrictions(self):
        self.assertTrue(coach_matches_course_template(self.own,self.private_template))
        self.assertFalse(coach_matches_course_template(self.foreign,self.private_template))
        self.assertFalse(coach_matches_course_template(self.foreign,self.private_template,allowed_coach_ids={self.foreign.pk}))
