from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from Client.models import Client, SiteContent
from booking.legal_documents import get_current_waiver, waiver_requires_resign
from booking.models import MemberDetail, Reservation, ReservationGroup


class WaiverContentTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='QA', internal_code='snowland')
        self.api = APIClient()
        self.api.force_authenticate(User.objects.create_superuser('qa-waiver-editor'))
        self.row = SiteContent.objects.create(client=self.tenant, content_type='page', location_key='membership.waiver',
            title='QA聲明', body='QA舊條款', status='active', metadata={'version':'QA-V1','custom':'preserve'})
        self.url = f'/api/admin/snowland/site-content/{self.row.pk}/'

    def test_body_edit_generates_version_even_if_old_version_is_submitted(self):
        member = MemberDetail.objects.create(reservation=Reservation.objects.create(group=ReservationGroup.objects.create(client=self.tenant)),
            waiver_signature='QA合成簽名', waiver_document_version='QA-V1', waiver_document_snapshot='QA舊條款')
        result = self.api.patch(self.url, {'body':'QA新版條款','metadata':{'version':'QA-V1','custom':'preserve'}}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        doc = get_current_waiver(self.tenant)
        self.assertNotEqual(doc['version'], 'QA-V1')
        self.assertTrue(waiver_requires_resign(member, doc))
        member.refresh_from_db()
        self.assertEqual(member.waiver_document_snapshot, 'QA舊條款')
        self.assertEqual(member.waiver_document_version, 'QA-V1')
        self.assertEqual(result.data['data']['metadata']['custom'], 'preserve')

    def test_title_changes_version_but_identical_save_and_sort_do_not(self):
        self.api.patch(self.url, {'title':'QA新標題'}, format='json')
        version = get_current_waiver(self.tenant)['version']
        self.assertNotEqual(version, 'QA-V1')
        for payload in [{'display_order':9}, {'title':'QA新標題','body':'QA舊條款'}, {'metadata':{'version':'QA-V1'}}]:
            response = self.api.patch(self.url, payload, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['data']['metadata']['version'], version)

    def test_legacy_updated_at_version_is_stable_after_non_document_edit(self):
        self.row.metadata = {}; self.row.save()
        SiteContent.objects.filter(pk=self.row.pk).update(updated_at=timezone.now()-timedelta(days=1))
        self.row.refresh_from_db()
        version = get_current_waiver(self.tenant)['version']
        self.api.patch(self.url, {'display_order':4}, format='json')
        self.assertEqual(get_current_waiver(self.tenant)['version'], version)

    def test_invalid_document_settings_do_not_write(self):
        for payload in [{'body':'  '}, {'metadata':{'is_draft':'false'}}, {'content_type':'article'}]:
            result = self.api.patch(self.url, payload, format='json')
            self.assertEqual(result.status_code, 400, result.data)
        self.row.refresh_from_db()
        self.assertEqual(self.row.body, 'QA舊條款')
        self.assertEqual(self.row.metadata['version'], 'QA-V1')

    def test_draft_create_has_version_without_changing_active_document(self):
        result = self.api.post('/api/admin/snowland/site-content/', {'content_type':'page','location_key':'membership.waiver',
            'title':'QA草稿', 'body':'QA待法務確認', 'status':'draft','metadata':{'is_draft':True}}, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        self.assertTrue(result.data['data']['metadata']['version'])
        self.assertEqual(get_current_waiver(self.tenant)['version'], 'QA-V1')

    def test_stale_sort_edit_does_not_restore_old_version_after_another_editor(self):
        from API.admin_serializers import SiteContentAdminSerializer
        serializer = SiteContentAdminSerializer(self.row, data={'display_order':8}, partial=True)
        serializer.is_valid(raise_exception=True)
        self.api.patch(self.url, {'body':'QA另一管理員更新'}, format='json')
        current = get_current_waiver(self.tenant)['version']
        serializer.save()
        document = get_current_waiver(self.tenant)
        self.assertEqual(document['version'], current)
        self.assertEqual(document['body'], 'QA另一管理員更新')

    def test_read_current_document_for_editor_does_not_create_or_change_it(self):
        result = self.api.get('/api/admin/snowland/site-content/waiver-current/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['data']['body'], 'QA舊條款')
        self.assertEqual(result.data['data']['version'], 'QA-V1')
        self.assertEqual(SiteContent.objects.count(), 1)

    def test_regular_member_cannot_edit_or_use_admin_document_reader(self):
        self.api.force_authenticate(User.objects.create_user('qa-waiver-member'))
        self.assertEqual(self.api.get('/api/admin/snowland/site-content/waiver-current/').status_code, 403)
        self.assertEqual(self.api.patch(self.url, {'body':'QA不可修改'}, format='json').status_code, 403)
        self.row.refresh_from_db()
        self.assertEqual(self.row.body, 'QA舊條款')

    def test_sorting_an_older_active_document_does_not_replace_current_document(self):
        newer = SiteContent.objects.create(client=self.tenant,content_type='page',location_key='membership.waiver',
            title='QA目前文件',body='QA目前條款',status='active',metadata={'version':'QA-V2'})
        SiteContent.objects.filter(pk=self.row.pk).update(updated_at=timezone.now()-timedelta(days=1))
        self.assertEqual(get_current_waiver(self.tenant)['version'],'QA-V2')
        self.api.patch(self.url,{'display_order':7},format='json')
        self.assertEqual(get_current_waiver(self.tenant)['version'],'QA-V2')

    def test_publishing_an_existing_draft_becomes_current_without_changing_its_body(self):
        draft = SiteContent.objects.create(client=self.tenant,content_type='page',location_key='membership.waiver',
            title='QA待公開',body='QA新正式條款',status='draft',metadata={'version':'QA-DRAFT'})
        SiteContent.objects.filter(pk=draft.pk).update(updated_at=timezone.now()-timedelta(days=2))
        result=self.api.patch(f'/api/admin/snowland/site-content/{draft.pk}/',{'status':'active'},format='json')
        self.assertEqual(result.status_code,200)
        self.assertEqual(get_current_waiver(self.tenant)['version'],'QA-DRAFT')
        self.assertEqual(get_current_waiver(self.tenant)['body'],'QA新正式條款')
