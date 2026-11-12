from datetime import time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, CoachCourseLevel, CoachResort
from Coursekit.models import CourseCategory, CourseType, CourseTemplate
from Resorts.models import Campus, Resorts
from booking.models import Booking, MemberDetail, Reservation, ReservationGroup, SharedCourseClass
from booking.scheduler import assign_coachs


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
        self.booking = Booking.objects.create(reservation=self.reservation, date=self.date, start_time=time(9), end_time=time(11),
            course_name='QA單板', course_type='單板', is_scheduled=True)

    def row(self):
        response = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['orders'][0]['reservations'][0]

    def test_auto_and_manual_assignment_do_not_imply_customer_designation(self):
        for status in ['auto_assigned', 'manually_assigned', 'pending_coach_confirmation', 'completed']:
            self.reservation.status = status
            self.reservation.save(update_fields=['status'])
            row = self.row()
            self.assertIs(row['is_preferred_coach'], False)
            self.assertEqual(row['coach'], '安排中')
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.course_fee, 6000)

    def test_reassignment_stays_private_until_the_first_scheduled_course_day(self):
        replacement = Coach.objects.create(client=self.tenant, name='QA重排教練', languages=['zh'])
        for coach in (self.coach, replacement):
            coach.languages = ['zh']
            coach.availability_status = 'active'
            coach.save(update_fields=['languages', 'availability_status'])
            coach.campuses.add(self.campus)
            CoachResort.objects.create(coach=coach, resort=self.resort)
            CoachCourseLevel.objects.create(coach=coach, course_type=self.reservation.course_type,
                ability_levels=['no_exp'], price_level='Lv1')
        self.reservation.preferred_coach = None
        self.reservation.status = 'created'
        self.reservation.max_ability_level = 'no_exp'
        self.reservation.save(update_fields=['preferred_coach', 'status', 'max_ability_level'])
        self.booking.is_scheduled = False
        self.booking.save(update_fields=['is_scheduled'])
        MemberDetail.objects.create(user=self.other, reservation=self.reservation)

        self.assertEqual(self.row()['coach'], '安排中')
        success, report = assign_coachs([self.reservation])
        self.assertTrue(success, report)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, self.coach.pk)
        self.assertEqual(self.row()['coach'], '安排中')

        self.coach.availability_status = 'unavailable'
        self.coach.save(update_fields=['availability_status'])
        success, report = assign_coachs([self.reservation])
        self.assertTrue(success, report)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, replacement.pk)
        self.assertEqual(self.row()['coach'], '安排中')
        self.api.force_authenticate(self.other)
        response = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['participant_courses'][0]['coach'], '安排中')

        self.booking.date = timezone.localdate()
        self.booking.save(update_fields=['date'])
        response = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['participant_courses'][0]['coach'], replacement.name)
        self.api.force_authenticate(self.owner)
        self.assertEqual(self.row()['coach'], replacement.name)

        self.reservation.status = 'pending_coach_confirmation'
        self.reservation.save(update_fields=['status'])
        self.assertEqual(self.row()['coach'], '安排中')
        self.reservation.status = 'manually_assigned'
        self.reservation.save(update_fields=['status'])
        self.booking.is_scheduled = False
        self.booking.save(update_fields=['is_scheduled'])
        self.assertEqual(self.row()['coach'], '安排中')

    def test_photographer_is_still_displayed_before_the_service_day(self):
        category = self.reservation.course_type.category
        category.service_type = 'photo'
        category.save(update_fields=['service_type'])
        self.assertEqual(self.row()['coach'], self.coach.name)

    def test_customer_designation_and_removed_coach_are_explicit(self):
        self.reservation.is_preferred_coach = True
        self.reservation.save(update_fields=['is_preferred_coach'])
        self.assertIs(self.row()['is_preferred_coach'], True)
        self.assertEqual(self.row()['coach'], self.coach.name)
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
        self.assertEqual(row['coach'], '安排中')
        self.api.force_authenticate(self.other)
        response = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['orders'], [])
