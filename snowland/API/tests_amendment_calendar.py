import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from API import tests_order_amendment_confirm as fixtures
from Coach.models import Coach, CoachCourseLevel, CoachLeaveRequest, CoachResort
from booking.models import OrderAmendment


class AmendmentCalendarTests(TestCase):
    setUp = fixtures.OrderAmendmentConfirmTests.setUp

    def scheduled_coach(self):
        coach = Coach.objects.create(client=self.tenant, name='QA改期教練', languages=['zh'])
        coach.campuses.add(self.campus_a)
        CoachResort.objects.create(coach=coach, resort=self.resort_a)
        CoachCourseLevel.objects.create(coach=coach, course_type=self.template.course_type,
            ability_levels=['level6'], price_level='Lv1')
        self.reservation.preferred_coach = coach
        self.reservation.status = 'manually_assigned'
        self.reservation.save()
        self.booking.is_scheduled = True
        self.booking.save()
        return coach

    def body(self, day):
        draft = {'changes': [{'reservation_id': self.reservation.pk, 'number_of_people': 1,
            'language': 'zh', 'equipment': None, 'is_preferred_coach': False, 'preferred_coach_id': None,
            'ability_level_counts': {'no_exp': 1}, 'retained_member_ids': [self.member.pk],
            'courses': [{'booking_id': self.booking.pk, 'template_id': self.template.pk,
                         'date': day.isoformat(), 'start_time': '09:00', 'end_time': '12:00'}]}]}
        preview = self.api.post(self.url, draft, format='json')
        self.assertEqual(preview.status_code, 200, preview.data)
        return {**draft, 'quote_token': preview.data['data']['quote_token'], 'request_key': str(uuid.uuid4()),
                'reason': 'QA客人改期', 'confirmed': True}

    def calendar(self, day):
        response = self.api.get('/api/admin/snowland/bookings/', {'start': day.isoformat(), 'end': day.isoformat()})
        self.assertEqual(response.status_code, 200, response.data)
        return [row for row in response.data['data']['list'] if row['group_id'] == self.group.pk]

    def test_amended_date_leaves_old_day_and_appears_on_new_day_with_same_manual_coach(self):
        coach = self.scheduled_coach()
        new_day = self.day - timedelta(days=1)
        self.assertEqual(len(self.calendar(self.day)), 1)
        response = self.api.post(self.url_confirm, self.body(new_day), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.calendar(self.day), [])
        new = self.calendar(new_day)
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]['coach_id'], coach.pk)
        self.assertTrue(new[0]['is_scheduled'])
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, 'manually_assigned')
        amendment = OrderAmendment.objects.get(group=self.group)
        self.assertEqual(amendment.before_snapshot['reservations'][0]['bookings'][0]['date'], self.day.isoformat())
        self.assertEqual(amendment.revision.snapshot['reservations'][0]['bookings'][0]['date'], new_day.isoformat())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'paid')

    def test_past_date_remains_on_hq_calendar_without_pretending_course_completed(self):
        self.scheduled_coach()
        new_day = timezone.localdate() - timedelta(days=2)
        response = self.api.post(self.url_confirm, self.body(new_day), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(self.calendar(new_day)), 1)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, 'manually_assigned')

    def test_new_date_approved_leave_rejects_atomically_and_keeps_old_calendar(self):
        coach = self.scheduled_coach()
        new_day = self.day - timedelta(days=1)
        body = self.body(new_day)
        CoachLeaveRequest.objects.create(coach=coach, start_date=new_day, end_date=new_day,
            status='approved', reason='QA')
        result = self.api.post(self.url_confirm, body, format='json')
        self.assertEqual(result.status_code, 409, result.data)
        self.assertEqual(len(self.calendar(self.day)), 1)
        self.assertEqual(self.calendar(new_day), [])
        self.assertFalse(OrderAmendment.objects.filter(group=self.group).exists())

    def test_completed_history_rejects_date_edit_instead_of_erasing_course(self):
        self.scheduled_coach()
        self.reservation.status = 'completed'
        self.reservation.save()
        draft = {'changes': [{'reservation_id': self.reservation.pk, 'courses': [{
            'booking_id': self.booking.pk, 'template_id': self.template.pk,
            'date': (self.day-timedelta(days=1)).isoformat(), 'start_time': '09:00', 'end_time': '12:00'}]}]}
        self.assertEqual(self.api.post(self.url, draft, format='json').status_code, 409)
        self.assertEqual(len(self.calendar(self.day)), 1)
        self.assertFalse(OrderAmendment.objects.filter(group=self.group).exists())
        self.assertEqual(self.calendar(self.day)[0]['status'], 'completed')
