from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Resorts.models import Campus, OperatingPolicy
from booking.models import Payment, Reservation, ReservationGroup
from booking.tasks import auto_cancel_unpaid_reservations, expire_unpaid_payment


class PaymentExpiryRaceTests(TestCase):
    """Payment state may change after the job selects its unpaid candidates."""

    def setUp(self):
        tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        owner = User.objects.create_user('expiry-race', 'expiry-race@example.test')
        campus = Campus.objects.create(client=tenant, name='到期校區', code='expiry-race')
        self.policy = OperatingPolicy.objects.create(client=tenant, campus=campus, unpaid_hold_days=1)
        self.group = ReservationGroup.objects.create(client=tenant, campus=campus, user=owner, order_number='QA-EXPIRY-RACE')
        self.reservation = Reservation.objects.create(group=self.group, status='auto_assigned', number_of_people=1, course_fee=1000)
        self.payment = Payment.objects.create(reservation_group=self.group, user=owner, status='unpaid', expires_at=None)
        Payment.objects.filter(pk=self.payment.pk).update(created_at=timezone.now()-timedelta(days=3))
        self.api = APIClient()
        self.api.force_authenticate(owner)
        tenant.bank_name = 'QA銀行'
        tenant.bank_branch = 'QA分行'
        tenant.bank_account_number = 'QA-ONLY-ACCOUNT'
        tenant.bank_account_holder = 'QA收款方'
        tenant.save()

    def report(self):
        return self.api.post('/booking/snowland/api/process-payment/', {
            'reservation_group_id': self.group.pk, 'payment_type': 'bank_transfer', 'sender_account': '12345',
        }, format='json')

    def run_with_change_after_candidate_selection(self, **changes):
        def changed_while_job_was_reading_policy(group):
            self.assertEqual(group.pk, self.group.pk)
            Payment.objects.filter(pk=self.payment.pk).update(**changes)
            return self.policy
        with patch('booking.tasks.get_operating_policy', side_effect=changed_while_job_was_reading_policy):
            result = auto_cancel_unpaid_reservations()
        self.payment.refresh_from_db()
        self.reservation.refresh_from_db()
        return result

    def test_reported_transfer_cannot_be_overwritten_by_stale_expiry_candidate(self):
        result = self.run_with_change_after_candidate_selection(status='pending')
        self.assertEqual(self.payment.status, 'pending')
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertIn('Expired 0 unpaid payments', result)

    def test_confirmed_payment_cannot_be_overwritten_by_stale_expiry_candidate(self):
        result = self.run_with_change_after_candidate_selection(status='paid')
        self.assertEqual(self.payment.status, 'paid')
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertIn('Expired 0 unpaid payments', result)

    def test_extended_deadline_is_rechecked_before_cancelling(self):
        future = timezone.now()+timedelta(days=2)
        result = self.run_with_change_after_candidate_selection(expires_at=future)
        self.assertEqual(self.payment.status, 'unpaid')
        self.assertEqual(self.payment.expires_at, future)
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertIn('Expired 0 unpaid payments', result)

    def test_latest_attempt_accepts_report_and_old_attempt_cannot_cancel_it(self):
        latest = Payment.objects.create(reservation_group=self.group, user=self.group.user,
            status='unpaid', expires_at=timezone.now()+timedelta(days=1))
        result = self.report()
        self.assertEqual(result.status_code, 200, result.data)
        latest.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(latest.status, 'pending')
        self.assertEqual(latest.bank_account, '12345')
        self.assertEqual(self.payment.status, 'unpaid')
        self.assertEqual(self.group.payments.count(), 2)
        self.assertEqual(expire_unpaid_payment(self.payment.pk), (1, 0))
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, 'auto_assigned')

    def test_report_wins_then_expiry_preserves_it_and_second_run_is_noop(self):
        result = self.report()
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(expire_unpaid_payment(self.payment.pk), (0, 0))
        self.assertEqual(expire_unpaid_payment(self.payment.pk), (0, 0))
        self.payment.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')
        self.assertEqual(self.reservation.status, 'auto_assigned')

    def test_expiry_wins_then_report_cannot_reopen_cancelled_order(self):
        self.assertEqual(expire_unpaid_payment(self.payment.pk), (1, 1))
        result = self.report()
        self.assertEqual(result.status_code, 400, result.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'expired')
        self.assertEqual(self.group.payments.count(), 1)

    def test_paid_attempt_cannot_be_downgraded_by_transfer_report(self):
        Payment.objects.filter(pk=self.payment.pk).update(status='paid')
        result = self.report()
        self.assertEqual(result.status_code, 400, result.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'paid')

    def test_reading_expired_payment_page_does_not_hide_order_from_expiry_job(self):
        Payment.objects.filter(pk=self.payment.pk).update(expires_at=timezone.now()-timedelta(minutes=1))
        response = self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': self.group.pk})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['payment_status'], 'expired')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'unpaid', 'A GET must not expire only the payment and leave its course forever reserved')
        self.assertEqual(expire_unpaid_payment(self.payment.pk), (1, 1))
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, 'cancelled')

    def test_equal_timestamp_attempts_cannot_downgrade_latest_paid_record(self):
        latest = Payment.objects.create(reservation_group=self.group, user=self.group.user, status='paid')
        original_bank = latest.bank_account
        self.payment.refresh_from_db()
        Payment.objects.filter(pk=latest.pk).update(created_at=self.payment.created_at)
        response = self.report()
        self.assertEqual(response.status_code, 400, response.data)
        latest.refresh_from_db()
        self.assertEqual(latest.status, 'paid')
        self.assertEqual(latest.bank_account, original_bank)
