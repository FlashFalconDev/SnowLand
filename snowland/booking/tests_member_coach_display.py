from datetime import time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach
from Coursekit.models import CourseCategory, CourseType, CourseTemplate
from Resorts.models import Campus, Resorts
from booking.models import Booking, Reservation, ReservationGroup, SharedCourseClass


class MemberCoachDisplayTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.owner = User.objects.create_user('card-owner', 'card-owner@example.test')
        self.other = User.objects.create_user('card-other', 'card-other@example.test')
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.resort = Resorts.objects.create(client=self.tenant, name='card-resort', display_name='卡片雪場')
        self.campus = Campus.objects.create(client=self.tenant, name='卡片校區', code='card')
        self.campus.resorts.add(self.resort)
        category = CourseCategory.objects.create(client=self.tenant, name='單板')
        kind = CourseType.objects.create(category=category, name='單板')
        self.template = CourseTemplate.objects.create(course_type=kind, name='私人課程', duration_hours=2, max_capacity=4)
        self.coach = Coach.objects.create(client=self.tenant, name='QA實際教練')
        self.group = ReservationGroup.objects.create(client=self.tenant, user=self.owner, campus=self.campus, order_number='QA-CARD')
        self.reservation = Reservation.objects.create(group=self.group, resort=self.resort, course_type=kind,
            course_template=self.template, preferred_coach=self.coach, is_preferred_coach=False,
            status='manually_assigned', number_of_people=2, course_fee=6000)
        self.date = timezone.localdate() + timedelta(days=10)
        Booking.objects.create(reservation=self.reservation, date=self.date, start_time=time(9), end_time=time(11),
            course_name='QA單板', course_type='單板', is_scheduled=True)

    def row(self):
        response = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['orders'][0]['reservations'][0]

    def test_auto_and_manual_assignment_do_not_imply_customer_designation(self):
        for status in ['auto_assigned', 'manually_assigned', 'pending_coach_approval', 'completed']:
            self.reservation.status = status
            self.reservation.save(update_fields=['status'])
            row = self.row()
            self.assertIs(row['is_preferred_coach'], False)
            self.assertEqual(row['coach'], 'QA實際教練')  # Actual coach remains available in details.
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.course_fee, 6000)

    def test_customer_designation_and_removed_coach_are_explicit(self):
        self.reservation.is_preferred_coach = True
        self.reservation.save(update_fields=['is_preferred_coach'])
        self.assertIs(self.row()['is_preferred_coach'], True)
        self.reservation.preferred_coach = None
        self.reservation.save(update_fields=['preferred_coach'])
        row = self.row()
        self.assertIs(row['is_preferred_coach'], True)
        self.assertEqual(row['coach'], '安排中')

    def test_shared_class_never_claims_designation_and_other_member_has_no_order(self):
        shared = SharedCourseClass.objects.create(client=self.tenant, campus=self.campus, resort=self.resort,
            template=self.template, date=self.date, start_time=time(9), end_time=time(11), ability_level='level1')
        self.reservation.shared_course_class = shared
        self.reservation.is_preferred_coach = True  # Defensive handling of historical inconsistent flags.
        self.reservation.save(update_fields=['shared_course_class', 'is_preferred_coach'])
        row = self.row()
        self.assertIs(row['is_preferred_coach'], False)
        self.assertIs(row['is_shared_class'], True)
        self.api.force_authenticate(self.other)
        response = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['orders'], [])
