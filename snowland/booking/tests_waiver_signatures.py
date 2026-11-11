from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from datetime import timedelta

from Client.models import Client, SiteContent
from Coach.models import Coach

from .models import Booking, MemberDetail, MemberWaiverSignature, Reservation, ReservationGroup


class HandwrittenWaiverTests(TestCase):
    url = '/booking/snowland/api/member-center/'
    ink = [[[20, 30], [70, 60], [120, 25]]]

    def setUp(self):
        self.school = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.owner = User.objects.create_user('waiver-owner', 'waiver-owner@example.test')
        group = ReservationGroup.objects.create(client=self.school, user=self.owner)
        reservation = Reservation.objects.create(group=group, number_of_people=1)
        self.member = MemberDetail.objects.create(reservation=reservation, user=self.owner)
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        document = self.api.get(self.url).data['waiver_document']
        self.assertNotIn('source_url', document)
        self.body = document['body']
        self.payload = {
            'action': 'update_pre_course_form', 'member_id': self.member.pk,
            'age_range': '25-35y', 'insurance_data': {
                'full_name': 'QA 學員', 'birth_date': '1998-01-01', 'waiver_signer_role': 'self',
            },
            'waiver_agreed': True, 'waiver_signature': 'QA 學員',
            'waiver_document_version': document['version'], 'waiver_course_revision': 0,
            'media_consent': 'decline', 'waiver_signature_ink': self.ink,
            'experience_assessment': {'kind': 'new', 'recent': 'no', 'finished': True},
        }

    def test_signing_is_retry_safe_and_archives_prior_signed_versions(self):
        for _ in range(2):
            response = self.api.post(self.url, self.payload, format='json')
            self.assertEqual(response.status_code, 200, response.data)
        first = MemberWaiverSignature.objects.get(member=self.member)
        self.assertEqual(first.document_snapshot, self.body)
        self.assertEqual(first.signer, self.owner)
        self.assertEqual(first.strokes, self.ink)
        form = self.api.get(self.url).data['pre_course_forms'][0]
        self.assertEqual(form['waiver_signature_strokes'], self.ink)

        draft = {**self.payload, 'waiver_signature_ink': None,
                 'insurance_data': {**self.payload['insurance_data'], 'phone': '0900000000'}}
        self.assertEqual(self.api.post(self.url, draft, format='json').status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.waiver_completed_at, first.signed_at)

        self.member.waiver_resign_required = True
        self.member.save(update_fields=['waiver_resign_required'])
        self.assertEqual(self.api.post(self.url, draft, format='json').status_code, 400)
        self.assertEqual(self.api.post(self.url, self.payload, format='json').status_code, 200)
        self.assertEqual(self.member.online_waiver_signatures.count(), 2)
        first.refresh_from_db()
        self.assertEqual(first.strokes, self.ink)

    def test_empty_invalid_or_forged_signature_does_not_complete_form(self):
        for override in (
            {'waiver_signature_ink': None}, {'waiver_signature_ink': [[[4, 4], [4, 4]]]},
            {'waiver_signature_ink': [[[4, 4], [4, 9999]]]},
            {'waiver_signature': 'QA 另一位'},
        ):
            with self.subTest(override=override):
                response = self.api.post(self.url, {**self.payload, **override}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.waiver_completed_at)
        self.assertFalse(self.member.online_waiver_signatures.exists())

        self.api.force_authenticate(User.objects.create_user('waiver-other'))
        self.assertEqual(self.api.post(self.url, self.payload, format='json').status_code, 404)
        self.assertEqual(self.api.get(self.url).data['pre_course_forms'], [])

    def test_new_contact_fields_are_preserved_on_an_unsigned_draft(self):
        insurance = {
            'full_name': 'QA 兒童', 'birth_date': '2020-01-01', 'nickname': 'QA 暱稱',
            'address': 'QA 地址', 'email': 'waiver-child@example.test',
            'guardian_id_number': 'QA ID',
        }
        draft = {**self.payload, 'waiver_agreed': False, 'age_range': '7-12y', 'insurance_data': insurance}
        bad = self.api.post(self.url, {**draft, 'insurance_data': {**insurance, 'email': 'invalid'}}, format='json')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.api.post(self.url, draft, format='json').status_code, 200)
        stored = self.api.get(self.url).data['pre_course_forms'][0]['insurance_data']
        for key in ('nickname', 'address', 'email', 'guardian_id_number'):
            self.assertEqual(stored[key], insurance[key])

    def test_unsigned_student_cannot_use_old_skill_selections_in_place_of_the_new_assessment(self):
        self.member.snowboard_skills = ['無經驗']
        self.member.save(update_fields=['snowboard_skills'])
        payload = {**self.payload, 'snowboard_skills': ['無經驗']}
        unfinished = {**payload, 'experience_assessment': {'kind': 'returning', 'finished': False}}
        omitted = {key: value for key, value in payload.items() if key != 'experience_assessment'}
        for submission in (unfinished, omitted):
            response = self.api.post(self.url, submission, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('請先完成程度自評', response.data['error'])
        self.assertFalse(self.member.online_waiver_signatures.exists())
        self.assertEqual(self.api.post(self.url, payload, format='json').status_code, 200)

    def test_old_signature_is_retained_when_updating_contact_details_in_the_new_form(self):
        legacy = {key: value for key, value in self.payload.items() if key not in ('experience_assessment', 'waiver_signature_ink')}
        self.assertEqual(self.api.post(self.url, legacy, format='json').status_code, 200)
        self.member.refresh_from_db()
        signed_at = self.member.waiver_completed_at
        updated = {**legacy, 'experience_assessment': {}, 'waiver_signature_ink': None,
                   'insurance_data': {**legacy['insurance_data'], 'phone': '0900000000'}}
        response = self.api.post(self.url, updated, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.member.refresh_from_db()
        self.assertEqual(self.member.waiver_completed_at, signed_at)
        self.assertFalse(self.member.online_waiver_signatures.exists())

    def test_legacy_contact_edit_keeps_an_existing_handwritten_signature(self):
        self.assertEqual(self.api.post(self.url, self.payload, format='json').status_code, 200)
        signature = self.member.online_waiver_signatures.get()
        legacy = {key: value for key, value in self.payload.items() if key not in ('experience_assessment', 'waiver_signature_ink')}
        response = self.api.post(self.url, {**legacy, 'insurance_data': {
            **legacy['insurance_data'], 'phone': '0900000000',
        }}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.member.refresh_from_db()
        self.assertEqual(self.member.waiver_completed_at, signature.signed_at)
        self.assertEqual(self.api.get(self.url).data['pre_course_forms'][0]['waiver_signature_strokes'], self.ink)
        changed = self.api.post(self.url, {**legacy, 'media_consent': 'agree'}, format='json')
        self.assertEqual(changed.status_code, 400, changed.data)
        self.assertEqual(self.member.online_waiver_signatures.count(), 1)

    def test_minor_can_save_a_draft_but_needs_guardian_id_to_complete_the_new_form(self):
        minor = {**self.payload, 'age_range': '7-12y', 'waiver_signature': 'QA 代理人', 'insurance_data': {
            'full_name': 'QA 學員', 'birth_date': '2020-01-01', 'id_number': 'QA STUDENT', 'phone': '0900000000',
            'waiver_signer_role': 'guardian', 'guardian_name': 'QA 代理人', 'guardian_relationship': '家長',
        }}
        draft = self.api.post(self.url, {**minor, 'waiver_agreed': False}, format='json')
        self.assertEqual(draft.status_code, 200, draft.data)
        self.assertFalse(draft.data['insurance_completed'])
        refused = self.api.post(self.url, minor, format='json')
        self.assertEqual(refused.status_code, 400, refused.data)
        self.assertIn('法定代理人身分證字號', refused.data['error'])
        minor['insurance_data']['guardian_id_number'] = 'QA GUARDIAN'
        signed = self.api.post(self.url, minor, format='json')
        self.assertEqual(signed.status_code, 200, signed.data)
        self.assertTrue(signed.data['insurance_completed'])
        self.assertTrue(signed.data['waiver_completed'])

    def test_updated_required_insurance_question_marks_the_record_pending_and_allows_preview(self):
        question = {'key': 'updated', 'title': '更新的保險題目', 'kind': 'text', 'section': 'insurance',
                    'required': True, 'options': []}
        SiteContent.objects.create(client=self.school, content_type='page', location_key='membership.waiver',
            title='QA 聲明', body='QA 聲明', status='active', metadata={'version': 'V1', 'questions': [question]})
        completed_at = timezone.now().replace(microsecond=0)
        self.member.insurance_completed_at = completed_at
        self.member.waiver_completed_at = completed_at
        self.member.waiver_signature = 'QA 學員'
        self.member.waiver_document_version = 'V1'
        self.member.save()
        editor = APIClient()
        editor.force_authenticate(User.objects.create_superuser('qa-insurance-update'))
        records = '/api/admin/snowland/insurance-records/'
        missing = editor.get(records, {'status': 'missing'})
        self.assertEqual(missing.status_code, 200, missing.data)
        row, = missing.data['data']['list']
        self.assertEqual(row['id'], self.member.pk)
        self.assertTrue(row['insurance_requires_update'])
        self.assertTrue(row['insurance_completed_at'])
        preview = editor.get(f'{records}{self.member.pk}/reminder/', {'field': 'insurance'})
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['data']['recipient_email'], self.owner.email)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_completed_at, completed_at)

    def test_school_questions_validate_and_keep_the_signed_answers_after_publish(self):
        question = {'key': 'coverage', 'title': '保險確認', 'kind': 'single', 'section': 'insurance',
                    'required': True, 'options': ['已閱讀', '需要協助']}
        document = SiteContent.objects.create(client=self.school, content_type='page', location_key='membership.waiver',
            title='本校聲明', body='本機合成測試文件', status='active', metadata={'version': 'V1', 'questions': [question]})
        data = {**self.payload, 'waiver_document_version': 'V1'}
        for answers in ({}, {'coverage': '外部選項'}, {'outside': '已閱讀'}):
            self.assertEqual(self.api.post(self.url, {**data, 'question_answers': answers}, format='json').status_code, 400)
        answers = {'coverage': '已閱讀'}
        self.assertEqual(self.api.post(self.url, {**data, 'question_answers': answers}, format='json').status_code, 200)
        signed = self.member.online_waiver_signatures.get()
        self.assertEqual(signed.form_snapshot['insurance'], {'questions': [question], 'answers': answers})
        editor = APIClient()
        editor.force_authenticate(User.objects.create_superuser('qa-waiver-question-editor'))
        updated = editor.patch(f'/api/admin/snowland/site-content/{document.pk}/',
            {'metadata': {'questions': [{**question, 'title': '新版保險問題'}]}}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(self.api.post(self.url, {**data, 'question_answers': answers}, format='json').status_code, 409)
        member_data = self.api.get(self.url).data['pre_course_forms'][0]
        self.assertFalse(member_data['waiver_completed'])
        self.assertFalse(member_data['insurance_completed'])
        self.assertEqual(member_data['question_answers'], {})
        signed.refresh_from_db()
        self.assertEqual(signed.form_snapshot['insurance']['questions'][0]['title'], '保險確認')
        other = Client.objects.create(name='QA 另一校', internal_code='qa-other')
        from .legal_documents import get_current_waiver
        self.assertEqual(get_current_waiver(other)['questions'], [])
        self.assertEqual(get_current_waiver(other)['body'], '')
