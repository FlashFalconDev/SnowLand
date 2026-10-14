from datetime import time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, CoachResort
from Resorts.models import Campus, Resorts
from booking.models import Booking, OrderRevision, Payment, Reservation, ReservationGroup


class OrderAssignmentScopeTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.other_tenant = Client.objects.create(name='Other', internal_code='other')
        self.campus = Campus.objects.create(client=self.tenant, name='道東', code='east')
        self.other_campus = Campus.objects.create(client=self.tenant, name='道央', code='central')
        self.resort = Resorts.objects.create(client=self.tenant, name='tomamu', display_name='Tomamu')
        self.other_resort = Resorts.objects.create(client=self.tenant, name='niseko', display_name='Niseko')
        self.campus.resorts.add(self.resort)
        self.other_campus.resorts.add(self.other_resort)
        self.group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus)
        self.reservation = Reservation.objects.create(group=self.group, resort=self.resort, status='created')
        self.booking = Booking.objects.create(
            reservation=self.reservation, date=timezone.localdate() + timedelta(days=2),
            start_time=time(9), end_time=time(13),
        )
        self.payment = Payment.objects.create(reservation_group=self.group, status='pending')
        self.api = APIClient()
        self.api.force_authenticate(User.objects.create_superuser('hq', 'hq@example.test', 'test-password'))
        self.url = f'/api/admin/snowland/orders/{self.group.id}/'

    def coach(self, *, tenant=None, campus=None, resort=None):
        coach = Coach.objects.create(client=tenant or self.tenant, name='測試教練')
        coach.campuses.add(campus or self.campus)
        CoachResort.objects.create(coach=coach, resort=resort or self.resort)
        return coach

    def test_rejects_coach_outside_tenant_campus_or_resort_without_changing_payment(self):
        foreign_campus = Campus.objects.create(client=self.other_tenant, name='其他', code='other')
        foreign_resort = Resorts.objects.create(client=self.other_tenant, name='foreign')
        invalid_coaches = [
            self.coach(tenant=self.other_tenant, campus=foreign_campus, resort=foreign_resort),
            self.coach(campus=self.other_campus),
            self.coach(resort=self.other_resort),
        ]
        for coach in invalid_coaches:
            with self.subTest(coach_id=coach.id):
                response = self.api.put(self.url, {
                    'action': 'save', 'payment_status': 'paid',
                    'reservation_updates': [{'reservation_id': self.reservation.id, 'coach_id': coach.id}],
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.reservation.refresh_from_db()
                self.payment.refresh_from_db()
                self.booking.refresh_from_db()
                self.assertIsNone(self.reservation.preferred_coach_id)
                self.assertEqual(self.payment.status, 'pending')
                self.assertFalse(self.booking.is_scheduled)

    def test_invalid_payment_status_is_rejected_and_valid_coach_can_be_assigned(self):
        invalid = self.api.put(self.url, {'payment_status': 'settled'}, format='json')
        self.assertEqual(invalid.status_code, 400, invalid.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

        coach = self.coach()
        response = self.api.put(self.url, {
            'action': 'save', 'reservation_updates': [{'reservation_id': self.reservation.id, 'coach_id': coach.id}],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.reservation.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, coach.id)
        self.assertTrue(self.booking.is_scheduled)

    def test_failed_scheduling_restores_booking_and_does_not_confirm_payment(self):
        original_date = self.booking.date
        with patch('booking.scheduler.assign_coachs', return_value=(False, {})):
            response = self.api.put(self.url, {
                'action': 'schedule', 'payment_status': 'paid',
                'booking_updates': [{
                    'booking_id': self.booking.id,
                    'date': (original_date + timedelta(days=1)).isoformat(),
                }],
            }, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.booking.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.booking.date, original_date)
        self.assertEqual(self.payment.status, 'pending')

    def test_unknown_booking_or_reservation_does_not_change_payment(self):
        for updates in (
            {'booking_updates': [{'booking_id': self.booking.id + 999}]},
            {'reservation_updates': [{'reservation_id': self.reservation.id + 999, 'coach_id': None}]},
        ):
            with self.subTest(updates=updates):
                response = self.api.put(self.url, {
                    'action': 'save', 'payment_status': 'paid', **updates,
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.payment.refresh_from_db()
                self.assertEqual(self.payment.status, 'pending')

    def test_unchanged_order_does_not_create_revision(self):
        response = self.api.put(self.url, {
            'action': 'save',
            'booking_updates': [{
                'booking_id': self.booking.id,
                'date': self.booking.date.isoformat(),
                'start_time': '09:00',
                'end_time': '13:00',
            }],
            'reservation_updates': [{'reservation_id': self.reservation.id, 'coach_id': None}],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(OrderRevision.objects.filter(group=self.group).count(), 0)
