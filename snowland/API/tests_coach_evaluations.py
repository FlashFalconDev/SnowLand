from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach
from Control.models import UserProfile
from Resorts.models import Campus
from booking.models import Booking, CourseEvaluation, MemberDetail, Reservation, ReservationGroup


class CoachEvaluationTests(TestCase):
    url = '/api/admin/snowland/coach/evaluations/'

    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.campus = Campus.objects.create(client=self.tenant, name='道東', code='east')
        self.member = User.objects.create_user('evaluation-member')
        self.coach_user = User.objects.create_user('evaluation-coach')
        profile, _ = UserProfile.objects.get_or_create(user=self.coach_user)
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        self.coach_user.refresh_from_db()
        self.coach = Coach.objects.create(client=self.tenant, user=self.coach_user, name='QA Coach')
        self.coach.campuses.add(self.campus)
        self.other = Coach.objects.create(client=self.tenant, name='Other Coach')
        self.own = self.evaluation(self.coach)
        self.foreign = self.evaluation(self.other)
        self.api = APIClient()
        self.api.force_authenticate(self.coach_user)

    def evaluation(self, coach, status='completed'):
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus, user=self.member)
        reservation = Reservation.objects.create(group=group, preferred_coach=coach, status=status)
        booking = Booking.objects.create(reservation=reservation, date=timezone.localdate()-timedelta(days=1), start_time='09:00', end_time='12:00')
        member = MemberDetail.objects.create(reservation=reservation, user=self.member, insurance_data={'full_name': 'QA Student'})
        return CourseEvaluation.objects.create(booking=booking, member=member, coach=coach)

    def test_coach_lists_and_edits_only_own_completed_course_and_member_sees_notes(self):
        pending = self.evaluation(self.coach, 'auto_assigned')
        response = self.api.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row['id'] for row in response.data['data']['list']], [self.own.id])
        updated = self.api.patch(f'{self.url}{self.own.id}/', {'coach_notes': '已能安全煞車', 'learning_progress': {'turn': '進步'}, 'completed_at': timezone.now().isoformat()}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(self.api.patch(f'{self.url}{self.foreign.id}/', {'coach_notes': '不可修改'}, format='json').status_code, 404)
        self.assertEqual(self.api.get(f'{self.url}{pending.id}/').status_code, 404)
        member_api = APIClient()
        member_api.force_authenticate(self.member)
        rows = member_api.get('/booking/snowland/api/member-center/').data['learning_records']
        self.assertEqual(next(row for row in rows if row['id'] == self.own.id)['coach_notes'], '已能安全煞車')

    def test_no_reassignment_no_member_rating_write_no_create_or_delete(self):
        for field, value in [('booking', self.foreign.booking_id), ('member', self.foreign.member_id), ('coach', self.other.id), ('self_assessment', {'satisfaction_rating': 5})]:
            with self.subTest(field=field):
                response = self.api.patch(f'{self.url}{self.own.id}/', {field: value}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
        self.own.refresh_from_db()
        self.assertEqual(self.own.coach_id, self.coach.id)
        self.assertFalse(self.own.self_assessment)
        self.assertEqual(self.api.delete(f'{self.url}{self.own.id}/').status_code, 405)
        self.assertEqual(self.api.post(self.url, {}, format='json').status_code, 405)

    def test_other_tenant_non_coach_and_admin_modules_are_denied(self):
        Client.objects.create(name='Other', internal_code='other')
        self.assertEqual(self.api.get('/api/admin/other/coach/evaluations/').status_code, 403)
        self.assertEqual(self.api.get('/api/admin/snowland/evaluations/').status_code, 403)
        self.assertEqual(self.api.get('/api/admin/snowland/insurance-records/').status_code, 403)
        self.api.force_authenticate(self.member)
        self.assertEqual(self.api.get(self.url).status_code, 403)

    def test_coach_media_is_private_and_invalid_media_does_not_save_notes(self):
        url = f'{self.url}{self.own.id}/'
        for media in [{'media_type': 'photo', 'url': 'javascript:alert(1)'}, {'media_type': 'photo', 'url': 'https://example.test/photo.jpg', 'is_public': True}]:
            response = self.api.patch(url, {'coach_notes': '不應保存', 'new_media': media}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.own.refresh_from_db()
        self.assertEqual(self.own.coach_notes, '')
        self.assertFalse(self.own.media.exists())
        saved = self.api.patch(url, {'coach_notes': '會員可看', 'new_media': {'media_type': 'photo', 'url': 'https://example.test/photo.jpg', 'is_public': False}}, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertFalse(self.own.media.get().is_public)

    def test_member_feedback_is_visible_to_own_coach_but_cannot_be_changed_by_coach(self):
        member_api = APIClient()
        member_api.force_authenticate(self.member)
        saved = member_api.post('/booking/snowland/api/member-center/', {
            'action': 'submit_satisfaction', 'evaluation_id': self.own.id,
            'rating': 4, 'feedback': '教練說明清楚，希望增加練習時間',
        }, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        row = self.api.get(self.url).data['data']['list'][0]
        self.assertEqual(row['self_assessment']['satisfaction_rating'], 4)
        self.assertEqual(row['self_assessment']['satisfaction_feedback'], '教練說明清楚，希望增加練習時間')
        denied = self.api.patch(f'{self.url}{self.own.id}/', {'self_assessment': {}}, format='json')
        self.assertEqual(denied.status_code, 400, denied.data)
        self.own.refresh_from_db()
        self.assertEqual(self.own.self_assessment['satisfaction_rating'], 4)
