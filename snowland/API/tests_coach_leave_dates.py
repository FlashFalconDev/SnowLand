from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, CoachLeaveRequest
from Resorts.models import Campus, OperatingPolicy
from booking.models import Booking, Reservation, ReservationGroup


@override_settings(TIME_ZONE='Asia/Taipei')
class CoachLeaveCalendarDateTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.campus=Campus.objects.create(client=self.tenant,code='a',name='A')
        self.user=User.objects.create_user('coach',password='test-password')
        profile=self.user.userprofile;profile.is_coach=True;profile.save()
        self.coach=Coach.objects.create(client=self.tenant,user=self.user,name='QA coach')
        self.coach.campuses.add(self.campus)
        OperatingPolicy.objects.create(client=self.tenant,campus=self.campus,leave_advance_days=3,
            leave_max_consecutive_days=2,leave_daily_coach_limit=2)
        self.api=APIClient();self.api.force_authenticate(self.user)
        self.url='/api/admin/snowland/coach/apply-leave/'
        # The school's date is already Oct 18; UTC is still Oct 17.
        self.now=datetime(2026,10,17,16,30,tzinfo=datetime_timezone.utc)

    def post(self,**changes):
        with patch('django.utils.timezone.now',return_value=self.now):
            return self.api.post(self.url,{'start_date':'2026-10-21','end_date':'2026-10-21','reason':'QA假請假',**changes},format='json')

    def test_three_day_rule_uses_school_local_date_not_utc(self):
        result=self.post(start_date='2026-10-20',end_date='2026-10-20')
        self.assertEqual(result.status_code,400,result.data)
        self.assertIn('提前 3 天',result.data['msg'])
        self.assertFalse(CoachLeaveRequest.objects.exists())

    def test_exact_three_local_days_is_valid_and_saved_once(self):
        result=self.post();self.assertEqual(result.status_code,200,result.data)
        row=CoachLeaveRequest.objects.get();self.assertEqual(str(row.start_date),'2026-10-21')
        self.assertEqual(row.status,'pending');self.assertEqual(row.coach,self.coach)
        self.assertEqual(self.post().status_code,400)
        self.assertEqual(CoachLeaveRequest.objects.count(),1)

    def test_malformed_field_types_are_400_not_500(self):
        for fields in [{'start_date':[]},{'end_date':{}},{'reason':['QA']},{'reason':{'text':'QA'}},{'reason':'x'*1001}]:
            with self.subTest(fields=fields):
                result=self.post(**fields)
                self.assertEqual(result.status_code,400,result.data)
        self.assertFalse(CoachLeaveRequest.objects.exists())

    def test_invalid_campus_identifier_is_400_not_500(self):
        for value in ([],{},True,'not-an-id',-1):
            with self.subTest(value=value):
                result=self.post(campus_id=value)
                self.assertEqual(result.status_code,400,result.data)
        self.assertFalse(CoachLeaveRequest.objects.exists())

    def test_rules_get_uses_same_school_day_and_current_policy_without_writes(self):
        policy=OperatingPolicy.objects.get(client=self.tenant,campus=self.campus)
        policy.leave_advance_days=5;policy.save(update_fields=['leave_advance_days'])
        policies_before=OperatingPolicy.objects.count()
        with patch('django.utils.timezone.now',return_value=self.now):
            result=self.api.get(self.url)
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['data'],{'today':'2026-10-18','minimum_start_date':'2026-10-23',
            'leave_advance_days':5,'leave_max_consecutive_days':2,'leave_daily_coach_limit':2})
        self.assertFalse(CoachLeaveRequest.objects.exists())
        self.assertEqual(OperatingPolicy.objects.count(),policies_before)

    def test_rules_get_checks_role_and_campus(self):
        self.assertEqual(self.api.get(self.url,{'campus_id':'bad'}).status_code,400)
        other=Client.objects.create(name='Other',internal_code='other')
        campus=Campus.objects.create(client=other,code='other',name='Other')
        self.assertEqual(self.api.get(self.url,{'campus_id':campus.pk}).status_code,400)
        self.api.force_authenticate(User.objects.create_user('ordinary'))
        self.assertEqual(self.api.get(self.url).status_code,403)

    def test_rules_without_saved_policy_do_not_create_settings_on_read(self):
        OperatingPolicy.objects.all().delete()
        self.assertEqual(self.api.get(self.url).status_code,200)
        self.assertFalse(OperatingPolicy.objects.exists())

    def affected_course(self):
        group=ReservationGroup.objects.create(client=self.tenant,campus=self.campus,user=self.user)
        reservation=Reservation.objects.create(group=group,preferred_coach=self.coach,status='manually_assigned')
        Booking.objects.create(reservation=reservation,date='2026-10-21',start_time='09:00',end_time='12:00')
        return reservation

    def test_leave_links_affected_course_without_cancelling_it(self):
        reservation=self.affected_course()
        result=self.post();self.assertEqual(result.status_code,200,result.data)
        row=CoachLeaveRequest.objects.get()
        self.assertEqual(list(row.affected_reservations.values_list('pk',flat=True)),[reservation.pk])
        self.assertEqual(result.data['data']['affected_count'],1)
        reservation.refresh_from_db();self.assertEqual(reservation.status,'manually_assigned')

    def test_failed_affected_course_link_leaves_no_partial_application(self):
        reservation=self.affected_course()
        manager=CoachLeaveRequest.affected_reservations.related_manager_cls
        with patch.object(manager,'set',side_effect=RuntimeError('QA affected-course link failure')):
            with self.assertRaisesRegex(RuntimeError,'QA affected-course link failure'):
                self.post()
        self.assertFalse(CoachLeaveRequest.objects.exists())
        reservation.refresh_from_db();self.assertEqual(reservation.status,'manually_assigned')
        # Retrying after recovery must create exactly one complete application.
        self.assertEqual(self.post().status_code,200)
        self.assertEqual(CoachLeaveRequest.objects.count(),1)
