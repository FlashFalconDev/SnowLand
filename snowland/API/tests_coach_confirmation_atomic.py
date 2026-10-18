from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from API import tests_operations as fixtures
from booking.models import Booking


class CoachConfirmationAtomicTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.reservation.status='pending_coach_confirmation';self.reservation.save()
        profile=self.coach_user.userprofile;profile.is_coach=True;profile.save()
        self.api=APIClient();self.api.force_authenticate(self.coach_user)
        self.url=f'/api/admin/snowland/coach/confirm/{self.reservation.pk}/'

    def test_booking_reset_failure_rolls_back_entire_rejection(self):
        original=Booking.save
        def fail_reset(booking,*args,**kwargs):
            if booking.reservation_id==self.reservation.pk and not booking.is_scheduled:
                raise RuntimeError('QA booking reset failure')
            return original(booking,*args,**kwargs)
        with patch.object(Booking,'save',fail_reset),self.assertRaises(RuntimeError):
            self.api.post(self.url,{'action':'reject'},format='json')
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status,'pending_coach_confirmation')
        self.assertEqual(self.reservation.preferred_coach_id,self.coach.pk)
        self.assertFalse(self.reservation.rejected_coaches.exists())
        self.assertTrue(all(self.reservation.bookings.values_list('is_scheduled',flat=True)))

    def test_failed_best_effort_reassignment_preserves_clean_manual_fallback(self):
        def fail_after_write(reservation):
            reservation.status='auto_assigned';reservation.preferred_coach=self.coach;reservation.save()
            Booking.objects.filter(reservation=reservation).update(is_scheduled=True)
            raise RuntimeError('QA reassignment interrupted')
        with patch('booking.scheduler.reassign_single_reservation',fail_after_write):
            response=self.api.post(self.url,{'action':'reject'},format='json')
        self.assertEqual(response.status_code,200)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status,'created')
        self.assertIsNone(self.reservation.preferred_coach_id)
        self.assertEqual(list(self.reservation.rejected_coaches.values_list('pk',flat=True)),[self.coach.pk])
        self.assertFalse(any(self.reservation.bookings.values_list('is_scheduled',flat=True)))
