from booking.tests_policy_support import checkout_policy_acknowledgement
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from API.admin_serializers import CoursePricingAdminSerializer
from Client.models import Client
from Coach.models import Coach, CoachCourseLevel, CoachPayRule, CoachResort
from Coursekit.models import (
    CourseCategory,
    CoursePricing,
    CoursePricingTier,
    CourseSession,
    CourseTemplate,
    CourseType,
    SeasonSetting,
)
from Resorts.models import Campus, Resorts
from booking.models import Booking, Payment, Reservation, ReservationGroup, StaffBookingLink


class PricingModeApiTests(TestCase):
    def setUp(self):
        self.client_record = Client.objects.create(
            name='SnowLand', internal_code='snowland',
            bank_name='測試銀行', bank_branch='測試分行',
            bank_account_number='QA-0001', bank_account_holder='測試戶名',
        )
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
        self.api.force_authenticate(get_user_model().objects.create_user('pricing-member', 'pricing@example.test'))

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

    def test_staff_selected_course_cannot_be_changed_before_booking(self):
        member = get_user_model().objects.create_user(
            username='staff-link-member@example.test', email='staff-link-member@example.test',
            password='local-test-only',
        )
        self.api.force_authenticate(member)
        campus = Campus.objects.create(client=self.client_record, name='北海道校區', code='hokkaido')
        campus.resorts.add(self.resort)
        self.resort.auto_scheduling_enabled = False
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        booking_date = (date.today() + timedelta(days=35)).isoformat()
        price = self.api.get('/booking/snowland/api/calculate-price/', {
            'template_id': self.private_template.id, 'people_count': 2,
            'date': booking_date, 'resort': self.resort.name,
        })
        self.assertEqual(price.status_code, 200, price.data)
        course_fee = price.data['course_fee']
        course = {
            'date': booking_date, 'courseTypeId': self.private_template.course_type_id,
            'courseTypeName': self.private_template.course_type.name,
            'courseTemplateId': self.private_template.id,
            'courseTemplateName': self.private_template.name,
            'durationHours': 4, 'timeSlotStart': '09:00',
            'timeSlotEnd': '13:00', 'price': course_fee,
        }
        selected_cart = [{
            'coach': 'any', 'peopleCount': 2, 'abilityLevel': 'no_exp',
            'equipment': False, 'equipmentOption': 'own_equipment',
            'language': 'zh', 'resort': self.resort.name,
            'resortName': self.resort.display_name,
            'courseCategory': self.private_template.course_type.category.name,
            'courses': [course], 'totalPrice': course_fee,
        }]
        link = StaffBookingLink.objects.create(
            client=self.client_record, campus=campus, created_by=member,
            title='櫃台預選課程', cart_snapshot=selected_cart,
            expires_at=timezone.now() + timedelta(days=1),
        )
        request_body = {
            'staff_link': str(link.token), 'cart': selected_cart,
            **checkout_policy_acknowledgement(),
            'contact': {
                'name': 'QA 測試會員', 'email': member.email,
                'phone': '0900000000', 'messengerType': 'line',
                'messengerId': 'qa-test',
            },
        }
        guest = APIClient().post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(guest.status_code, 401, guest.data)
        self.assertFalse(ReservationGroup.objects.exists())

        changed_cart = [{**selected_cart[0], 'courses': [{**course, 'courseTemplateName': '擅自改課程'}]}]
        changed = self.api.post('/booking/snowland/api/create-reservation/', {
            **request_body, 'cart': changed_cart,
        }, format='json')
        self.assertEqual(changed.status_code, 400, changed.data)
        self.assertIn('代客訂課連結', changed.data['msg'])
        self.assertFalse(ReservationGroup.objects.exists())

        link.cart_snapshot = [{**selected_cart[0], 'internal_note': '舊連結內部欄位'}]
        link.save(update_fields=['cart_snapshot'])
        shared = APIClient().get(f'/booking/snowland/api/staff-booking-link/{link.token}/')
        self.assertEqual(shared.status_code, 200, shared.data)
        self.assertEqual(shared.data['cart_snapshot'], selected_cart)

        accepted = self.api.post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(ReservationGroup.objects.count(), 1)

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
            'is_active': True, 'is_full': False, 'shared_class': None,
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
            **checkout_policy_acknowledgement(),
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

    def test_new_member_order_is_visible_to_owner_and_admin_with_registered_name(self):
        self.api.force_authenticate(None)
        self.resort.auto_scheduling_enabled = False
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        registered = self.api.post('/booking/snowland/api/member-auth/', {
            'action': 'register', 'name': '王小雪',
            'email': 'new-member@example.test', 'password': 'local-test-only',
        }, format='json')
        self.assertEqual(registered.status_code, 201, registered.data)
        self.assertEqual(registered.data['member']['name'], '王小雪')
        member = get_user_model().objects.get(email='new-member@example.test')
        booking_date = (date.today() + timedelta(days=40)).isoformat()
        price = self.api.get('/booking/snowland/api/calculate-price/', {
            'template_id': self.private_template.id,
            'people_count': 1,
            'date': booking_date,
            'resort': self.resort.name,
        })
        self.assertEqual(price.status_code, 200, price.data)
        course_fee = price.data['course_fee']
        request_body = {
            **checkout_policy_acknowledgement(),
            'contact': {
                'name': '王小雪', 'email': member.email, 'phone': '0900000000',
                'messengerType': 'line', 'messengerId': 'qa-test', 'referralSource': '其他',
            },
            'cart': [{
                'coach': 'any', 'peopleCount': 1,
                'abilityLevel': 'no_exp', 'equipment': False,
                'equipmentOption': 'own_equipment', 'language': 'zh',
                'resort': self.resort.name, 'resortName': self.resort.display_name,
                'courseCategory': self.private_template.course_type.category.name,
                'courses': [{
                    'date': booking_date,
                    'courseTypeId': self.private_template.course_type_id,
                    'courseTypeName': self.private_template.course_type.name,
                    'courseTemplateId': self.private_template.id,
                    'courseTemplateName': self.private_template.name,
                    'durationHours': 4, 'timeSlotStart': '09:00', 'timeSlotEnd': '13:00',
                    'price': course_fee,
                }],
                'totalPrice': course_fee,
            }],
        }
        request_body['cart'][0]['totalPrice'] = 0
        rejected_price = self.api.post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(rejected_price.status_code, 400, rejected_price.data)
        self.assertFalse(ReservationGroup.objects.exists())
        request_body['cart'][0]['totalPrice'] = course_fee
        booking = self.api.post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(booking.status_code, 200, booking.data)
        self.assertTrue(booking.data['requires_payment'])
        group = ReservationGroup.objects.get(pk=booking.data['reservation_group_ids'][0])
        self.assertEqual(group.user, member)
        self.assertEqual(group.booking_contact['name'], '王小雪')
        self.assertEqual(group.reservations.get().total_fee, course_fee)

        member_center = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(member_center.status_code, 200, member_center.data)
        own_order = next(order for order in member_center.data['orders'] if order['id'] == group.id)
        self.assertEqual(own_order['total_amount'], course_fee)
        self.assertEqual(own_order['payment_status'], 'unpaid')
        other_member = get_user_model().objects.create_user('other-member@example.test', password='local-test-only')
        other_api = APIClient()
        other_api.force_authenticate(user=other_member)
        other_orders = other_api.get('/booking/snowland/api/member-center/')
        self.assertEqual(other_orders.status_code, 200, other_orders.data)
        self.assertNotIn(group.id, [order['id'] for order in other_orders.data['orders']])

        admin = get_user_model().objects.create_superuser('booking-admin', 'booking-admin@example.test', 'local-test-only')
        admin_api = APIClient()
        admin_api.force_authenticate(user=admin)
        admin_orders = admin_api.get('/api/admin/snowland/orders/?search=王小雪')
        self.assertEqual(admin_orders.status_code, 200, admin_orders.data)
        matching_order = next(order for order in admin_orders.data['data']['list'] if order['id'] == group.id)
        self.assertEqual(matching_order['user_name'], '王小雪')

        transfer = self.api.post('/booking/snowland/api/process-payment/', {
            'reservation_group_id': group.id,
            'payment_type': 'bank_transfer',
            'sender_account': '12345',
        }, format='json')
        self.assertEqual(transfer.status_code, 200, transfer.data)
        pending_order = next(
            order for order in self.api.get('/booking/snowland/api/member-center/').data['orders']
            if order['id'] == group.id
        )
        self.assertEqual(pending_order['payment_status'], 'pending')
        confirmed = admin_api.patch(
            f'/api/admin/snowland/orders/{group.id}/',
            {'payment_status': 'paid'}, format='json',
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        admin_orders_after_payment = admin_api.get('/api/admin/snowland/orders/?search=王小雪')
        confirmed_admin_order = next(
            order for order in admin_orders_after_payment.data['data']['list'] if order['id'] == group.id
        )
        self.assertEqual(confirmed_admin_order['payment_status'], 'paid')
        own_orders_after_payment = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(own_orders_after_payment.status_code, 200, own_orders_after_payment.data)
        paid_order = next(order for order in own_orders_after_payment.data['orders'] if order['id'] == group.id)
        self.assertEqual(paid_order['payment_status'], 'paid')
        other_orders_after_payment = other_api.get('/booking/snowland/api/member-center/')
        self.assertNotIn(group.id, [order['id'] for order in other_orders_after_payment.data['orders']])

    def test_member_order_reaches_coach_calendar_and_payroll_after_admin_completion(self):
        campus = Campus.objects.create(client=self.client_record, name='測試校區', code='test-campus')
        campus.resorts.add(self.resort)
        coach_user = get_user_model().objects.create_user('lifecycle-coach@example.test', password='local-test-only')
        coach_user.userprofile.is_coach = True
        coach_user.userprofile.save(update_fields=['is_coach'])
        coach = Coach.objects.create(client=self.client_record, user=coach_user, name='QA 教練', languages=['zh'])
        coach.campuses.add(campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(coach=coach, course_type=self.private_template.course_type,
                                       ability_levels=['level6'], price_level='Lv1')
        member = get_user_model().objects.create_user('lifecycle-member@example.test', password='local-test-only')
        self.api.force_authenticate(user=member)
        booking_date = date.today() + timedelta(days=1)
        price = self.api.get('/booking/snowland/api/calculate-price/', {
            'template_id': self.private_template.id, 'people_count': 1,
            'date': booking_date.isoformat(), 'resort': self.resort.name,
        })
        self.assertEqual(price.status_code, 200, price.data)
        course_fee = price.data['course_fee']
        self.resort.auto_scheduling_enabled = False
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        created = self.api.post('/booking/snowland/api/create-reservation/', {
            **checkout_policy_acknowledgement(),
            'contact': {
                'name': 'QA 會員', 'email': member.username, 'phone': '0900000000',
                'messengerType': 'line', 'messengerId': 'qa-test', 'referralSource': '其他',
            },
            'cart': [{
                'coach': 'any', 'peopleCount': 1, 'abilityLevel': 'no_exp',
                'equipment': False, 'equipmentOption': 'own_equipment', 'language': 'zh',
                'resort': self.resort.name, 'resortName': self.resort.display_name,
                'courseCategory': self.private_template.course_type.category.name,
                'courses': [{
                    'date': booking_date.isoformat(), 'courseTypeId': self.private_template.course_type_id,
                    'courseTypeName': self.private_template.course_type.name,
                    'courseTemplateId': self.private_template.id, 'courseTemplateName': self.private_template.name,
                    'durationHours': 4, 'timeSlotStart': '09:00', 'timeSlotEnd': '13:00',
                    'price': course_fee,
                }],
                'totalPrice': course_fee,
            }],
        }, format='json')
        self.assertEqual(created.status_code, 200, created.data)
        group = ReservationGroup.objects.get(pk=created.data['reservation_group_ids'][0])
        reservation = group.reservations.get()
        self.assertEqual(group.campus_id, campus.id)
        self.assertEqual(group.payments.get().status, 'unpaid')

        admin = APIClient()
        admin.force_authenticate(user=get_user_model().objects.create_superuser(
            'lifecycle-admin', 'lifecycle-admin@example.test', 'local-test-only',
        ))
        paid = admin.patch(f'/api/admin/snowland/orders/{group.id}/', {'payment_status': 'paid'}, format='json')
        self.assertEqual(paid.status_code, 200, paid.data)
        assigned = admin.put(f'/api/admin/snowland/orders/{group.id}/', {
            'action': 'save',
            'reservation_updates': [{'reservation_id': reservation.id, 'coach_id': coach.id}],
        }, format='json')
        self.assertEqual(assigned.status_code, 200, assigned.data)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'manually_assigned')

        coach_api = APIClient()
        coach_api.force_authenticate(user=coach_user)
        calendar = coach_api.get('/api/admin/snowland/coach/my-calendar/')
        self.assertEqual(calendar.status_code, 200, calendar.data)
        self.assertTrue(any(row['date'] == booking_date.isoformat() for row in calendar.data['data']['list']))

        # Move the isolated test lesson into the past to represent time passing.
        completed_date = date.today() - timedelta(days=1)
        reservation.bookings.update(date=completed_date)
        completed = admin.post(f'/api/admin/snowland/orders/{group.id}/complete-course/', {
            'reservation_id': reservation.id,
        }, format='json')
        self.assertEqual(completed.status_code, 200, completed.data)
        CoachPayRule.objects.create(coach=coach, discipline='ski', hourly_rate=1000, referral_percent=0)
        payroll = admin.post('/api/admin/snowland/payroll-statements/calculate/', {
            'coach': coach.id, 'campus': campus.id,
            'period_start': completed_date.isoformat(), 'period_end': completed_date.isoformat(),
        }, format='json')
        self.assertEqual(payroll.status_code, 200, payroll.data)
        self.assertEqual(payroll.data['data']['course_pay'], 4000)

    def test_booking_creates_order_and_payment_with_authoritative_price(self):
        member = get_user_model().objects.create_user(
            username='booking-member@example.test',
            email='booking-member@example.test',
            password='local-test-only',
        )
        self.api.force_authenticate(user=member)
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
        without_consent = self.api.post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(without_consent.status_code, 400, without_consent.data)
        self.assertIn('取消及更改政策', without_consent.data['msg'])
        self.assertFalse(ReservationGroup.objects.exists())
        request_body['accepted_policy'] = False
        declined_consent = self.api.post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(declined_consent.status_code, 400, declined_consent.data)
        self.assertFalse(ReservationGroup.objects.exists())
        request_body.update(checkout_policy_acknowledgement())
        response = self.api.post('/booking/snowland/api/create-reservation/', request_body, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data.get('requires_payment'), response.data)
        group = ReservationGroup.objects.get(pk=response.data['reservation_group_ids'][0])
        self.assertEqual(group.client, self.client_record)
        self.assertEqual(group.user, member)
        self.assertTrue(group.booking_contact['policy_accepted_at'])
        self.assertEqual(group.reservations.count(), 1)
        self.assertEqual(group.reservations.get().ability_level_counts, {'no_exp': 2})
        self.assertEqual(Booking.objects.filter(reservation__group=group).count(), 1)
        payment = Payment.objects.get(reservation_group=group)
        self.assertEqual(payment.status, 'unpaid')
        self.assertIsNotNone(payment.expires_at)
        member_center = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(member_center.status_code, 200, member_center.data)
        member_order = next(
            (order for order in member_center.data['orders'] if order['id'] == group.id), None
        )
        self.assertIsNotNone(member_order)
        self.assertEqual(member_order['order_number'], group.order_number)
        self.assertEqual(member_order['payment_status'], 'unpaid')
        self.assertEqual(member_order['total_amount'], course_fee)
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
        member_center = self.api.get('/booking/snowland/api/member-center/')
        member_order = next(order for order in member_center.data['orders'] if order['id'] == group.id)
        self.assertEqual(member_order['payment_status'], 'pending')
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
        cancel_failed = self.api.post('/booking/snowland/api/cancel-failed-reservations/', {
            'reservation_group_ids': [pending_group.id],
        }, format='json')
        self.assertEqual(cancel_failed.status_code, 200, cancel_failed.data)
        self.assertEqual(cancel_failed.data['deleted_count'], 1)
        self.assertFalse(ReservationGroup.objects.filter(pk=pending_group.id).exists())
        repeated_cancel = self.api.post('/booking/snowland/api/cancel-failed-reservations/', {
            'reservation_group_ids': [pending_group.id],
        }, format='json')
        self.assertEqual(repeated_cancel.status_code, 200, repeated_cancel.data)
        self.assertEqual(repeated_cancel.data['deleted_count'], 0)

        coach = Coach.objects.create(
            client=self.client_record, name='QA 教練',
            languages=['zh'], availability_status='active',
        )
        coach.campuses.add(*Campus.objects.filter(client=self.client_record))
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
        cancel_scheduled = self.api.post('/booking/snowland/api/cancel-failed-reservations/', {
            'reservation_group_ids': [scheduled_group.id],
        }, format='json')
        self.assertEqual(cancel_scheduled.status_code, 200, cancel_scheduled.data)
        self.assertEqual(cancel_scheduled.data['deleted_count'], 0)
        self.assertTrue(ReservationGroup.objects.filter(pk=scheduled_group.id).exists())

    def test_member_payment_details_and_submission_are_owner_only(self):
        owner = get_user_model().objects.create_user('payment-owner@example.test', password='local-test-only')
        other = get_user_model().objects.create_user('payment-other@example.test', password='local-test-only')
        group = ReservationGroup.objects.create(client=self.client_record, user=owner)
        Reservation.objects.create(
            group=group, resort=self.resort, course_template=self.private_template,
            number_of_people=1, course_fee=10000, total_fee=10000,
        )
        payment = Payment.objects.create(reservation_group=group, user=owner, status='unpaid')
        info_url = '/booking/snowland/api/payment-info/'
        submit_url = '/booking/snowland/api/process-payment/'
        submission = {
            'reservation_group_id': group.id,
            'payment_type': 'bank_transfer',
            'sender_account': '12345',
        }

        for user in (None, other):
            self.api.force_authenticate(user=user)
            self.assertEqual(self.api.get(info_url, {'reservation_group': group.id}).status_code, 404)
            self.assertEqual(self.api.post(submit_url, submission, format='json').status_code, 404)
            payment.refresh_from_db()
            self.assertEqual(payment.status, 'unpaid')
            self.assertFalse(payment.bank_account)

        self.api.force_authenticate(user=owner)
        self.assertEqual(self.api.get(info_url, {'reservation_group': group.id}).status_code, 200)
        self.assertEqual(self.api.post(submit_url, submission, format='json').status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.bank_account, '12345')

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
            **checkout_policy_acknowledgement(),
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
            **checkout_policy_acknowledgement(),
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

        coach.campuses.add(*Campus.objects.filter(client=self.client_record))
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

    def selectable_coach_fixture(self):
        self.resort.auto_scheduling_enabled = True
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        campus = Campus.objects.create(client=self.client_record, name='QA 校區', code='qa')
        campus.resorts.add(self.resort)
        coach = Coach.objects.create(client=self.client_record, name='QA 教練', languages=['zh'])
        coach.campuses.add(campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(coach=coach, course_type=self.private_template.course_type,
                                       ability_levels=['no_exp'], price_level='Lv1')
        self.private_template.resorts.add(self.resort)
        CourseSession.objects.create(template=self.private_template, start_time='09:00', end_time='13:00')
        payload = {**checkout_policy_acknowledgement(), 'contact': {
            'name': 'QA 會員', 'email': 'qa@example.test', 'phone': 'QA-PHONE',
            'messengerType': 'line', 'messengerId': 'qa', 'referralSource': '其他',
        }, 'cart': [{'coach': coach.id, 'peopleCount': 1, 'abilityLevel': 'no_exp',
                    'language': 'zh', 'equipmentOption': 'own_equipment', 'equipment': False,
                    'resort': self.resort.name, 'campusId': campus.id,
                    'courseCategory': self.private_template.course_type.category.name,
                    'courses': [{'date': '2026-11-20', 'courseTypeId': self.private_template.course_type_id,
                                 'courseTemplateId': self.private_template.id, 'durationHours': 4,
                                 'timeSlotStart': '09:00', 'timeSlotEnd': '13:00'}]}]}
        return coach, payload

    def test_customer_coach_visibility_is_independent_from_auto_assignment(self):
        coach, payload = self.selectable_coach_fixture()
        admin = APIClient()
        admin.force_authenticate(get_user_model().objects.create_superuser('visibility-admin', password='pw'))
        url = f'/api/admin/snowland/coaches/{coach.id}/'
        initial = admin.get(url)
        self.assertTrue(initial.data['customer_selectable'])
        response = admin.patch(url, {'customer_selectable': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        coach.refresh_from_db()
        self.assertFalse(coach.customer_selectable)
        self.assertTrue(coach.auto_assignment_enabled)
        listed = APIClient().get('/booking/snowland/api/coaches/', {
            'resort': self.resort.name, 'courseType': self.private_template.course_type_id,
        })
        self.assertEqual(listed.status_code, 200, listed.data)
        self.assertEqual(listed.data['coach_list'], [])
        payload['cart'][0]['coach'] = 'any'
        automatic = self.api.post('/booking/snowland/api/create-reservation/', payload, format='json')
        self.assertEqual(automatic.status_code, 200, automatic.data)
        group = ReservationGroup.objects.get(pk=automatic.data['reservation_group_ids'][0])
        self.assertEqual(group.reservations.get().preferred_coach_id, coach.id)
        self.assertFalse(group.reservations.get().is_preferred_coach)
        self.assertEqual(admin.patch(url, {'customer_selectable': True}, format='json').status_code, 200)
        visible = APIClient().get('/booking/snowland/api/coaches/', {
            'resort': self.resort.name, 'courseType': self.private_template.course_type_id,
        })
        self.assertEqual([row['pk'] for row in visible.data['coach_list']], [coach.id])

    def test_hidden_coach_cannot_be_requested_by_stale_cart_or_direct_price_request(self):
        coach, payload = self.selectable_coach_fixture()
        coach.customer_selectable = False
        coach.save(update_fields=['customer_selectable'])
        price = self.api.get('/booking/snowland/api/calculate-price/', {
            'template_id': self.private_template.id, 'people_count': 1,
            'date': '2026-11-20', 'resort': self.resort.name, 'coach': coach.id,
        })
        self.assertEqual(price.status_code, 400, price.data)
        for url in ['/booking/snowland/api/discount-preview/', '/booking/snowland/api/create-reservation/']:
            response = self.api.post(url, payload, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('不開放指定', str(response.data))
        self.assertFalse(ReservationGroup.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(Payment.objects.exists())
