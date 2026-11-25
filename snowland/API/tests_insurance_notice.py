from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, SiteContent
from Control.models import TenantStaffMembership
from booking.models import MemberDetail, Reservation, ReservationGroup


class InsuranceNoticeTests(TestCase):
    notice_key = 'membership.insurance-notice'
    waiver_key = 'membership.waiver'
    cms_url = '/api/admin/qa-documents/site-content/'
    current_url = cms_url + 'insurance-notice-current/'

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Client.objects.create(name='QA 甲校', internal_code='qa-documents')
        cls.other = Client.objects.create(name='QA 乙校', internal_code='snowland')
        cls.student = User.objects.create_user('qa-document-student')
        cls.editor = User.objects.create_user('qa-document-editor')
        cls.staff = TenantStaffMembership.objects.create(
            client=cls.tenant, user=cls.editor, is_manager=True, role='assistant',
            admin_permissions=['course_documents'],
        )

    def setUp(self):
        self.admin_api = APIClient()
        self.admin_api.force_authenticate(self.editor)
        self.member_api = APIClient()
        self.member_api.force_authenticate(self.student)

    def member_center(self, tenant=None):
        response = self.member_api.get(self.member_url(tenant or self.tenant))
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    @staticmethod
    def member_url(tenant):
        return f'/booking/{tenant.internal_code}/api/member-center/'

    def create_content(self, key, title, body, **fields):
        response = self.admin_api.post(self.cms_url, {
            'content_type': 'page', 'location_key': key, 'title': title, 'body': body, **fields,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['data']

    def test_two_public_documents_and_latest_notice_in_member_center(self):
        self.create_content(self.waiver_key, 'QA 聲明書', 'QA 聲明書正文', status='active')
        self.create_content(self.notice_key, 'QA 舊說明', 'QA 舊說明正文', status='active')
        notice = self.create_content(self.notice_key, 'QA 新說明', 'QA 新說明正文', status='active')
        self.create_content(self.notice_key, 'QA 未公開', 'QA 未公開正文', status='draft')
        SiteContent.objects.create(
            client=self.tenant, location_key=self.notice_key, content_type='article',
            body='QA 非頁面正文', status='active',
        )
        data = self.member_center()
        self.assertEqual(data['waiver_document']['title'], 'QA 聲明書')
        self.assertEqual(data['waiver_document']['body'], 'QA 聲明書正文')
        self.assertEqual(data['insurance_notice'], {
            'title': 'QA 新說明', 'body': 'QA 新說明正文', 'version': notice['metadata']['version'],
            'status': 'active', 'is_draft': False,
        })
        self.assertEqual(self.admin_api.get(self.current_url).data['data'], data['insurance_notice'])

    def test_public_notice_can_appear_without_a_public_waiver(self):
        self.create_content(self.waiver_key, 'QA 草稿', 'QA 不公開聲明', status='draft')
        self.create_content(self.notice_key, 'QA 保險說明', 'QA 公開保險', status='active')
        data = self.member_center()
        self.assertEqual(data['waiver_document']['body'], '')
        self.assertEqual(data['waiver_document']['version'], '')
        self.assertEqual(data['insurance_notice']['body'], 'QA 公開保險')

    def test_waiver_appears_without_an_active_notice(self):
        waiver = self.create_content(self.waiver_key, 'QA 聲明書', 'QA 可簽署聲明', status='active')
        for status in ('draft', 'hidden', 'ended'):
            self.create_content(self.notice_key, 'QA 未公開', f'QA {status}', status=status)
        # Content imported outside the Console can have a conflicting status and legal-review flag.
        SiteContent.objects.create(
            client=self.tenant, location_key=self.notice_key, content_type='page', title='QA 待法務確認',
            body='QA 仍是草稿', status='active', metadata={'is_draft': True},
        )
        data = self.member_center()
        self.assertEqual(data['waiver_document']['version'], waiver['metadata']['version'])
        self.assertEqual(data['waiver_document']['body'], 'QA 可簽署聲明')
        for field in ('title', 'body', 'version', 'status'):
            self.assertEqual(data['insurance_notice'][field], '')

    def test_notice_is_tenant_scoped_with_no_snowland_fallback_or_public_listing(self):
        self.create_content(self.notice_key, 'QA 甲校說明', 'QA 甲校正文', status='active')
        self.assertEqual(self.member_center()['insurance_notice']['body'], 'QA 甲校正文')
        other = self.member_center(self.other)
        self.assertEqual(other['insurance_notice']['body'], '')
        self.assertEqual(other['insurance_notice']['version'], '')
        self.assertEqual(other['waiver_document']['version'], 'V0-2026-10-08')
        catalog = self.member_api.get('/booking/qa-documents/api/site-content/', {'location_key': self.notice_key})
        self.assertEqual(catalog.status_code, 200, catalog.data)
        self.assertNotIn('QA 甲校正文', catalog.content.decode())

    def test_notice_crud_requires_course_documents_and_respects_tenant_scope(self):
        notice = self.create_content(self.notice_key, 'QA 說明', 'QA 草稿正文', metadata={'is_draft': True})
        url = self.cms_url + f'{notice["id"]}/'
        detail = self.admin_api.get(url)
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['body'], 'QA 草稿正文')
        self.assertEqual(self.admin_api.get(self.current_url).data['data']['body'], '')
        self.assertEqual(self.admin_api.patch(url, {'status': 'active'}, format='json').status_code, 400)
        publish = self.admin_api.patch(url, {'status': 'active', 'metadata': {'is_draft': False}}, format='json')
        self.assertEqual(publish.status_code, 200, publish.data)
        self.assertNotEqual(publish.data['data']['metadata']['version'], notice['metadata']['version'])
        self.assertEqual(self.member_center()['insurance_notice']['body'], 'QA 草稿正文')

        other_notice = SiteContent.objects.create(client=self.other, location_key=self.notice_key, content_type='page')
        self.assertEqual(self.admin_api.get(self.cms_url + f'{other_notice.pk}/').status_code, 404)
        self.staff.admin_permissions = ['site_home']
        self.staff.save(update_fields=['admin_permissions'])
        self.assertEqual(self.admin_api.get(self.current_url).status_code, 403)
        self.assertEqual(self.admin_api.get(url).status_code, 404)
        self.assertEqual(self.admin_api.patch(url, {'body': 'QA 未授權'}, format='json').status_code, 404)
        self.assertEqual(self.admin_api.delete(url).status_code, 404)
        self.assertEqual(self.admin_api.post(self.cms_url, {
            'content_type': 'page', 'location_key': self.notice_key, 'title': 'QA 說明', 'body': 'QA 未授權',
        }, format='json').status_code, 403)

        self.staff.admin_permissions = ['course_documents']
        self.staff.save(update_fields=['admin_permissions'])
        self.assertEqual(self.admin_api.delete(url).status_code, 200)
        self.assertEqual(self.member_center()['insurance_notice']['body'], '')

    def test_updating_notice_preserves_existing_signature_and_snapshot(self):
        waiver = self.create_content(self.waiver_key, 'QA 聲明書', 'QA 簽署時全文', status='active')
        notice = self.create_content(self.notice_key, 'QA 保險說明', 'QA 原保險說明', status='active')
        order = ReservationGroup.objects.create(client=self.tenant, user=self.student)
        reservation = Reservation.objects.create(group=order, number_of_people=1)
        member = MemberDetail.objects.create(reservation=reservation, user=self.student)
        version = waiver['metadata']['version']
        payload = {
            'action': 'update_pre_course_form', 'member_id': member.pk, 'age_range': '25-35y',
            'insurance_data': {'full_name': 'QA 學員', 'birth_date': '1998-01-01', 'waiver_signer_role': 'self'},
            'waiver_agreed': True, 'waiver_signature': 'QA 學員', 'waiver_document_version': version,
            'waiver_course_revision': 0, 'media_consent': 'decline',
            'waiver_signature_ink': [[[20, 30], [70, 60], [120, 25]]],
        }
        url = self.member_url(self.tenant)
        signed = self.member_api.post(url, payload, format='json')
        self.assertEqual(signed.status_code, 200, signed.data)
        signature = member.online_waiver_signatures.get()

        updated = self.admin_api.patch(self.cms_url + f'{notice["id"]}/', {'body': 'QA 新版保險'}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        data = self.member_center()
        self.assertEqual(data['insurance_notice']['body'], 'QA 新版保險')
        self.assertNotEqual(data['insurance_notice']['version'], notice['metadata']['version'])
        self.assertEqual(data['waiver_document']['version'], version)
        self.assertTrue(data['pre_course_forms'][0]['waiver_completed'])
        self.assertFalse(data['pre_course_forms'][0]['waiver_resign_required'])

        saved = self.member_api.post(url, {
            **payload, 'waiver_signature_ink': None,
            'insurance_data': {**payload['insurance_data'], 'phone': '0900000000'},
        }, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        member.refresh_from_db()
        self.assertEqual(member.waiver_document_version, version)
        self.assertEqual(member.waiver_document_snapshot, 'QA 簽署時全文')
        self.assertEqual(member.waiver_completed_at, signature.signed_at)
        original = member.online_waiver_signatures.get()
        self.assertEqual(original.pk, signature.pk)
        self.assertEqual(original.document_snapshot, 'QA 簽署時全文')
