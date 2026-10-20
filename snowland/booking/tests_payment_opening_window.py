from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach
from Resorts.models import Campus, OperatingPolicy
from booking.models import Payment, Reservation, ReservationGroup
from booking.operations import sync_group_payment_window
from booking.tasks import expire_unpaid_payment


class PaymentOpeningWindowTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='QA',internal_code='snowland')
        self.owner=User.objects.create_user('window-owner')
        self.user=User.objects.create_user('window-coach')
        self.coach=Coach.objects.create(client=self.tenant,user=self.user,name='QA coach')
        profile=self.user.userprofile;profile.is_coach=True;profile.save()
        self.campus=Campus.objects.create(client=self.tenant,name='QA',code='qa')
        self.coach.campuses.add(self.campus)
        OperatingPolicy.objects.create(client=self.tenant,campus=self.campus,unpaid_hold_days=3)
        self.group=ReservationGroup.objects.create(client=self.tenant,campus=self.campus,user=self.owner)
        self.reservation=Reservation.objects.create(group=self.group,preferred_coach=self.coach,
            status='pending_coach_confirmation',course_fee=1000)
        self.now=timezone.now()

    def accept(self):
        api=APIClient();api.force_authenticate(self.user)
        with patch('django.utils.timezone.now',return_value=self.now):
            return api.post(f'/api/admin/snowland/coach/confirm/{self.reservation.pk}/',{'action':'accept'},format='json')

    def test_acceptance_starts_deadline_before_member_visits_payment_page(self):
        self.assertFalse(self.group.payments.exists())
        response=self.accept();self.assertEqual(response.status_code,200,response.data)
        payment=self.group.payments.get()
        self.assertEqual(payment.expires_at,self.now+timedelta(days=3))
        with patch('django.utils.timezone.now',return_value=self.now+timedelta(days=1)):
            sync_group_payment_window(self.group)
        payment.refresh_from_db()
        self.assertEqual(payment.expires_at,self.now+timedelta(days=3),'Refresh must not extend payment time')
        self.assertEqual(self.group.payments.count(),1)

    def test_waiting_for_another_coach_does_not_start_timer(self):
        Reservation.objects.create(group=self.group,status='pending_coach_confirmation',course_fee=1000)
        self.assertEqual(self.accept().status_code,200)
        self.assertFalse(self.group.payments.exists())

    def test_pending_confirmation_is_never_expired_by_an_old_payment_deadline(self):
        payment=Payment.objects.create(reservation_group=self.group,user=self.owner,status='unpaid',
            expires_at=self.now-timedelta(days=1))
        self.assertEqual(expire_unpaid_payment(payment.pk,now=self.now),(0,0))
        sync_group_payment_window(self.group)
        payment.refresh_from_db();self.assertIsNone(payment.expires_at)
        self.assertEqual(self.accept().status_code,200)
        payment.refresh_from_db();self.assertEqual(payment.expires_at,self.now+timedelta(days=3))

    def test_received_or_reported_money_is_unchanged(self):
        for status in ('paid','pending','refunded','expired'):
            with self.subTest(status=status):
                self.group.payments.all().delete()
                payment=Payment.objects.create(reservation_group=self.group,user=self.owner,status=status,
                    expires_at=self.now-timedelta(days=1))
                sync_group_payment_window(self.group)
                payment.refresh_from_db()
                self.assertEqual(payment.status,status)
                self.assertEqual(payment.expires_at,self.now-timedelta(days=1))
                self.assertEqual(self.group.payments.count(),1)
