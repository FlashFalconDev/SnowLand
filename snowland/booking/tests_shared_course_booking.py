from booking.tests_policy_support import checkout_policy_acknowledgement
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, CoachCourseLevel, CoachLeaveRequest, CoachPayRule, CoachResort
from Coach.payroll import calculate_payroll_statement
from Coursekit.models import CourseCategory, CoursePricing, CourseSession, CourseTemplate, CourseType
from Resorts.models import Campus, EquipmentAssistanceTimeSlot, Resorts
from booking.models import Booking, CancellationRequest, MemberDetail, MemberCourseDocumentRevision, NotificationDelivery, NotificationTemplate, Payment, Reservation, ReservationGroup, SharedCourseClass
from booking.payment_access import payment_access_token
from booking.tasks import auto_cancel_unpaid_reservations


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
        self.member = User.objects.create_user('shared-class-member', 'member@example.test')
        self.api.force_authenticate(self.member)

    def payload(self, *, campus=None, level='level1', people=1):
        return {
            **checkout_policy_acknowledgement(),
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

    def test_member_sees_anonymous_classmate_level_counts_only_for_own_class(self):
        own = self.book()
        group_id = own.data['reservation_group_ids'][0]
        other = User.objects.create_user('other-classmate', 'private-classmate@example.test')
        self.api.force_authenticate(other)
        joined = self.book(people=2)
        self.assertEqual(joined.status_code, 200, joined.data)
        other_group_id = joined.data['reservation_group_ids'][0]
        self.book(level='level2', people=4)
        self.api.force_authenticate(self.member)
        result = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual([row['id'] for row in result.data['orders']], [group_id])
        summary = result.data['orders'][0]['reservations'][0]['shared_class_summary']
        self.assertEqual(summary, {'status': 'ready', 'registered_students': 3,
            'minimum_students': 3, 'other_students': 2, 'ability_level_label': '等級 1'})
        self.assertNotIn(other.email, str(result.data))
        self.api.force_authenticate(other)
        other_rows = self.api.get('/booking/snowland/api/member-center/').data['orders']
        other_summary = next(row for row in other_rows if row['id'] == other_group_id)['reservations'][0]['shared_class_summary']
        self.assertEqual(other_summary['other_students'], 1)
        Reservation.objects.filter(group_id=other_group_id).update(status='cancelled')
        own_reservation = Reservation.objects.get(group_id=group_id)
        own_reservation.shared_course_class.refresh_readiness()
        self.api.force_authenticate(self.member)
        updated = self.api.get('/booking/snowland/api/member-center/').data['orders'][0]['reservations'][0]['shared_class_summary']
        self.assertEqual(updated['other_students'], 0)
        self.assertEqual(updated['registered_students'], 1)
        self.assertEqual(updated['status'], 'collecting')

    def test_member_classmate_summary_is_hidden_for_cancelled_or_cross_tenant_links(self):
        group_id = self.book().data['reservation_group_ids'][0]
        reservation = Reservation.objects.get(group_id=group_id)
        reservation.status = 'cancelled'
        reservation.save(update_fields=['status'])
        row = self.api.get('/booking/snowland/api/member-center/').data['orders'][0]['reservations'][0]
        self.assertIsNone(row['shared_class_summary'])
        other_tenant = Client.objects.create(name='Other school', internal_code='other-school')
        SharedCourseClass.objects.filter(pk=reservation.shared_course_class_id).update(client=other_tenant)
        reservation.status = 'created'
        reservation.save(update_fields=['status'])
        row = self.api.get('/booking/snowland/api/member-center/').data['orders'][0]['reservations'][0]
        self.assertIsNone(row['shared_class_summary'])

    def test_quick_rebook_preserves_shared_class_rules_not_assigned_coach(self):
        response = self.book()
        self.assertEqual(response.status_code, 200, response.data)
        group_id = response.data['reservation_group_ids'][0]
        reservation = Reservation.objects.get(group_id=group_id)
        coach = Coach.objects.create(client=self.tenant, name='School assigned coach')
        reservation.preferred_coach = coach
        reservation.save(update_fields=['preferred_coach'])
        copied = self.api.post('/booking/snowland/api/member-center/', {
            'quick_rebook_group_id': group_id,
        }, format='json')
        self.assertEqual(copied.status_code, 200, copied.data)
        item = copied.data['cart'][0]
        self.assertTrue(item['courses'][0]['sharedClassEnabled'])
        self.assertEqual(item['coach'], 'any')
        self.assertEqual(item['coachName'], '由學校安排')
        self.assertIsNone(item['courses'][0]['price'])

    def test_public_course_catalog_and_availability_are_tenant_scoped(self):
        Client.objects.exclude(pk=self.tenant.pk).update(is_active=False)
        for path in ('course-categories/', 'course-types/', 'course-templates/', 'course-sessions/'):
            with self.subTest(single_client_legacy_path=path):
                self.assertEqual(self.api.get(f'/booking/api/{path}').status_code, 200)

        other_client = Client.objects.create(name='Other school', internal_code='other-school')
        other_resort = Resorts.objects.create(client=other_client, name='other-resort', display_name='Other resort')
        other_category = CourseCategory.objects.create(client=other_client, name='Other category')
        other_type = CourseType.objects.create(category=other_category, name='Other course')
        other_template = CourseTemplate.objects.create(
            course_type=other_type, name='Other template', duration_hours=4,
            billing_mode='per_person', max_capacity=6,
        )
        other_template.resorts.add(other_resort)
        other_session = CourseSession.objects.create(
            template=other_template, start_time='10:00', end_time='14:00',
        )
        other_pricing = CoursePricing.objects.create(
            resort=other_resort, base_price_off_peak=10000,
            peak_season_surcharge=0, additional_person_fee=0, max_capacity=6,
        )
        other_pricing.templates.add(other_template)

        cases = [
            ('course-categories/', self.template.course_type.category_id, other_category.id),
            ('course-types/', self.template.course_type_id, other_type.id),
            ('course-templates/', self.template.id, other_template.id),
            ('course-sessions/', CourseSession.objects.get(template=self.template).id, other_session.id),
        ]
        for path, own_id, foreign_id in cases:
            with self.subTest(path=path):
                response = self.api.get(f'/booking/snowland/api/{path}')
                self.assertEqual(response.status_code, 200, response.data)
                ids = [row['id'] for row in response.data]
                self.assertIn(own_id, ids)
                self.assertNotIn(foreign_id, ids)

        session_response = self.api.get('/booking/snowland/api/course-sessions/', {'template_id': other_template.id})
        self.assertEqual(session_response.status_code, 200, session_response.data)
        self.assertEqual(session_response.data, [])
        date_response = self.api.get(
            f'/booking/snowland/api/course-templates/{other_template.id}/available-dates/',
            {'month': self.date[:7]},
        )
        self.assertEqual(date_response.status_code, 404, date_response.data)
        own_date_response = self.api.get(
            f'/booking/snowland/api/course-templates/{self.template.id}/available-dates/',
            {'month': self.date[:7]},
        )
        self.assertEqual(own_date_response.status_code, 200, own_date_response.data)
        self.assertEqual(own_date_response.data['template_id'], self.template.id)

        for path, _, _ in cases:
            with self.subTest(legacy_path=path):
                response = self.api.get(f'/booking/api/{path}')
                self.assertEqual(response.status_code, 400, response.data)

        self.assertEqual(self.api.get('/booking/unknown-client/api/course-sessions/').status_code, 404)

    def test_public_course_catalog_rejects_invalid_ids_without_server_error(self):
        cases = [
            ('course-types/', 'category_id'),
            ('course-templates/', 'course_type_id'),
            ('course-sessions/', 'template_id'),
        ]
        for path, key in cases:
            for value in ('not-a-number', '0', '-1'):
                with self.subTest(path=path, value=value):
                    response = self.api.get(f'/booking/snowland/api/{path}', {key: value})
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn('error', response.data)

    def test_booking_calendar_and_slots_show_only_matching_campus_level_and_capacity(self):
        other_campus = Campus.objects.create(client=self.tenant, name='道央', code='central')
        other_campus.resorts.add(self.resort)
        self.assertEqual(self.book(people=2).status_code, 200)
        self.assertEqual(self.book(campus=other_campus, people=1).status_code, 200)

        lookup = {
            'campus_id': self.campus.id, 'resort': self.resort.name,
            'ability_level': 'level1', 'language': 'zh',
        }
        calendar = self.api.get(
            f'/booking/snowland/api/course-templates/{self.template.id}/available-dates/',
            {'month': self.date[:7], **lookup},
        )
        self.assertEqual(calendar.status_code, 200, calendar.data)
        self.assertEqual(len(calendar.data['shared_class_dates'][self.date]), 1)
        row = calendar.data['shared_class_dates'][self.date][0]
        self.assertEqual((row['status'], row['registered_students'], row['minimum_students']), ('collecting', 2, 3))
        self.assertEqual(row['remaining_capacity'], 4)

        slots_url = '/booking/snowland/api/course-sessions/'
        slots = self.api.get(slots_url, {'template_id': self.template.id, 'date': self.date, 'people_count': 4, **lookup})
        self.assertEqual(slots.status_code, 200, slots.data)
        self.assertEqual(slots.data[0]['shared_class']['registered_students'], 2)
        self.assertFalse(slots.data[0]['is_full'])
        oversized = self.api.get(slots_url, {'template_id': self.template.id, 'date': self.date, 'people_count': 5, **lookup})
        self.assertTrue(oversized.data[0]['is_full'])

        other_lookup = {**lookup, 'campus_id': other_campus.id}
        other_calendar = self.api.get(
            f'/booking/snowland/api/course-templates/{self.template.id}/available-dates/',
            {'month': self.date[:7], **other_lookup},
        )
        self.assertEqual(other_calendar.data['shared_class_dates'][self.date][0]['registered_students'], 1)
        other_level = self.api.get(slots_url, {
            'template_id': self.template.id, 'date': self.date, **{**lookup, 'ability_level': 'level2'},
        })
        self.assertIsNone(other_level.data[0]['shared_class'])
        invalid_campus = self.api.get(slots_url, {'template_id': self.template.id, 'date': self.date, **{**lookup, 'campus_id': 9999}})
        self.assertEqual(invalid_campus.status_code, 400, invalid_campus.data)

    def test_school_can_open_empty_class_then_customer_joins_same_class(self):
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        url = '/api/admin/snowland/bookings/shared-classes/open/'
        options = admin.get(url)
        self.assertEqual(options.status_code, 200, options.data)
        self.assertEqual(options.data['data']['templates'][0]['id'], self.template.id)
        session = CourseSession.objects.get(template=self.template)
        payload = {
            'campus_id': self.campus.id, 'resort_id': self.resort.id,
            'template_id': self.template.id, 'session_id': session.id,
            'date': self.date, 'ability_level': 'level1', 'language': 'zh',
        }
        opened = admin.post(url, payload, format='json')
        self.assertEqual(opened.status_code, 200, opened.data)
        shared_class = SharedCourseClass.objects.get()
        self.assertEqual((shared_class.opening_mode, shared_class.registered_students), ('school', 0))
        group_candidates = admin.get('/api/admin/snowland/bookings/group-candidates/', {
            'start': self.date, 'end': self.date,
        })
        self.assertEqual(group_candidates.status_code, 200, group_candidates.data)
        self.assertEqual(group_candidates.data['data']['list'][0]['shared_class_id'], shared_class.id)
        self.assertEqual(group_candidates.data['data']['list'][0]['registered_students'], 0)
        self.assertEqual(admin.post(url, payload, format='json').status_code, 409)

        booked = self.book()
        self.assertEqual(booked.status_code, 200, booked.data)
        shared_class.refresh_from_db()
        self.assertEqual((shared_class.opening_mode, shared_class.registered_students), ('school', 1))
        self.assertEqual(Reservation.objects.get().shared_course_class_id, shared_class.id)

    def test_school_opening_rejects_wrong_campus_template_and_non_headquarters(self):
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        url = '/api/admin/snowland/bookings/shared-classes/open/'
        session = CourseSession.objects.get(template=self.template)
        payload = {
            'campus_id': self.campus.id, 'resort_id': self.resort.id,
            'template_id': self.template.id, 'session_id': session.id,
            'date': self.date, 'ability_level': 'level1', 'language': 'zh',
        }
        self.assertEqual(admin.post(url, {**payload, 'campus_id': 'invalid'}, format='json').status_code, 400)
        self.assertEqual(admin.post(url, {**payload, 'ability_level': 'invalid'}, format='json').status_code, 400)
        other_campus = Campus.objects.create(client=self.tenant, name='未綁雪場', code='unbound')
        self.assertEqual(admin.post(url, {**payload, 'campus_id': other_campus.id}, format='json').status_code, 400)
        self.assertFalse(SharedCourseClass.objects.exists())

        manager = User.objects.create_user('manager', 'manager@example.test', 'test-password')
        from Control.models import UserProfile
        profile = UserProfile.objects.get(user=manager)
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = ['scheduling']
        profile.save()
        profile.campuses.add(self.campus)
        manager_api = APIClient()
        manager_api.force_authenticate(manager)
        self.assertEqual(manager_api.get(url).status_code, 403)
        self.assertEqual(manager_api.post(url, payload, format='json').status_code, 403)

    @override_settings(SHARED_CLASS_FEATURE_ENABLED=False)
    def test_school_opening_stays_closed_when_shared_class_gate_is_off(self):
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        self.assertFalse(admin.get('/api/admin/snowland/bookings/shared-classes/open/').data['data']['enabled'])
        self.assertEqual(admin.post('/api/admin/snowland/bookings/shared-classes/open/', {}, format='json').status_code, 400)

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
        held = self.api.get('/booking/snowland/api/payment-info/', {
            'reservation_group': first_id, 'access_token': payment_access_token(Reservation.objects.get(group_id=first_id).group),
        })
        self.assertEqual(held.status_code, 400, held.data)
        self.assertEqual(held.data['payment_status'], 'collecting_class')

        second = self.book()
        self.assertEqual(second.status_code, 200, second.data)
        self.assertFalse(second.data['requires_payment'])
        third = self.book()
        self.assertEqual(third.status_code, 200, third.data)
        self.assertTrue(third.data['requires_payment'])
        self.assertNotIn('access_token=', third.data['payment_url'])
        self.assertEqual(SharedCourseClass.objects.get().status, 'ready')
        self.assertEqual(Payment.objects.count(), 3)
        self.assertEqual(Reservation.objects.filter(shared_course_class__isnull=False).count(), 3)
        released = self.api.get('/booking/snowland/api/payment-info/', {
            'reservation_group': first_id, 'access_token': payment_access_token(Reservation.objects.get(group_id=first_id).group),
        })
        self.assertEqual(released.status_code, 200, released.data)

    def test_admin_cannot_change_one_shared_class_members_lesson_or_coach(self):
        first = self.book()
        self.assertEqual(first.status_code, 200, first.data)
        second = self.book()
        self.assertEqual(second.status_code, 200, second.data)
        reservation = Reservation.objects.get(group_id=first.data['reservation_group_ids'][0])
        booking = reservation.bookings.get()
        original_date = booking.date
        other_booking = Reservation.objects.get(group_id=second.data['reservation_group_ids'][0]).bookings.get()
        self.assertFalse(Payment.objects.filter(reservation_group=reservation.group).exists())
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        url = f'/api/admin/snowland/orders/{reservation.group_id}/'
        detail = admin.get(url)
        self.assertEqual(detail.status_code, 200, detail.data)
        shared_reservation = detail.data['data']['reservations'][0]
        self.assertEqual(shared_reservation['shared_course_class_id'], reservation.shared_course_class_id)
        self.assertEqual(shared_reservation['shared_class_status'], 'collecting')

        premature_payment = admin.put(url, {
            'action': 'save', 'payment_status': 'paid',
        }, format='json')
        self.assertEqual(premature_payment.status_code, 400, premature_payment.data)
        self.assertFalse(Payment.objects.filter(reservation_group=reservation.group).exists())

        changed_lesson = admin.put(url, {
            'action': 'save',
            'payment_status': 'paid',
            'booking_updates': [{
                'booking_id': booking.id,
                'date': (original_date + timedelta(days=1)).isoformat(),
            }],
        }, format='json')
        self.assertEqual(changed_lesson.status_code, 400, changed_lesson.data)
        booking.refresh_from_db()
        other_booking.refresh_from_db()
        self.assertEqual(booking.date, original_date)
        self.assertEqual(other_booking.date, original_date)
        self.assertEqual(reservation.shared_course_class.date, original_date)
        self.assertFalse(Payment.objects.filter(reservation_group=reservation.group).exists())

        coach = Coach.objects.create(client=self.tenant, name='人工教練')
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        changed_coach = admin.put(url, {
            'action': 'save',
            'payment_status': 'paid',
            'reservation_updates': [{'reservation_id': reservation.id, 'coach_id': coach.id}],
        }, format='json')
        self.assertEqual(changed_coach.status_code, 400, changed_coach.data)
        reservation.refresh_from_db()
        self.assertIsNone(reservation.preferred_coach_id)
        self.assertFalse(Payment.objects.filter(reservation_group=reservation.group).exists())

    def test_admin_can_confirm_one_ready_class_order_without_paying_others(self):
        group_ids = []
        for _ in range(3):
            response = self.book()
            self.assertEqual(response.status_code, 200, response.data)
            group_ids.append(response.data['reservation_group_ids'][0])
        self.assertEqual(SharedCourseClass.objects.get().status, 'ready')
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))

        confirmed = admin.put(f'/api/admin/snowland/orders/{group_ids[0]}/', {
            'action': 'save', 'payment_status': 'paid',
        }, format='json')

        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.assertEqual(Payment.objects.get(reservation_group_id=group_ids[0]).status, 'paid')
        self.assertEqual(set(Payment.objects.filter(reservation_group_id__in=group_ids[1:]).values_list('status', flat=True)), {'unpaid'})

    def test_headquarters_assigns_one_coach_to_every_ready_class_order(self):
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)
        shared_class = SharedCourseClass.objects.get()
        self.assertEqual(shared_class.status, 'ready')
        coach = Coach.objects.create(client=self.tenant, name='整班教練', languages=['zh'])
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach, course_type=self.template.course_type,
            ability_levels=['level1'], price_level='Lv1',
        )
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        url = f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/coach/'

        options = admin.get(url)
        self.assertEqual(options.status_code, 200, options.data)
        self.assertEqual([item['id'] for item in options.data['data']['coaches']], [coach.id])
        assigned = admin.post(url, {'coach_id': coach.id}, format='json')
        self.assertEqual(assigned.status_code, 200, assigned.data)
        reservations = list(shared_class.reservations.all())
        self.assertEqual(len(reservations), 3)
        self.assertEqual({row.preferred_coach_id for row in reservations}, {coach.id})
        self.assertEqual({row.status for row in reservations}, {'manually_assigned'})
        self.assertTrue(all(row.bookings.get().is_scheduled for row in reservations))
        self.assertTrue(all(row.group.revisions.count() >= 2 for row in reservations))

    def test_whole_class_coach_assignment_rejects_collecting_conflict_and_leave_without_partial_updates(self):
        self.assertEqual(self.book().status_code, 200)
        shared_class = SharedCourseClass.objects.get()
        coach = Coach.objects.create(client=self.tenant, name='衝突教練', languages=['zh'])
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach, course_type=self.template.course_type,
            ability_levels=['level1'], price_level='Lv1',
        )
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        url = f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/coach/'
        self.assertEqual(admin.post(url, {'coach_id': coach.id}, format='json').status_code, 400)
        self.assertEqual(self.book().status_code, 200)
        self.assertEqual(self.book().status_code, 200)
        shared_class.refresh_from_db()
        self.assertEqual(shared_class.status, 'ready')

        other_group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus)
        other = Reservation.objects.create(
            group=other_group, resort=self.resort, course_template=self.template,
            preferred_coach=coach, status='manually_assigned', number_of_people=1,
        )
        Booking.objects.create(
            reservation=other, date=shared_class.date,
            start_time=shared_class.start_time, end_time=shared_class.end_time,
            is_scheduled=True,
        )
        conflict = admin.post(url, {'coach_id': coach.id}, format='json')
        self.assertEqual(conflict.status_code, 400, conflict.data)
        self.assertEqual(shared_class.reservations.filter(preferred_coach__isnull=False).count(), 0)

        other.bookings.all().delete()
        other.delete()
        other_group.delete()
        CoachLeaveRequest.objects.create(
            coach=coach, start_date=shared_class.date, end_date=shared_class.date,
            reason='測試請假', status='approved',
        )
        leave = admin.post(url, {'coach_id': coach.id}, format='json')
        self.assertEqual(leave.status_code, 400, leave.data)
        self.assertEqual(shared_class.reservations.filter(preferred_coach__isnull=False).count(), 0)

    def test_campus_staff_cannot_reassign_shared_class_coach(self):
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)
        shared_class = SharedCourseClass.objects.get()
        manager = User.objects.create_user('manager', 'manager@example.test', 'test-password')
        profile = manager.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = ['scheduling']
        profile.save()
        profile.campuses.add(self.campus)
        manager.refresh_from_db()
        scoped = APIClient()
        scoped.force_authenticate(manager)
        url = f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/coach/'
        self.assertEqual(scoped.get(url).status_code, 403)
        self.assertEqual(scoped.post(url, {'coach_id': 1}, format='json').status_code, 403)

    def test_headquarters_reschedules_every_order_and_reminder_in_shared_class(self):
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)
        shared_class = SharedCourseClass.objects.get()
        coach = Coach.objects.create(client=self.tenant, name='改期教練', languages=['zh'])
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach, course_type=self.template.course_type,
            ability_levels=['level1'], price_level='Lv1',
        )
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        coach_url = f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/coach/'
        self.assertEqual(admin.post(coach_url, {'coach_id': coach.id}, format='json').status_code, 200)
        template = NotificationTemplate.objects.create(
            client=self.tenant, name='課前提醒', event='pre_course', channel='email',
            body='提醒上課', days_before=2,
        )
        groups = list(ReservationGroup.objects.filter(reservations__shared_course_class=shared_class).distinct())
        for group in groups:
            Payment.objects.filter(reservation_group=group).update(status='paid')
        old_amounts = list(shared_class.reservations.order_by('id').values_list('payment_amount', flat=True))
        learners=[]
        for index,reservation in enumerate(shared_class.reservations.order_by('pk')):
            member=reservation.members.first() or MemberDetail.objects.create(reservation=reservation)
            member.waiver_signature=f'QA整班舊簽名{index}'
            member.insurance_processing_status='insured' if index==0 else 'pending'
            member.insurance_premium_amount=100 if index==0 else None
            member.insurance_premium_currency='JPY' if index==0 else ''
            member.save();learners.append(member)
        url = f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/schedule/'
        options=admin.get(url)
        self.assertEqual(options.status_code, 200)
        self.assertEqual((options.data['data']['waiver_resign_count'],options.data['data']['insurance_recheck_count']),(3,1))
        new_date = (shared_class.date + timedelta(days=2)).isoformat()
        response = admin.post(url, {
            'date': new_date, 'start_time': '09:00', 'end_time': '13:00',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        shared_class.refresh_from_db()
        self.assertEqual(shared_class.date.isoformat(), new_date)
        self.assertEqual(set(Booking.objects.filter(reservation__shared_course_class=shared_class).values_list('date', flat=True)), {shared_class.date})
        self.assertEqual(set(shared_class.reservations.values_list('preferred_coach_id', flat=True)), {coach.id})
        self.assertEqual(list(shared_class.reservations.order_by('id').values_list('payment_amount', flat=True)), old_amounts)
        self.assertEqual(NotificationDelivery.objects.filter(template=template, group__in=groups).count(), 3)
        self.assertEqual({timezone.localtime(row.scheduled_at).date() for row in NotificationDelivery.objects.filter(template=template)},
                         {shared_class.date - timedelta(days=2)})
        self.assertTrue(all(group.revisions.count() >= 3 for group in groups))
        self.assertEqual(MemberCourseDocumentRevision.objects.count(),3)
        for member in learners:
            member.refresh_from_db();self.assertTrue(member.waiver_resign_required)
            history=member.course_document_revisions.get()
            self.assertEqual(history.revision.group_id,member.reservation.group_id)
            self.assertEqual(history.snapshot['previous_courses'][0]['date'],self.date)
        learners[0].refresh_from_db()
        self.assertEqual(learners[0].insurance_processing_status,'checking')
        self.assertIsNone(learners[0].insurance_premium_amount)

    def test_shared_class_time_only_change_preserves_signed_document_state(self):
        for _ in range(3):
            self.assertEqual(self.book().status_code,200)
        shared=SharedCourseClass.objects.get()
        reservation=shared.reservations.first()
        member=reservation.members.first() or MemberDetail.objects.create(reservation=reservation)
        member.waiver_signature='QA整班時間調整';member.insurance_processing_status='insured';member.save()
        CourseSession.objects.create(template=self.template,start_time='14:00',end_time='18:00')
        admin=APIClient();admin.force_authenticate(User.objects.create_superuser('time-hq','time@example.test','test-password'))
        response=admin.post(f'/api/admin/snowland/bookings/shared-classes/{shared.pk}/schedule/',
            {'date':str(shared.date),'start_time':'14:00','end_time':'18:00'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        member.refresh_from_db()
        self.assertFalse(member.waiver_resign_required)
        self.assertEqual(member.insurance_processing_status,'insured')
        self.assertFalse(member.course_document_revisions.exists())

    def test_shared_class_date_change_rejects_inconsistent_foreign_company_order(self):
        for _ in range(3):
            self.assertEqual(self.book().status_code,200)
        shared=SharedCourseClass.objects.get()
        group=shared.reservations.first().group
        group.client=Client.objects.create(name='Other',internal_code='other');group.save(update_fields=['client'])
        admin=APIClient();admin.force_authenticate(User.objects.create_superuser('scope-hq','scope@example.test','test-password'))
        response=admin.post(f'/api/admin/snowland/bookings/shared-classes/{shared.pk}/schedule/',
            {'date':str(shared.date+timedelta(days=1)),'start_time':'09:00','end_time':'13:00'},format='json')
        self.assertEqual(response.status_code,409,response.data)
        shared.refresh_from_db();self.assertEqual(str(shared.date),self.date)
        self.assertFalse(MemberCourseDocumentRevision.objects.exists())

    def test_shared_class_reschedule_rejects_conflict_invalid_slot_and_campus_staff(self):
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)
        shared_class = SharedCourseClass.objects.get()
        coach = Coach.objects.create(client=self.tenant, name='撞課教練', languages=['zh'])
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach, course_type=self.template.course_type,
            ability_levels=['level1'], price_level='Lv1',
        )
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        self.assertEqual(admin.post(
            f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/coach/',
            {'coach_id': coach.id}, format='json',
        ).status_code, 200)
        url = f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/schedule/'
        new_date = shared_class.date + timedelta(days=1)
        self.assertEqual(admin.post(url, {
            'date': new_date.isoformat(), 'start_time': '10:00', 'end_time': '14:00',
        }, format='json').status_code, 400)
        other_group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus)
        other = Reservation.objects.create(
            group=other_group, resort=self.resort, course_template=self.template,
            preferred_coach=coach, status='manually_assigned', number_of_people=1,
        )
        Booking.objects.create(
            reservation=other, date=new_date, start_time='09:00', end_time='13:00', is_scheduled=True,
        )
        conflict = admin.post(url, {
            'date': new_date.isoformat(), 'start_time': '09:00', 'end_time': '13:00',
        }, format='json')
        self.assertEqual(conflict.status_code, 409, conflict.data)
        shared_class.refresh_from_db()
        self.assertNotEqual(shared_class.date, new_date)
        self.assertEqual(set(Booking.objects.filter(reservation__shared_course_class=shared_class).values_list('date', flat=True)), {shared_class.date})
        manager = User.objects.create_user('manager', 'manager@example.test', 'test-password')
        profile = manager.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = ['scheduling']
        profile.save()
        profile.campuses.add(self.campus)
        scoped = APIClient()
        scoped.force_authenticate(manager)
        self.assertEqual(scoped.get(url).status_code, 403)
        self.assertEqual(scoped.post(url, {
            'date': new_date.isoformat(), 'start_time': '09:00', 'end_time': '13:00',
        }, format='json').status_code, 403)

    def test_shared_class_reschedule_checks_course_and_equipment_and_reconfirms_passive_coach(self):
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)
        shared_class = SharedCourseClass.objects.get()
        CourseSession.objects.create(template=self.template, start_time='13:00', end_time='17:00')
        coach = Coach.objects.create(
            client=self.tenant, name='待重新確認教練', languages=['zh'], availability_status='passive',
        )
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach, course_type=self.template.course_type,
            ability_levels=['level1'], price_level='Lv1',
        )
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        self.assertEqual(admin.post(
            f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/coach/',
            {'coach_id': coach.id}, format='json',
        ).status_code, 200)
        shared_class.reservations.update(status='manually_assigned')
        slot = EquipmentAssistanceTimeSlot.objects.create(
            resort=self.resort, label='上午裝備協助', session_period='morning',
        )
        first = shared_class.reservations.order_by('id').first()
        first.equipment_assistance_time_slot = slot
        first.save(update_fields=['equipment_assistance_time_slot'])
        url = f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/schedule/'
        new_date = shared_class.date + timedelta(days=1)
        self.assertEqual(admin.post(url, {
            'date': new_date.isoformat(), 'start_time': '13:00', 'end_time': '17:00',
        }, format='json').status_code, 409)
        self.assertEqual(set(shared_class.reservations.values_list('status', flat=True)), {'manually_assigned'})
        self.template.course_end_date = shared_class.date
        self.template.save(update_fields=['course_end_date'])
        self.assertEqual(admin.post(url, {
            'date': new_date.isoformat(), 'start_time': '09:00', 'end_time': '13:00',
        }, format='json').status_code, 400)
        self.template.course_end_date = new_date
        self.template.save(update_fields=['course_end_date'])
        moved = admin.post(url, {
            'date': new_date.isoformat(), 'start_time': '09:00', 'end_time': '13:00',
        }, format='json')
        self.assertEqual(moved.status_code, 200, moved.data)
        self.assertIn('教練重新確認', moved.data['msg'])
        self.assertEqual(set(shared_class.reservations.values_list('status', flat=True)), {'pending_coach_confirmation'})

    def test_whole_class_change_preserves_completed_forms_and_blocks_started_lesson(self):
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)
        shared_class = SharedCourseClass.objects.get()
        first = shared_class.reservations.order_by('id').first()
        first.status = 'form_filled'
        first.save(update_fields=['status'])
        coach = Coach.objects.create(client=self.tenant, name='表單保留教練', languages=['zh'])
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach, course_type=self.template.course_type,
            ability_levels=['level1'], price_level='Lv1',
        )
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        url = f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/coach/'
        self.assertEqual(admin.post(url, {'coach_id': coach.id}, format='json').status_code, 200)
        first.refresh_from_db()
        self.assertEqual(first.status, 'form_filled')

        shared_class.date = timezone.localdate()
        shared_class.start_time = '00:00'
        shared_class.end_time = '01:00'
        shared_class.save(update_fields=['date', 'start_time', 'end_time'])
        Booking.objects.filter(reservation__shared_course_class=shared_class).update(
            date=timezone.localdate(), start_time='00:00', end_time='01:00',
        )
        self.assertEqual(admin.get(url).status_code, 400)
        self.assertEqual(admin.post(url, {'coach_id': coach.id}, format='json').status_code, 400)

    def test_passive_coach_acceptance_and_rejection_are_whole_class_actions(self):
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)
        shared_class = SharedCourseClass.objects.get()
        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        url = f'/api/admin/snowland/bookings/shared-classes/{shared_class.id}/coach/'

        coaches = []
        for index in range(2):
            user = User.objects.create_user(f'coach{index}', f'coach{index}@example.test', 'test-password')
            profile = user.userprofile
            profile.is_coach = True
            profile.save(update_fields=['is_coach'])
            coach = Coach.objects.create(
                client=self.tenant, user=user, name=f'待確認教練{index}',
                languages=['zh'], availability_status='passive',
            )
            coach.campuses.add(self.campus)
            CoachResort.objects.create(coach=coach, resort=self.resort)
            CoachCourseLevel.objects.create(
                coach=coach, course_type=self.template.course_type,
                ability_levels=['level1'], price_level='Lv1',
            )
            coaches.append((coach, user))

        self.assertEqual(admin.post(url, {'coach_id': coaches[0][0].id}, format='json').status_code, 200)
        self.assertEqual(set(shared_class.reservations.values_list('status', flat=True)), {'pending_coach_confirmation'})
        coach_api = APIClient()
        coach_api.force_authenticate(coaches[0][1])
        first_id = shared_class.reservations.order_by('id').first().id
        shared_class.status = 'collecting'
        shared_class.save(update_fields=['status'])
        pending = coach_api.get('/api/admin/snowland/coach/pending/')
        self.assertEqual(pending.status_code, 200, pending.data)
        self.assertEqual(pending.data['data']['list'], [])
        self.assertEqual(coach_api.post(
            f'/api/admin/snowland/coach/confirm/{first_id}/', {'action': 'accept'}, format='json',
        ).status_code, 409)
        shared_class.status = 'ready'
        shared_class.save(update_fields=['status'])
        accepted = coach_api.post(f'/api/admin/snowland/coach/confirm/{first_id}/', {'action': 'accept'}, format='json')
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(set(shared_class.reservations.values_list('status', flat=True)), {'manually_assigned'})

        self.assertEqual(admin.post(url, {'coach_id': coaches[1][0].id}, format='json').status_code, 200)
        coach_api.force_authenticate(coaches[1][1])
        rejected = coach_api.post(f'/api/admin/snowland/coach/confirm/{first_id}/', {'action': 'reject'}, format='json')
        self.assertEqual(rejected.status_code, 200, rejected.data)
        self.assertEqual(set(shared_class.reservations.values_list('status', flat=True)), {'created'})
        self.assertEqual(set(shared_class.reservations.values_list('preferred_coach_id', flat=True)), {None})
        self.assertFalse(Booking.objects.filter(reservation__shared_course_class=shared_class, is_scheduled=True).exists())
        self.assertEqual(shared_class.reservations.filter(rejected_coaches=coaches[1][0]).count(), 3)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        SNOWLAND_PUBLIC_PAYMENT_URL='https://example.test/snowland/payment',
    )
    def test_existing_guests_receive_their_own_payment_link_when_class_fills(self):
        NotificationTemplate.objects.create(
            client=self.tenant, name='團體班成班付款', event='shared_class_ready',
            channel='email', subject='成班請付款',
            body='訂單 {order_number}：{payment_url}',
        )
        group_ids = []
        for index in range(3):
            payload = self.payload()
            payload['contact']['email'] = f'guest{index}@example.test'
            response = self.api.post('/booking/snowland/api/create-reservation/', payload, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            group_ids.append(response.data['reservation_group_ids'][0])
            # Model an already-existing guest order, not an anonymous new submission.
            ReservationGroup.objects.filter(pk=group_ids[-1]).update(user=None)
            if index < 2:
                call_command('process_snowland_jobs')
                self.assertEqual(len(mail.outbox), 0)

        call_command('process_snowland_jobs')
        self.assertEqual(len(mail.outbox), 3)
        for index, group_id in enumerate(group_ids):
            message = next(msg for msg in mail.outbox if msg.to == [f'guest{index}@example.test'])
            self.assertIn(f'reservation_group={group_id}', message.body)
            self.assertIn('access_token=', message.body)
            self.assertIn('https://example.test/snowland/payment?', message.body)
            payment_link = message.body.split('：', 1)[1]
            link_query = parse_qs(urlsplit(payment_link).query)
            self.assertEqual(self.api.get('/booking/snowland/api/payment-info/', {
                'reservation_group': group_id, 'access_token': link_query['access_token'][0],
            }).status_code, 200)
        call_command('process_snowland_jobs')
        self.assertEqual(len(mail.outbox), 3)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        SNOWLAND_PUBLIC_PAYMENT_URL='',
    )
    def test_missing_public_payment_url_fails_visible_delivery_instead_of_sending_wrong_link(self):
        NotificationTemplate.objects.create(
            client=self.tenant, name='團體班成班付款', event='shared_class_ready',
            channel='email', subject='成班請付款', body='請付款：{payment_url}',
        )
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)

        call_command('process_snowland_jobs')
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(NotificationDelivery.objects.filter(status='failed').count(), 3)
        self.assertTrue(all(
            'SNOWLAND_PUBLIC_PAYMENT_URL' in delivery.error_message
            for delivery in NotificationDelivery.objects.filter(status='failed')
        ))

        with override_settings(SNOWLAND_PUBLIC_PAYMENT_URL='https://example.test/snowland/payment'):
            call_command('process_snowland_jobs')
            self.assertEqual(len(mail.outbox), 3)
            self.assertEqual(NotificationDelivery.objects.filter(status='sent').count(), 6)
            self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 3)
            call_command('process_snowland_jobs')
            self.assertEqual(len(mail.outbox), 3)
            self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 3)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        SNOWLAND_PUBLIC_PAYMENT_URL='https://example.test/booking/payment',
    )
    def test_wrong_public_payment_path_is_not_sent_and_can_be_corrected(self):
        NotificationTemplate.objects.create(
            client=self.tenant, name='團體班成班付款', event='shared_class_ready',
            channel='email', subject='成班請付款', body='請付款：{payment_url}',
        )
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)

        call_command('process_snowland_jobs')
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(NotificationDelivery.objects.filter(status='failed').count(), 3)
        with override_settings(SNOWLAND_PUBLIC_PAYMENT_URL='https://example.test/snowland/payment'):
            call_command('process_snowland_jobs')
        self.assertEqual(len(mail.outbox), 3)
        self.assertTrue(all('/snowland/payment?' in message.body for message in mail.outbox))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        SNOWLAND_PUBLIC_PAYMENT_URL='https://example.test/snowland/payment',
    )
    def test_already_paid_guest_does_not_receive_stale_class_payment_notice(self):
        NotificationTemplate.objects.create(
            client=self.tenant, name='團體班成班付款', event='shared_class_ready',
            channel='email', subject='成班請付款', body='請付款：{payment_url}',
        )
        group_ids = []
        for index in range(3):
            payload = self.payload()
            payload['contact']['email'] = f'paid-guest{index}@example.test'
            response = self.api.post('/booking/snowland/api/create-reservation/', payload, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            ReservationGroup.objects.filter(pk__in=response.data['reservation_group_ids']).update(user=None)
            group_ids.append(response.data['reservation_group_ids'][0])

        Payment.objects.filter(reservation_group_id=group_ids[0]).update(status='paid')
        call_command('process_snowland_jobs')
        self.assertEqual(len(mail.outbox), 2)
        self.assertFalse(any(message.to == ['paid-guest0@example.test'] for message in mail.outbox))
        self.assertEqual(
            NotificationDelivery.objects.get(group_id=group_ids[0], template__event='shared_class_ready').status,
            'cancelled',
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        SNOWLAND_PUBLIC_PAYMENT_URL='https://example.test/snowland/payment',
    )
    def test_class_falls_below_minimum_before_send_without_payment_notice(self):
        NotificationTemplate.objects.create(
            client=self.tenant, name='團體班成班付款', event='shared_class_ready',
            channel='email', subject='成班請付款', body='請付款：{payment_url}',
        )
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)
        first_reservation = Reservation.objects.order_by('id').first()
        first_reservation.status = 'cancelled'
        first_reservation.save(update_fields=['status'])
        shared_class = SharedCourseClass.objects.get()
        shared_class.refresh_readiness()
        self.assertEqual(shared_class.status, 'collecting')

        call_command('process_snowland_jobs')
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(NotificationDelivery.objects.filter(status='cancelled', template__event='shared_class_ready').count(), 3)

    def test_member_order_waits_for_class_before_offering_payment(self):
        member = User.objects.create_user('class-member', 'class-member@example.test')
        self.api.force_authenticate(user=member)
        first_id = self.book().data['reservation_group_ids'][0]

        waiting = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(waiting.status_code, 200, waiting.data)
        first_order = next(order for order in waiting.data['orders'] if order['id'] == first_id)
        self.assertEqual(first_order['payment_status'], 'unpaid')
        self.assertEqual(first_order['payment_hold_status'], 'collecting_class')
        self.assertTrue(first_order['reservations'][0]['is_shared_class'])

        self.book()
        self.book()
        ready = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(ready.status_code, 200, ready.data)
        first_order = next(order for order in ready.data['orders'] if order['id'] == first_id)
        self.assertEqual(first_order['payment_status'], 'unpaid')
        self.assertIsNone(first_order['payment_hold_status'])

    def test_cancelled_member_order_does_not_offer_payment(self):
        member = User.objects.create_user('cancelled-member', 'cancelled-member@example.test')
        self.api.force_authenticate(user=member)
        first_id = self.book().data['reservation_group_ids'][0]
        self.book()
        self.book()

        cancellation = CancellationRequest.objects.create(
            group_id=first_id, reason='schedule', original_amount=10000, refund_amount=10000,
        )
        admin = User.objects.create_superuser('cancel-admin', 'cancel-admin@example.test', 'test-password')
        admin_api = APIClient()
        admin_api.force_authenticate(user=admin)
        approved = admin_api.post(
            f'/api/admin/snowland/cancellations/{cancellation.id}/process/',
            {'status': 'approved'}, format='json',
        )
        self.assertEqual(approved.status_code, 200, approved.data)

        orders = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(orders.status_code, 200, orders.data)
        cancelled_order = next(order for order in orders.data['orders'] if order['id'] == first_id)
        self.assertEqual(cancelled_order['payment_status'], 'unpaid')
        self.assertEqual(cancelled_order['payment_hold_status'], 'all_cancelled')
        self.assertEqual(cancelled_order['total_amount'], 0)
        payment_info = self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': first_id})
        self.assertEqual(payment_info.status_code, 400, payment_info.data)
        self.assertEqual(payment_info.data['payment_status'], 'all_cancelled')

    def test_ready_class_payments_belong_to_each_order_member(self):
        orders = []
        for index in range(3):
            user = User.objects.create_user(
                username=f'member{index}@example.test', email=f'member{index}@example.test',
            )
            api = APIClient()
            api.force_authenticate(user=user)
            response = api.post(
                '/booking/snowland/api/create-reservation/', self.payload(), format='json',
            )
            self.assertEqual(response.status_code, 200, response.data)
            orders.append((response.data['reservation_group_ids'][0], user))

        for group_id, user in orders:
            self.assertEqual(Payment.objects.get(reservation_group_id=group_id).user_id, user.id)

    def test_ready_class_payments_keep_each_orders_contact(self):
        orders = []
        for index in range(3):
            email = f'customer{index}@example.test'
            payload = self.payload()
            payload['contact']['email'] = email
            response = self.api.post(
                '/booking/snowland/api/create-reservation/', payload, format='json',
            )
            self.assertEqual(response.status_code, 200, response.data)
            orders.append((response.data['reservation_group_ids'][0], email))

        for group_id, email in orders:
            contact = Payment.objects.get(reservation_group_id=group_id).DataJSON['contact']
            self.assertEqual(contact['email'], email)

    def test_cancelling_one_unpaid_member_reopens_collecting_and_holds_other_payments(self):
        group_ids = [self.book().data['reservation_group_ids'][0] for _ in range(3)]
        shared_class = SharedCourseClass.objects.get()
        self.assertEqual(shared_class.status, 'ready')

        cancellation = CancellationRequest.objects.create(
            group_id=group_ids[0], reason='schedule', original_amount=10000, refund_amount=10000,
        )
        admin = User.objects.create_superuser('class-admin', 'class-admin@example.test', 'test-password')
        admin_api = APIClient()
        admin_api.force_authenticate(user=admin)
        approved = admin_api.post(
            f'/api/admin/snowland/cancellations/{cancellation.id}/process/',
            {'status': 'approved'}, format='json',
        )
        self.assertEqual(approved.status_code, 200, approved.data)

        shared_class.refresh_from_db()
        self.assertEqual(shared_class.registered_students, 2)
        self.assertEqual(shared_class.status, 'collecting')
        held = self.api.get('/booking/snowland/api/payment-info/', {
            'reservation_group': group_ids[1], 'access_token': payment_access_token(Reservation.objects.get(group_id=group_ids[1]).group),
        })
        self.assertEqual(held.status_code, 400, held.data)
        self.assertEqual(held.data['payment_status'], 'collecting_class')

        remaining_payment = Payment.objects.get(reservation_group_id=group_ids[1])
        remaining_payment.expires_at = timezone.now() - timedelta(minutes=1)
        remaining_payment.save(update_fields=['expires_at'])
        auto_cancel_unpaid_reservations()
        remaining_payment.refresh_from_db()
        self.assertEqual(remaining_payment.status, 'unpaid')
        self.assertNotEqual(Reservation.objects.get(group_id=group_ids[1]).status, 'cancelled')

        replacement = self.book()
        self.assertEqual(replacement.status_code, 200, replacement.data)
        self.assertTrue(replacement.data['requires_payment'])
        shared_class.refresh_from_db()
        self.assertEqual(shared_class.status, 'ready')
        remaining_payment.refresh_from_db()
        self.assertGreater(remaining_payment.expires_at, timezone.now())
        released = self.api.get('/booking/snowland/api/payment-info/', {
            'reservation_group': group_ids[1], 'access_token': payment_access_token(Reservation.objects.get(group_id=group_ids[1]).group),
        })
        self.assertEqual(released.status_code, 200, released.data)

    def test_expiring_one_member_reopens_collecting_for_remaining_orders(self):
        group_ids = [self.book().data['reservation_group_ids'][0] for _ in range(3)]
        # This fixture mocks the scheduler. Represent actual confirmed scheduling:
        # the payment window must not expire courses still waiting for assignment.
        Reservation.objects.filter(group_id__in=group_ids).update(status='auto_assigned')
        payment = Payment.objects.get(reservation_group_id=group_ids[0])
        payment.expires_at = timezone.now() - timedelta(minutes=1)
        payment.save(update_fields=['expires_at'])

        auto_cancel_unpaid_reservations()

        shared_class = SharedCourseClass.objects.get()
        self.assertEqual(shared_class.registered_students, 2)
        self.assertEqual(shared_class.status, 'collecting')
        held = self.api.get('/booking/snowland/api/payment-info/', {
            'reservation_group': group_ids[1], 'access_token': payment_access_token(Reservation.objects.get(group_id=group_ids[1]).group),
        })
        self.assertEqual(held.status_code, 400, held.data)
        self.assertEqual(held.data['payment_status'], 'collecting_class')

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
            'campus_id': self.campus.id, 'resort': self.resort.name,
            'ability_level': 'level1', 'language': 'zh',
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data[0]['is_full'])

    def test_coach_course_rows_expose_shared_class_for_deduplicated_hours(self):
        user = User.objects.create_user('shared-hours-coach')
        user.userprofile.is_coach = True
        user.userprofile.save(update_fields=['is_coach'])
        coach = Coach.objects.create(client=self.tenant, user=user, name='統計教練')
        coach.campuses.add(self.campus)
        for _ in range(3):
            self.assertEqual(self.book().status_code, 200)
        Reservation.objects.update(preferred_coach=coach, status='manually_assigned')
        Payment.objects.update(status='paid')
        api = APIClient()
        api.force_authenticate(user)
        response = api.get('/api/admin/snowland/coach/my-courses/')
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['data']['list']
        self.assertEqual(len(rows), 3)
        self.assertEqual({row['shared_class_id'] for row in rows}, {SharedCourseClass.objects.get().pk})

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
