from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_operations
from booking.models import Payment


class OrderPaymentHistoryUpdateTests(TestCase):
    setUp = tests_operations.OperationsTests.setUp

    def api(self):
        api = APIClient()
        api.force_authenticate(User.objects.create_superuser('payment-history-hq', 'hq@example.test', 'test-password'))
        return api

    def test_only_current_payment_changes_and_history_is_retained(self):
        old = Payment.objects.create(reservation_group=self.group, user=self.user, status='refunded')
        latest = Payment.objects.create(reservation_group=self.group, user=self.user, status='pending', bank_account='54321')
        response = self.api().patch(f'/api/admin/snowland/orders/{self.group.pk}/',
            {'action': 'save', 'payment_status': 'paid'}, format='json')
        self.assertEqual(response.status_code, 200)
        old.refresh_from_db(); latest.refresh_from_db()
        self.assertEqual(old.status, 'refunded')
        self.assertEqual(latest.status, 'paid')
        self.assertEqual(latest.bank_account, '54321')
        self.assertEqual(self.group.payments.count(), 2)

    def test_equal_timestamps_use_newest_primary_key(self):
        old = Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        latest = Payment.objects.create(reservation_group=self.group, user=self.user, status='pending')
        self.group.payments.update(created_at=timezone.now())
        response = self.api().patch(f'/api/admin/snowland/orders/{self.group.pk}/',
            {'action': 'save', 'payment_status': 'expired'}, format='json')
        self.assertEqual(response.status_code, 200)
        old.refresh_from_db(); latest.refresh_from_db()
        self.assertEqual((old.status, latest.status), ('paid', 'expired'))

    def test_missing_payment_is_created_once(self):
        api = self.api()
        for status in ('pending', 'paid'):
            response = api.patch(f'/api/admin/snowland/orders/{self.group.pk}/',
                {'action': 'save', 'payment_status': status}, format='json')
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.group.payments.count(), 1)
        self.assertEqual(self.group.payments.get().status, 'paid')
