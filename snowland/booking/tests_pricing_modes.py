from datetime import date, time, timedelta

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from API.admin_serializers import CoursePricingAdminSerializer
from Client.models import Client
from Coach.models import Coach, CoachCourseLevel, CoachResort
from Coursekit.models import (
    CourseCategory,
    CoursePricing,
    CoursePricingTier,
    CourseSession,
    CourseTemplate,
    CourseType,
    SeasonSetting,
)
from Resorts.models import Resorts
from booking.models import Booking, Payment, Reservation, ReservationGroup


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

    def test_other_template_bookings_do_not_fill_session(self):
        course_date = date.today() + timedelta(days=10)
        start_time, end_time = time(9), time(13)
        own_session = CourseSession.objects.create(
            template=self.private_template, start_time=start_time, end_time=end_time,
        )
        CourseSession.objects.create(
            template=self.per_person_template, start_time=start_time, end_time=end_time,
        )
        for _ in range(6):
            group = ReservationGroup.objects.create(client=self.client_record)
            reservation = Reservation.objects.create(
                group=group, resort=self.resort, course_template=self.per_person_template,
                number_of_people=2,
            )
            Booking.objects.create(
                reservation=reservation, date=course_date,
                start_time=start_time, end_time=end_time,
            )

        response = self.api.get('/booking/snowland/api/course-sessions/', {
            'template_id': self.private_template.id, 'date': course_date.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{
            'id': own_session.id,
            'template_id': self.private_template.id,
            'start_time': '09:00', 'end_time': '13:00',
            'is_active': True, 'is_full': False,
        }])

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
        self.assertIn('每筆預約至少 2 人', response.json()['error'])

    def test_mixed_courses_reject_students_below_either_template_minimum(self):
        self.resort.auto_scheduling_enabled = False
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        self.private_template.duration_hours = 6
        self.private_template.save(update_fields=['duration_hours'])
        advanced_template = CourseTemplate.objects.create(
            course_type=self.private_template.course_type,
            name='進階課程', duration_hours=4, max_capacity=6,
            minimum_student_level='level2',
        )
        CoursePricing.objects.get(resort=self.resort).templates.add(advanced_template)
        courses = []
        for template, date in ((self.private_template, '2026-11-20'), (advanced_template, '2026-11-21')):
            courses.append({
                'date': date, 'courseTypeId': template.course_type_id,
                'courseTypeName': template.course_type.name,
                'courseTemplateId': template.id, 'courseTemplateName': template.name,
                'durationHours': template.duration_hours,
                'timeSlotStart': '09:00', 'timeSlotEnd': '13:00',
            })
        payload = {
            'contact': {
                'name': 'QA 測試會員', 'email': 'qa@example.test',
                'phone': '0900000000', 'messengerType': 'line',
                'messengerId': 'qa-test', 'referralSource': '其他',
            },
            'cart': [{
                'coach': 'any', 'peopleCount': 2,
                'abilityLevel': 'level1',
                'abilityLevelCounts': {'level1': 1, 'level3': 1},
                'equipment': False, 'equipmentOption': 'own_equipment',
                'language': 'zh', 'resort': self.resort.name,
                'resortName': self.resort.display_name,
                'courseCategory': self.private_template.course_type.category.name,
                'courses': courses, 'totalPrice': 20000,
            }],
        }

        preview = self.api.post('/booking/snowland/api/discount-preview/', payload, format='json')
        self.assertEqual(preview.status_code, 400, preview.data)
        self.assertIn('進階課程', str(preview.data))
        booking = self.api.post('/booking/snowland/api/create-reservation/', payload, format='json')
        self.assertEqual(booking.status_code, 400, booking.data)
        self.assertFalse(ReservationGroup.objects.exists())

        item = payload['cart'][0]
        item['abilityLevel'] = 'level2'
        item['abilityLevelCounts'] = {'level2': 1, 'level3': 1}
        allowed_preview = self.api.post('/booking/snowland/api/discount-preview/', payload, format='json')
        self.assertEqual(allowed_preview.status_code, 200, allowed_preview.data)
        item['totalPrice'] = allowed_preview.data['total']
        allowed_booking = self.api.post('/booking/snowland/api/create-reservation/', payload, format='json')
        self.assertEqual(allowed_booking.status_code, 200, allowed_booking.data)
        self.assertEqual(ReservationGroup.objects.count(), 1)
        reservation = Reservation.objects.get(group__id=allowed_booking.data['reservation_group_ids'][0])
        self.assertEqual(reservation.ability_level_counts, {'level2': 1, 'level3': 1})
        self.assertEqual(reservation.max_ability_level, 'level3')

        item['peopleCount'] = 3
        invalid_preview = self.api.post('/booking/snowland/api/discount-preview/', payload, format='json')
        self.assertEqual(invalid_preview.status_code, 400, invalid_preview.data)
        self.assertIn('總和須等於預約人數', str(invalid_preview.data))
        invalid_booking = self.api.post('/booking/snowland/api/create-reservation/', payload, format='json')
        self.assertEqual(invalid_booking.status_code, 400, invalid_booking.data)
        self.assertIn('總和須等於預約人數', str(invalid_booking.data))
        self.assertEqual(ReservationGroup.objects.count(), 1)

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

    def test_booking_creates_order_and_payment_with_authoritative_price(self):
        self.resort.auto_scheduling_enabled = False
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        course_type = self.private_template.course_type
        booking_date = '2026-11-20'
        price = self.api.get('/booking/snowland/api/calculate-price/', {
            'template_id': self.private_template.id,
            'people_count': 2,
            'date': booking_date,
            'resort': self.resort.name,
        })
        self.assertEqual(price.status_code, 200)
        course_fee = price.json()['course_fee']
        request_body = {
            'contact': {
                'name': 'QA 測試會員', 'email': 'qa@example.test',
                'phone': '0900000000', 'messengerType': 'line',
                'messengerId': 'qa-test', 'referralSource': '其他',
            },
            'cart': [{
                'coach': 'any', 'peopleCount': 2,
                'abilityLevel': 'no_exp', 'equipment': False,
                'equipmentOption': 'own_equipment', 'language': 'zh',
                'resort': self.resort.name, 'resortName': self.resort.display_name,
                'courseCategory': course_type.category.name,
                'courses': [{
                    'date': booking_date, 'courseTypeId': course_type.id,
                    'courseTypeName': course_type.name,
                    'courseTemplateId': self.private_template.id,
                    'courseTemplateName': self.private_template.name,
                    'durationHours': 4, 'timeSlotStart': '09:00',
                    'timeSlotEnd': '13:00', 'price': course_fee,
                }],
                'totalPrice': course_fee,
            }],
        }
        response = self.api.post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data.get('requires_payment'), response.data)
        group = ReservationGroup.objects.get(pk=response.data['reservation_group_ids'][0])
        self.assertEqual(group.client, self.client_record)
        self.assertEqual(group.reservations.count(), 1)
        self.assertEqual(group.reservations.get().ability_level_counts, {'no_exp': 2})
        self.assertEqual(Booking.objects.filter(reservation__group=group).count(), 1)
        payment = Payment.objects.get(reservation_group=group)
        self.assertEqual(payment.status, 'unpaid')
        self.assertIsNotNone(payment.expires_at)
        payment_info = self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': group.id})
        self.assertEqual(payment_info.status_code, 200, payment_info.data)
        self.assertEqual(payment_info.data['total_amount'], course_fee)
        self.assertEqual(payment_info.data['payment_methods'], ['bank_transfer'])
        self.assertIn(self.private_template.name, payment_info.data['order_details'][0]['course_label'])
        group.source_country = 'JP'
        group.save(update_fields=['source_country'])
        with override_settings(NEWEBPAY_MERCHANT_ID='', NEWEBPAY_HASH_KEY='', NEWEBPAY_HASH_IV=''):
            overseas_info = self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': group.id})
            self.assertEqual(overseas_info.status_code, 200, overseas_info.data)
            self.assertEqual(overseas_info.data['payment_methods'], ['bank_transfer'])
            card_attempt = self.api.post('/booking/snowland/api/process-payment/', {
                'reservation_group_id': group.id,
                'payment_type': 'newebpay',
            }, format='json')
            self.assertEqual(card_attempt.status_code, 503, card_attempt.data)
            callback_attempt = self.api.post('/call_back/NewebPay/', {
                'MerchantID': 'test', 'TradeInfo': 'test', 'TradeSha': 'test',
            })
            self.assertEqual(callback_attempt.status_code, 503)
        with override_settings(NEWEBPAY_MERCHANT_ID='test', NEWEBPAY_HASH_KEY='test', NEWEBPAY_HASH_IV='test'):
            configured_info = self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': group.id})
            self.assertEqual(configured_info.status_code, 200, configured_info.data)
            self.assertEqual(configured_info.data['payment_methods'], ['bank_transfer', 'newebpay'])
        group.source_country = 'TW'
        group.save(update_fields=['source_country'])
        submitted_payment = self.api.post('/booking/snowland/api/process-payment/', {
            'reservation_group_id': group.id,
            'payment_type': 'bank_transfer',
            'sender_account': '12345',
        }, format='json')
        self.assertEqual(submitted_payment.status_code, 200, submitted_payment.data)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.bank_account, '12345')
        payment.status = 'paid'
        payment.save(update_fields=['status'])
        repeated_payment = self.api.post('/booking/snowland/api/process-payment/', {
            'reservation_group_id': group.id,
            'payment_type': 'bank_transfer',
            'sender_account': '12345',
        }, format='json')
        self.assertEqual(repeated_payment.status_code, 400, repeated_payment.data)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        payment.status = 'expired'
        payment.save(update_fields=['status'])
        expired_info = self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': group.id})
        self.assertEqual(expired_info.status_code, 400, expired_info.data)
        expired_payment = self.api.post('/booking/snowland/api/process-payment/', {
            'reservation_group_id': group.id,
            'payment_type': 'bank_transfer',
            'sender_account': '12345',
        }, format='json')
        self.assertEqual(expired_payment.status_code, 400, expired_payment.data)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'expired')

        self.resort.auto_scheduling_enabled = True
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        unscheduled = self.api.post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(unscheduled.status_code, 200, unscheduled.data)
        self.assertTrue(unscheduled.data['scheduling_failed'])
        self.assertFalse(unscheduled.data['requires_payment'])
        pending_group = ReservationGroup.objects.get(pk=unscheduled.data['reservation_group_ids'][0])
        self.assertFalse(Payment.objects.filter(reservation_group=pending_group).exists())
        self.assertEqual(pending_group.reservations.get().status, 'auto_assignment_failed')

        coach = Coach.objects.create(
            client=self.client_record, name='QA 教練',
            languages=['zh'], availability_status='active',
        )
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach, course_type=course_type,
            ability_levels=['no_exp', 'level1'], price_level='Lv1',
        )
        scheduled = self.api.post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(scheduled.status_code, 200, scheduled.data)
        self.assertFalse(scheduled.data['scheduling_failed'])
        self.assertTrue(scheduled.data['requires_payment'])
        scheduled_group = ReservationGroup.objects.get(pk=scheduled.data['reservation_group_ids'][0])
        reservation = scheduled_group.reservations.get()
        self.assertEqual(reservation.preferred_coach, coach)
        self.assertEqual(reservation.status, 'auto_assigned')
        self.assertTrue(reservation.bookings.get().is_scheduled)
        self.assertTrue(Payment.objects.filter(reservation_group=scheduled_group, status='unpaid').exists())

    def test_advanced_schedule_preserves_each_student_level_on_split_days(self):
        self.resort.auto_scheduling_enabled = False
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        course_type = self.private_template.course_type
        courses = [{
            'date': date, 'courseTypeId': course_type.id,
            'courseTypeName': course_type.name,
            'courseTemplateId': self.private_template.id,
            'courseTemplateName': self.private_template.name,
            'durationHours': 4, 'timeSlotStart': '09:00',
            'timeSlotEnd': '13:00',
        } for date in ('2026-11-20', '2026-11-21')]
        payload = {
            'contact': {
                'name': 'QA 測試會員', 'email': 'qa@example.test',
                'phone': '0900000000', 'messengerType': 'line',
                'messengerId': 'qa-test', 'referralSource': '其他',
            },
            'cart': [{
                'coach': 'any', 'peopleCount': 2,
                'abilityLevel': 'level3',
                'abilityLevelCounts': {'level1': 1, 'level3': 1},
                'equipment': False, 'equipmentOption': 'own_equipment',
                'language': 'zh', 'resort': self.resort.name,
                'resortName': self.resort.display_name,
                'courseCategory': course_type.category.name,
                'courses': courses,
            }],
        }
        response = self.api.post('/booking/snowland/api/super-schedule/', payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        group = ReservationGroup.objects.get(pk=response.data['reservation_group_id'])
        self.assertEqual(group.reservations.count(), 2)
        self.assertEqual(Booking.objects.filter(reservation__group=group).count(), 2)
        for reservation in group.reservations.all():
            self.assertEqual(reservation.ability_level_counts, {'level1': 1, 'level3': 1})
            self.assertEqual(reservation.max_ability_level, 'level3')

        payload['cart'][0]['abilityLevelCounts'] = {'level1': 1}
        rejected = self.api.post('/booking/snowland/api/super-schedule/', payload, format='json')
        self.assertEqual(rejected.status_code, 400, rejected.data)
        self.assertIn('總和須等於預約人數', str(rejected.data))
        self.assertEqual(ReservationGroup.objects.count(), 1)

    def test_coach_can_be_selected_but_excluded_from_automatic_assignment(self):
        self.resort.auto_scheduling_enabled = True
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        course_type = self.private_template.course_type
        coach = Coach.objects.create(
            client=self.client_record, name='Cash', languages=['zh'],
            availability_status='active', auto_assignment_enabled=False,
        )
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach, course_type=course_type,
            ability_levels=['no_exp'], price_level='Lv1',
        )
        price = self.api.get('/booking/snowland/api/calculate-price/', {
            'template_id': self.private_template.id,
            'people_count': 1,
            'date': '2026-11-20',
            'resort': self.resort.name,
        }).json()['course_fee']
        item = {
            'coach': 'any', 'peopleCount': 1,
            'abilityLevel': 'no_exp', 'equipment': False,
            'equipmentOption': 'own_equipment', 'language': 'zh',
            'resort': self.resort.name, 'resortName': self.resort.display_name,
            'courseCategory': course_type.category.name,
            'courses': [{
                'date': '2026-11-20', 'courseTypeId': course_type.id,
                'courseTypeName': course_type.name,
                'courseTemplateId': self.private_template.id,
                'courseTemplateName': self.private_template.name,
                'durationHours': 4, 'timeSlotStart': '09:00',
                'timeSlotEnd': '13:00', 'price': price,
            }],
            'totalPrice': price,
        }
        payload = {
            'contact': {
                'name': 'QA 測試會員', 'email': 'qa@example.test',
                'phone': '0900000000', 'messengerType': 'line',
                'messengerId': 'qa-test', 'referralSource': '其他',
            },
            'cart': [item],
        }

        automatic = self.api.post('/booking/snowland/api/create-reservation/', payload, format='json')
        self.assertEqual(automatic.status_code, 200, automatic.data)
        self.assertTrue(automatic.data['scheduling_failed'])
        self.assertFalse(automatic.data['requires_payment'])

        item['coach'] = coach.id
        preview = self.api.post('/booking/snowland/api/discount-preview/', payload, format='json')
        self.assertEqual(preview.status_code, 200, preview.data)
        item['totalPrice'] = preview.data['item_subtotals'][0]
        requested = self.api.post('/booking/snowland/api/create-reservation/', payload, format='json')
        self.assertEqual(requested.status_code, 200, requested.data)
        self.assertFalse(requested.data['scheduling_failed'])
        self.assertTrue(requested.data['requires_payment'])
        selected_group = ReservationGroup.objects.get(pk=requested.data['reservation_group_ids'][0])
        self.assertEqual(selected_group.reservations.get().preferred_coach_id, coach.id)
