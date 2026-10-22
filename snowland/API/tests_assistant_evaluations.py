from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from API import tests_campus_scope as fixtures
from Coach.models import Coach
from booking.models import Booking, CourseEvaluation, MemberDetail, Reservation, ReservationGroup


class AssistantEvaluationTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)
        self.profile.role = 'assistant'
        self.profile.admin_permissions = None
        self.profile.save()
        self.manager.refresh_from_db()
        self.api = APIClient()
        self.api.force_authenticate(self.manager)
        self.learner = User.objects.create_user('qa-assistant-evaluation-learner')
        self.coach = Coach.objects.create(client=self.tenant, user=self.manager, name='QA 兼任教練')
        self.coach.campuses.add(self.campus_a)
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, user=self.learner)
        reservation = Reservation.objects.create(group=group, preferred_coach=self.coach, status='completed')
        booking = Booking.objects.create(reservation=reservation, date=timezone.localdate()-timedelta(days=1), start_time='09:00', end_time='12:00')
        member = MemberDetail.objects.create(reservation=reservation, user=self.learner)
        self.evaluation = CourseEvaluation.objects.create(booking=booking, member=member, coach=self.coach,
            coach_notes='原教練評語', learning_progress={'turn':'持續練習'}, trail_names=['QA雪道'], completed_at=timezone.now())
        self.url = '/api/admin/snowland/evaluations/'

    def test_assistant_cannot_rewrite_assessment_or_create_delete_evaluations(self):
        detail = f'{self.url}{self.evaluation.pk}/'
        for data in ({'coach_notes':'冒寫'}, {'learning_progress':{'turn':'冒寫'}}, {'trail_names':[]},
                     {'completed_at':None}, {'self_assessment':{'satisfaction_rating':5}},
                     {'new_media':{'media_type':'photo','url':'https://example.test/a.png'}, 'coach_notes':'夾帶修改'}):
            result = self.api.patch(detail, data, format='json')
            self.assertEqual(result.status_code, 403, result.data)
        self.assertEqual(self.api.post(self.url, {}, format='json').status_code, 403)
        self.assertEqual(self.api.delete(detail).status_code, 403)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.coach_notes, '原教練評語')
        self.assertFalse(self.evaluation.media.exists())
        self.assertFalse(self.api.get(self.url).data['data']['list'][0]['can_edit_assessment'])

    def test_assistant_adds_private_media_without_marking_or_changing_assessment(self):
        detail = f'{self.url}{self.evaluation.pk}/'
        before = (self.evaluation.coach_notes, self.evaluation.learning_progress, self.evaluation.completed_at)
        result = self.api.patch(detail, {'new_media':{'media_type':'photo','url':'https://example.test/a.png','is_public':False}}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.evaluation.refresh_from_db()
        self.assertEqual((self.evaluation.coach_notes,self.evaluation.learning_progress,self.evaluation.completed_at), before)
        self.assertFalse(self.evaluation.media.get().is_public)
        published = self.api.post(f'{detail}media/', {'media_type':'photo','url':'https://example.test/b.png','is_public':True}, format='json')
        self.assertEqual(published.status_code, 403, published.data)
        self.assertEqual(self.evaluation.media.count(), 1)

    def test_private_file_upload_still_works_and_does_not_modify_evaluation(self):
        output = BytesIO()
        Image.new('RGB', (2,2), 'blue').save(output, format='PNG')
        with TemporaryDirectory() as root, override_settings(PRIVATE_COURSE_MEDIA_ROOT=root):
            response = self.api.patch(f'{self.url}{self.evaluation.pk}/upload/',
                {'file':SimpleUploadedFile('qa.png', output.getvalue(), content_type='image/png')}, format='multipart')
            self.assertEqual(response.status_code, 201, response.data)
            self.evaluation.refresh_from_db()
            self.assertEqual(self.evaluation.coach_notes, '原教練評語')
            self.assertFalse(self.evaluation.media.get().is_public)
            learner = APIClient()
            learner.force_authenticate(self.learner)
            photo = learner.get(response.data['data']['url'])
            self.assertEqual(photo.status_code, 200)
            photo.close()

    def test_dual_role_assistant_can_edit_only_when_acting_as_assigned_coach(self):
        self.profile.is_coach = True
        self.profile.save()
        self.manager.refresh_from_db()
        url = f'/api/admin/snowland/coach/evaluations/{self.evaluation.pk}/'
        self.assertTrue(self.api.get(url).data['can_edit_assessment'])
        updated = self.api.patch(url, {'coach_notes':'本人授課評語'}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertFalse(self.api.get(self.url).data['data']['list'][0]['can_edit_assessment'])

    def test_session_media_writes_require_csrf(self):
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(self.manager)
        detail = f'{self.url}{self.evaluation.pk}/'
        media = {'new_media':{'media_type':'photo','url':'https://example.test/a.png'}}
        self.assertEqual(api.patch(detail, media, format='json').status_code, 403)
        api.get(self.url)
        response = api.patch(detail, media, format='json', HTTP_X_CSRFTOKEN=api.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200, response.data)
