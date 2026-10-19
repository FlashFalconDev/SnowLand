from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from API import tests_campus_scope as fixtures
from Coursekit.models import CourseCategory, CourseType, CourseTemplate, CoursePricing
from booking.models import ReservationGroup, Reservation, StaffBookingLink


class StaffLinkCurrentScopeTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)
        self.campus_b.resorts.add(self.resort_a)
        kind=CourseType.objects.create(category=CourseCategory.objects.create(client=self.tenant,name='QA共用雪場'),name='單板')
        self.template=CourseTemplate.objects.create(course_type=kind,name='QA預選課程',duration_hours=3,max_capacity=4)
        self.template.resorts.add(self.resort_a)
        self.api=APIClient();self.api.force_authenticate(self.superuser)
        self.snapshot=[{'campusId':self.campus_a.pk,'resort':self.resort_a.name,'peopleCount':1,'courses':[{'courseTemplateId':self.template.pk,'date':str(timezone.localdate()+timedelta(days=30))}]}]
        created=self.api.post('/api/admin/snowland/staff-booking-links/',{'campus':self.campus_a.pk,'title':'QA原選課連結','expires_at':(timezone.now()+timedelta(days=1)).isoformat(),'cart_snapshot':self.snapshot},format='json')
        self.assertEqual(created.status_code,201,created.data)
        self.link=StaffBookingLink.objects.get(pk=created.data['id'])
        self.url=f'/booking/snowland/api/staff-booking-link/{self.link.token}/'
        self.old=ReservationGroup.objects.create(client=self.tenant,campus=self.campus_a,name='原有訂單')
        Reservation.objects.create(group=self.old,resort=self.resort_a)

    def test_unlink_one_campus_invalidates_its_link_but_not_other_campus_or_history(self):
        self.assertEqual(APIClient().get(self.url).status_code,200)
        self.campus_a.resorts.remove(self.resort_a)
        self.assertEqual(APIClient().get(self.url).status_code,404)
        listed=self.api.get('/api/admin/snowland/staff-booking-links/').data['data']['list']
        self.assertFalse(next(row for row in listed if row['id']==self.link.pk)['is_available'])
        resort=next(row for row in APIClient().get('/booking/snowland/api/resorts/').data if row['name']==self.resort_a.name)
        self.assertEqual([row['id'] for row in resort['campuses']],[self.campus_b.pk])
        self.assertEqual(self.api.get(f'/api/admin/snowland/orders/{self.old.pk}/').status_code,200)
        self.campus_a.resorts.add(self.resort_a)
        self.assertEqual(APIClient().get(self.url).status_code,200)

    def test_withdrawn_or_detached_course_is_not_published_as_usable_link(self):
        self.template.is_active=False;self.template.save(update_fields=['is_active'])
        self.assertEqual(APIClient().get(self.url).status_code,404)
        self.template.is_active=True;self.template.save(update_fields=['is_active'])
        self.template.resorts.clear()
        self.assertEqual(APIClient().get(self.url).status_code,404)
        self.template.resorts.add(self.resort_a)
        self.assertEqual(APIClient().get(self.url).status_code,200)

    def test_stale_link_cannot_create_order_or_mark_link_used(self):
        self.campus_a.resorts.remove(self.resort_a)
        result=self.api.post('/booking/snowland/api/create-reservation/',{'staff_link':str(self.link.token),'cart':self.snapshot},format='json')
        self.assertEqual(result.status_code,400,result.data);self.assertIn('失效',result.data['msg'])
        self.assertEqual(ReservationGroup.objects.count(),1)
        self.link.refresh_from_db();self.assertIsNone(self.link.used_at)

    def test_legacy_empty_link_remains_valid_and_all_disabled_campuses_hide_shared_resort(self):
        legacy=StaffBookingLink.objects.create(client=self.tenant,campus=self.campus_a,created_by=self.superuser,expires_at=timezone.now()+timedelta(days=1))
        legacy_url=f'/booking/snowland/api/staff-booking-link/{legacy.token}/'
        self.assertEqual(APIClient().get(legacy_url).status_code,200)
        self.campus_a.is_active=False;self.campus_a.save(update_fields=['is_active'])
        self.campus_b.is_active=False;self.campus_b.save(update_fields=['is_active'])
        self.assertEqual(APIClient().get(legacy_url).status_code,404)
        self.assertEqual(APIClient().get(self.url).status_code,404)
        self.assertEqual(APIClient().get('/booking/snowland/api/resorts/').data,[])

    def test_legacy_price_only_binding_is_supported_without_expanding_explicit_binding(self):
        self.template.resorts.clear()
        price=CoursePricing.objects.create(resort=self.resort_a,base_price_off_peak=10000,peak_season_surcharge=0,additional_person_fee=0,max_capacity=4,is_active=True)
        price.templates.add(self.template)
        self.assertEqual(APIClient().get(self.url).status_code,200)
        price.is_active=False;price.save(update_fields=['is_active'])
        self.assertEqual(APIClient().get(self.url).status_code,404)
        price.is_active=True;price.save(update_fields=['is_active'])
        self.template.resorts.add(self.resort_b)
        self.assertEqual(APIClient().get(self.url).status_code,404)

    def test_malformed_legacy_snapshots_fail_closed_without_500(self):
        for snapshot in [1,{'bad':'shape'},[1],[{'resort':self.resort_a.name,'courses':[None]}],[{'resort':self.resort_a.name,'courses':[{'courseTemplateId':True}]}]]:
            self.link.cart_snapshot=snapshot;self.link.save(update_fields=['cart_snapshot'])
            self.assertEqual(APIClient().get(self.url).status_code,404)
