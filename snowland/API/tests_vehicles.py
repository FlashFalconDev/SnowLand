from datetime import date, datetime, timedelta
from io import BytesIO
import json
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, CoachPayRule, PayrollLine, PayrollStatement
from Coach.payroll_review import publish_statement
from Coach.payroll_settlement import save_settlement
from Coach.vehicle_models import Vehicle, VehicleCharge, VehiclePolicy, VehicleTrip
from Coach.vehicle_payroll import JAPAN_TIME, charge_balance
from Control.models import TenantStaffMembership
from Resorts.models import Campus, Resorts


def vehicle_fixture():
    tenant = Client.objects.create(name='QA Vehicle', internal_code='qa-vehicles')
    campus = Campus.objects.create(client=tenant, name='QA 本校', code='home')
    west = Campus.objects.create(client=tenant, name='QA 西校', code='west')
    resort = Resorts.objects.create(client=tenant, name='Furano', display_name='QA 富良野')
    hoshino = Resorts.objects.create(client=tenant, name='Tomamu', display_name='星野 Tomamu')
    campus.resorts.add(resort, hoshino)
    west.resorts.add(resort)
    coaches = []
    for index, name in enumerate(('QA 駕駛教練', 'QA 同行教練', 'QA 西校教練')):
        user = User.objects.create_user('qa-driver-' + str(index))
        coach = Coach.objects.create(client=tenant, user=user, name=name)
        coach.campuses.add(west if index == 2 else campus)
        TenantStaffMembership.objects.create(client=tenant, user=user, is_coach=True, role='coach')
        CoachPayRule.objects.create(coach=coach, discipline='ski', hourly_rate=1000)
        coaches.append(coach)
    manager = User.objects.create_user('qa-fleet-manager')
    membership = TenantStaffMembership.objects.create(
        client=tenant, user=manager, is_manager=True, role='campus_manager', admin_permissions=['vehicle_review'])
    membership.campuses.add(campus)
    admin = User.objects.create_superuser('qa-fleet-admin')
    return tenant, campus, west, resort, hoshino, coaches, manager, admin


def png_bytes():
    stream = BytesIO()
    Image.new('RGB', (24, 24), 'purple').save(stream, format='PNG')
    return stream.getvalue()


