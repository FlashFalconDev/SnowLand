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

from Client.models import Client, SiteContent
from Coach.models import Coach
from Control.models import TenantStaffMembership
from booking import tests_participants as fixtures
from booking.coach_pre_course_summary import COACH_SUMMARY_LOCATION
from booking.models import (
    Booking, CourseAlbumAsset, CourseEvaluation, LearnerProfile, MemberDetail,
    MemberWaiverSignature, Payment, Reservation, ReservationGroup,
)


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


class CoachPreCourseSummaryTests(TestCase):
    def setUp(self):
        self.school = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.other_school = Client.objects.create(name='Other', internal_code='other')
        self.owner = User.objects.create_user('qa-summary-member')
        self.api = APIClient()
        self.reservation = self.make_course(self.school)
        self.coach = self.reservation.preferred_coach
        self.path = f'{COACH}learner-history/{self.reservation.pk}/'
        self.cms = '/api/admin/snowland/site-content/'

    def make_course(self, school, coach=None):
        if coach is None:
            user = User.objects.create_user(f'qa-summary-coach-{school.internal_code}')
            TenantStaffMembership.objects.create(client=school, user=user, is_coach=True)
            coach = Coach.objects.create(client=school, user=user, name='QA coach')
        group = ReservationGroup.objects.create(client=school, user=self.owner)
        Payment.objects.create(reservation_group=group, status='pending', payment_method='TT')
        reservation = Reservation.objects.create(
            group=group, preferred_coach=coach, status='manually_assigned', number_of_people=7,
        )
        Booking.objects.create(
            reservation=reservation, date=timezone.localdate(), start_time='09:00', end_time='12:00',
        )
        return reservation

    def make_place(self, *, reservation=None, **values):
        return MemberDetail.all_objects.create(**{
            'reservation': reservation or self.reservation, 'user': self.owner, 'age_range': '', **values,
        })

    def authenticate_manager(self, school):
        user = User.objects.create_user(f'qa-summary-manager-{school.internal_code}')
        TenantStaffMembership.objects.create(client=school, user=user, is_manager=True, role='hq_admin')
        self.api.force_authenticate(user)

    def save_setting(self, fields, *, cms=None):
        return self.api.post(cms or self.cms, {
            'content_type': 'setting', 'location_key': COACH_SUMMARY_LOCATION,
            'metadata': {'fields': fields},
        }, format='json')

    def summaries(self):
        self.api.force_authenticate(self.coach.user)
        response = self.api.get(self.path)
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id']: row['pre_course_summary'] for row in response.data['data']}

    def test_summary_uses_defaults_and_distinguishes_assessment_states(self):
        completed = self.make_place(
            age_range='25-35y', ski_skills=['雪場並腿轉彎'], snowboard_skills=['雪場S turn'],
            pre_course_answers={'experience': {
                'kind': 'returning', 'recent': 'yes', 'boards': ['ski', 'snowboard'], 'finished': True,
            }},
        )
        no_experience = self.make_place(
            snowboard_skills=['無經驗'],
            pre_course_answers={'experience': {'kind': 'new', 'recent': 'no', 'finished': True}},
        )
        incomplete = self.make_place(pre_course_answers={'experience': {'kind': 'new', 'finished': False}})
        empty = self.make_place(pre_course_answers={'experience': {
            'kind': '', 'recent': '', 'boards': [], 'areas': [], 'notes': '', 'resort': '', 'finished': False,
        }})
        old_skills = self.make_place(ski_skills=['雪場綠線順滑'])
        old_age = self.make_place(age_range='7-12y')
        data = self.summaries()
        for place, status, label in (
            (completed, 'filled', '已填'), (no_experience, 'filled', '已填'),
            (incomplete, 'incomplete', '未完成'), (empty, 'empty', '未填'),
            (old_skills, 'incomplete', '未完成'), (old_age, 'incomplete', '未完成'),
        ):
            with self.subTest(place=place.pk):
                self.assertEqual(data[place.pk]['status'], status)
                self.assertEqual(data[place.pk]['status_label'], label)
                self.assertEqual(data[place.pk]['items'][0]['value'], label)
        self.assertEqual(data[completed.pk]['items'], [
            {'key': 'status', 'label': '完成狀態', 'value': '已填', 'filled': True},
            {'key': 'kind', 'label': '新／舊生', 'value': '舊生', 'filled': True},
            {'key': 'recent', 'label': '近期經驗', 'value': '有經驗', 'filled': True},
            {'key': 'boards', 'label': '板種', 'value': '單板、雙板', 'filled': True},
            {'key': 'skills', 'label': '技能', 'value': '單板：雪場S turn；雙板：雪場並腿轉彎', 'filled': True},
            {'key': 'age_range', 'label': '年齡', 'value': '成人25-35y', 'filled': True},
        ])
        self.assertEqual(data[no_experience.pk]['items'][2]['value'], '沒有經驗')
        self.assertEqual(data[no_experience.pk]['items'][4]['value'], '單板：無經驗')
        self.assertEqual(data[empty.pk]['empty_label'], '未填')
        self.assertEqual(data[empty.pk]['items'][1], {
            'key': 'kind', 'label': '新／舊生', 'value': None, 'filled': False,
        })
        self.assertEqual(data[old_skills.pk]['items'][4]['value'], '雙板：雪場綠線順滑')

    def test_setting_changes_order_and_visibility_without_changing_waiver(self):
        self.authenticate_manager(self.school)
        current_url = self.cms + 'coach-pre-course-summary/'
        defaults = self.api.get(current_url).data['data']
        self.assertIsNone(defaults['id'])
        self.assertEqual(defaults['available_fields'], defaults['fields'])
        note_field, = (field for field in defaults['fields'] if field['key'] == 'notes')
        self.assertFalse(note_field['visible'])
        document = SiteContent.objects.create(
            client=self.school, content_type='page', location_key='membership.waiver',
            title='QA document', body='QA waiver', status='active', metadata={'version': 'QA version'},
        )
        place = self.make_place(
            age_range='7-12y', waiver_signature='QA signer', waiver_document_version='QA version',
            waiver_completed_at=timezone.now(),
            pre_course_answers={'experience': {'kind': 'new', 'recent': 'no', 'finished': True}},
        )
        strokes = [[[20, 30], [70, 60], [120, 25]]]
        signature = MemberWaiverSignature.objects.create(
            member=place, signer=self.owner, signer_name='QA signer', signer_role='self',
            signed_at=place.waiver_completed_at, document_version='QA version',
            document_snapshot=document.body, strokes=strokes, media_consent='decline',
        )
        fields = [
            {'key': 'status', 'label': '表單狀態', 'order': 8, 'visible': True},
            {'key': 'recent', 'label': '滑雪經驗', 'order': 2, 'visible': True},
            {'key': 'age_range', 'label': '年齡區間', 'order': 1, 'visible': False},
        ]
        before = self.api.get(self.cms + 'waiver-current/').data['data']
        created = self.save_setting(defaults['fields'])
        self.assertEqual(created.status_code, 201, created.data)
        setting_id = created.data['data']['id']
        updated = self.api.patch(f'{self.cms}{setting_id}/', {'metadata': {'fields': fields}}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(self.api.get(current_url).data['data']['fields'], [fields[2], fields[1], fields[0]])
        self.assertEqual(self.api.get(self.cms + 'waiver-current/').data['data'], before)
        document.refresh_from_db()
        place.refresh_from_db()
        signature.refresh_from_db()
        self.assertEqual(document.metadata, {'version': 'QA version'})
        self.assertEqual(place.waiver_completed_at, signature.signed_at)
        self.assertEqual(place.waiver_document_version, signature.document_version)
        self.assertEqual(signature.strokes, strokes)
        self.assertEqual(signature.document_snapshot, document.body)
        self.assertEqual(self.summaries()[place.pk]['items'], [
            {'key': 'recent', 'label': '滑雪經驗', 'value': '沒有經驗', 'filled': True},
            {'key': 'status', 'label': '表單狀態', 'value': '已填', 'filled': True},
        ])

    def test_settings_validate_types_keys_and_admin_permission(self):
        valid = {'key': 'kind', 'label': '學員類型', 'order': 1, 'visible': True}
        self.api.force_authenticate(self.coach.user)
        url = self.cms + 'coach-pre-course-summary/'
        self.assertEqual(self.api.get(url).status_code, 403)
        self.assertEqual(self.save_setting([valid]).status_code, 403)
        self.authenticate_manager(self.school)
        for invalid in (
            [{**valid, 'key': 'insurance'}], [{**valid, 'label': '　'}], [{**valid, 'label': '字' * 61}],
            [{**valid, 'order': True}], [{**valid, 'order': '1'}], [{**valid, 'order': 1.5}],
            [{**valid, 'visible': 1}], [valid, valid],
        ):
            with self.subTest(fields=invalid):
                response = self.save_setting(invalid)
                self.assertEqual(response.status_code, 400, response.data)
        self.assertIsNone(self.api.get(url).data['data']['id'])
        result = self.save_setting([valid])
        self.assertEqual(result.status_code, 201, result.data)
        setting_url = f"{self.cms}{result.data['data']['id']}/"
        self.assertEqual(self.api.patch(setting_url, {
            'metadata': {'fields': [{**valid, 'key': 'waiver'}]},
        }, format='json').status_code, 400)
        self.assertEqual(self.save_setting([valid]).status_code, 400)
        self.authenticate_manager(self.other_school)
        other_cms = self.cms.replace('/snowland/', '/other/')
        self.assertIsNone(self.api.get(other_cms + 'coach-pre-course-summary/').data['data']['id'])
        foreign_url = setting_url.replace('/snowland/', '/other/')
        self.assertEqual(self.api.patch(foreign_url, {'metadata': {'fields': []}}, format='json').status_code, 404)

    def test_history_limits_results_to_assigned_coach_and_active_places(self):
        current = self.make_place()
        self.make_place(is_active=False, pre_course_answers={'experience': {'finished': True}})
        self.make_place(is_deleted=True, pre_course_answers={'experience': {'finished': True}})
        self.assertEqual(set(self.summaries()), {current.pk})
        unassigned = User.objects.create_user('qa-summary-unassigned')
        TenantStaffMembership.objects.create(client=self.school, user=unassigned, is_coach=True)
        Coach.objects.create(client=self.school, user=unassigned, name='Unassigned')
        self.api.force_authenticate(unassigned)
        self.assertEqual(self.api.get(self.path).status_code, 404)
        other_course = self.make_course(self.other_school)
        self.api.force_authenticate(other_course.preferred_coach.user)
        self.assertEqual(self.api.get(self.path).status_code, 403)
        self.assertEqual(self.api.get(self.path.replace('/snowland/', '/other/')).status_code, 404)

    def test_summary_filters_private_and_unrecognized_values_and_other_orders(self):
        self.authenticate_manager(self.school)
        settings = self.api.get(self.cms + 'coach-pre-course-summary/').data['data']['fields']
        for field in settings:
            field['visible'] = True
        self.assertEqual(self.save_setting(settings).status_code, 201)
        learner = LearnerProfile.objects.create(client=self.school, owner=self.owner, name='QA learner')
        old_reservation = self.make_course(self.school, self.coach)
        self.make_place(
            reservation=old_reservation, learner=learner, age_range='56y以上', ski_skills=['雪場黑線順滑'],
            pre_course_answers={'experience': {'kind': 'returning', 'recent': 'yes', 'finished': True}},
        )
        current = self.make_place(
            learner=learner, age_range='PRIVATE_AGE', ski_skills=['PRIVATE_SKILL', '無經驗'],
            insurance_data={'email': 'private@example.test', 'phone': 'PRIVATE_PHONE', 'id_number': 'PRIVATE_ID'},
            waiver_signature='PRIVATE_SIGNATURE',
            pre_course_answers={
                'experience': {'kind': 'new', 'boards': ['PRIVATE_BOARD'], 'notes': 'PRIVATE_NOTE', 'resort': 'PRIVATE_RESORT'},
                'waiver': {'answers': {'PRIVATE_WAIVER': 'secret'}},
                'insurance': {'answers': {'PRIVATE_INSURANCE': 'secret'}},
            },
        )
        self.api.force_authenticate(self.coach.user)
        response = self.api.get(self.path)
        self.assertEqual(response.status_code, 200, response.data)
        row, = response.data['data']
        self.assertEqual(row['id'], current.pk)
        summary = row['pre_course_summary']
        self.assertEqual(summary['status'], 'incomplete')
        self.assertEqual({field['key']: field['value'] for field in summary['items']}, {
            'status': '未完成', 'kind': '新生', 'recent': None, 'boards': None,
            'notes': None, 'skills': '雙板：無經驗', 'age_range': None,
        })
        for marker in ('PRIVATE_', 'private@example.test', 'waiver', 'insurance', '56y以上', '雪場黑線順滑'):
            self.assertNotContains(response, marker)
        public = self.api.get('/booking/snowland/api/site-content/', {'location_key': COACH_SUMMARY_LOCATION})
        self.assertEqual(public.status_code, 200)
        self.assertNotContains(public, COACH_SUMMARY_LOCATION)

    def test_other_tenant_can_enable_member_assessment_by_saving_settings(self):
        reservation = self.make_course(self.other_school)
        place = self.make_place(reservation=reservation)
        member_url = MEMBER.replace('/snowland/', '/other/')
        self.api.force_authenticate(self.owner)
        self.assertNotIn('experience_assessment', self.api.get(member_url).data['pre_course_forms'][0])
        self.authenticate_manager(self.other_school)
        fields = [{'key': 'recent', 'label': '其他學校的滑雪經驗', 'order': 1, 'visible': True}]
        result = self.save_setting(fields, cms=self.cms.replace('/snowland/', '/other/'))
        self.assertEqual(result.status_code, 201, result.data)
        self.api.force_authenticate(self.owner)
        form, = self.api.get(member_url).data['pre_course_forms']
        self.assertEqual(form['experience_assessment'], {})
        self.assertFalse(form['snowland_waiver_rules'])
        submission = {
            'action': 'update_pre_course_form', 'member_id': place.pk, 'age_range': '25-35y',
            'experience_assessment': {'kind': 'new', 'recent': 'no', 'finished': True},
        }
        invalid = {**submission, 'experience_assessment': {'kind': 'unknown'}}
        self.assertEqual(self.api.post(member_url, invalid, format='json').status_code, 400)
        response = self.api.post(member_url, submission, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        form, = self.api.get(member_url).data['pre_course_forms']
        self.assertTrue(form['experience_assessment']['finished'])
        self.api.force_authenticate(reservation.preferred_coach.user)
        response = self.api.get(f"/api/admin/other/coach/learner-history/{reservation.pk}/")
        self.assertEqual(response.status_code, 200, response.data)
        summary = response.data['data'][0]['pre_course_summary']
        self.assertEqual(summary['status'], 'filled')
        self.assertEqual(summary['items'], [
            {'key': 'recent', 'label': '其他學校的滑雪經驗', 'value': '沒有經驗', 'filled': True},
        ])


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
