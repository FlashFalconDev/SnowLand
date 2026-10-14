from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, CoachCourseLevel, CoachPayRule, CoachResort
from Coach.payroll import calculate_payroll_statement
from Coursekit.models import CourseCategory, CoursePricing, CourseSession, CourseTemplate, CourseType
from Resorts.models import Campus, Resorts
from booking.models import Payment, Reservation, SharedCourseClass


@override_settings(SHARED_CLASS_FEATURE_ENABLED=True)
class SharedCourseBookingTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.resort = Resorts.objects.create(
            client=self.tenant, name='tomamu', display_name='星野', auto_scheduling_enabled=False,
        )
        self.campus = Campus.objects.create(client=self.tenant, name='道東', code='east')
        self.campus.resorts.add(self.resort)
        category = CourseCategory.objects.create(client=self.tenant, name='滑雪')
        course_type = CourseType.objects.create(category=category, name='團體課')
        self.template = CourseTemplate.objects.create(
            course_type=course_type, name='團體半日', duration_hours=4,
            billing_mode='per_person', minimum_group_size=3,
            shared_class_enabled=True, shared_class_minimum_students=3, max_capacity=6,
        )
        self.template.resorts.add(self.resort)
        CourseSession.objects.create(template=self.template, start_time='09:00', end_time='13:00')
        pricing = CoursePricing.objects.create(
            resort=self.resort, base_price_off_peak=10000,
            peak_season_surcharge=0, additional_person_fee=0, max_capacity=6,
        )
        pricing.templates.add(self.template)
        self.date = (timezone.localdate() + timedelta(days=10)).isoformat()
        self.api = APIClient()

    def payload(self, *, campus=None, level='level1', people=1):
        return {
            'contact': {
                'name': '測試客人', 'email': 'member@example.test', 'phone': '0900000000',
                'messengerType': 'line', 'messengerId': 'test-id', 'referralSource': '其他',
            },
            'cart': [{
                'coach': 'any', 'peopleCount': people, 'abilityLevel': level,
                'abilityLevelCounts': {level: people}, 'equipment': False,
                'equipmentOption': 'own_equipment', 'language': 'zh',
                'resort': self.resort.name, 'resortName': self.resort.display_name,
                'campusId': (campus or self.campus).id,
                'courseCategory': '滑雪',
                'courses': [{
                    'date': self.date, 'courseTypeId': self.template.course_type_id,
                    'courseTypeName': self.template.course_type.name,
                    'courseTemplateId': self.template.id, 'courseTemplateName': self.template.name,
                    'durationHours': 4, 'timeSlotStart': '09:00', 'timeSlotEnd': '13:00',
                }],
            }],
        }

    def book(self, **kwargs):
        return self.api.post('/booking/snowland/api/create-reservation/', self.payload(**kwargs), format='json')

    @override_settings(SHARED_CLASS_FEATURE_ENABLED=False)
    def test_release_gate_hides_and_rejects_unfinished_shared_class(self):
        visible = self.api.get('/booking/snowland/api/course-templates/', {
            'resort': self.resort.name, 'course_type_id': self.template.course_type_id,
        })
        self.assertEqual(visible.status_code, 200, visible.data)
        self.assertFalse(any(row['id'] == self.template.id for row in visible.data))
        attempted = self.book()
        self.assertEqual(attempted.status_code, 400, attempted.data)
        self.assertIn('尚未開放', attempted.data['msg'])
        self.assertFalse(Reservation.objects.exists())

    def test_three_separate_orders_wait_then_open_each_payment(self):
        first = self.book()
        self.assertEqual(first.status_code, 200, first.data)
        self.assertFalse(first.data['requires_payment'])
        first_id = first.data['reservation_group_ids'][0]
        self.assertFalse(Payment.objects.exists())
        held = self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': first_id})
        self.assertEqual(held.status_code, 400, held.data)
        self.assertEqual(held.data['payment_status'], 'collecting_class')

        second = self.book()
        self.assertEqual(second.status_code, 200, second.data)
        self.assertFalse(second.data['requires_payment'])
        third = self.book()
        self.assertEqual(third.status_code, 200, third.data)
        self.assertTrue(third.data['requires_payment'])
        self.assertEqual(SharedCourseClass.objects.get().status, 'ready')
        self.assertEqual(Payment.objects.count(), 3)
        self.assertEqual(Reservation.objects.filter(shared_course_class__isnull=False).count(), 3)
        released = self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': first_id})
        self.assertEqual(released.status_code, 200, released.data)

    def test_different_levels_and_campuses_do_not_mix(self):
        other_campus = Campus.objects.create(client=self.tenant, name='道央', code='central')
        other_campus.resorts.add(self.resort)
        for kwargs in ({}, {'level': 'level2'}, {'campus': other_campus}):
            response = self.book(**kwargs)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertFalse(response.data['requires_payment'])
        self.assertEqual(SharedCourseClass.objects.count(), 3)
        self.assertFalse(Payment.objects.exists())

    def test_class_capacity_prevents_seventh_student_without_partial_order(self):
        first = self.book(people=3)
        second = self.book(people=3)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        full = self.book()
        self.assertEqual(full.status_code, 400, full.data)
        self.assertIn('名額已滿', full.data['msg'])
        self.assertEqual(Reservation.objects.count(), 2)

    def test_session_is_full_after_shared_class_reaches_student_capacity(self):
        self.assertEqual(self.book(people=3).status_code, 200)
        self.assertEqual(self.book(people=3).status_code, 200)
        response = self.api.get('/booking/snowland/api/course-sessions/', {
            'template_id': self.template.id, 'date': self.date,
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data[0]['is_full'])

    def test_ready_class_uses_one_coach_and_counts_one_lesson_for_payroll(self):
        self.resort.auto_scheduling_enabled = True
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        coach = Coach.objects.create(
            client=self.tenant, name='團體班教練', languages=['zh'], availability_status='active',
        )
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach, course_type=self.template.course_type,
            ability_levels=['level1'], price_level='Lv1',
        )
        CoachPayRule.objects.create(
            coach=coach, discipline='ski', hourly_rate=1000, referral_percent=0,
        )
        for index in range(3):
            response = self.book()
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['requires_payment'], index == 2)
        reservations = list(Reservation.objects.order_by('id'))
        self.assertEqual({reservation.preferred_coach_id for reservation in reservations}, {coach.id})
        self.assertEqual({reservation.status for reservation in reservations}, {'auto_assigned'})
        self.assertTrue(all(reservation.bookings.get().is_scheduled for reservation in reservations))

        Reservation.objects.update(status='completed')
        class_date = SharedCourseClass.objects.get().date
        statement = calculate_payroll_statement(
            coach=coach, campus=self.campus, period_start=class_date, period_end=class_date,
        )
        self.assertEqual(statement.course_pay, 4000)
        self.assertEqual(statement.lines.filter(line_type='course').count(), 1)
