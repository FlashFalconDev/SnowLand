from django.test import TestCase
from rest_framework.test import APIClient

from API.admin_serializers import CoursePricingAdminSerializer
from Client.models import Client
from Coursekit.models import (
    CourseCategory,
    CoursePricing,
    CoursePricingTier,
    CourseTemplate,
    CourseType,
    SeasonSetting,
)
from Resorts.models import Resorts


class PricingModeApiTests(TestCase):
    def setUp(self):
        self.client_record = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.resort = Resorts.objects.create(
            client=self.client_record,
            name='TestResort',
            display_name='測試雪場',
        )
        category = CourseCategory.objects.create(client=self.client_record, name='滑雪課程')
        course_type = CourseType.objects.create(category=category, name='測試課程')
        self.private_template = CourseTemplate.objects.create(
            course_type=course_type,
            name='私人包班',
            duration_hours=4,
            max_capacity=6,
            billing_mode='private',
        )
        self.per_person_template = CourseTemplate.objects.create(
            course_type=course_type,
            name='團體課程',
            duration_hours=4,
            max_capacity=6,
            billing_mode='per_person',
            minimum_group_size=2,
        )
        pricing = CoursePricing.objects.create(
            resort=self.resort,
            base_price_off_peak=10000,
            peak_season_surcharge=2000,
            additional_person_fee=1000,
            max_capacity=6,
            is_active=True,
        )
        pricing.templates.set([self.private_template, self.per_person_template])
        self.api = APIClient()

    def get_price(self, template, people_count):
        return self.api.get(
            '/booking/snowland/api/calculate-price/',
            {
                'template_id': template.id,
                'people_count': people_count,
                'date': '2026-01-15',
                'resort': self.resort.name,
            },
        )

    def test_private_and_per_person_templates_produce_different_totals(self):
        private_response = self.get_price(self.private_template, 3)
        per_person_response = self.get_price(self.per_person_template, 3)

        self.assertEqual(private_response.status_code, 200)
        self.assertEqual(per_person_response.status_code, 200)
        self.assertEqual(private_response.json()['course_fee'], 12000)
        self.assertEqual(per_person_response.json()['course_fee'], 30000)
        self.assertEqual(private_response.json()['billing_mode'], 'private')
        self.assertEqual(per_person_response.json()['billing_mode'], 'per_person')

    def test_per_person_template_rejects_group_below_minimum(self):
        response = self.get_price(self.per_person_template, 1)

        self.assertEqual(response.status_code, 400)
        self.assertIn('最低開班人數為 2 人', response.json()['error'])

    def test_peak_surcharge_uses_the_selected_billing_mode(self):
        SeasonSetting.objects.create(
            name='測試旺季',
            season_type='peak',
            start_date='2026-01-01',
            end_date='2026-01-31',
        )

        private_response = self.get_price(self.private_template, 3)
        per_person_response = self.get_price(self.per_person_template, 3)

        self.assertEqual(private_response.json()['course_fee'], 14000)
        self.assertEqual(per_person_response.json()['course_fee'], 36000)

    def test_people_tier_is_total_for_private_and_unit_price_for_per_person(self):
        pricing = CoursePricing.objects.get(resort=self.resort)
        CoursePricingTier.objects.create(
            pricing=pricing,
            min_people=3,
            max_people=3,
            price=9000,
        )

        private_response = self.get_price(self.private_template, 3)
        per_person_response = self.get_price(self.per_person_template, 3)

        self.assertEqual(private_response.json()['course_fee'], 9000)
        self.assertEqual(per_person_response.json()['course_fee'], 27000)

    def test_admin_cannot_share_one_price_between_different_billing_modes(self):
        serializer = CoursePricingAdminSerializer(data={
            'templates': [self.private_template.id, self.per_person_template.id],
            'resort': self.resort.id,
            'base_price_off_peak': 10000,
            'peak_season_surcharge': 0,
            'additional_person_fee': 1000,
            'max_capacity': 6,
            'people_tiers': [],
            'is_active': True,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('不能共用同一組價格', str(serializer.errors['templates']))
