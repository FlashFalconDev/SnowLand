from datetime import time,timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from API import tests_operations as fixtures
from Resorts.models import EquipmentAssistanceTimeSlot
from booking.models import Payment


class SchedulePaymentHistoryTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        profile=self.coach_user.userprofile;profile.is_coach=True;profile.save()
        self.hq=User.objects.create_superuser('schedule-hq',password='test-password')
        self.day=timezone.localdate()+timedelta(days=1)
        self.reservation.bookings.update(date=self.day)
        slot=EquipmentAssistanceTimeSlot.objects.create(resort=self.resort,label='QA協助',start_time=time(8),end_time=time(8,30),day_type='same_day')
        self.reservation.equipment='purchaseAssistanceTime';self.reservation.equipment_assistance_time_slot=slot;self.reservation.save()
        self.old=Payment.objects.create(reservation_group=self.group,status='paid')
        self.latest=Payment.objects.create(reservation_group=self.group,status='refunded')
        self.api=APIClient()

    def assert_views(self,visible):
        self.api.force_authenticate(self.coach_user)
        for path in ('coach/my-courses/','coach/my-calendar/'):
            response=self.api.get('/api/admin/snowland/'+path)
            self.assertEqual(response.status_code,200,response.data)
            self.assertEqual(bool(response.data['data']['list']),visible,(path,self.latest.status))
        self.api.force_authenticate(self.hq)
        response=self.api.get('/api/admin/snowland/bookings/',{'start':str(self.day),'end':str(self.day)})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(bool(response.data['data']['list']),visible)
        self.assertEqual(response.data['data']['daily_summary'][0]['booked_coaches'],int(visible))

    def test_latest_state_not_any_old_paid_attempt_controls_schedule(self):
        for state in ('refunded','expired','unpaid','pending','paid'):
            with self.subTest(state=state):
                self.latest.status=state;self.latest.save()
                self.assert_views(state in ('pending','paid'))

    def test_same_timestamp_breaks_ties_by_newest_payment_id(self):
        timestamp=timezone.now()
        Payment.objects.filter(pk__in=[self.old.pk,self.latest.pk]).update(created_at=timestamp)
        self.assert_views(False)
        self.old.status='refunded';self.old.save()
        self.latest.status='paid';self.latest.save()
        self.assert_views(True)

    def test_no_payment_never_becomes_a_visible_scheduled_course(self):
        self.group.payments.all().delete()
        self.assert_views(False)
