from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from API import tests_operations as fixtures


class ScheduleDateFilterTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        profile=self.coach_user.userprofile;profile.is_coach=True;profile.save()
        self.api=APIClient();self.api.force_authenticate(self.coach_user)
        self.hq=User.objects.create_superuser('date-filter-hq',password='test-password')

    def test_invalid_coach_calendar_dates_return_400_not_server_error(self):
        for params in ({'start':'oops'},{'end':'2026-02-30'}):
            with self.subTest(params=params):
                response=self.api.get('/api/admin/snowland/coach/my-calendar/',params)
                self.assertEqual(response.status_code,400)

    def test_invalid_course_dates_never_silently_remove_filter(self):
        for params in ({'date_from':'oops'},{'date_to':'2026-02-30'}):
            with self.subTest(params=params):
                self.assertEqual(self.api.get('/api/admin/snowland/coach/my-courses/',params).status_code,400)

    def test_invalid_headquarters_dates_never_silently_return_all(self):
        self.api.force_authenticate(self.hq)
        for params in ({'start':'oops'},{'end':'2026-02-30'}):
            with self.subTest(params=params):
                self.assertEqual(self.api.get('/api/admin/snowland/bookings/',params).status_code,400)

    def test_reversed_explicit_range_is_rejected_on_all_three_surfaces(self):
        for path,params in (
            ('coach/my-calendar/',{'start':'2026-12-02','end':'2026-12-01'}),
            ('coach/my-courses/',{'date_from':'2026-12-02','date_to':'2026-12-01'}),
            ('bookings/',{'start':'2026-12-02','end':'2026-12-01'}),
        ):
            with self.subTest(path=path):
                self.api.force_authenticate(self.hq if path=='bookings/' else self.coach_user)
                self.assertEqual(self.api.get('/api/admin/snowland/'+path,params).status_code,400)

    def test_omitted_and_empty_dates_keep_existing_default_behavior(self):
        for path,params in (
            ('coach/my-calendar/',{'start':'','end':''}),
            ('coach/my-courses/',{'date_from':'','date_to':''}),
            ('bookings/',{'start':'','end':''}),
        ):
            self.api.force_authenticate(self.hq if path=='bookings/' else self.coach_user)
            self.assertEqual(self.api.get('/api/admin/snowland/'+path,params).status_code,200)
