from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, CoachCourseLevel, CoachResort
from Coursekit.models import CourseCategory, CoursePricing, CourseSession, CourseTemplate, CourseType
from Resorts.models import Campus, Resorts
from booking.models import Booking, CourseEvaluation, MemberDetail, Reservation, ReservationGroup


class MemberEnrollmentTests(TestCase):
    url = '/booking/snowland/api/member-center/'

    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.campus = Campus.objects.create(client=self.tenant, name='道東校區', code='east')
        self.resort = Resorts.objects.create(client=self.tenant, name='qa-tomamu', display_name='星野')
        self.campus.resorts.add(self.resort)
        category = CourseCategory.objects.create(client=self.tenant, name='單板')
        course_type = CourseType.objects.create(category=category, name='初階')
        self.template = CourseTemplate.objects.create(
            course_type=course_type, name='半日課程', duration_hours=4,
            billing_mode='per_person', minimum_group_size=1, max_capacity=4,
        )
        self.template.resorts.add(self.resort)
        CourseSession.objects.create(template=self.template, start_time='09:00', end_time='13:00')
        pricing = CoursePricing.objects.create(
            resort=self.resort, base_price_off_peak=5000,
            peak_season_surcharge=0, additional_person_fee=0, max_capacity=4,
        )
        pricing.templates.add(self.template)
        self.coach = Coach.objects.create(client=self.tenant, name='QA 教練', languages=['zh'])
        self.coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=self.coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=self.coach, course_type=course_type, ability_levels=['no_exp'], price_level='Lv1',
        )
        self.owner = User.objects.create_user('order-owner', 'owner@example.test', 'local-test-password')
        self.api = APIClient()
        self.api.force_authenticate(self.owner)

    def book(self, expected_status=200):
        response = self.api.post('/booking/snowland/api/create-reservation/', {
            'accepted_policy': True,
            'contact': {
                'name': '訂課人', 'email': 'owner@example.test', 'phone': '0900000000',
                'messengerType': 'line', 'messengerId': 'qa-owner', 'referralSource': '其他',
            },
            'cart': [{
                'coach': 'any', 'peopleCount': 2, 'abilityLevel': 'no_exp',
                'abilityLevelCounts': {'no_exp': 2}, 'equipment': False,
                'equipmentOption': 'own_equipment', 'language': 'zh',
                'resort': self.resort.name, 'campusId': self.campus.id, 'courseCategory': '單板',
                'courses': [{
                    'date': (timezone.localdate() + timedelta(days=20)).isoformat(),
                    'courseTypeId': self.template.course_type_id,
                    'courseTypeName': '初階', 'courseTemplateId': self.template.id,
                    'courseTemplateName': self.template.name, 'durationHours': 4,
                    'timeSlotStart': '09:00', 'timeSlotEnd': '13:00',
                }],
            }],
        }, format='json')
        self.assertEqual(response.status_code, expected_status, response.data)
        if expected_status != 200:
            return response
        return Reservation.objects.get(group_id=response.data['reservation_group_ids'][0])

    def test_anonymous_submission_is_rejected_before_creating_order_or_students(self):
        self.api.force_authenticate(None)
        response = self.book(expected_status=401)
        self.assertIn('登入', response.data['msg'])
        self.assertFalse(ReservationGroup.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(MemberDetail.objects.exists())
        self.assertFalse(Booking.objects.exists())

    def test_real_member_session_owns_order_and_logout_prevents_another_submission(self):
        self.api.force_authenticate(None)
        logged_in = self.api.post('/booking/snowland/api/member-auth/', {
            'action': 'login', 'email': self.owner.email, 'password': 'local-test-password',
        }, format='json')
        self.assertEqual(logged_in.status_code, 200, logged_in.data)
        reservation = self.book()
        self.assertEqual(reservation.group.user_id, self.owner.id)
        self.assertEqual(set(reservation.members.values_list('user_id', flat=True)), {self.owner.id})
        visible = self.api.get(self.url).data
        self.assertEqual([order['id'] for order in visible['orders']], [reservation.group_id])
        self.assertEqual(self.api.post('/control/api/logout/').status_code, 200)
        self.book(expected_status=401)
        self.assertEqual(ReservationGroup.objects.count(), 1)
        self.assertEqual(MemberDetail.objects.count(), 2)

    def test_real_new_booking_creates_each_student_and_flows_to_forms_and_evaluation(self):
        reservation = self.book()
        self.assertEqual(reservation.members.count(), 2)
        self.assertEqual(set(reservation.members.values_list('user_id', flat=True)), {self.owner.id})
        self.assertTrue(all(not member.insurance_data and not member.age_range for member in reservation.members.all()))
        forms = self.api.get(self.url).data['pre_course_forms']
        self.assertEqual(len(forms), 2)
        self.assertEqual([row['student_number'] for row in forms], [1, 2])
        for form, name, age in zip(forms, ['QA 成人學員', 'QA 兒童學員'], ['25-35y', '7-12y']):
            saved = self.api.post(self.url, {
                'action': 'update_pre_course_form', 'member_id': form['id'],
                'age_range': age, 'insurance_data': {'full_name': name},
            }, format='json')
            self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(
            {row['member_name'] for row in self.api.get(self.url).data['pre_course_forms']},
            {'QA 成人學員', 'QA 兒童學員'},
        )

        admin = APIClient()
        admin.force_authenticate(User.objects.create_superuser('qa-hq', 'hq@example.test', 'pw'))
        paid = admin.put(f'/api/admin/snowland/orders/{reservation.group_id}/', {
            'action': 'save', 'payment_status': 'paid',
        }, format='json')
        self.assertEqual(paid.status_code, 200, paid.data)
        reservation.bookings.update(date=timezone.localdate() - timedelta(days=1))
        completed = admin.post(f'/api/admin/snowland/orders/{reservation.group_id}/complete-course/', {
            'reservation_id': reservation.id,
        }, format='json')
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertEqual(CourseEvaluation.objects.filter(booking__reservation=reservation).count(), 2)
        rows = admin.get('/api/admin/snowland/evaluations/').data['data']['list']
        self.assertEqual({row['member_name'] for row in rows}, {'QA 成人學員', 'QA 兒童學員'})
        self.assertEqual(
            {row['member_name'] for row in self.api.get(self.url).data['learning_records']},
            {'QA 成人學員', 'QA 兒童學員'},
        )

    def legacy_order(self, *, user=None, status='auto_assigned', people=2):
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus, user=user or self.owner)
        return Reservation.objects.create(
            group=group, resort=self.resort, course_type=self.template.course_type,
            course_template=self.template, number_of_people=people, status=status, preferred_coach=self.coach,
        )

    def prepare(self, reservation_id):
        return self.api.post(self.url, {
            'action': 'prepare_pre_course_forms', 'reservation_id': reservation_id,
        }, format='json')

    def test_legacy_order_can_prepare_missing_students_without_duplicates_or_losing_existing_data(self):
        reservation = self.legacy_order()
        member = MemberDetail.objects.create(
            reservation=reservation, user=self.owner, insurance_data={'full_name': '已有學員'},
            waiver_signature='既有簽名', waiver_document_snapshot='既有文件',
        )
        for _ in range(2):
            response = self.prepare(reservation.id)
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(reservation.members.count(), 2)
        member.refresh_from_db()
        self.assertEqual(member.insurance_data, {'full_name': '已有學員'})
        self.assertEqual(member.waiver_signature, '既有簽名')
        self.assertEqual(member.waiver_document_snapshot, '既有文件')
        order = self.api.get(self.url).data['orders'][0]['reservations'][0]
        self.assertEqual(order['student_count'], 2)
        self.assertEqual(order['missing_students'], 0)

    def test_completed_legacy_order_prepares_evaluations_once(self):
        reservation = self.legacy_order(status='completed')
        Booking.objects.create(
            reservation=reservation, date=timezone.localdate()-timedelta(days=1),
            start_time='09:00', end_time='13:00', is_scheduled=True,
        )
        for _ in range(2):
            self.assertEqual(self.prepare(reservation.id).status_code, 200)
        self.assertEqual(reservation.members.count(), 2)
        self.assertEqual(CourseEvaluation.objects.filter(booking__reservation=reservation).count(), 2)

    def test_malformed_skill_values_return_validation_error_without_changing_form(self):
        reservation = self.legacy_order(people=1)
        self.assertEqual(self.prepare(reservation.id).status_code, 200)
        member = reservation.members.get()
        for field in ['snowboard_skills', 'ski_skills']:
            for invalid in [[{}], [[]], [None], [123], '無經驗', {'skill': '無經驗'}]:
                with self.subTest(field=field, invalid=invalid):
                    response = self.api.post(self.url, {
                        'action': 'update_pre_course_form', 'member_id': member.id,
                        'age_range': '25-35y', 'insurance_data': {'full_name': 'QA 學員'},
                        field: invalid,
                    }, format='json')
                    self.assertEqual(response.status_code, 400, response.data)
                    member.refresh_from_db()
                    self.assertEqual(member.age_range, '')
                    self.assertFalse(member.insurance_data)

    def test_matching_contact_email_does_not_grant_guest_order_or_student_access(self):
        reservation = self.legacy_order(people=1)
        reservation.group.user = None
        reservation.group.booking_contact = {'email': self.owner.email}
        reservation.group.save(update_fields=['user', 'booking_contact'])
        from booking.participants import ensure_reservation_members
        member = ensure_reservation_members(reservation)[0]
        data = self.api.get(self.url).data
        self.assertEqual(data['orders'], [])
        self.assertEqual(data['pre_course_forms'], [])
        self.assertEqual(self.prepare(reservation.id).status_code, 404)
        response = self.api.post(self.url, {
            'action': 'update_pre_course_form', 'member_id': member.id,
            'age_range': '25-35y', 'insurance_data': {'full_name': '冒用測試'},
        }, format='json')
        self.assertEqual(response.status_code, 404)
        member.refresh_from_db()
        self.assertIsNone(member.user_id)
        self.assertFalse(member.insurance_data)

    def test_prepare_rejects_other_owner_other_tenant_cancelled_and_invalid_input(self):
        other = User.objects.create_user('another-owner')
        other_reservation = self.legacy_order(user=other)
        self.assertEqual(self.prepare(other_reservation.id).status_code, 404)
        foreign = self.legacy_order()
        foreign.group.client = Client.objects.create(name='Other', internal_code='other')
        foreign.group.save(update_fields=['client'])
        self.assertEqual(self.prepare(foreign.id).status_code, 404)
        cancelled = self.legacy_order(status='cancelled')
        self.assertEqual(self.prepare(cancelled.id).status_code, 400)
        self.assertEqual(self.prepare('not-an-id').status_code, 400)
        self.assertEqual(self.prepare(None).status_code, 400)
        self.assertFalse(MemberDetail.objects.exists())
        self.api.force_authenticate(None)
        self.assertEqual(self.prepare(other_reservation.id).status_code, 401)

    def test_guardian_signer_details_are_saved_without_changing_document_content(self):
        reservation = self.legacy_order(people=1)
        self.prepare(reservation.id)
        member = reservation.members.get()
        document = self.api.get(self.url).data['waiver_document']
        payload = {
            'action': 'update_pre_course_form', 'member_id': member.id,
            'age_range': '7-12y',
            'insurance_data': {'full_name': 'QA 兒童', 'birth_date': '2018-01-01', 'waiver_signer_role': 'guardian', 'guardian_name': 'QA 家長', 'guardian_relationship': '父親'},
        }
        draft = self.api.post(self.url, payload, format='json')
        self.assertEqual(draft.status_code, 200, draft.data)
        member.refresh_from_db()
        self.assertEqual(member.insurance_data['guardian_name'], 'QA 家長')
        self.assertFalse(member.waiver_completed_at)
        signed = self.api.post(self.url, {**payload, 'waiver_agreed': True, 'waiver_signature': 'QA 家長', 'waiver_document_version': document['version'], 'media_consent': 'decline'}, format='json')
        self.assertEqual(signed.status_code, 200, signed.data)
        member.refresh_from_db()
        self.assertEqual(member.insurance_data['waiver_signer_role'], 'guardian')
        self.assertEqual(member.insurance_data['guardian_relationship'], '父親')
        self.assertEqual(member.waiver_document_snapshot, document['body'])

    def test_guardian_signing_requires_name_and_relationship_without_partial_save(self):
        reservation = self.legacy_order(people=1)
        self.prepare(reservation.id)
        member = reservation.members.get()
        document = self.api.get(self.url).data['waiver_document']
        for missing in ['guardian_name', 'guardian_relationship']:
            insurance = {'full_name': 'QA 兒童', 'waiver_signer_role': 'guardian', 'guardian_name': 'QA 家長', 'guardian_relationship': '母親'}
            insurance.pop(missing)
            response = self.api.post(self.url, {
                'action': 'update_pre_course_form', 'member_id': member.id, 'age_range': '7-12y',
                'insurance_data': insurance, 'waiver_agreed': True, 'waiver_signature': 'QA 家長',
                'waiver_document_version': document['version'], 'media_consent': 'decline',
            }, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        member.refresh_from_db()
        self.assertFalse(member.insurance_data)
        self.assertFalse(member.waiver_completed_at)

    def test_birth_date_not_age_bucket_controls_minor_signing_and_eighteenth_birthday(self):
        reservation = self.legacy_order(people=1)
        self.prepare(reservation.id)
        member = reservation.members.get()
        document = self.api.get(self.url).data['waiver_document']
        payload = {'action': 'update_pre_course_form', 'member_id': member.id,
                   'age_range': '13-18y', 'waiver_agreed': True, 'waiver_signature': 'QA 測試簽名',
                   'waiver_document_version': document['version'], 'media_consent': 'decline'}
        with patch('django.utils.timezone.localdate', return_value=date(2026, 10, 16)):
            for birth, status_code in [('2008-10-17', 400), ('2008-10-16', 200), ('2008-10-15', 200)]:
                response = self.api.post(self.url, {**payload, 'insurance_data': {
                    'full_name': 'QA 學員', 'birth_date': birth, 'waiver_signer_role': 'self',
                }}, format='json')
                self.assertEqual(response.status_code, status_code, response.data)
                if status_code == 400:
                    member.refresh_from_db()
                    self.assertFalse(member.insurance_data)
                    self.assertFalse(member.waiver_completed_at)

    def test_minor_draft_is_allowed_but_insurance_requires_guardian_details(self):
        reservation = self.legacy_order(people=1)
        self.prepare(reservation.id)
        member = reservation.members.get()
        payload = {'action': 'update_pre_course_form', 'member_id': member.id, 'age_range': '7-12y',
                   'insurance_data': {'full_name': 'QA 兒童', 'birth_date': '2018-01-01',
                                      'id_number': 'QA-NOT-REAL', 'phone': 'QA-PHONE'}}
        response = self.api.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['insurance_completed'])
        center_form = next(item for item in self.api.get(self.url).data['pre_course_forms'] if item['id'] == member.id)
        self.assertFalse(center_form['insurance_completed'])
        payload['insurance_data'].update({'waiver_signer_role': 'guardian', 'guardian_name': 'QA 家長', 'guardian_relationship': '母親'})
        completed = self.api.post(self.url, payload, format='json')
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertTrue(completed.data['insurance_completed'])
        center_form = next(item for item in self.api.get(self.url).data['pre_course_forms'] if item['id'] == member.id)
        self.assertTrue(center_form['insurance_completed'])
        member.refresh_from_db()
        self.assertFalse(member.waiver_completed_at)

    def test_invalid_or_future_birth_date_and_signing_without_birth_date_are_rejected(self):
        reservation = self.legacy_order(people=1)
        self.prepare(reservation.id)
        member = reservation.members.get()
        document = self.api.get(self.url).data['waiver_document']
        payload = {'action': 'update_pre_course_form', 'member_id': member.id, 'age_range': '25-35y'}
        with patch('django.utils.timezone.localdate', return_value=date(2026, 10, 16)):
            for birth in ['2026-10-17', '2026-02-30', 'not-a-date', '20260101']:
                response = self.api.post(self.url, {**payload, 'insurance_data': {'full_name': 'QA', 'birth_date': birth}}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
        response = self.api.post(self.url, {**payload, 'insurance_data': {'full_name': 'QA'},
            'waiver_agreed': True, 'waiver_signature': 'QA', 'waiver_document_version': document['version'], 'media_consent': 'decline'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        member.refresh_from_db()
        self.assertFalse(member.insurance_data)
