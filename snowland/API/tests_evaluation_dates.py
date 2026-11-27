from datetime import date, datetime, time, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Control.models import TenantStaffMembership
from Resorts.models import Campus
from booking.models import Booking, CourseEvaluation, LearnerProfile, MemberDetail, Reservation, ReservationGroup


UTC = datetime_timezone.utc
TODAY = date(2026, 11, 27)
TAIPEI_MIDNIGHT = datetime(2026, 11, 26, 16, tzinfo=UTC)


class EvaluationDateTests(TestCase):
    url = '/api/admin/snowland/evaluations/'

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        cls.other_tenant = Client.objects.create(name='Other', internal_code='other')
        cls.campus = Campus.objects.create(client=cls.tenant, name='A 校區', code='a')
        cls.other_campus = Campus.objects.create(client=cls.tenant, name='B 校區', code='b')
        cls.assistant = User.objects.create_user('qa-date-assistant')
        profile = TenantStaffMembership.objects.create(
            user=cls.assistant, client=cls.tenant, is_manager=True, role='assistant',
            all_campuses=False, admin_permissions=['evaluations'],
        )
        profile.campuses.add(cls.campus)
        cls.hq = User.objects.create_superuser('qa-date-hq')

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.assistant)

    def make_evaluation(self, ordered_at=TAIPEI_MIDNIGHT, lesson_date=TODAY, *, group=None,
                        tenant=None, campus=None, order_number='QA-DATE', member=None):
        if group is None:
            group = ReservationGroup.objects.create(
                client=tenant or self.tenant, campus=campus or self.campus, order_number=order_number,
            )
            ReservationGroup.objects.filter(pk=group.pk).update(created_at=ordered_at)
        reservation = Reservation.objects.create(group=group, status='completed')
        booking = Booking.objects.create(
            reservation=reservation, date=lesson_date, start_time=time(9), end_time=time(12),
        )
        learner = MemberDetail.objects.create(reservation=reservation, **(member or {}))
        return CourseEvaluation.objects.create(booking=booking, member=learner)

    def list_data(self, **params):
        with patch('django.utils.timezone.now', return_value=TAIPEI_MIDNIGHT + timedelta(hours=1)):
            response = self.api.get(self.url, params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['data']

    def assert_rows(self, data, *rows):
        self.assertEqual([row['id'] for row in data['list']], [evaluation.pk for evaluation in rows])

    def test_default_uses_thirty_taipei_order_dates_and_groups_same_order(self):
        newer = self.make_evaluation(lesson_date=TODAY - timedelta(days=4))
        same_order_later_lesson = self.make_evaluation(group=newer.booking.reservation.group)
        first_in_window = self.make_evaluation(TAIPEI_MIDNIGHT - timedelta(days=29))
        self.make_evaluation(TAIPEI_MIDNIGHT - timedelta(days=29, microseconds=1))
        self.make_evaluation(TAIPEI_MIDNIGHT + timedelta(days=1))

        with timezone.override('UTC'):
            data = self.list_data()
        self.assert_rows(data, same_order_later_lesson, newer, first_in_window)
        self.assertEqual(data['date_filters'], {
            'date_field': 'ordered', 'date_from': TODAY - timedelta(days=29), 'date_to': TODAY,
        })
        self.assertEqual(data['list'][1]['order_date'], TODAY.isoformat())
        self.assertEqual(data['list'][1]['course_date'], '2026-11-23')
        self.assertFalse(data['list'][1]['can_edit_assessment'])

    def test_order_range_includes_both_taipei_days_and_excludes_adjacent_midnights(self):
        self.make_evaluation(TAIPEI_MIDNIGHT - timedelta(microseconds=1))
        start = self.make_evaluation(TAIPEI_MIDNIGHT)
        end = self.make_evaluation(TAIPEI_MIDNIGHT + timedelta(days=2, microseconds=-1))
        self.make_evaluation(TAIPEI_MIDNIGHT + timedelta(days=2))
        data = self.list_data(date_field='ordered', date_from='2026-11-27', date_to='2026-11-28')
        self.assert_rows(data, end, start)
        self.assertEqual([row['order_date'] for row in data['list']], ['2026-11-28', '2026-11-27'])

    def test_lesson_mode_uses_inclusive_lesson_dates_with_old_orders(self):
        old_order = TAIPEI_MIDNIGHT - timedelta(days=60)
        first = self.make_evaluation(lesson_date=TODAY - timedelta(days=1))
        last = self.make_evaluation(old_order)
        self.make_evaluation(lesson_date=TODAY - timedelta(days=2))
        self.make_evaluation(lesson_date=TODAY + timedelta(days=1))
        data = self.list_data(date_field='lesson', date_from='2026-11-26', date_to='2026-11-27')
        self.assert_rows(data, last, first)
        self.assertEqual(data['date_filters']['date_field'], 'lesson')
        self.assertEqual(data['list'][0]['order_date'], '2026-09-28')

    def test_keyword_filters_order_number_and_member_names_before_pagination(self):
        account = User.objects.create_user('qa-date-member', first_name='Test', last_name='Skier')
        learner = LearnerProfile.objects.create(client=self.tenant, owner=account, name='林學員')
        insurance = self.make_evaluation(order_number='QA-INS', member={'insurance_data': {'full_name': '陳學員'}})
        linked = self.make_evaluation(member={'guardian': account, 'learner': learner})
        user = self.make_evaluation(member={'user': account})
        fallback = self.make_evaluation(order_number='')
        ReservationGroup.objects.filter(pk=fallback.booking.reservation.group_id).update(order_number='')
        self.make_evaluation(TAIPEI_MIDNIGHT - timedelta(days=45), order_number='QA-INS-OLD')

        for search, match in [('qa-ins', insurance), ('陳學', insurance), ('林學', linked), ('Test Skier', user),
                              (f'訂單 #{fallback.booking.reservation.group_id}', fallback)]:
            with self.subTest(search=search):
                data = self.list_data(search=search, page_size=1)
                self.assert_rows(data, match)
                self.assertEqual(data['total'], 1)

    def test_scope_applies_to_search_counts_pages_and_booking_links(self):
        own = self.make_evaluation()
        other_campus = self.make_evaluation(campus=self.other_campus)
        foreign_campus = Campus.objects.create(client=self.other_tenant, name='外部校區', code='outside')
        foreign = self.make_evaluation(tenant=self.other_tenant, campus=foreign_campus)
        data = self.list_data(search='QA-DATE', page_size=1)
        self.assert_rows(data, own)
        self.assertEqual((data['total'], data['total_pages']), (1, 1))
        for excluded in (other_campus, foreign):
            self.assert_rows(self.list_data(booking=excluded.booking_id))
            self.assertEqual(self.api.get(f'{self.url}{excluded.pk}/').status_code, 404)
        self.assertEqual(self.api.get(self.url, HTTP_X_CAMPUS_ID=str(self.other_campus.pk)).status_code, 403)

        self.api.force_authenticate(self.hq)
        self.assert_rows(self.list_data(), other_campus, own)
        self.assert_rows(self.list_data(booking=foreign.booking_id))

    def test_old_booking_link_and_detail_ignore_the_default_range(self):
        historical = self.make_evaluation(TAIPEI_MIDNIGHT - timedelta(days=90))
        self.assert_rows(self.list_data())
        self.assert_rows(self.list_data(booking=historical.booking_id), historical)
        self.assertEqual(self.api.get(f'{self.url}{historical.pk}/').status_code, 200)

    def test_stable_pages_and_query_count_with_linked_learners(self):
        account = User.objects.create_user('qa-date-guardian')
        learner = LearnerProfile.objects.create(client=self.tenant, owner=account, name='同訂單學員')
        first = self.make_evaluation(member={'guardian': account, 'learner': learner})
        rows = [first] + [self.make_evaluation(group=first.booking.reservation.group,
                member={'guardian': account, 'learner': learner}) for _ in range(11)]
        with CaptureQueriesContext(connection) as single:
            self.assert_rows(self.list_data(page_size=1), rows[-1])
        with CaptureQueriesContext(connection) as many:
            page = self.list_data()
            self.assert_rows(page, *list(reversed(rows[2:])))
        self.assertEqual(len(many), len(single))
        self.assertEqual((page['total'], page['page'], page['page_size'], page['total_pages']), (12, 1, 10, 2))
        self.assertEqual(page['list'][0]['member_name'], '同訂單學員')
        self.assert_rows(self.list_data(page=2), rows[1], rows[0])
        self.assertEqual(self.list_data(page=50)['page'], 2)

    def test_invalid_filters_return_field_errors(self):
        for params, field in [({'date_field': 'unknown'}, 'date_field'), ({'date_to': '2026-02-30'}, 'date_to'),
                              ({'date_from': '2026-11-28', 'date_to': '2026-11-27'}, 'date_to'),
                              ({'booking': 'invalid'}, 'booking')]:
            with self.subTest(params=params):
                response = self.api.get(self.url, params)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

    def test_tenant_can_override_defaults_or_restore_legacy_list(self):
        module = ModuleInfo.objects.create(module_sid='booking', module_name='訂課')
        config = ModuleSetting.objects.create(client=self.tenant, module=module, settings={
            'evaluation_default_date_field': 'lesson', 'evaluation_default_date_range_days': 3,
        })
        latest_order = self.make_evaluation(lesson_date=TODAY - timedelta(days=5))
        latest_lesson = self.make_evaluation(TAIPEI_MIDNIGHT - timedelta(days=90))
        revised = self.list_data()
        self.assert_rows(revised, latest_lesson)
        self.assertEqual(revised['date_filters']['date_from'], TODAY - timedelta(days=2))

        config.settings = {'evaluation_date_filters_enabled': False}
        config.save(update_fields=['settings'])
        legacy = self.list_data()
        self.assert_rows(legacy, latest_lesson, latest_order)
        self.assertEqual(set(legacy), {'list', 'total'})
