from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from API import tests_order_assignment_scope as fixtures
from Coach.models import Coach, CoachCourseLevel
from Control.models import TenantStaffMembership
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from Resorts.models import OperatingPolicy
from booking.models import Booking, OrderRevision, Reservation


class ManualAssignmentQualificationTests(TestCase):
    def setUp(self):
        fixtures.OrderAssignmentScopeTests.setUp(self)
        self.reservation.max_ability_level = 'level3'
        self.reservation.save()
        self.coach = fixtures.OrderAssignmentScopeTests.coach(self)
        self.level = CoachCourseLevel.objects.get(coach=self.coach, course_type=self.kind)

    def candidates(self):
        response = self.api.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['data']['reservations'][0]

    def offered(self):
        return {row['id'] for row in self.candidates()['available_coaches']}

    def assign(self):
        return self.api.put(self.url, {'action': 'save', 'payment_status': 'paid',
            'reservation_updates': [{'reservation_id': self.reservation.pk, 'coach_id': self.coach.pk}]}, format='json')

    def assert_rejected(self, *reason_codes):
        candidates = self.candidates()
        self.assertEqual(candidates['candidate_status'], 'ok')
        self.assertNotIn(self.coach.pk, {row['id'] for row in candidates['available_coaches']})
        unavailable = {row['id']: row for row in candidates['unavailable_coaches']}
        self.assertEqual(unavailable[self.coach.pk]['name'], self.coach.name)
        self.assertEqual(unavailable[self.coach.pk]['reason_codes'], list(reason_codes))
        response = self.assign()
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['reason_codes'], list(reason_codes))
        self.reservation.refresh_from_db()
        self.booking.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertFalse(self.booking.is_scheduled)
        self.assertEqual(self.payment.status, 'pending')
        self.assertFalse(OrderRevision.objects.filter(group=self.group).exists())

    def assert_allowed(self):
        self.assertIn(self.coach.pk, self.offered())
        response = self.assign()
        self.assertEqual(response.status_code, 200, response.data)

    def test_language_removed_after_picker_was_loaded_is_rejected(self):
        self.assertIn(self.coach.pk, self.offered())
        self.coach.languages = ['en']
        self.coach.save(update_fields=['languages'])
        self.assert_rejected('missing_language')

    def test_insufficient_ability_is_rejected_then_restoring_ability_works(self):
        self.level.ability_levels = ['level1']
        self.level.save(update_fields=['ability_levels'])
        self.assert_rejected('ability_level')
        self.level.ability_levels = ['level6']
        self.level.save(update_fields=['ability_levels'])
        self.assert_allowed()

    def test_removed_course_qualification_is_rejected(self):
        self.level.delete()
        self.assert_rejected('course_type')

    def test_template_minimum_coach_level_is_enforced(self):
        self.template.minimum_coach_price_level = 'director'
        self.template.save(update_fields=['minimum_coach_price_level'])
        self.assert_rejected('min_coach_level')
        self.level.price_level = 'director'
        self.level.save(update_fields=['price_level'])
        self.assert_allowed()

    def test_template_coach_whitelist_cannot_be_bypassed(self):
        other = fixtures.OrderAssignmentScopeTests.coach(self)
        self.template.allowed_coaches.add(other)
        self.assert_rejected('template_roster')
        self.template.allowed_coaches.add(self.coach)
        self.assert_allowed()

    def test_rejected_coach_cannot_be_reintroduced_via_stale_picker(self):
        self.reservation.rejected_coaches.add(self.coach)
        self.assert_rejected('rejected')

    def test_all_applicable_reasons_are_returned_together(self):
        self.coach.campuses.set([self.other_campus])
        self.coach.coachresort_set.update(resort=self.other_resort)
        self.coach.languages = ['en']
        self.coach.availability_status = 'unavailable'
        self.coach.save(update_fields=['languages', 'availability_status'])
        self.assert_rejected('campus_mismatch', 'missing_resort', 'missing_language', 'unavailable_status')

    def test_candidate_names_stay_within_tenant_and_staff_scope(self):
        Coach.objects.create(client=self.other_tenant, name='外校教練')
        other_campus = fixtures.OrderAssignmentScopeTests.coach(self, campus=self.other_campus)
        result = self.candidates()
        self.assertEqual([row['id'] for row in result['available_coaches']], [self.coach.pk])
        self.assertEqual([row['id'] for row in result['unavailable_coaches']], [other_campus.pk])

        user = User.objects.create_user('order-editor')
        profile = TenantStaffMembership.objects.create(
            client=self.tenant, user=user, is_manager=True, role='assistant',
            all_campuses=False, admin_permissions=['order_view', 'order_edit'],
        )
        profile.campuses.add(self.campus)
        self.api.force_authenticate(user)
        result = self.candidates()
        self.assertEqual([row['id'] for row in result['available_coaches']], [self.coach.pk])
        self.assertEqual(result['unavailable_coaches'], [])

    def test_candidate_order_prioritizes_status_then_course_order_and_resort_score(self):
        better_score = fixtures.OrderAssignmentScopeTests.coach(self)
        self.coach.coachresort_set.update(assignment_score=10)
        later_course = fixtures.OrderAssignmentScopeTests.coach(self)
        later_course.course_levels.update(course_order=1)
        passive = fixtures.OrderAssignmentScopeTests.coach(self)
        passive.availability_status = 'passive'
        passive.save(update_fields=['availability_status'])
        candidates = self.candidates()['available_coaches']
        self.assertEqual([row['id'] for row in candidates], [better_score.pk, self.coach.pk, later_course.pk, passive.pk])
        self.assertTrue(candidates[-1]['requires_confirmation'])

    def test_candidate_failure_is_distinct_from_empty_success_and_does_not_create_policy(self):
        self.coach.delete()
        self.assertFalse(OperatingPolicy.objects.filter(client=self.tenant).exists())
        empty = self.candidates()
        self.assertEqual(empty['candidate_status'], 'ok')
        self.assertEqual(empty['available_coaches'], [])
        self.assertEqual(empty['unavailable_coaches'], [])
        self.assertFalse(OperatingPolicy.objects.filter(client=self.tenant).exists())

        with patch('booking.scheduler.check_manual_assignment', side_effect=RuntimeError('private detail')):
            with self.assertLogs('API.admin_serializers', level='WARNING'):
                failed = self.candidates()
        self.assertEqual(failed['candidate_status'], 'error')
        self.assertIsNone(failed['available_coaches'])
        self.assertIsNone(failed['unavailable_coaches'])
        self.assertNotIn('private detail', str(failed))

    def test_hidden_or_automatic_disabled_coach_is_still_manually_available(self):
        self.coach.customer_selectable = False
        self.coach.auto_assignment_enabled = False
        self.coach.save(update_fields=['customer_selectable', 'auto_assignment_enabled'])
        self.assert_allowed()

    def test_every_lesson_template_must_be_covered_not_only_group_default(self):
        second_kind = CourseType.objects.create(category=self.kind.category, name='QA另一類課程')
        second = CourseTemplate.objects.create(course_type=second_kind, name='QA另一模板', duration_hours=4)
        second.resorts.add(self.resort)
        Booking.objects.create(reservation=self.reservation, date=self.booking.date + timedelta(days=1),
            start_time=self.booking.start_time, end_time=self.booking.end_time, course_template=second)
        self.assert_rejected('course_type')
        CoachCourseLevel.objects.create(coach=self.coach, course_type=second_kind,
                                         ability_levels=['level6'], price_level='Lv1')
        self.assert_allowed()

    def test_missing_course_metadata_is_rejected_not_silently_assumed_qualified(self):
        self.reservation.course_type = None
        self.reservation.course_template = None
        self.reservation.save()
        self.booking.course_template = None
        self.booking.save(update_fields=['course_template'])
        self.assert_rejected('course_type')

    def test_inactive_catalog_template_does_not_cancel_existing_teaching_qualification(self):
        self.template.is_active = False
        self.template.save(update_fields=['is_active'])
        self.assert_allowed()

    def test_later_lesson_whitelist_is_also_enforced(self):
        other = fixtures.OrderAssignmentScopeTests.coach(self)
        second = CourseTemplate.objects.create(course_type=self.kind, name='QA後堂限定', duration_hours=4)
        second.resorts.add(self.resort)
        second.allowed_coaches.add(other)
        Booking.objects.create(reservation=self.reservation, date=self.booking.date + timedelta(days=1),
            start_time=self.booking.start_time, end_time=self.booking.end_time, course_template=second)
        self.assert_rejected('template_roster')
        second.allowed_coaches.add(self.coach)
        self.assert_allowed()

    def test_foreign_tenant_lesson_template_is_not_a_qualification_source(self):
        category = CourseCategory.objects.create(client=self.other_tenant, name='QA其他公司')
        kind = CourseType.objects.create(category=category, name='QA其他類型')
        foreign = CourseTemplate.objects.create(course_type=kind, name='QA其他模板', duration_hours=4)
        CoachCourseLevel.objects.create(coach=self.coach, course_type=kind, ability_levels=['level6'], price_level='Lv1')
        self.booking.course_template = foreign
        self.booking.save(update_fields=['course_template'])
        self.assert_rejected('course_type')

    def test_lesson_template_supplies_type_when_old_group_type_is_missing(self):
        self.reservation.course_type = None
        self.reservation.course_template = None
        self.reservation.save()
        self.assert_allowed()

    def test_one_unqualified_reservation_rejects_the_whole_batch(self):
        second = Reservation.objects.create(group=self.group, resort=self.resort, course_type=self.kind,
            course_template=self.template, language='en', max_ability_level='level3', status='created')
        slot = Booking.objects.create(reservation=second, date=self.booking.date + timedelta(days=1),
            start_time=self.booking.start_time, end_time=self.booking.end_time, course_template=self.template)
        response = self.api.put(self.url, {'action': 'save', 'payment_status': 'paid', 'reservation_updates': [
            {'reservation_id': self.reservation.pk, 'coach_id': self.coach.pk},
            {'reservation_id': second.pk, 'coach_id': self.coach.pk},
        ]}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        for reservation in (self.reservation, second):
            reservation.refresh_from_db()
            self.assertIsNone(reservation.preferred_coach_id)
        self.booking.refresh_from_db()
        slot.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertFalse(self.booking.is_scheduled)
        self.assertFalse(slot.is_scheduled)
        self.assertEqual(self.payment.status, 'pending')
        self.assertFalse(OrderRevision.objects.filter(group=self.group).exists())

    def test_payment_only_does_not_rewrite_existing_assignment_when_qualifications_change(self):
        self.reservation.preferred_coach = self.coach
        self.reservation.status = 'manually_assigned'
        self.reservation.save()
        self.booking.is_scheduled = True
        self.booking.save()
        self.coach.languages = ['en']
        self.coach.save(update_fields=['languages'])
        response = self.assign()  # Same coach: only the payment status actually changes.
        self.assertEqual(response.status_code, 200, response.data)
        self.reservation.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, self.coach.pk)
        self.assertEqual(self.reservation.status, 'manually_assigned')
        self.assertTrue(self.booking.is_scheduled)
