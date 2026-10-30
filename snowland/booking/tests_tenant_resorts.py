from django.db import IntegrityError, transaction
from django.test import TestCase
from Client.models import Client
from Coursekit.models import CourseCategory, CourseType, CourseTemplate
from Resorts.models import Resorts
from booking.tenant_scope import resort_for_course
from booking import tests_pricing_modes as fixtures


class TenantResortTests(TestCase):
    def setUp(self):
        fixtures.PricingModeApiTests.setUp(self)
        self.other=Client.objects.create(name='B',internal_code='school-b')
        self.second=Resorts.objects.create(client=self.other,name=self.resort.name,display_name='Other school resort')
        kind=CourseType.objects.create(category=CourseCategory.objects.create(client=self.other,name='B'),name='B')
        self.other_template=CourseTemplate.objects.create(course_type=kind,name='B',duration_hours=4,max_capacity=6)

    def test_same_resort_code_is_school_scoped_and_cannot_use_foreign_template(self):
        self.assertEqual(resort_for_course(self.resort.name,client=self.client_record).pk,self.resort.pk)
        self.assertEqual(resort_for_course(self.resort.name,template_id=self.other_template.pk).pk,self.second.pk)
        with self.assertRaises(Resorts.DoesNotExist):
            resort_for_course(self.resort.name)
        with self.assertRaises(Resorts.DoesNotExist):
            resort_for_course(self.resort.name,client=self.client_record,template_id=self.other_template.pk)
        with self.assertRaises(IntegrityError),transaction.atomic():
            Resorts.objects.create(client=self.other,name=self.resort.name)

    def test_price_lookup_remains_in_url_school_even_when_codes_match(self):
        response=self.api.get('/booking/snowland/api/calculate-price/',{'template_id':self.private_template.pk,'people_count':2,'date':'2026-01-15','resort':self.resort.name})
        self.assertEqual(response.status_code,200,response.data)
        self.assertGreater(response.data['course_fee'],0)
        forbidden=self.api.get('/booking/school-b/api/calculate-price/',{'template_id':self.private_template.pk,'people_count':2,'date':'2026-01-15','resort':self.resort.name})
        self.assertIn(forbidden.status_code,[400,404])