class VehicleTests(TestCase):
    def setUp(self):
        self.tenant, self.campus, self.west, self.resort, self.hoshino, coaches, self.manager, self.admin = vehicle_fixture()
        self.driver, self.rider, self.west_coach = coaches
        self.url = '/api/admin/qa-vehicles/vehicles/'
        self.personal = '/api/admin/qa-vehicles/coach/vehicles/'
        self.vehicle = Vehicle.objects.create(campus=self.campus, name='QA Van', plate='QA-01')
        self.policy = VehiclePolicy.objects.create(client=self.tenant, yen_per_km=45, yen_per_twd=5, payroll_day=10)
        self.policy.exempt_resorts.add(self.hoshino)
        self.start = datetime(2026, 12, 1, 9, tzinfo=JAPAN_TIME)
        self.api = APIClient()
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        storage = override_settings(PRIVATE_COURSE_MEDIA_ROOT=directory.name)
        storage.enable()
        self.addCleanup(storage.disable)

    def post(self, action, user, url=None, expected=200, **data):
        self.api.force_authenticate(user)
        response = self.api.post(url or self.url, {'action': action, **data}, format='json')
        self.assertEqual(response.status_code, expected, response.data)
        return response.data['data'] if expected < 300 else None

    def request(self, purpose='private', expected=201, start=None, user=None, campus=None, **data):
        start = start or self.start
        return self.post('request', user or self.driver.user, self.personal, expected, purpose=purpose,
                         campus=(campus or self.campus).pk, starts_at=start.isoformat(),
                         ends_at=(start + timedelta(hours=4)).isoformat(), **data)

    def record(self, action, trip, km, expected=200, expenses=None, receipt=True):
        self.api.force_authenticate(self.driver.user)
        upload = lambda name: SimpleUploadedFile(name + '.png', png_bytes(), 'image/png')
        data = {'action': action, 'trip': trip, 'km': km, 'photo': upload('mileage')}
        if expenses is not None:
            data['expenses'] = json.dumps(expenses)
            if receipt:
                data['receipt_0'] = upload('receipt')
        approved_start = VehicleTrip.objects.get(pk=trip).starts_at
        with patch('API.vehicle_views.timezone.now', return_value=approved_start):
            response = self.api.post(self.personal, data, format='multipart')
        self.assertEqual(response.status_code, expected, response.data)
        return response.data['data'] if expected < 300 else None

    def test_private_with_receipts_review_and_payroll(self):
        trip = self.request(participants=[self.rider.pk])['id']
        self.post('approve', self.driver.user, expected=403, trip=trip, vehicle=self.vehicle.pk)
        self.post('approve', self.manager, trip=trip, vehicle=self.vehicle.pk)
        self.record('depart', trip, '100')
        self.record('return', trip, '99', expected=400)
        rows = [{'kind': 'fuel', 'amount_yen': '500'}, {'kind': 'toll', 'amount_yen': '300'}]
        self.record('return', trip, '121', expected=400, expenses=rows, receipt=False)
        result = self.record('return', trip, '120', expenses=rows)
        self.assertEqual([row['reimbursable'] for row in result['expenses']], [True, False])
        self.post('review', self.manager, trip=trip)
        self.record('return', trip, '122')
        self.post('settle', self.admin, expected=400, trip=trip)
        self.post('review', self.manager, trip=trip)
        self.post('settle', self.manager, expected=403, trip=trip)
        with patch('API.vehicle_views.timezone.now', return_value=self.start):
            result = self.post('settle', self.admin, trip=trip)
        self.assertEqual((result['amount_yen'], result['amount_twd']), (990, 198))
        self.assertEqual(sorted(charge['amount_twd'] for charge in result['charges']), [99, 99])
        self.api.force_authenticate(self.driver.user)
        self.assertEqual(self.api.get(result['return_photo']).status_code, 403)
        own = self.api.get(self.personal).data['data']['trips'][0]
        response = self.api.get(own['return_photo'])
        self.assertEqual(response.status_code, 200)
        response.close()
        self.api.force_authenticate(self.west_coach.user)
        self.assertEqual(self.api.get(own['return_photo']).status_code, 404)
        charge = VehicleCharge.objects.get(coach=self.driver)
        for month, amount, deduction in ((charge.first_month, 50, 50), (charge.last_month, 80, 49)):
            statement = PayrollStatement.objects.create(coach=self.driver, campus=self.campus, period_start=month,
                period_end=(month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1), total_amount=amount)
            payload = {'reviewed': True, 'base_amount': amount, 'currency': 'TWD', 'rate': '1', 'deductions': []}
            with patch('Coach.vehicle_payroll.timezone.now', return_value=datetime.combine(month, datetime.min.time(), JAPAN_TIME)):
                statement = save_settlement(statement, payload, self.admin)
                PayrollLine.objects.create(statement=statement, line_type='course', description='QA', total_amount=amount)
                publish_statement(statement, statement.period_end + timedelta(days=1))
            self.assertEqual(statement.settlement_snapshot['vehicle_deduction_twd'], deduction)
            self.assertEqual(statement.settlement_snapshot['net_after_vehicle'], amount - deduction)
        self.assertEqual(charge_balance(charge), 0)

    def test_priority_sharing_and_weekly_free_shopping(self):
        self.request('shopping', expected=400)
        first = self.request('shopping', participants=[self.rider.pk])['id']
        self.request('shopping', participants=[self.rider.pk], start=self.start + timedelta(days=1), expected=400)
        self.request('lesson', resort=self.hoshino.pk, expected=400)
        lesson = self.request('lesson', resort=self.resort.pk)['id']
        self.post('approve', self.manager, expected=400, trip=first, vehicle=self.vehicle.pk)
        self.post('approve', self.manager, trip=lesson, vehicle=self.vehicle.pk)
        self.post('approve', self.manager, expected=400, trip=first, vehicle=self.vehicle.pk)
        self.post('reject', self.manager, trip=lesson, note='QA 改派')
        self.post('approve', self.manager, trip=first, vehicle=self.vehicle.pk)
        self.record('depart', first, '100')
        self.record('return', first, '900')
        self.post('review', self.manager, trip=first)
        result = self.post('settle', self.admin, trip=first)
        self.assertEqual((result['amount_yen'], result['amount_twd'], result['charges']), (0, 0, []))
        western = self.request('lesson', user=self.west_coach.user, campus=self.west, resort=self.resort.pk)['id']
        self.post('approve', self.manager, expected=404, trip=western, vehicle=self.vehicle.pk)
        self.post('approve', self.admin, expected=400, trip=western, vehicle=self.vehicle.pk)
        self.vehicle.shared_campuses.add(self.west)
        self.post('approve', self.admin, trip=western, vehicle=self.vehicle.pk)

    def test_approval_after_payday_and_april_collection(self):
        trip = VehicleTrip.objects.create(campus=self.campus, driver=self.driver, purpose='private',
            starts_at=self.start, ends_at=self.start + timedelta(hours=1), status='reviewed', departure_km=100,
            return_km=120, returned_at=datetime(2027, 4, 10, 10, tzinfo=JAPAN_TIME))
        with patch('API.vehicle_views.timezone.now', return_value=datetime(2027, 5, 11, 10, tzinfo=JAPAN_TIME)):
            result = self.post('settle', self.admin, trip=trip.pk)
            charge = VehicleCharge.objects.get(trip=trip)
            self.assertEqual((charge.first_month, charge.last_month), (date(2027, 5, 1), date(2027, 4, 1)))
            self.assertEqual(result['charges'][0]['balance'], 180)
            self.post('collect', self.admin, trip=trip.pk, charge=charge.pk, amount=181, expected_balance=180, expected=400)
            self.post('collect', self.admin, trip=trip.pk, charge=charge.pk, amount=90, expected_balance=180)
            self.post('collect', self.admin, trip=trip.pk, charge=charge.pk, amount=90, expected_balance=180, expected=400)
            self.post('collect', self.admin, trip=trip.pk, charge=charge.pk, amount=90, expected_balance=90)
            charge.refresh_from_db()
            self.assertEqual(charge_balance(charge), 0)

    def test_personal_scope_ignores_manager_campus_filter(self):
        profile = TenantStaffMembership.objects.get(user=self.driver.user, client=self.tenant)
        profile.is_manager = True
        profile.role = 'campus_manager'
        profile.admin_permissions = ['vehicle_review']
        profile.save()
        profile.campuses.add(self.west)
        self.api.force_authenticate(self.driver.user)
        result = self.api.get(self.personal, HTTP_X_CAMPUS_ID=str(self.west.pk)).data['data']
        self.assertEqual([campus['id'] for campus in result['campuses']], [self.campus.pk])
        self.assertTrue(result['eligible'])

    def test_payroll_must_be_reviewed_again_after_vehicle_charge_approval(self):
        day = self.start.date()
        statement = PayrollStatement.objects.create(
            coach=self.driver, campus=self.campus, period_start=day, period_end=day, total_amount=50,
        )
        PayrollLine.objects.create(statement=statement, line_type='course', description='QA', total_amount=50)
        trip = VehicleTrip.objects.create(campus=self.campus, driver=self.driver, purpose='private',
            starts_at=self.start, ends_at=self.start + timedelta(hours=1), status='reviewed',
            departure_km=100, return_km=120, returned_at=self.start)
        payload = {'reviewed': True, 'base_amount': 50, 'currency': 'TWD', 'rate': '1', 'deductions': []}
        with patch('Coach.vehicle_payroll.timezone.now', return_value=self.start):
            statement = save_settlement(statement, payload, self.admin)
            self.post('settle', self.admin, trip=trip.pk)
            with self.assertRaisesRegex(ValueError, '車資扣款已變更'):
                publish_statement(statement, day + timedelta(days=1))
            payload['expected_reviewed_at'] = statement.settlement_snapshot['reviewed_at']
            statement = save_settlement(statement, payload, self.admin)
            self.assertEqual(statement.settlement_snapshot['net_after_vehicle'], 0)
            self.assertEqual(publish_statement(statement, day + timedelta(days=1)).status, 'review')

    def test_duplicate_plate_early_departure_and_japan_date(self):
        self.post('vehicle', self.admin, expected=400, campus=self.west.pk, name='Duplicate', plate='qa-01')
        start = self.start.replace(hour=0, minute=10)
        trip = self.request(start=start)['id']
        self.post('approve', self.manager, trip=trip, vehicle=self.vehicle.pk)
        self.api.force_authenticate(self.driver.user)
        with patch('API.vehicle_views.timezone.now', return_value=start - timedelta(minutes=10)):
            self.assertEqual(self.api.post(self.personal, {'action': 'depart', 'trip': trip, 'km': '100'}).status_code, 400)
        self.api.force_authenticate(self.manager)
        result = self.api.get(self.url, {'from': start.date(), 'to': start.date()})
        self.assertEqual([item['id'] for item in result.data['data']['trips']], [trip])
