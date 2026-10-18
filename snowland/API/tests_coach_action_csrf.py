from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_coach_leave_dates as fixtures
from Coach.models import Coach, CoachLeaveRequest
from booking.models import Booking, Reservation, ReservationGroup


class CoachActionCsrfTests(TestCase):
    def setUp(self):
        fixtures.CoachLeaveCalendarDateTests.setUp(self)
        self.browser=APIClient(enforce_csrf_checks=True)
        self.browser.force_login(self.user)
        self.group=ReservationGroup.objects.create(client=self.tenant,campus=self.campus,user=self.user)
        self.reservation=Reservation.objects.create(group=self.group,preferred_coach=self.coach,status='pending_coach_confirmation')
        Booking.objects.create(reservation=self.reservation,date=timezone.localdate()+timedelta(days=2),start_time='09:00',end_time='12:00')
        self.confirm_url=f'/api/admin/snowland/coach/confirm/{self.reservation.pk}/'

    def token_from(self,url):
        response=self.browser.get(url)
        self.assertEqual(response.status_code,200,response.data)
        self.assertTrue('csrftoken' in self.browser.cookies, 'Read endpoint must issue a CSRF token')
        return self.browser.cookies['csrftoken'].value

    def test_real_session_accept_needs_csrf_then_same_origin_succeeds(self):
        denied=self.browser.post(self.confirm_url,{'action':'accept'},format='json')
        self.assertEqual(denied.status_code,403,denied.data)
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.status,'pending_coach_confirmation')
        token=self.token_from('/api/admin/snowland/coach/pending/')
        untrusted=self.browser.post(self.confirm_url,{'action':'accept'},format='json',HTTP_X_CSRFTOKEN=token,HTTP_ORIGIN='https://not-snowland.invalid')
        self.assertEqual(untrusted.status_code,403)
        allowed=self.browser.post(self.confirm_url,{'action':'accept'},format='json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(allowed.status_code,200,allowed.data)
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.status,'manually_assigned')

    def test_real_session_reject_cannot_clear_assignment_without_csrf(self):
        with patch('booking.scheduler.reassign_single_reservation',return_value='created'):
            denied=self.browser.post(self.confirm_url,{'action':'reject'},format='json')
            self.assertEqual(denied.status_code,403,denied.data)
            self.reservation.refresh_from_db()
            self.assertEqual(self.reservation.preferred_coach,self.coach)
            self.assertFalse(self.reservation.rejected_coaches.exists())
            token=self.token_from('/api/admin/snowland/coach/pending/')
            allowed=self.browser.post(self.confirm_url,{'action':'reject'},format='json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(allowed.status_code,200,allowed.data)
        self.reservation.refresh_from_db();self.assertIsNone(self.reservation.preferred_coach)
        self.assertTrue(self.reservation.rejected_coaches.filter(pk=self.coach.pk).exists())

    def test_real_session_leave_needs_csrf_and_rules_get_seeds_token(self):
        day=str(timezone.localdate()+timedelta(days=5))
        payload={'start_date':day,'end_date':day,'reason':'QA CSRF請假'}
        denied=self.browser.post(self.url,payload,format='json')
        self.assertEqual(denied.status_code,403,denied.data)
        self.assertFalse(CoachLeaveRequest.objects.exists())
        token=self.token_from(self.url)
        allowed=self.browser.post(self.url,payload,format='json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(allowed.status_code,200,allowed.data)
        self.assertEqual(CoachLeaveRequest.objects.count(),1)

    def test_csrf_token_does_not_authorize_another_coachs_course(self):
        token=self.token_from('/api/admin/snowland/coach/pending/')
        other_user=User.objects.create_user('other-coach',password='test-password')
        profile=other_user.userprofile;profile.is_coach=True;profile.save()
        Coach.objects.create(client=self.tenant,user=other_user,name='Other')
        self.browser.force_login(other_user)
        response=self.browser.post(self.confirm_url,{'action':'accept'},format='json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,404,response.data)
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.status,'pending_coach_confirmation')
