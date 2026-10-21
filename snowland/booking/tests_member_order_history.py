from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client
from booking.models import Payment, Reservation, ReservationGroup


class MemberOrderHistoryTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.owner = User.objects.create_user('history-owner', 'history-owner@example.test')
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.group = ReservationGroup.objects.create(client=self.tenant, user=self.owner, order_number='QA-HISTORY')
        self.reservation = Reservation.objects.create(group=self.group, status='cancelled', number_of_people=1,
            course_fee=6000, equipment_rental_fee=1500, language_fee=600, coach_fee=500, discount_amount=1000)
        Payment.objects.create(reservation_group=self.group, user=self.owner, status='expired')

    def read_order(self):
        response = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['orders'][0]

    def test_cancelled_history_keeps_discounted_total_but_no_current_amount(self):
        row = self.read_order()
        self.assertEqual(row['total_amount'], 0)
        self.assertEqual(row['historical_amount'], 7600)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.payment_amount, 7600)
        self.assertEqual(self.reservation.status, 'cancelled')
        self.assertEqual(self.group.payments.get().status, 'expired')

    def test_partial_cancellation_and_deleted_revision_do_not_change_current_payable(self):
        Reservation.objects.create(group=self.group, status='created', number_of_people=1, course_fee=2000)
        Reservation.objects.create(group=self.group, status='deleted', number_of_people=1, course_fee=99000)
        row = self.read_order()
        self.assertEqual(row['total_amount'], 2000)
        self.assertEqual(row['historical_amount'], 9600)
        self.assertEqual(len(row['reservations']), 2)

    def test_fully_discounted_history_stays_zero_not_list_price(self):
        self.reservation.discount_amount = 8600
        self.reservation.save()
        self.assertEqual(self.read_order()['historical_amount'], 0)

    def test_other_member_cannot_read_the_order_or_its_historical_amount(self):
        other = User.objects.create_user('history-other')
        self.api.force_authenticate(other)
        response = self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['orders'], [])

    def test_elapsed_unpaid_deadline_is_displayed_expired_without_mutating_payment(self):
        from datetime import timedelta
        from django.utils import timezone
        self.reservation.status = 'manually_assigned'
        self.reservation.save(update_fields=['status'])
        payment = self.group.payments.get()
        payment.status = 'unpaid'
        payment.expires_at = timezone.now() - timedelta(seconds=1)
        payment.save(update_fields=['status', 'expires_at'])
        row = self.read_order()
        self.assertEqual(row['payment_hold_status'], 'expired')
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'unpaid', 'Only the expiry job releases reservations and changes payment state')
