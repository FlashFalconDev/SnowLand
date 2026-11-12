from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach
from Control.models import TenantStaffMembership
from booking import tests_participants as fixtures
from booking.models import Booking, CourseAlbumAsset, CourseEvaluation, LearnerProfile, MemberDetail, Payment, Reservation, ReservationGroup


PROFILES = '/booking/snowland/api/learner-profiles/'
ALBUMS = '/booking/snowland/api/course-albums/'
MEMBER = '/booking/snowland/api/member-center/'
COACH = '/api/admin/snowland/coach/'


class LearnerHistoryTests(TestCase):
    def setUp(self):
        fixtures.MemberEnrollmentTests.setUp(self)
        self.school = Client.objects.get(internal_code='snowland')
        self.other_school = Client.objects.create(name='Other', internal_code='other')
        self.child_a = self.make_profile('QA child A')
        self.child_b = self.make_profile('QA child B')
        self.coach_a = self.make_coach('qa-course-coach-a')
        self.coach_b = self.make_coach('qa-course-coach-b')

    def make_profile(self, name):
        response = self.api.post(PROFILES, {'action': 'create', 'name': name}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def make_coach(self, name):
        user = User.objects.create_user(name)
        TenantStaffMembership.objects.create(client=self.school, user=user, is_coach=True)
        return Coach.objects.create(client=self.school, user=user, name=name)

    def book_with_profiles(self, *ids, advanced=False):
        url = '/booking/snowland/api/super-schedule/' if advanced else '/booking/snowland/api/create-reservation/'
        body = self.checkout_body()
        body['cart'] = [{
            'coach': 'any', 'peopleCount': 2, 'abilityLevel': 'no_exp', 'abilityLevelCounts': {'no_exp': 2},
            'equipment': False, 'equipmentOption': 'own_equipment', 'language': 'zh',
            'resort': self.resort.name, 'campusId': self.campus.pk, 'courseCategory': '單板',
            'courses': [{
                'date': str(timezone.localdate() + timedelta(days=20)),
                'courseTypeId': self.template.course_type_id, 'courseTemplateId': self.template.pk,
                'durationHours': 4, 'timeSlotStart': '09:00', 'timeSlotEnd': '13:00',
            }],
        }]
        body['learner_selections'] = [list(ids)]
        return self.api.post(url, body, format='json')

    def checkout_body(self):
        from booking.tests_policy_support import checkout_policy_acknowledgement
        return {
            **checkout_policy_acknowledgement(),
            'contact': {'name': 'QA parent', 'email': self.owner.email, 'phone': '0900000000',
                        'messengerType': 'line', 'messengerId': 'qa-only', 'referralSource': '其他'},
        }

    def evaluate(self, reservation, coach, days_ago, scores):
        reservation.preferred_coach = coach
        reservation.status = 'completed'
        reservation.save()
        booking = reservation.bookings.first()
        booking.date = timezone.localdate() - timedelta(days=days_ago)
        booking.save(update_fields=['date'])
        self.api.force_authenticate(coach.user)
        rubric = self.api.get(COACH + 'evaluations/rubric/').data['data']
        evaluations = []
        for place, score in zip(reservation.members.order_by('pk'), scores):
            evaluation = CourseEvaluation.objects.create(booking=booking, member=place, coach=coach)
            updated = self.api.patch(f'{COACH}evaluations/{evaluation.pk}/', {
                'completed_at': timezone.now().isoformat(), 'coach_notes': f'QA technique {score}',
                'skill_review': {'revision': rubric['revision'], 'entries': {
                    'snowboard': {'scores': {score: 2}, 'next_steps': []},
                }},
            }, format='json')
            self.assertEqual(updated.status_code, 200, updated.data)
            evaluations.append(evaluation)
        self.api.force_authenticate(self.owner)
        return evaluations

    def test_two_children_and_two_orders_accumulate_only_the_matching_child(self):
        reservations = []
        for _ in range(2):
            response = self.book_with_profiles(self.child_a, self.child_b)
            self.assertEqual(response.status_code, 200, response.data)
            row = Reservation.objects.get(group_id=response.data['reservation_group_ids'][0])
            self.assertEqual(list(row.members.order_by('pk').values_list('learner_id', flat=True)), [self.child_a, self.child_b])
            reservations.append(row)
        first, sibling = self.evaluate(reservations[0], self.coach_a, 3, ['heel-leaf', 'toe-leaf'])
        second, = self.evaluate(reservations[1], self.coach_b, 1, ['toe-leaf'])
        payload = self.api.get(MEMBER).data
        rows = {row['id']: row for row in payload['learning_records']}
        self.assertEqual(rows[first.pk]['technical_assessment'][0]['level'], 1)
        self.assertEqual(rows[sibling.pk]['technical_assessment'][0]['level'], 1)
        self.assertEqual(rows[second.pk]['technical_assessment'][0]['level'], 2)
        self.assertEqual(rows[second.pk]['member_name'], 'QA child A')
        self.assertEqual(rows[sibling.pk]['member_name'], 'QA child B')

        # New coach can prepare for the next lesson, without opening the original coach's evaluation.
        order = self.book_with_profiles(self.child_a, self.child_b)
        self.assertEqual(order.status_code, 200, order.data)
        future = Reservation.objects.get(group_id=order.data['reservation_group_ids'][0])
        future.bookings.update(date=timezone.localdate() + timedelta(days=2))
        future.preferred_coach = self.coach_b
        future.status = 'pending_coach_confirmation'
        future.save()
        path = f'{COACH}learner-history/{future.pk}/'
        self.api.force_authenticate(self.coach_b.user)
        self.assertEqual(self.api.get(path).status_code, 404)
        future.status = 'manually_assigned'
        future.save()
        self.assertEqual(self.api.get(path).status_code, 404)
        Payment.objects.create(reservation_group=future.group, status='pending', payment_method='TT')
        result = self.api.get(path)
        self.assertEqual(result.status_code, 200, result.data)
        history = {row['name']: row['records'] for row in result.data['data']}
        self.assertEqual([row['technical_assessment'][0]['level'] for row in history['QA child A']], [2, 1])
        self.assertEqual(len(history['QA child B']), 1)
        self.assertEqual(set(history['QA child A'][0]), {'date', 'course_name', 'coach_notes', 'technical_assessment', 'learning_progress'})
        self.assertEqual(self.api.patch(path, {}, format='json').status_code, 405)
        self.assertEqual(self.api.get(f'{COACH}evaluations/{first.pk}/').status_code, 404)
        self.api.force_authenticate(self.coach_a.user)
        self.assertEqual(self.api.get(path).status_code, 404)

    def test_checkout_rejects_foreign_or_duplicate_profiles_without_partial_order(self):
        foreign = LearnerProfile.objects.create(client=self.other_school, owner=self.owner, name='Foreign')
        unrelated = LearnerProfile.objects.create(client=self.school, owner=self.coach_a.user, name='Unrelated')
        before = ReservationGroup.objects.count()
        for ids in [(self.child_a, self.child_a), (self.child_a, foreign.pk), (self.child_a, unrelated.pk), (self.child_a,)]:
            response = self.book_with_profiles(*ids)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(ReservationGroup.objects.count(), before)
        response = self.book_with_profiles(self.child_b, self.child_a, advanced=True)
        self.assertEqual(response.status_code, 200, response.data)
        reservation = Reservation.objects.get(group_id=response.data['reservation_group_ids'][0])
        self.assertEqual(list(reservation.members.order_by('pk').values_list('learner_id', flat=True)), [self.child_b, self.child_a])

    def test_staff_must_confirm_old_record_and_only_choose_same_account(self):
        response = self.book_with_profiles(None, None)
        self.assertEqual(response.status_code, 200, response.data)
        reservation = Reservation.objects.get(group_id=response.data['reservation_group_ids'][0])
        evaluation, = self.evaluate(reservation, self.coach_a, 1, ['heel-leaf'])
        self.assertEqual(self.api.post(PROFILES, {'action': 'bind', 'member_id': evaluation.member_id, 'profile_id': self.child_a}, format='json').status_code, 409)
        path = f'/api/admin/snowland/evaluations/{evaluation.pk}/learner-profile/'
        hq = User.objects.create_user('learning-hq')
        TenantStaffMembership.objects.create(user=hq, client=self.school, role='hq_admin', is_manager=True)
        self.api.force_authenticate(hq)
        choices = self.api.get(path)
        self.assertEqual(choices.status_code, 200, choices.data)
        self.assertEqual({row['id'] for row in choices.data['data']['profiles']}, {self.child_a, self.child_b})
        self.assertEqual(self.api.head(path).status_code, 200)
        self.assertIsNone(MemberDetail.objects.get(pk=evaluation.member_id).learner_id)
        self.assertEqual(self.api.patch(path, [], format='json').status_code, 400)
        self.assertEqual(self.api.patch(path, {'profile_id': self.child_a}, format='json').status_code, 400)
        self.assertEqual(self.api.patch(path, {'profile_id': self.child_a, 'verified': True}, format='json').status_code, 200)
        self.assertEqual(MemberDetail.objects.get(pk=evaluation.member_id).learner_id, self.child_a)


class CourseAlbumTests(TestCase):
    def test_four_participants_one_storage_object_with_optional_claims(self):
        school = Client.objects.create(name='SnowLand', internal_code='snowland')
        other = Client.objects.create(name='Other', internal_code='other')
        coach_user = User.objects.create_user('qa-album-coach')
        TenantStaffMembership.objects.create(client=school, user=coach_user, is_coach=True)
        coach = Coach.objects.create(client=school, user=coach_user, name='QA Coach')
        parent, second, third, fourth, unrelated = [User.objects.create_user(f'qa-album-{i}') for i in range(5)]
        group = ReservationGroup.objects.create(client=school, user=parent)
        reservation = Reservation.objects.create(group=group, preferred_coach=coach, status='completed', number_of_people=4)
        booking = Booking.objects.create(reservation=reservation, date=timezone.localdate()-timedelta(days=1), start_time='09:00', end_time='12:00')
        tomorrow = Booking.objects.create(reservation=reservation, date=timezone.localdate()+timedelta(days=1), start_time='09:00', end_time='12:00')
        places = [MemberDetail.objects.create(reservation=reservation, guardian=parent)] + [
            MemberDetail.objects.create(reservation=reservation, user=user) for user in [second, third, fourth]
        ]
        api = APIClient()
        api.force_authenticate(coach_user)
        path = f'{COACH}course-albums/{booking.pk}/'
        self.assertEqual(api.get(path).status_code, 404)
        self.assertEqual(api.post(path, {}, format='multipart').status_code, 404)
        Payment.objects.create(reservation_group=group, status='pending', payment_method='TT')
        self.assertEqual(api.get(f'{COACH}course-albums/{tomorrow.pk}/').status_code, 404)
        self.assertEqual(api.get(path).data['data']['assets'], [])
        self.assertEqual(api.patch(path, [], format='json').status_code, 400)
        png = BytesIO()
        Image.new('RGB', (16, 16), '#123456').save(png, format='PNG')
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder, override_settings(PRIVATE_COURSE_MEDIA_ROOT=folder):
            self.assertEqual(api.post(path, {'file': SimpleUploadedFile('bad.jpg', b'not a photo')}, format='multipart').status_code, 400)
            uploaded = api.post(path, {'file': SimpleUploadedFile('photo.png', png.getvalue(), content_type='image/png')}, format='multipart')
            self.assertEqual(uploaded.status_code, 201, uploaded.data)
            asset = uploaded.data['data']
            self.assertEqual(api.patch(path, {'asset_id': asset['id'], 'member_id': places[1].pk, 'tagged': True}, format='json').status_code, 200)
            for user, place in zip([parent, second, third, fourth], places):
                api.force_authenticate(user)
                result = api.get(ALBUMS)
                self.assertEqual(result.status_code, 200, result.data)
                album, = result.data['albums']
                self.assertEqual(album['date'], str(booking.date))
                self.assertEqual([row['id'] for row in album['members']], [place.pk])
                self.assertEqual(album['assets'][0]['id'], asset['id'])
                response = api.get(asset['url'])
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b''.join(response.streaming_content), png.getvalue())
            api.force_authenticate(parent)
            tag = {'asset_id': asset['id'], 'member_id': places[0].pk, 'tagged': True}
            self.assertEqual(api.patch(ALBUMS, tag, format='json').status_code, 200)
            self.assertEqual(api.patch(ALBUMS, {**tag, 'member_id': places[2].pk}, format='json').status_code, 404)
            self.assertEqual(api.get(ALBUMS).data['albums'][0]['assets'][0]['tagged_member_ids'], [places[0].pk])
            self.assertEqual(api.get(asset['url'].replace('/snowland/', '/other/')).status_code, 404)
            self.assertEqual(CourseAlbumAsset.objects.get().tagged_members.count(), 2)
            self.assertEqual(len([p for p in Path(folder).rglob('*') if p.is_file()]), 1)
            self.assertEqual(api.patch(ALBUMS, {**tag, 'tagged': False}, format='json').status_code, 200)
            self.assertEqual(api.get(ALBUMS).data['albums'][0]['assets'][0]['tagged_member_ids'], [])
            self.assertEqual(CourseAlbumAsset.objects.get().tagged_members.count(), 1)
            api.force_authenticate(unrelated)
            self.assertEqual(api.get(ALBUMS).data['albums'], [])
            self.assertEqual(api.get(asset['url']).status_code, 404)
            places[3].is_active = False
            places[3].save(update_fields=['is_active'])
            api.force_authenticate(fourth)
            self.assertEqual(api.get(asset['url']).status_code, 404)
