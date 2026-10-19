from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Client.models import Client
from Coach.models import Coach, CoachLeaveRequest
from Resorts.models import Campus
from booking.models import Payment


class ScheduleRosterTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.day = timezone.localdate() + timedelta(days=2)
        self.booking_1.date = self.day
        self.booking_1.save(update_fields=['date'])
        self.reservation.is_preferred_coach = True
        self.reservation.max_ability_level = 'level3'
        self.reservation.save()
        Payment.objects.create(reservation_group=self.group, status='paid')
        self.empty = Coach.objects.create(client=self.client_tenant, name='同名教練')
        self.empty.campuses.add(self.campus)
        self.coach.name = '同名教練'
        self.coach.save()
        self.other_campus = Campus.objects.create(client=self.client_tenant, name='B', code='b')
        self.outside = Coach.objects.create(client=self.client_tenant, name='B教練')
        self.outside.campuses.add(self.other_campus)
        foreign = Client.objects.create(name='Other', internal_code='other')
        self.foreign = Coach.objects.create(client=foreign, name='外公司教練')
        self.foreign.campuses.add(self.campus)
        self.leave = CoachLeaveRequest.objects.create(coach=self.empty,
            start_date=self.day - timedelta(days=1), end_date=self.day + timedelta(days=1),
            reason='PRIVATE-MEDICAL-REASON', status='approved')
        self.api = APIClient()
        self.api.force_authenticate(User.objects.create_superuser('roster-hq', password='qa'))
        self.params = {'start': self.day.isoformat(), 'end': self.day.isoformat()}

    def get(self, **headers):
        result = self.api.get('/api/admin/snowland/bookings/', self.params, **headers)
        self.assertEqual(result.status_code, 200, result.data)
        return result.data['data']

    def test_roster_includes_empty_coach_and_keeps_duplicate_names_distinct(self):
        data = self.get(HTTP_X_CAMPUS_ID=str(self.campus.pk))
        self.assertCountEqual([row['id'] for row in data['coaches']], [self.coach.pk, self.empty.pk])
        event = next(row for row in data['list'] if row['id'] == self.booking_1.pk)
        self.assertEqual(event['coach_id'], self.coach.pk)
        self.assertEqual(event['ability_level'], 'level3')
        self.assertTrue(event['is_preferred_coach'])

    def test_leave_names_and_clipped_dates_without_private_reasons(self):
        data = self.get(HTTP_X_CAMPUS_ID=str(self.campus.pk))
        self.assertEqual(data['leaves'], [{'coach_id': self.empty.pk, 'coach_name': '同名教練',
            'start_date': self.day.isoformat(), 'end_date': self.day.isoformat()}])
        self.assertNotIn('PRIVATE-MEDICAL-REASON', str(data))
        for status in ('pending', 'rejected', 'cancelled'):
            self.leave.status = status
            self.leave.save()
            self.assertEqual(self.get()['leaves'], [])

    def test_manager_roster_and_leave_range_do_not_leak_other_campus_or_future(self):
        manager = User.objects.create_user('roster-manager')
        profile = manager.userprofile
        profile.is_manager = True
        profile.manager_client = self.client_tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = ['scheduling']
        profile.save()
        profile.campuses.add(self.campus)
        self.api.force_authenticate(manager)
        data = self.get()
        self.assertCountEqual([row['id'] for row in data['coaches']], [self.coach.pk, self.empty.pk])
        self.params = {'start': (self.day + timedelta(days=11)).isoformat(),
                       'end': (self.day + timedelta(days=20)).isoformat()}
        data = self.get()
        self.assertEqual(data['coaches'], [])
        self.assertEqual(data['leaves'], [])

    def test_no_date_range_does_not_expand_all_leave_history(self):
        self.params = {}
        self.assertEqual(self.get()['leaves'], [])

    def test_headquarters_all_campuses_still_excludes_foreign_company(self):
        data = self.get()
        self.assertCountEqual([row['id'] for row in data['coaches']],
            [self.coach.pk, self.empty.pk, self.outside.pk])
