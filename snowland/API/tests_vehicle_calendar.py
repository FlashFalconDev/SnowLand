from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Coach.vehicle_models import Vehicle, VehicleTrip
from Coach.vehicle_payroll import JAPAN_TIME
from Resorts.models import Campus, Resorts

from .tests_vehicles import vehicle_fixture


class VehicleCalendarTests(TestCase):
    url = '/api/admin/qa-vehicles/coach/vehicles/'
    today = datetime(2026, 11, 26, 8, tzinfo=JAPAN_TIME)
    start = datetime(2026, 12, 1, 9, tzinfo=JAPAN_TIME)

    @classmethod
    def setUpTestData(cls):
        cls.tenant, cls.campus, cls.west, cls.resort, _, coaches, _, _ = vehicle_fixture()
        cls.coach, cls.driver, cls.west_coach = coaches
        cls.vehicle = Vehicle.objects.create(campus=cls.campus, name='QA Van', plate='CAL-01')
        cls.module = ModuleInfo.objects.create(module_sid='vehicle_review', module_name='車輛排班與用車審核')

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.coach.user)

    def desk(self, **dates):
        with patch('API.vehicle_views.timezone.now', return_value=self.today):
            response = self.api.get(self.url, dates)
        self.assertEqual(response.status_code, 200, response.data)
        return response.json()['data']

    def trip(self, *, start=None, hours=1, **overrides):
        start = start or self.start
        fields = {'campus': self.campus, 'driver': self.driver, 'vehicle': self.vehicle,
                  'purpose': 'business', 'status': 'approved'}
        return VehicleTrip.objects.create(starts_at=start, ends_at=start + timedelta(hours=hours),
                                          **{**fields, **overrides})

    def set_config(self, config):
        ModuleSetting.objects.update_or_create(
            client=self.tenant, module=self.module, defaults={'settings': config},
        )

    def test_default_and_invalid_settings_show_calendar(self):
        self.assertIsNotNone(self.desk()['vehicle_calendar'])
        key = 'vehicle_calendar_visible_to_coaches'
        for config in ({}, [], {key: ''}, {key: None}, {key: 'unknown'}, {key: {}}, {key: True}):
            with self.subTest(config=config):
                self.set_config(config)
                self.assertEqual(self.desk()['vehicle_calendar']['vehicles'][0]['id'], self.vehicle.pk)

    def test_explicit_false_hides_calendar_and_preserves_personal_records(self):
        self.trip(note='其他教練的用車備註')
        owned = self.trip(driver=self.coach, purpose='private', note='本人駕駛的備註')
        shared = self.trip(purpose='private', note='本人同行的備註')
        shared.participants.add(self.coach)
        for value in (False, 0, ' False ', 'OFF', 'no', '0'):
            with self.subTest(value=value):
                self.set_config({'vehicle_calendar_visible_to_coaches': value})
                data = self.desk()
                self.assertIsNone(data['vehicle_calendar'])
                self.assertEqual(data['vehicles'], [])
                personal_notes = {trip['id']: trip['note'] for trip in data['trips']}
                self.assertEqual(personal_notes, {owned.pk: owned.note, shared.pk: shared.note})

    def test_calendar_returns_course_resort_and_only_times_for_private_or_no_resort(self):
        self.trip(purpose='lesson', resort=self.resort)
        private = self.trip(start=self.start + timedelta(hours=2), status='driving', purpose='private',
                            resort=self.resort, note='行程申請原因', decision_note='內部處理原因')
        private.participants.add(self.west_coach)
        self.trip(start=self.start + timedelta(hours=4), purpose='lesson')
        data = self.desk()
        self.assertEqual(data['trips'], [])
        self.assertEqual(data['vehicles'], [])
        vehicle, = data['vehicle_calendar']['vehicles']
        self.assertEqual((vehicle['id'], vehicle['name'], vehicle['plate']), (self.vehicle.pk, 'QA Van', 'CAL-01'))
        lesson, private_interval, no_resort = vehicle['occupancy']
        self.assertEqual(set(lesson), {'starts_at', 'ends_at', 'resort'})
        self.assertEqual(lesson['resort'], self.resort.display_name)
        for interval, start in ((private_interval, private.starts_at), (no_resort, self.start + timedelta(hours=4))):
            self.assertEqual(set(interval), {'starts_at', 'ends_at'})
            self.assertEqual(datetime.fromisoformat(interval['starts_at']), start)
            self.assertEqual(datetime.fromisoformat(interval['ends_at']), start + timedelta(hours=1))

    def test_calendar_scope_applies_to_both_shared_vehicles_and_trips(self):
        other_tenant = Client.objects.create(name='QA Other Fleet', internal_code='qa-other-fleet')
        other_campus = Campus.objects.create(client=other_tenant, name='QA 其他租戶', code='other')
        other_resort = Resorts.objects.create(client=other_tenant, name='Other', display_name='QA 外校雪場')
        ModuleSetting.objects.create(client=other_tenant, module=self.module,
                                     settings={'vehicle_calendar_visible_to_coaches': False})
        foreign_vehicle = Vehicle.objects.create(campus=other_campus, name='QA 外租戶車', plate='CAL-02')
        foreign_vehicle.shared_campuses.add(self.campus)
        Vehicle.objects.create(campus=self.west, name='QA 西校專用車', plate='CAL-03')
        shared_vehicle = Vehicle.objects.create(campus=self.west, name='QA 西校共用車', plate='CAL-04')
        shared_vehicle.shared_campuses.add(self.campus)
        self.vehicle.shared_campuses.add(self.west)
        self.trip(campus=self.west, driver=self.west_coach)
        self.trip(campus=other_campus, vehicle=self.vehicle)
        self.trip(vehicle=foreign_vehicle)
        self.trip(vehicle=shared_vehicle, purpose='lesson', resort=other_resort)
        calendar = self.desk()['vehicle_calendar']
        vehicles = {vehicle['id']: vehicle['occupancy'] for vehicle in calendar['vehicles']}
        self.assertEqual(vehicles.keys(), {self.vehicle.pk, shared_vehicle.pk})
        self.assertEqual(vehicles[self.vehicle.pk], [])
        interval, = vehicles[shared_vehicle.pk]
        self.assertEqual(set(interval), {'starts_at', 'ends_at'})
        scoped = self.api.get(self.url, {'from': '2026-12-01', 'to': '2026-12-01'},
                              HTTP_X_CAMPUS_ID=str(self.west.pk))
        self.assertEqual(scoped.status_code, 200)
        self.assertEqual(scoped.json()['data']['vehicle_calendar']['vehicles'], calendar['vehicles'])
        self.assertEqual(self.api.get('/api/admin/qa-other-fleet/coach/vehicles/').status_code, 403)

    def test_date_filters_use_japan_days_and_only_include_assigned_live_occupancy(self):
        midnight = self.start.replace(hour=0)
        self.trip(start=midnight - timedelta(hours=1))
        spanning = self.trip(start=midnight - timedelta(hours=1), hours=2)
        self.trip(start=midnight + timedelta(days=1))
        self.trip(status='pending')
        self.trip(status='rejected')
        self.trip(status='driving', vehicle=None)
        self.trip(status='approved', is_deleted=True)
        self.trip(status='returned')
        historical = [
            self.trip(start=self.today - timedelta(days=1) + timedelta(hours=hour), status=status)
            for hour, status in enumerate(('returned', 'reviewed', 'settled'))
        ]
        default = self.desk()['vehicle_calendar']
        self.assertEqual((default['from'], default['to']), ('2026-11-26', '2026-12-09'))
        self.assertEqual(len(default['vehicles'][0]['occupancy']), 3)
        same_day = self.desk(**{'from': '2026-12-01', 'to': '2026-12-01'})['vehicle_calendar']
        slot, = same_day['vehicles'][0]['occupancy']
        self.assertEqual(datetime.fromisoformat(slot['starts_at']), spanning.starts_at)
        self.assertEqual(datetime.fromisoformat(slot['ends_at']), spanning.ends_at)
        past = self.desk(to='2026-11-25')['vehicle_calendar']
        self.assertEqual((past['from'], past['to']), ('2026-11-12', '2026-11-25'))
        self.assertEqual([datetime.fromisoformat(slot['starts_at']) for slot in past['vehicles'][0]['occupancy']],
                         [trip.starts_at for trip in historical])
        from_only = self.desk(**{'from': '2026-12-01'})['vehicle_calendar']
        self.assertEqual((from_only['from'], from_only['to']), ('2026-12-01', '2026-12-14'))
