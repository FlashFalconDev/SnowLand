from django.contrib.auth.models import User
from rest_framework.test import APIClient

from API import tests_coach_evaluations
from Client.models import Client
from Resorts.models import Resorts


class EvaluationTrailTests(tests_coach_evaluations.CoachEvaluationTests):
    def setUp(self):
        super().setUp()
        self.resort = Resorts.objects.create(client=self.tenant, name='qa-trails', display_name='QA 雪場')
        self.campus.resorts.add(self.resort)
        reservation = self.own.booking.reservation
        reservation.resort = self.resort
        reservation.save(update_fields=['resort'])
        self.hq = APIClient()
        self.hq.force_authenticate(User.objects.create_superuser('trail-hq', 'hq@example.test', 'test-password'))
        self.resort_url = f'/api/admin/snowland/resorts/{self.resort.pk}/'

    def test_hq_maintains_catalog_and_own_coach_gets_only_course_resort_choices(self):
        response = self.hq.patch(self.resort_url, {'trail_names': [' Green ', 'Family Run', 'Green']}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.resort.refresh_from_db()
        self.assertEqual(self.resort.trail_names, ['Green', 'Family Run'])
        other = Client.objects.create(name='Other', internal_code='other-trails')
        Resorts.objects.create(client=other, name='foreign-trails', display_name='Foreign', trail_names=['Private trail'])
        row = self.api.get(f'{self.url}{self.own.pk}/').data
        self.assertEqual(row['available_trails'], ['Green', 'Family Run'])
        self.assertEqual(self.api.patch(self.resort_url, {'trail_names': ['Overwrite']}, format='json').status_code, 403)
        self.resort.refresh_from_db()
        self.assertEqual(self.resort.trail_names, ['Green', 'Family Run'])

    def test_selected_and_custom_trails_reach_member_and_catalog_edits_keep_history(self):
        response = self.api.patch(f'{self.url}{self.own.pk}/', {
            'trail_names': [' Green ', 'Family Run', 'Green', 'Old course'],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.own.refresh_from_db()
        self.assertEqual(self.own.trail_names, ['Green', 'Family Run', 'Old course'])
        self.hq.patch(self.resort_url, {'trail_names': ['New course']}, format='json')
        self.own.refresh_from_db()
        self.assertEqual(self.own.trail_names, ['Green', 'Family Run', 'Old course'])
        member_api = APIClient()
        member_api.force_authenticate(self.member)
        records = member_api.get('/booking/snowland/api/member-center/').data['learning_records']
        own = next(row for row in records if row['id'] == self.own.pk)
        self.assertEqual(own['trail_names'], self.own.trail_names)

    def test_invalid_evaluation_trails_do_not_partially_save_notes(self):
        for value in ({'Green': True}, None, [' '], ['x' * 121], ['a'] * 101):
            with self.subTest(value=value):
                response = self.api.patch(f'{self.url}{self.own.pk}/', {
                    'trail_names': value, 'coach_notes': 'must not save',
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('雪道', str(response.data))
                self.own.refresh_from_db()
                self.assertEqual(self.own.coach_notes, '')
                self.assertEqual(self.own.trail_names, [])

    def test_legacy_text_is_read_as_list_without_rewriting_and_old_input_still_works(self):
        type(self.own).objects.filter(pk=self.own.pk).update(trail_names='Green、Old course')
        row = self.api.get(f'{self.url}{self.own.pk}/').data
        self.assertEqual(row['trail_names'], ['Green', 'Old course'])
        self.own.refresh_from_db()
        self.assertEqual(self.own.trail_names, 'Green、Old course')
        member_api = APIClient()
        member_api.force_authenticate(self.member)
        records = member_api.get('/booking/snowland/api/member-center/').data['learning_records']
        self.assertEqual(next(row for row in records if row['id'] == self.own.pk)['trail_names'], ['Green', 'Old course'])
        updated = self.api.patch(f'{self.url}{self.own.pk}/', {'trail_names': ' Family Run '}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.own.refresh_from_db()
        self.assertEqual(self.own.trail_names, ['Family Run'])

    def test_invalid_catalog_is_rejected_without_changing_resort_name(self):
        for value in ({'Green': True}, 'Green', None, [' '], ['x' * 121], ['a'] * 101):
            with self.subTest(value=value):
                response = self.hq.patch(self.resort_url, {
                    'trail_names': value, 'display_name': 'must not save',
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('雪道', str(response.data))
                self.resort.refresh_from_db()
                self.assertEqual(self.resort.display_name, 'QA 雪場')
