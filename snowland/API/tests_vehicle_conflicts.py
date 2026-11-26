from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Coach.vehicle_models import Vehicle, VehicleTrip
from Coach.vehicle_payroll import JAPAN_TIME
from Control.models import TenantStaffMembership
from Resorts.models import Campus

from .tests_vehicles import vehicle_fixture


class VehicleConflictTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant, cls.campus, cls.west, cls.resort, _, coaches, cls.manager, cls.admin = vehicle_fixture()
        cls.driver, cls.rider, cls.west_coach = coaches
        cls.vehicle = Vehicle.objects.create(campus=cls.campus, name='QA Van', plate='QA-01')
        cls.module = ModuleInfo.objects.create(module_sid='vehicle_review', module_name='車輛排班與用車審核')
        cls.finance = User.objects.create_user('qa-fleet-finance')
        TenantStaffMembership.objects.create(
            client=cls.tenant, user=cls.finance, is_manager=True, role='assistant', admin_permissions=['vehicle_finance'],
        )
        cls.other_tenant = Client.objects.create(name='QA Other Fleet', internal_code='qa-other-fleet')
        cls.other_campus = Campus.objects.create(client=cls.other_tenant, name='QA 其他校區', code='other')

    url = '/api/admin/qa-vehicles/vehicles/'
    personal = '/api/admin/qa-vehicles/coach/vehicles/'
    other_url = '/api/admin/qa-other-fleet/vehicles/'
    start = datetime(2026, 12, 1, 9, tzinfo=JAPAN_TIME)

    def setUp(self):
        self.api = APIClient()

    def trip(self, purpose='lesson', status='pending', start=None, hours=4, campus=None, driver=None, **kwargs):
        start = start or self.start
        return VehicleTrip.objects.create(
            campus=campus or self.campus, driver=driver or self.driver,
            purpose=purpose, status=status, starts_at=start, ends_at=start + timedelta(hours=hours), **kwargs,
        )

    def desk(self, user=None, url=None, **filters):
        self.api.force_authenticate(user or self.manager)
        response = self.api.get(url or self.url, filters)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['data']

    def post(self, action, trip, user=None, url=None, expected=200, **kwargs):
        self.api.force_authenticate(user or self.manager)
        response = self.api.post(url or self.url, {'action': action, 'trip': trip.pk, **kwargs}, format='json')
        self.assertEqual(response.status_code, expected, response.data)
        return response.data['data'] if expected == 200 else response.data

    def options(self, data, trip):
        payload = next(row for row in data['trips'] if row['id'] == trip.pk)
        return {option['vehicle']: option for option in payload['vehicle_options']}

    def test_tenant_mode_defaults_and_all_modes_use_the_same_conflict_rules(self):
        ModuleSetting.objects.create(
            client=self.other_tenant, module=self.module, settings={'vehicle_conflict_mode': 'block'},
        )
        self.assertEqual(self.desk(user=self.admin, url=self.other_url)['conflict_mode'], 'block')
        self.assertEqual(self.desk()['conflict_mode'], 'manual_review')
        self.assertFalse(ModuleSetting.objects.filter(client=self.tenant).exists())
        private = self.trip(purpose='private')
        self.post('approve', private, vehicle=self.vehicle.pk)
        lesson = self.trip()
        for config, effective in (
            ({}, 'manual_review'),
            ({'vehicle_conflict_mode': ''}, 'manual_review'),
            ({'vehicle_conflict_mode': None}, 'manual_review'),
            ({'vehicle_conflict_mode': 'unexpected'}, 'manual_review'),
            ({'vehicle_conflict_mode': 'manual_review'}, 'manual_review'),
            ({'vehicle_conflict_mode': 'block'}, 'block'),
            ({'vehicle_conflict_mode': 'auto_revoke'}, 'manual_review'),
        ):
            with self.subTest(config=config):
                ModuleSetting.objects.update_or_create(client=self.tenant, module=self.module, defaults={'settings': config})
                data = self.desk()
                self.assertEqual(data['conflict_mode'], effective)
                conflict = self.options(data, lesson)[self.vehicle.pk]['conflicts'][0]
                self.assertEqual((conflict['trip'], conflict['can_revoke']), (private.pk, True))
                error = str(self.post('approve', lesson, expected=400, vehicle=self.vehicle.pk))
                for detail in ('私用', '2026/12/01 09:00', '2026/12/01 13:00', '請改選其他車輛'):
                    self.assertIn(detail, error)
                private.refresh_from_db()
                self.assertEqual(private.status, 'approved')

    def test_available_alternative_back_to_back_and_archived_trip(self):
        private = self.trip(purpose='private', status='approved', vehicle=self.vehicle)
        lesson = self.trip()
        alternative = Vehicle.objects.create(campus=self.campus, name='QA Spare', plate='QA-02')
        self.trip(purpose='private', status='approved', vehicle=alternative, is_deleted=True)
        adjacent = self.trip(start=private.ends_at)
        data = self.desk()
        self.assertEqual(self.options(data, lesson)[alternative.pk]['conflicts'], [])
        self.assertEqual(self.options(data, adjacent)[self.vehicle.pk]['conflicts'], [])
        self.assertEqual(self.post('approve', lesson, vehicle=alternative.pk)['vehicle'], alternative.pk)
        self.assertEqual(self.post('approve', adjacent, vehicle=self.vehicle.pk)['vehicle'], self.vehicle.pk)

    def test_get_marks_each_visible_conflict_and_only_offers_active_open_vehicles(self):
        first = self.trip(purpose='private', status='approved', hours=1, vehicle=self.vehicle)
        second = self.trip(purpose='private', status='driving', start=first.ends_at, hours=1, vehicle=self.vehicle)
        self.trip(status='returned', hours=1, vehicle=self.vehicle)
        shared = Vehicle.objects.create(campus=self.west, name='QA Shared', plate='QA-02')
        shared.shared_campuses.add(self.campus)
        Vehicle.objects.create(campus=self.west, name='QA West only', plate='QA-03')
        Vehicle.objects.create(campus=self.campus, name='QA Disabled', plate='QA-04', active=False)
        other = Vehicle.objects.create(campus=self.other_campus, name='QA Other tenant', plate='QA-05')
        other.shared_campuses.add(self.campus)
        pending = self.trip()
        options = self.options(self.desk(user=self.admin), pending)
        self.assertEqual(set(options), {self.vehicle.pk, shared.pk})
        self.assertEqual(options[shared.pk]['conflicts'], [])
        self.assertEqual(options[self.vehicle.pk]['conflicts'], [
            {'trip': trip.pk, 'purpose': 'private', 'driver': self.driver.name, 'starts_at': trip.starts_at,
             'ends_at': trip.ends_at, 'can_revoke': can_revoke}
            for trip, can_revoke in ((first, True), (second, False))
        ])
        finance_data = self.desk(user=self.finance)
        self.assertEqual(finance_data['conflict_mode'], 'manual_review')
        self.assertTrue(all('vehicle_options' not in trip for trip in finance_data['trips']))

    def test_conflict_batch_covers_a_pending_trip_past_the_get_date_filter(self):
        pending = self.trip(start=self.start.replace(hour=23))
        next_day = self.trip(purpose='private', status='approved', start=self.start + timedelta(days=1, hours=-9),
                             vehicle=self.vehicle)
        filters = {'to': self.start.date().isoformat()}
        with CaptureQueriesContext(connection) as first:
            data = self.desk(**filters)
        self.assertNotIn(next_day.pk, [row['id'] for row in data['trips']])
        self.assertEqual(self.options(data, pending)[self.vehicle.pk]['conflicts'][0]['trip'], next_day.pk)
        for _ in range(3):
            self.trip()
        with CaptureQueriesContext(connection) as more:
            self.desk(**filters)
        self.assertEqual(len(more), len(first))

    def test_shared_vehicle_conflict_is_blocked_without_leaking_outside_campus(self):
        self.vehicle.shared_campuses.add(self.west)
        private = self.trip(purpose='private', status='approved', campus=self.west, driver=self.west_coach, vehicle=self.vehicle)
        lesson = self.trip()
        options = self.options(self.desk(), lesson)
        self.assertEqual(options[self.vehicle.pk], {
            'vehicle': self.vehicle.pk, 'occupied_outside_scope': True, 'conflicts': [],
        })
        error = str(self.post('approve', lesson, expected=400, vehicle=self.vehicle.pk))
        self.assertIn('其他校區', error)
        for hidden in ('私用', '09:00', self.west_coach.name):
            self.assertNotIn(hidden, error)
        error = self.post('revoke', private, expected=404, note='QA 改排')
        self.assertEqual(error['detail'], '找不到可操作的用車行程')
        private.refresh_from_db()
        self.assertEqual((private.status, private.decision_note), ('approved', ''))

    def test_revocation_releases_vehicle_and_is_visible_to_driver_and_rider(self):
        private = self.trip(purpose='private', status='approved', vehicle=self.vehicle, approved_by=self.admin)
        private.participants.add(self.rider)
        lesson = self.trip()
        reason = '課' * 500
        result = self.post('revoke', private, note=f' {reason}  ')
        self.assertEqual((result['status'], result['revoked'], result['decision_note']), ('rejected', True, reason))
        private.refresh_from_db()
        self.assertEqual((private.vehicle, private.approved_by, private.reviewed_by), (self.vehicle, self.admin, self.manager))
        self.assertEqual(self.options(self.desk(), lesson)[self.vehicle.pk]['conflicts'], [])
        self.assertEqual(self.post('approve', lesson, vehicle=self.vehicle.pk)['status'], 'approved')
        for coach, owner in ((self.driver, True), (self.rider, False)):
            data = self.desk(user=coach.user, url=self.personal)
            self.assertIsNone(data['conflict_mode'])
            trip = next(row for row in data['trips'] if row['id'] == private.pk)
            self.assertTrue(trip['revoked'])
            self.assertEqual((trip['owner'], trip['decision_note']), (owner, reason))
            self.assertNotIn('vehicle_options', trip)
            self.assertFalse(trip['can_revoke'])

    def test_revocation_is_recorded_even_when_an_old_approved_trip_has_no_vehicle(self):
        private = self.trip(purpose='private', status='approved')
        result = self.post('revoke', private, note='QA 改排')
        self.assertTrue(result['revoked'])
        self.assertIsNone(result['vehicle'])

    def test_revocation_rejects_missing_invalid_or_too_long_reason(self):
        private = self.trip(purpose='private', status='approved', vehicle=self.vehicle)
        for payload in ({}, {'note': None}, {'note': ' \t '}, {'note': 123}, {'note': '課' * 501}):
            with self.subTest(payload=payload):
                self.assertIn('1 至 500 字', str(self.post('revoke', private, expected=400, **payload)))
        private.refresh_from_db()
        self.assertEqual((private.status, private.decision_note), ('approved', ''))

    def test_revocation_rejects_trips_outside_approved_unstarted_private_state(self):
        for status in ('driving', 'returned', 'reviewed', 'settled'):
            with self.subTest(status=status):
                private = self.trip(purpose='private', status=status, vehicle=self.vehicle)
                self.assertIn('已出車', str(self.post('revoke', private, expected=400, note='QA 改排')))
                private.refresh_from_db()
                self.assertEqual((private.status, private.decision_note), (status, ''))
        lesson = self.trip(status='approved', vehicle=self.vehicle)
        self.assertIn('僅可撤銷私用', str(self.post('revoke', lesson, expected=400, note='QA 改排')))
        lesson.refresh_from_db()
        self.assertEqual((lesson.status, lesson.decision_note), ('approved', ''))
        pending = self.trip(purpose='private')
        self.assertIn('僅可撤銷已排車', str(self.post('revoke', pending, expected=400, note='QA 改排')))
        self.assertFalse(self.post('reject', pending, note='QA 退回')['revoked'])

    def test_revocation_requires_review_access_and_the_same_tenant(self):
        private = self.trip(purpose='private', status='approved', vehicle=self.vehicle)
        for user in (self.driver.user, self.finance):
            self.post('revoke', private, user=user, expected=403, note='QA 改排')
        self.post('revoke', private, url=self.other_url, expected=403, note='QA 改排')
        error = self.post('revoke', private, user=self.admin, url=self.other_url, expected=404, note='QA 改排')
        self.assertEqual(error['detail'], '找不到可操作的用車行程')
        private.refresh_from_db()
        self.assertEqual((private.status, private.decision_note), ('approved', ''))

    def test_legacy_reject_of_approved_private_trip_uses_revocation_rules(self):
        private = self.trip(purpose='private', status='approved', vehicle=self.vehicle)
        self.assertIn('撤銷原因', str(self.post('reject', private, expected=400, note=' ')))
        result = self.post('reject', private, note=' 改排課程 ')
        self.assertEqual((result['revoked'], result['decision_note']), (True, '改排課程'))
