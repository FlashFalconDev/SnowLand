from datetime import timedelta

from django.test import TestCase

from API import tests_order_assignment_scope as fixtures
from Coach.models import CoachCourseLevel
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from booking.models import Booking, OrderRevision, Reservation


class ManualAssignmentQualificationTests(TestCase):
    def setUp(self):
        fixtures.OrderAssignmentScopeTests.setUp(self)
        self.reservation.max_ability_level = 'level3'
        self.reservation.save()
        self.coach = fixtures.OrderAssignmentScopeTests.coach(self)
        self.level = CoachCourseLevel.objects.get(coach=self.coach, course_type=self.kind)

    def offered(self):
        response = self.api.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id'] for row in response.data['data']['reservations'][0]['available_coaches']}

    def assign(self):
        return self.api.put(self.url, {'action': 'save', 'payment_status': 'paid',
            'reservation_updates': [{'reservation_id': self.reservation.pk, 'coach_id': self.coach.pk}]}, format='json')

    def assert_rejected(self):
        self.assertNotIn(self.coach.pk, self.offered())
        response = self.assign()
        self.assertEqual(response.status_code, 400, response.data)
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
        self.assert_rejected()

    def test_insufficient_ability_is_rejected_then_restoring_ability_works(self):
        self.level.ability_levels = ['level1']
        self.level.save(update_fields=['ability_levels'])
        self.assert_rejected()
        self.level.ability_levels = ['level6']
        self.level.save(update_fields=['ability_levels'])
        self.assert_allowed()

    def test_removed_course_qualification_is_rejected(self):
        self.level.delete()
        self.assert_rejected()

    def test_template_minimum_coach_level_is_enforced(self):
        self.template.minimum_coach_price_level = 'director'
        self.template.save(update_fields=['minimum_coach_price_level'])
        self.assert_rejected()
        self.level.price_level = 'director'
        self.level.save(update_fields=['price_level'])
        self.assert_allowed()

    def test_template_coach_whitelist_cannot_be_bypassed(self):
        other = fixtures.OrderAssignmentScopeTests.coach(self)
        self.template.allowed_coaches.add(other)
        self.assert_rejected()
        self.template.allowed_coaches.add(self.coach)
        self.assert_allowed()

    def test_rejected_coach_cannot_be_reintroduced_via_stale_picker(self):
        self.reservation.rejected_coaches.add(self.coach)
        self.assert_rejected()

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
        self.assert_rejected()
        CoachCourseLevel.objects.create(coach=self.coach, course_type=second_kind,
                                         ability_levels=['level6'], price_level='Lv1')
        self.assert_allowed()

    def test_missing_course_metadata_is_rejected_not_silently_assumed_qualified(self):
        self.reservation.course_type = None
        self.reservation.course_template = None
        self.reservation.save()
        self.booking.course_template = None
        self.booking.save(update_fields=['course_template'])
        self.assert_rejected()

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
        self.assert_rejected()
        second.allowed_coaches.add(self.coach)
        self.assert_allowed()

    def test_foreign_tenant_lesson_template_is_not_a_qualification_source(self):
        category = CourseCategory.objects.create(client=self.other_tenant, name='QA其他公司')
        kind = CourseType.objects.create(category=category, name='QA其他類型')
        foreign = CourseTemplate.objects.create(course_type=kind, name='QA其他模板', duration_hours=4)
        CoachCourseLevel.objects.create(coach=self.coach, course_type=kind, ability_levels=['level6'], price_level='Lv1')
        self.booking.course_template = foreign
        self.booking.save(update_fields=['course_template'])
        self.assert_rejected()

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
