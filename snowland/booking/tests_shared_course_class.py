from datetime import date, time

from django.db import IntegrityError, transaction
from django.test import TestCase

from Client.models import Client
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from Resorts.models import Campus, Resorts
from booking.models import Reservation, ReservationGroup, SharedCourseClass


class SharedCourseClassModelTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.campus = Campus.objects.create(client=self.tenant, name='道東', code='east')
        self.resort = Resorts.objects.create(client=self.tenant, name='tomamu', display_name='星野')
        self.campus.resorts.add(self.resort)
        category = CourseCategory.objects.create(client=self.tenant, name='滑雪')
        course_type = CourseType.objects.create(category=category, name='團體課')
        self.template = CourseTemplate.objects.create(
            course_type=course_type, name='團體半日', duration_hours=4,
            billing_mode='per_person', shared_class_enabled=True,
        )
        self.slot = dict(
            client=self.tenant, campus=self.campus, resort=self.resort,
            template=self.template, date=date(2027, 1, 8),
            start_time=time(9), end_time=time(13), ability_level='level1',
        )

    def test_three_people_across_orders_make_one_class_ready(self):
        shared_class = SharedCourseClass.objects.create(**self.slot)
        for index in range(2):
            group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus)
            Reservation.objects.create(
                group=group, resort=self.resort, course_template=self.template,
                shared_course_class=shared_class, number_of_people=1,
            )
            self.assertEqual(shared_class.refresh_readiness(), 'collecting')
            self.assertEqual(shared_class.registered_students, index + 1)
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus)
        Reservation.objects.create(
            group=group, resort=self.resort, course_template=self.template,
            shared_course_class=shared_class, number_of_people=1,
        )
        self.assertEqual(shared_class.refresh_readiness(), 'ready')
        self.assertEqual(shared_class.registered_students, 3)

    def test_cancelled_order_does_not_count_and_same_slot_is_unique(self):
        shared_class = SharedCourseClass.objects.create(**self.slot)
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus)
        Reservation.objects.create(
            group=group, resort=self.resort, course_template=self.template,
            shared_course_class=shared_class, number_of_people=3, status='cancelled',
        )
        self.assertEqual(shared_class.refresh_readiness(), 'collecting')
        self.assertEqual(shared_class.registered_students, 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SharedCourseClass.objects.create(**self.slot)

    def test_distinct_campus_can_use_same_resort_and_time(self):
        SharedCourseClass.objects.create(**self.slot)
        other_campus = Campus.objects.create(client=self.tenant, name='道央', code='central')
        other_campus.resorts.add(self.resort)
        other_class = SharedCourseClass.objects.create(**{**self.slot, 'campus': other_campus})
        self.assertEqual(SharedCourseClass.objects.count(), 2)
        self.assertEqual(other_class.campus, other_campus)

    def test_legacy_templates_remain_opted_out(self):
        legacy = CourseTemplate.objects.create(
            course_type=self.template.course_type, name='一般課程', duration_hours=4,
        )
        self.assertFalse(legacy.shared_class_enabled)
        self.assertEqual(legacy.minimum_group_size, 1)
