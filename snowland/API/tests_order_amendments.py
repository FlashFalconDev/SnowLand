from datetime import time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_campus_scope as fixtures
from Coach.models import Coach, CoachResort
from Coursekit.models import CourseCategory, CoursePricing, CourseTemplate, CourseType, SeasonSetting
from Resorts.models import EquipmentAssistanceTimeSlot, EquipmentPricingTier, ResortFee
from booking.models import Booking, CancellationRequest, MemberDetail, NotificationDelivery, OrderRevision, Payment, Reservation, ReservationGroup, SharedCourseClass


class OrderAmendmentQuoteTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)
        kind=CourseType.objects.create(category=CourseCategory.objects.create(client=self.tenant,name='單板'),name='私人課')
        self.template=CourseTemplate.objects.create(course_type=kind,name='半天',duration_hours=3,max_capacity=4)
        self.template.resorts.add(self.resort_a)
        self.pricing=CoursePricing.objects.create(resort=self.resort_a,base_price_off_peak=10000,peak_season_surcharge=3000,additional_person_fee=2000,max_capacity=4)
        self.pricing.templates.add(self.template)
        self.group=ReservationGroup.objects.create(client=self.tenant,campus=self.campus_a,user=self.manager)
        self.reservation=Reservation.objects.create(group=self.group,resort=self.resort_a,course_type=kind,course_template=self.template,number_of_people=1,course_fee=10000,discount_amount=500)
        self.day=timezone.localdate()+timedelta(days=20)
        self.booking=Booking.objects.create(reservation=self.reservation,date=self.day,start_time=time(9),end_time=time(12))
        self.member=MemberDetail.objects.create(reservation=self.reservation,insurance_data={'full_name':'QA原學員'})
        self.url=f'/api/admin/snowland/orders/{self.group.pk}/amendment-quote/'
        self.api=APIClient();self.api.force_authenticate(self.superuser)

    def draft(self, **changes):
        return {'changes':[{'reservation_id':self.reservation.pk,'number_of_people':2,'language':'zh','equipment':'ownWithoutAssistance',
            'is_preferred_coach':False,'preferred_coach_id':None,'courses':[{'booking_id':self.booking.pk,'template_id':self.template.pk,
            'date':str(self.day),'start_time':'09:00','end_time':'12:00'}],**changes}]}

    def test_people_quote_uses_backend_prices_preserves_discount_and_never_changes_order(self):
        before=(Payment.objects.count(),OrderRevision.objects.count(),NotificationDelivery.objects.count())
        response=self.api.post(self.url,self.draft(),format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        data=response.data['data']
        self.assertEqual((data['previous_total'],data['new_total'],data['difference_amount']),(9500,11500,2000))
        self.assertEqual(data['items'][0]['course_fee'],12000)
        self.assertTrue(data['quote_token'])
        self.reservation.refresh_from_db();self.member.refresh_from_db()
        self.assertEqual(self.reservation.number_of_people,1);self.assertEqual(self.reservation.payment_amount,9500)
        self.assertEqual(self.member.insurance_data,{'full_name':'QA原學員'})
        self.assertEqual(before,(Payment.objects.count(),OrderRevision.objects.count(),NotificationDelivery.objects.count()))

    def test_only_shift_start_time_has_no_difference_even_after_catalog_price_changes(self):
        self.pricing.base_price_off_peak=99000;self.pricing.save()
        data=self.draft(number_of_people=1,equipment=None)
        data['changes'][0]['courses'][0].update(start_time='10:00',end_time='13:00')
        response=self.api.post(self.url,data,format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        self.assertEqual(response.data['data']['difference_amount'],0)
        self.assertEqual(response.data['data']['new_total'],9500)

    def test_date_change_reprices_peak_and_full_day_uses_its_own_configured_price(self):
        peak=self.day+timedelta(days=1)
        SeasonSetting.objects.create(name='QA旺季',season_type='peak',start_date=peak,end_date=peak)
        data=self.draft(number_of_people=1)
        data['changes'][0]['courses'][0]['date']=str(peak)
        response=self.api.post(self.url,data,format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        self.assertEqual(response.data['data']['difference_amount'],3000)
        full=CourseTemplate.objects.create(course_type=self.template.course_type,name='全天',duration_hours=6,max_capacity=4)
        full.resorts.add(self.resort_a)
        price=CoursePricing.objects.create(resort=self.resort_a,base_price_off_peak=18000,peak_season_surcharge=0,additional_person_fee=1000,max_capacity=4)
        price.templates.add(full)
        data['changes'][0]['courses'][0].update(template_id=full.pk,date=str(self.day),end_time='15:00')
        response=self.api.post(self.url,data,format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        self.assertEqual(response.data['data']['difference_amount'],8000)

    def test_invalid_fields_counts_times_and_unpriced_extra_hours_are_rejected(self):
        for update in ({'number_of_people':0},{'number_of_people':True},{'number_of_people':1.2},{'number_of_people':5},
                       {'language':'bad'},{'equipment':'bad'},{'course_fee':1},{'discount_amount':-1}):
            with self.subTest(update=update):
                self.assertEqual(self.api.post(self.url,self.draft(**update),format='json').status_code,400)
        for change in ({'end_time':'08:00'},{'end_time':'13:00'},{'date':'bad'}):
            data=self.draft();data['changes'][0]['courses'][0].update(change)
            self.assertEqual(self.api.post(self.url,data,format='json').status_code,400)

    def test_other_order_booking_template_and_duplicate_changes_are_rejected(self):
        other=Reservation.objects.create(group=ReservationGroup.objects.create(client=self.other_tenant))
        booking=Booking.objects.create(reservation=other,date=self.day,start_time='09:00',end_time='12:00')
        data=self.draft();data['changes'][0]['courses'][0]['booking_id']=booking.pk
        self.assertEqual(self.api.post(self.url,data,format='json').status_code,400)
        self.template.course_type.category.client=self.other_tenant;self.template.course_type.category.save()
        self.assertEqual(self.api.post(self.url,self.draft(),format='json').status_code,400)

    def test_duplicate_changes_and_terminal_courses_are_not_silently_repriced(self):
        data=self.draft();data['changes']*=2
        self.assertEqual(self.api.post(self.url,data,format='json').status_code,400)
        for state in ['completed','cancelled','deleted']:
            self.reservation.status=state;self.reservation.save()
            self.assertEqual(self.api.post(self.url,self.draft(),format='json').status_code,409)

    def test_shared_class_and_cancellation_in_progress_require_their_own_workflow(self):
        shared=SharedCourseClass.objects.create(client=self.tenant,campus=self.campus_a,resort=self.resort_a,template=self.template,
            date=self.day,start_time='09:00',end_time='12:00',ability_level='no_exp')
        self.reservation.shared_course_class=shared;self.reservation.save()
        self.assertEqual(self.api.post(self.url,self.draft(),format='json').status_code,409)
        self.reservation.shared_course_class=None;self.reservation.save()
        CancellationRequest.objects.create(group=self.group,reason='schedule')
        self.assertEqual(self.api.post(self.url,self.draft(),format='json').status_code,409)

    def test_designated_language_coach_uses_configured_fee_not_an_invented_language_surcharge(self):
        coach=Coach.objects.create(client=self.tenant,name='英文教練',languages=['zh','en'])
        coach.campuses.add(self.campus_a);CoachResort.objects.create(coach=coach,resort=self.resort_a)
        draft=self.draft(number_of_people=1,language='en',equipment=None,is_preferred_coach=True,preferred_coach_id=coach.pk)
        self.assertEqual(self.api.post(self.url,draft,format='json').status_code,400)
        ResortFee.objects.create(resort=self.resort_a,fee_type='coach_general',price=700)
        response=self.api.post(self.url,draft,format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        self.assertEqual(response.data['data']['difference_amount'],700)
        self.assertEqual(response.data['data']['items'][0]['language_fee'],0)
        coach.customer_selectable=False;coach.save()
        self.assertEqual(self.api.post(self.url,draft,format='json').status_code,400)

    def test_equipment_requires_configured_people_fee_and_matching_slot(self):
        draft=self.draft(number_of_people=1,equipment='purchaseAssistanceTime')
        self.assertEqual(self.api.post(self.url,draft,format='json').status_code,400)
        EquipmentPricingTier.objects.create(resort=self.resort_a,min_people=1,max_people=2,price=350)
        self.assertEqual(self.api.post(self.url,draft,format='json').status_code,400)
        slot=EquipmentAssistanceTimeSlot.objects.create(resort=self.resort_a,label='QA協助',lesson_duration='half_day')
        draft['changes'][0]['equipment_assistance_time_slot_id']=slot.pk
        response=self.api.post(self.url,draft,format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        self.assertEqual(response.data['data']['difference_amount'],350)
        slot.lesson_duration='full_day';slot.save()
        self.assertEqual(self.api.post(self.url,draft,format='json').status_code,400)

    def test_hiding_a_coach_from_new_customers_does_not_break_existing_specified_order_quote(self):
        coach=Coach.objects.create(client=self.tenant,name='既有指定教練',customer_selectable=False)
        coach.campuses.add(self.campus_a);CoachResort.objects.create(coach=coach,resort=self.resort_a)
        self.reservation.is_preferred_coach=True;self.reservation.preferred_coach=coach;self.reservation.coach_fee=700;self.reservation.save()
        data=self.draft(number_of_people=1,equipment=None,is_preferred_coach=True,preferred_coach_id=coach.pk)
        data['changes'][0]['courses'][0].update(start_time='10:00',end_time='13:00')
        response=self.api.post(self.url,data,format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        self.assertEqual(response.data['data']['difference_amount'],0)
        self.assertEqual(response.data['data']['items'][0]['coach_fee'],700)

    def test_manual_discount_and_per_person_billing_return_a_negative_difference_without_refunding(self):
        self.template.billing_mode='per_person';self.template.save()
        response=self.api.post(self.url,self.draft(discount_amount=3000),format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        self.assertEqual(response.data['data']['new_total'],17000)
        self.assertTrue(response.data['data']['items'][0]['discount_changed'])
        self.pricing.base_price_off_peak=3000;self.pricing.save()
        response=self.api.post(self.url,self.draft(),format='json')
        self.assertEqual(response.data['data']['difference_amount'],-4000)
        self.assertEqual(Payment.objects.count(),0)

    def test_each_booking_keeps_its_own_template_for_mixed_half_and_full_day_time_changes(self):
        full=CourseTemplate.objects.create(course_type=self.template.course_type,name='全天',duration_hours=6,max_capacity=4)
        full.resorts.add(self.resort_a)
        self.booking.course_template=self.template;self.booking.save()
        second=Booking.objects.create(reservation=self.reservation,course_template=full,date=self.day+timedelta(days=1),start_time='09:00',end_time='15:00')
        self.reservation.course_template=full;self.reservation.course_fee=28000;self.reservation.save()
        self.pricing.base_price_off_peak=99000;self.pricing.save()
        data=self.draft(number_of_people=1,equipment=None)
        data['changes'][0]['courses'][0].update(start_time='10:00',end_time='13:00')
        data['changes'][0]['courses'].append({'booking_id':second.pk,'template_id':full.pk,'date':str(second.date),'start_time':'10:00','end_time':'16:00'})
        response=self.api.post(self.url,data,format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        self.assertEqual(response.data['data']['new_total'],27500)
        self.assertEqual(response.data['data']['difference_amount'],0)

    def test_booking_creation_records_validated_template_and_old_records_remain_unknown(self):
        from booking.api_views import CreateReservationAPI, SuperScheduleAPI
        from API.admin_serializers import BookingAdminSerializer
        self.assertIsNone(self.booking.course_template_id)
        course={'courseTemplateId':self.template.pk,'courseTypeId':self.template.course_type_id,'date':str(self.day),
            'timeSlotStart':'09:00','timeSlotEnd':'12:00','courseTemplateName':self.template.name,'courseTypeName':'單板'}
        created=CreateReservationAPI()._create_booking(self.reservation,course)
        self.assertEqual(created.course_template_id,self.template.pk)
        other=SuperScheduleAPI()._create_single_day_reservation(self.group,{'resort':self.resort_a.name,'peopleCount':1,'equipmentOption':'own_equipment'},course)
        self.assertEqual(other.bookings.get().course_template_id,self.template.pk)
        serializer=BookingAdminSerializer(created,data={'course_template':None},partial=True)
        self.assertTrue(serializer.is_valid(),serializer.errors)
        self.assertNotIn('course_template',serializer.validated_data)

    def test_scope_summary_roles_and_csrf(self):
        self.assertEqual(self.api.post(self.url,self.draft(),format='json',HTTP_X_CAMPUS_ID=str(self.campus_b.pk)).status_code,404)
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.api.post(self.url,self.draft(),format='json').status_code,403)
        api=APIClient(enforce_csrf_checks=True);api.force_login(self.superuser)
        self.assertEqual(api.post(self.url,self.draft(),format='json').status_code,403)
