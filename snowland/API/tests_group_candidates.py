from datetime import time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach
from Control.models import UserProfile
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from Resorts.models import Campus, Resorts
from booking.models import Booking, Payment, Reservation, ReservationGroup, SharedCourseClass


class GroupCandidateApiTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.campus = Campus.objects.create(client=self.tenant, name='道東', code='east')
        self.resort = Resorts.objects.create(client=self.tenant, name='tomamu', display_name='星野')
        self.campus.resorts.add(self.resort)
        category = CourseCategory.objects.create(client=self.tenant, name='單板')
        course_type = CourseType.objects.create(category=category, name='團體課')
        self.template = CourseTemplate.objects.create(
            course_type=course_type, name='團體半日', duration_hours=4,
            billing_mode='per_person', max_capacity=6,
        )
        self.private_template = CourseTemplate.objects.create(
            course_type=course_type, name='私人半日', duration_hours=4,
            billing_mode='private', max_capacity=6,
        )
        self.day = timezone.localdate() + timedelta(days=2)
        self.user = User.objects.create_superuser('headquarters', 'hq@example.test', 'test-password')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/admin/snowland/bookings/group-candidates/'

    def add_booking(self, *, campus=None, resort=None, template=None, counts=None,
                    status='created', payment_status='paid', day=None, tenant=None):
        group = ReservationGroup.objects.create(client=tenant or self.tenant, campus=campus or self.campus)
        Payment.objects.create(reservation_group=group, status=payment_status)
        reservation = Reservation.objects.create(
            group=group, resort=resort or self.resort,
            course_template=template or self.template,
            ability_level_counts=counts or {'level1': 1},
            number_of_people=sum((counts or {'level1': 1}).values()),
            status=status,
        )
        Booking.objects.create(
            reservation=reservation, date=day or self.day,
            start_time=time(9), end_time=time(13),
        )
        return group

    def query(self, client=None):
        return (client or self.api).get(self.url, {
            'start': self.day.isoformat(), 'end': self.day.isoformat(),
        })

    def test_same_level_across_orders_counts_people_and_separates_payment(self):
        first = self.add_booking(counts={'level1': 1})
        second = self.add_booking(counts={'level1': 2, 'level2': 1}, payment_status='pending')
        self.add_booking(template=self.private_template, counts={'level1': 4})
        self.add_booking(status='cancelled', counts={'level1': 3})
        self.add_booking(counts={'level1': 5}, payment_status='expired')
        self.add_booking(counts={'level1': 5}, payment_status='refunded')

        response = self.query()
        self.assertEqual(response.status_code, 200, response.data)
        rows = {row['ability_level']: row for row in response.data['data']['list']}
        self.assertEqual(response.data['data']['total'], 2)
        self.assertEqual(rows['level1']['registered_students'], 3)
        self.assertEqual(rows['level1']['paid_students'], 1)
        self.assertEqual({order['group_id'] for order in rows['level1']['orders']}, {first.id, second.id})
        self.assertEqual(rows['level2']['registered_students'], 1)
        self.assertEqual(rows['level2']['paid_students'], 0)

    def test_formal_shared_class_is_separate_from_unlinked_candidates_and_uses_its_own_minimum(self):
        linked = self.add_booking(counts={'level1': 2}, payment_status='pending')
        self.add_booking(counts={'level1': 1}, payment_status='paid')
        shared_class = SharedCourseClass.objects.create(
            client=self.tenant, campus=self.campus, resort=self.resort,
            template=self.template, date=self.day, start_time=time(9), end_time=time(13),
            ability_level='level1', minimum_students=4, max_capacity=6,
        )
        linked.reservations.update(shared_course_class=shared_class)

        response = self.query()
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['data']['list']
        self.assertEqual(len(rows), 2)
        formal = next(row for row in rows if row['shared_class_id'] == shared_class.id)
        candidate = next(row for row in rows if row['shared_class_id'] is None)
        self.assertEqual((formal['minimum_students'], formal['registered_students']), (4, 2))
        self.assertEqual(formal['shared_class_status'], 'collecting')
        self.assertEqual((candidate['minimum_students'], candidate['registered_students']), (None, 1))
        self.assertIsNone(candidate['shared_class_status'])

    def test_campus_and_date_scope_exclude_other_orders(self):
        own = self.add_booking()
        other_campus = Campus.objects.create(client=self.tenant, name='道央', code='central')
        other_campus.resorts.add(self.resort)
        other = self.add_booking(campus=other_campus, resort=self.resort, counts={'level1': 2})
        self.add_booking(day=self.day + timedelta(days=11))

        headquarters_response = self.query()
        self.assertEqual(headquarters_response.status_code, 200, headquarters_response.data)
        headquarters_rows = {row['campus_id']: row for row in headquarters_response.data['data']['list']}
        self.assertEqual(set(headquarters_rows), {self.campus.id, other_campus.id})
        self.assertEqual(headquarters_rows[self.campus.id]['campus_name'], '道東')
        self.assertEqual(headquarters_rows[self.campus.id]['registered_students'], 1)
        self.assertEqual(headquarters_rows[other_campus.id]['campus_name'], '道央')
        self.assertEqual(headquarters_rows[other_campus.id]['registered_students'], 2)
        self.assertEqual(headquarters_rows[other_campus.id]['orders'][0]['group_id'], other.id)

        manager = User.objects.create_user('east-manager', 'east@example.test', 'test-password')
        profile = UserProfile.objects.get(user=manager)
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = ['scheduling']
        profile.save()
        profile.campuses.add(self.campus)
        manager.refresh_from_db()
        scoped = APIClient()
        scoped.force_authenticate(manager)
        calendar = scoped.get('/api/admin/snowland/bookings/', {
            'start': self.day.isoformat(), 'end': self.day.isoformat(),
        })
        self.assertEqual(calendar.status_code, 200, calendar.data)
        response = self.query(scoped)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['total'], 1)
        row = response.data['data']['list'][0]
        self.assertEqual(row['orders'][0]['group_id'], own.id)
        self.assertNotIn('paid_students', row)
        self.assertNotIn('payment_status', row['orders'][0])

        profile.role = 'campus_principal'
        profile.save(update_fields=['role'])
        manager.refresh_from_db()
        principal_response = self.query(scoped)
        self.assertEqual(principal_response.status_code, 200, principal_response.data)
        principal_row = principal_response.data['data']['list'][0]
        self.assertNotIn('paid_students', principal_row)
        self.assertNotIn('payment_status', principal_row['orders'][0])

    def test_inactive_campus_history_is_not_new_group_candidate(self):
        active_group = self.add_booking()
        inactive_campus = Campus.objects.create(
            client=self.tenant, name='停用校區', code='inactive',
        )
        inactive_campus.resorts.add(self.resort)
        self.add_booking(campus=inactive_campus)
        inactive_campus.is_active = False
        inactive_campus.save(update_fields=['is_active'])

        response = self.query()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['total'], 1)
        self.assertEqual(response.data['data']['list'][0]['campus_id'], self.campus.id)
        self.assertEqual(
            [order['group_id'] for order in response.data['data']['list'][0]['orders']],
            [active_group.id],
        )

    def test_invalid_range_and_missing_permission_are_rejected(self):
        self.assertEqual(self.api.get(self.url).status_code, 400)
        manager = User.objects.create_user('no-schedule', 'no-schedule@example.test', 'test-password')
        profile = UserProfile.objects.get(user=manager)
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = ['orders']
        profile.save()
        profile.campuses.add(self.campus)
        manager.refresh_from_db()
        unauthorized = APIClient()
        unauthorized.force_authenticate(manager)
        self.assertEqual(self.query(unauthorized).status_code, 403)

    def test_already_assigned_orders_are_flagged_before_manual_grouping(self):
        assigned = self.add_booking(counts={'level1': 2}, status='auto_assigned')
        reservation = assigned.reservations.get()
        reservation.preferred_coach = Coach.objects.create(client=self.tenant, name='已排課教練')
        reservation.save(update_fields=['preferred_coach'])
        Booking.objects.filter(reservation__group=assigned).update(is_scheduled=True)
        unassigned = self.add_booking(counts={'level1': 1})

        response = self.query()
        self.assertEqual(response.status_code, 200, response.data)
        row = response.data['data']['list'][0]
        self.assertEqual(row['registered_students'], 3)
        self.assertEqual(row['assigned_students'], 2)
        orders = {order['group_id']: order for order in row['orders']}
        self.assertTrue(orders[assigned.id]['already_assigned'])
        self.assertFalse(orders[unassigned.id]['already_assigned'])

    def test_preferred_coach_does_not_mark_manual_assignment_needed_as_scheduled(self):
        group = self.add_booking(status='manual_assignment_needed')
        reservation = group.reservations.get()
        reservation.preferred_coach = Coach.objects.create(client=self.tenant, name='待確認教練')
        reservation.save(update_fields=['preferred_coach'])

        response = self.query()
        self.assertEqual(response.status_code, 200, response.data)
        row = response.data['data']['list'][0]
        self.assertEqual(row['registered_students'], 1)
        self.assertEqual(row['assigned_students'], 0)
        self.assertFalse(row['orders'][0]['already_assigned'])

        Booking.objects.filter(reservation=reservation).update(is_scheduled=True)
        response = self.query()
        row = response.data['data']['list'][0]
        self.assertEqual(row['assigned_students'], 0)
        self.assertFalse(row['orders'][0]['already_assigned'])
