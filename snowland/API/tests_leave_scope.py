from datetime import datetime, timedelta, timezone as datetime_timezone

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_campus_scope as fixtures
from Coach.models import Coach, CoachLeaveRequest
from booking.models import Reservation, ReservationGroup


class LeaveScopeTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)
        self.profile.admin_permissions = ['coaches']
        self.profile.save()
        self.manager.refresh_from_db()
        self.api = APIClient()
        self.api.force_authenticate(self.manager)
        self.a = Coach.objects.create(client=self.tenant, name='A coach')
        self.a.campuses.add(self.campus_a)
        self.b = Coach.objects.create(client=self.tenant, name='B coach')
        self.b.campuses.add(self.campus_b)
        self.foreign = Coach.objects.create(client=self.other_tenant, name='Foreign coach')
        self.own = self.leave(self.a)
        self.other = self.leave(self.b)
        self.external = self.leave(self.foreign)
        self.url = '/api/admin/snowland/coach-leaves/'

    def leave(self, coach):
        return CoachLeaveRequest.objects.create(
            coach=coach, start_date=timezone.localdate()+timedelta(days=2),
            end_date=timezone.localdate()+timedelta(days=3), reason='QA 請假',
        )

    def test_manager_lists_only_own_campus_and_cannot_review_other_campus(self):
        listed = self.api.get(self.url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row['id'] for row in listed.data['data']['list']], [self.own.pk])
        for leave in (self.other, self.external):
            self.assertEqual(self.api.get(f'{self.url}{leave.pk}/').status_code, 404)
            self.assertEqual(self.api.put(f'{self.url}{leave.pk}/', {'status': 'approved'}, format='json').status_code, 404)
            leave.refresh_from_db()
            self.assertEqual(leave.status, 'pending')

    def test_headquarters_selected_campus_and_assistant_read_only(self):
        self.profile.role = 'assistant'
        self.profile.admin_permissions = None
        self.profile.save()
        self.manager.refresh_from_db()
        rows = self.api.get(self.url).data['data']['list']
        self.assertEqual({row['id'] for row in rows}, {self.own.pk, self.other.pk})
        self.assertTrue(all(row['can_review'] is False for row in rows))
        options = self.api.get(f'{self.url}special-options/').data['data']
        self.assertFalse(options['can_create'])
        self.assertEqual(options['coaches'], [])
        result = self.api.put(f'{self.url}{self.own.pk}/', {'status': 'approved'}, format='json')
        self.assertEqual(result.status_code, 403, result.data)
        self.own.refresh_from_db()
        self.assertEqual(self.own.status, 'pending')
        selected = self.api.get(self.url, HTTP_X_CAMPUS_ID=str(self.campus_b.pk))
        self.assertEqual([row['id'] for row in selected.data['data']['list']], [self.other.pk])

    def test_review_validates_note_and_only_pending_request_can_transition(self):
        detail = f'{self.url}{self.own.pk}/'
        for note in ([], {}, True, 'x'*1001):
            with self.subTest(note_type=type(note).__name__):
                result = self.api.put(detail, {'status': 'approved', 'processing_result': note}, format='json')
                self.assertEqual(result.status_code, 400, result.data)
        self.assertEqual(self.api.put(detail, {'status': 'rejected', 'processing_result': '  '}, format='json').status_code, 400)
        approved = self.api.put(detail, {'status': 'approved', 'processing_result': '  已確認  '}, format='json')
        self.assertEqual(approved.status_code, 200, approved.data)
        self.own.refresh_from_db()
        stamp = self.own.reviewed_at
        self.assertEqual(self.own.processing_result, '已確認')
        self.assertEqual(self.own.reviewed_by_id, self.manager.pk)
        repeated = self.api.patch(detail, {'status': 'rejected', 'processing_result': '不能覆蓋'}, format='json')
        self.assertEqual(repeated.status_code, 409, repeated.data)
        self.own.refresh_from_db()
        self.assertEqual(self.own.status, 'approved')
        self.assertEqual(self.own.reviewed_at, stamp)

    def test_assistant_cannot_create_and_admin_cannot_delete_leave_history(self):
        self.profile.role = 'assistant'
        self.profile.save()
        self.manager.refresh_from_db()
        created = self.api.post(self.url, {'coach': self.a.pk, 'start_date': '2026-12-01', 'end_date': '2026-12-02', 'reason': '不應代建'}, format='json')
        self.assertEqual(created.status_code, 403, created.data)
        self.assertEqual(self.api.delete(f'{self.url}{self.own.pk}/').status_code, 405)
        self.assertTrue(CoachLeaveRequest.objects.filter(pk=self.own.pk).exists())

    def test_special_leave_requires_ack_and_scope_but_can_override_normal_advance_rule(self):
        options = self.api.get(f'{self.url}special-options/').data['data']
        self.assertTrue(options['can_create'])
        self.assertEqual([coach['id'] for coach in options['coaches']], [self.a.pk])
        payload = {'coach': self.a.pk, 'start_date': str(timezone.localdate()),
                   'end_date': str(timezone.localdate()), 'reason': 'QA 緊急特批'}
        self.assertEqual(self.api.post(self.url, payload, format='json').status_code, 400)
        payload['confirm_special_leave'] = True
        for coach in (self.b, self.foreign):
            blocked = self.api.post(self.url, {**payload, 'coach':coach.pk}, format='json')
            self.assertEqual(blocked.status_code, 403, blocked.data)
        created = self.api.post(self.url, payload, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        leave = CoachLeaveRequest.objects.get(pk=created.data['data']['id'])
        self.assertEqual(leave.status, 'approved')
        self.assertEqual(leave.reviewed_by_id, self.manager.pk)
        self.assertIsNotNone(leave.reviewed_at)
        self.assertEqual(self.api.post(self.url, payload, format='json').status_code, 409)

    def test_shared_coach_leave_is_visible_but_cannot_change_other_campus_availability(self):
        self.a.campuses.add(self.campus_b)
        row = self.api.get(self.url).data['data']['list'][0]
        self.assertEqual(row['id'], self.own.pk)
        self.assertFalse(row['can_review'])
        blocked = self.api.patch(f'{self.url}{self.own.pk}/', {'status': 'approved'}, format='json')
        self.assertEqual(blocked.status_code, 403, blocked.data)
        headquarters = APIClient()
        headquarters.force_authenticate(self.superuser)
        approved = headquarters.patch(f'{self.url}{self.own.pk}/', {'status': 'approved'}, format='json')
        self.assertEqual(approved.status_code, 200, approved.data)

    def test_csrf_is_required_for_session_review(self):
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(self.manager)
        url = f'{self.url}{self.own.pk}/'
        denied = api.put(url, {'status': 'approved'}, format='json')
        self.assertEqual(denied.status_code, 403, denied.data)
        self.assertEqual(api.get(self.url).status_code, 200)
        token = api.cookies['csrftoken'].value
        allowed = api.put(url, {'status': 'approved'}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(allowed.status_code, 200, allowed.data)

    def test_coach_own_history_uses_local_time_and_shows_review_result(self):
        user = User.objects.create_user('qa-leave-coach')
        profile = user.userprofile
        profile.is_coach = True
        profile.save()
        self.a.user = user
        self.a.save(update_fields=['user'])
        stamp = datetime(2026, 10, 15, 16, 10, tzinfo=datetime_timezone.utc)
        CoachLeaveRequest.objects.filter(pk=self.own.pk).update(created_at=stamp)
        result = self.api.put(f'{self.url}{self.own.pk}/', {'status': 'rejected', 'processing_result': 'QA 請改日期'}, format='json')
        self.assertEqual(result.status_code, 200)
        api = APIClient()
        api.force_authenticate(user)
        rows = api.get('/api/admin/snowland/coach/my-leaves/').data['data']['list']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['created_at'], '2026-10-16 00:10')
        self.assertEqual(rows[0]['status'], 'rejected')
        self.assertEqual(rows[0]['processing_result'], 'QA 請改日期')

    def test_selected_headquarters_scope_does_not_review_other_campus(self):
        api = APIClient()
        api.force_authenticate(self.superuser)
        scope = {'HTTP_X_CAMPUS_ID': str(self.campus_a.pk)}
        rows = api.get(self.url, **scope).data['data']['list']
        self.assertEqual([row['id'] for row in rows], [self.own.pk])
        result = api.put(f'{self.url}{self.other.pk}/', {'status': 'approved'}, format='json', **scope)
        self.assertEqual(result.status_code, 404)
        self.other.refresh_from_db()
        self.assertEqual(self.other.status, 'pending')

    def test_campus_principal_can_review_and_affected_count_is_scoped(self):
        for tenant, campus in [(self.tenant,self.campus_a), (self.tenant,self.campus_b), (self.other_tenant,None)]:
            group = ReservationGroup.objects.create(client=tenant, campus=campus)
            self.own.affected_reservations.add(Reservation.objects.create(group=group))
        self.profile.role = 'campus_principal'
        self.profile.save()
        self.manager.refresh_from_db()
        row = self.api.get(self.url).data['data']['list'][0]
        self.assertEqual(row['affected_count'], 1)
        self.assertTrue(row['can_review'])
        reviewed = self.api.put(f'{self.url}{self.own.pk}/', {'status': 'approved'}, format='json')
        self.assertEqual(reviewed.status_code, 200, reviewed.data)
        self.assertEqual(reviewed.data['data']['affected_count'], 1)

    def test_cancelled_request_is_not_reviewable(self):
        self.own.status = 'cancelled'
        self.own.save(update_fields=['status'])
        row = self.api.get(self.url).data['data']['list'][0]
        self.assertFalse(row['can_review'])
        response = self.api.put(f'{self.url}{self.own.pk}/', {'status': 'approved'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.own.refresh_from_db()
        self.assertEqual(self.own.status, 'cancelled')
