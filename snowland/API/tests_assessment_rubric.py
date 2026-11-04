from copy import deepcopy
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from booking.assessment import achieved_level, default_rubric
from booking.models import Booking, CourseEvaluation, MemberDetail, Reservation, ReservationGroup
from Client.models import Client
from Coach.models import Coach
from Control.models import TenantStaffMembership


class AssessmentRubricTests(TestCase):
    admin_path = '/api/admin/snowland/evaluations/rubric/'
    coach_path = '/api/admin/snowland/coach/evaluations/'
    member_path = '/booking/snowland/api/member-center/'

    def setUp(self):
        self.school = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.hq = User.objects.create_user('rubric-hq')
        TenantStaffMembership.objects.create(user=self.hq, client=self.school, role='hq_admin', is_manager=True)
        self.coach = Coach.objects.create(client=self.school, user=User.objects.create_user('rubric-coach'), name='Coach')
        TenantStaffMembership.objects.create(user=self.coach.user, client=self.school, is_coach=True)
        self.parent = User.objects.create_user('rubric-parent')
        group = ReservationGroup.objects.create(client=self.school, user=self.parent)
        self.reservation = Reservation.objects.create(group=group, preferred_coach=self.coach, status='completed')
        self.first = MemberDetail.objects.create(reservation=self.reservation, user=self.parent, insurance_data={'full_name': 'First'})
        self.sibling = MemberDetail.objects.create(reservation=self.reservation, user=self.parent, insurance_data={'full_name': 'Sibling'})
        self.api = APIClient()

    def evaluation(self, learner, days_ago):
        booking, _ = Booking.objects.get_or_create(
            reservation=self.reservation, date=timezone.localdate() - timedelta(days=days_ago),
            defaults={'start_time': '09:00', 'end_time': '12:00'},
        )
        evaluation, _ = CourseEvaluation.objects.get_or_create(booking=booking, member=learner, defaults={'coach': self.coach})
        return evaluation

    def review(self, evaluation, revision, discipline, scores):
        return self.api.patch(f'{self.coach_path}{evaluation.pk}/', {
            'completed_at': timezone.now().isoformat(),
            'skill_review': {'revision': revision, 'entries': {discipline: {'scores': scores, 'next_steps': list(scores)}}},
        }, format='json')

    def test_figma_progression_rules(self):
        snowboard, ski = default_rubric()['disciplines'].values()
        for skills, level in (({}, 0), ({'heel-leaf': 3}, 1), ({'heel-leaf': 2, 'toe-leaf': 2}, 2),
                              ({'linked': 2}, 3), ({'carve': 1}, 4), ({'carve': 2}, 5), ({'carve': 3}, 6)):
            self.assertEqual(achieved_level(snowboard, skills), level)
        for skills, level in (({'green-wedge': 2}, 1), ({'green-wedge': 3}, 2),
                              ({'pole-turn': 1}, 4), ({'pole-turn': 2}, 5), ({'pole-turn': 3}, 6)):
            self.assertEqual(achieved_level(ski, skills), level)

    def test_member_report_accumulates_each_learner_and_discipline_separately(self):
        self.api.force_authenticate(self.coach.user)
        config = self.api.get(self.coach_path + 'rubric/').data['data']
        self.assertFalse(config['can_edit'])
        first = self.evaluation(self.first, 3)
        second = self.evaluation(self.first, 2)
        sibling = self.evaluation(self.sibling, 3)
        third = self.evaluation(self.first, 1)
        for evaluation, discipline, scores in ((first, 'snowboard', {'heel-leaf': 2}),
                                               (second, 'snowboard', {'toe-leaf': 2}),
                                               (sibling, 'snowboard', {'toe-leaf': 2}),
                                               (third, 'ski', {'green-wedge': 3})):
            response = self.review(evaluation, config['revision'], discipline, scores)
            self.assertEqual(response.status_code, 200, response.data)

        self.api.force_authenticate(self.parent)
        response = self.api.get(self.member_path)
        self.assertEqual(response.status_code, 200, response.data)
        reports = {row['id']: row['technical_assessment'][0] for row in response.data['learning_records']}
        self.assertEqual({key: row['level'] for key, row in reports.items()},
                         {first.pk: 1, second.pk: 2, sibling.pk: 1, third.pk: 2})
        self.assertEqual(reports[second.pk]['next_steps'], ['初級道落葉飄 Toe'])
        self.assertEqual(reports[third.pk]['scores'], [{'title': '綠道－全制動轉彎', 'rating': '熟練'}])

    def test_settings_are_school_scoped_and_historical_reviews_keep_their_rubric(self):
        first = self.evaluation(self.first, 2)
        second = self.evaluation(self.first, 1)
        self.api.force_authenticate(self.coach.user)
        current = self.api.get(self.coach_path + 'rubric/').data['data']
        self.assertEqual(self.api.put(self.admin_path, current, format='json').status_code, 403)
        self.assertEqual(self.review(first, current['revision'], 'snowboard', {'unknown': 2}).status_code, 400)
        self.assertEqual(self.review(first, current['revision'], 'snowboard', {'heel-leaf': 2}).status_code, 200)

        self.api.force_authenticate(self.hq)
        changed = deepcopy(current['rubric'])
        changed['ratings']['2'] = '達標'
        changed['disciplines']['snowboard']['rules'][0]['match'] = 'any'
        payload = {'revision': current['revision'], 'rubric': changed}
        saved = self.api.put(self.admin_path, payload, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(self.api.put(self.admin_path, payload, format='json').status_code, 409)
        other = Client.objects.create(name='Other school', internal_code='other')
        self.assertEqual(self.api.get('/api/admin/other/evaluations/rubric/').status_code, 403)
        self.assertFalse(other.site_contents.exists())

        self.api.force_authenticate(self.coach.user)
        self.assertEqual(self.review(second, current['revision'], 'snowboard', {'heel-leaf': 2}).status_code, 400)
        self.assertEqual(self.review(second, saved.data['data']['revision'], 'snowboard', {'heel-leaf': 2}).status_code, 200)
        self.api.force_authenticate(self.parent)
        records = {row['id']: row['technical_assessment'][0] for row in self.api.get(self.member_path).data['learning_records']}
        self.assertEqual((records[first.pk]['level'], records[first.pk]['scores'][0]['rating']), (1, '很好'))
        self.assertEqual((records[second.pk]['level'], records[second.pk]['scores'][0]['rating']), (2, '達標'))
