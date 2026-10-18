import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_campus_scope as fixtures
from Client.models import SiteContent
from booking.models import MemberDetail, NotificationDelivery, Reservation, ReservationGroup


class InsuranceReminderTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)
        self.owner = User.objects.create_user('insurance-owner', email='owner@example.test')
        self.group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, user=self.owner)
        self.member = MemberDetail.objects.create(reservation=Reservation.objects.create(group=self.group))
        self.api = APIClient(); self.api.force_authenticate(self.superuser)
        self.url = f'/api/admin/snowland/insurance-records/{self.member.pk}/reminder/'
        self.payload = {'field':'insurance','recipient_email':self.owner.email,'request_key':str(uuid.uuid4())}

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_preview_has_no_side_effect_and_send_is_idempotent(self, send):
        preview = self.api.get(self.url, {'field':'insurance'})
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['data']['recipient_email'], self.owner.email)
        send.assert_not_called(); self.assertEqual(NotificationDelivery.objects.count(), 0)
        first = self.api.post(self.url, self.payload, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        repeat = self.api.post(self.url, self.payload, format='json')
        self.assertEqual(repeat.status_code, 200, repeat.data)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(NotificationDelivery.objects.filter(template__channel='email',recipient=self.owner.email).count(), 1)
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 1)
        self.member.refresh_from_db(); self.assertIsNone(self.member.insurance_completed_at)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_assistant_can_remind_but_cannot_mark_complete(self, send):
        self.profile.role='assistant'; self.profile.admin_permissions=None; self.profile.save()
        self.api.force_authenticate(User.objects.get(pk=self.manager.pk))
        self.assertEqual(self.api.post(self.url, self.payload, format='json').status_code, 200)
        self.assertEqual(self.api.post(self.url.replace('reminder/','complete/'), {'field':'insurance'}, format='json').status_code, 403)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_completed_cancelled_changed_recipient_and_extra_fields_do_not_send(self, send):
        for data in ({**self.payload,'recipient_email':'stranger@example.test'}, {**self.payload,'message':'injected'},
                     {**self.payload,'field':'other'}, {k:v for k,v in self.payload.items() if k!='request_key'}):
            self.assertIn(self.api.post(self.url,data,format='json').status_code,[400,409])
        self.member.insurance_completed_at=timezone.now(); self.member.save()
        self.assertEqual(self.api.post(self.url,self.payload,format='json').status_code,409)
        self.member.insurance_completed_at=None; self.member.save()
        self.member.reservation.status='cancelled'; self.member.reservation.save()
        self.assertEqual(self.api.post(self.url,self.payload,format='json').status_code,409)
        send.assert_not_called()

    def test_scoped_record_and_csrf_are_enforced(self):
        self.assertEqual(self.api.get(self.url, {'field':'insurance'},HTTP_X_CAMPUS_ID=str(self.campus_b.pk)).status_code,404)
        api=APIClient(enforce_csrf_checks=True); api.force_login(self.superuser)
        self.assertEqual(api.post(self.url,self.payload,format='json').status_code,403)

    def test_guardian_is_preferred_to_order_owner_without_unrelated_email_claiming(self):
        parent=User.objects.create_user('insurance-parent', email='parent@example.test')
        self.member.guardian=parent; self.member.save()
        response=self.api.get(self.url, {'field':'waiver'})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['data']['recipient_email'],parent.email)
        self.assertNotIn('id_number',response.data['data'])

    def test_missing_address_returns_readable_error(self):
        self.group.user=None; self.group.save()
        response=self.api.get(self.url, {'field':'insurance'})
        self.assertEqual(response.status_code,400,response.data)

    def old_signed_waiver(self):
        SiteContent.objects.create(client=self.tenant, content_type='page', location_key='membership.waiver',
            title='QA新版聲明', body='QA文件，非正式法律文件', status='active', metadata={'version':'QA-V2'})
        self.member.insurance_completed_at = timezone.now()
        self.member.waiver_completed_at = timezone.now()
        self.member.waiver_signature = 'QA合成簽名'
        self.member.waiver_document_version = 'QA-V1'
        self.member.waiver_document_snapshot = 'QA舊版快照'
        self.member.save()

    def test_old_signature_requires_resign_and_is_not_filtered_as_complete(self):
        self.old_signed_waiver()
        listed = self.api.get('/api/admin/snowland/insurance-records/', {'status':'missing'})
        rows = listed.data['data']['list']
        self.assertIn(self.member.pk, [row['id'] for row in rows])
        row = next(row for row in rows if row['id'] == self.member.pk)
        self.assertTrue(row['waiver_requires_resign'])
        completed = self.api.get('/api/admin/snowland/insurance-records/', {'status':'completed'})
        self.assertNotIn(self.member.pk, [row['id'] for row in completed.data['data']['list']])
        self.assertEqual(self.api.get(self.url, {'field':'waiver'}).status_code, 200)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_old_signature_can_receive_one_reminder_without_overwriting_signed_history(self, send):
        self.old_signed_waiver()
        payload = {**self.payload, 'field':'waiver'}
        response = self.api.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.api.post(self.url, payload, format='json').status_code, 200)
        self.assertEqual(send.call_count, 1)
        self.member.refresh_from_db()
        self.assertEqual(self.member.waiver_document_version, 'QA-V1')
        self.assertEqual(self.member.waiver_document_snapshot, 'QA舊版快照')
        self.assertIsNotNone(self.member.waiver_completed_at)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_resigned_after_preview_stops_outdated_reminder(self, send):
        self.old_signed_waiver()
        self.assertEqual(self.api.get(self.url, {'field':'waiver'}).status_code, 200)
        self.member.waiver_document_version = 'QA-V2'
        self.member.save(update_fields=['waiver_document_version'])
        response = self.api.post(self.url, {**self.payload,'field':'waiver'}, format='json')
        self.assertEqual(response.status_code, 409, response.data)
        send.assert_not_called()

    def test_current_online_signature_and_manual_paper_acknowledgement_remain_complete(self):
        self.old_signed_waiver()
        for signature, version in [('QA合成簽名','QA-V2'), ('','')]:
            self.member.waiver_signature = signature
            self.member.waiver_document_version = version
            self.member.save()
            response = self.api.get(f'/api/admin/snowland/insurance-records/{self.member.pk}/')
            self.assertFalse(response.data['waiver_requires_resign'])
            self.assertEqual(self.api.get(self.url, {'field':'waiver'}).status_code, 409)

    def test_version_status_does_not_fetch_client_or_document_once_per_student(self):
        self.old_signed_waiver()
        MemberDetail.objects.bulk_create([MemberDetail(reservation=self.member.reservation) for _ in range(15)])
        with CaptureQueriesContext(connection) as queries:
            response = self.api.get('/api/admin/snowland/insurance-records/', {'page_size':100})
        self.assertEqual(response.status_code, 200)
        statements = [row['sql'].replace('"','').replace('`','').lower() for row in queries.captured_queries]
        self.assertLessEqual(sum('from client_client ' in sql for sql in statements), 3)
        self.assertLessEqual(sum('from client_sitecontent ' in sql for sql in statements), 2)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_insurance_only_role_does_not_need_or_gain_order_management(self, send):
        self.profile.role='insurance'; self.profile.admin_permissions=None; self.profile.save()
        self.api.force_authenticate(User.objects.get(pk=self.manager.pk))
        self.assertEqual(self.api.get(self.url,{'field':'insurance'}).status_code,200)
        self.assertEqual(self.api.post(self.url,self.payload,format='json').status_code,200)
        self.assertEqual(self.api.get('/api/admin/snowland/orders/').status_code,403)

    @patch('booking.scheduler.send_gmail', side_effect=RuntimeError('private server secret'))
    def test_transport_failure_is_recorded_not_retried_or_reported_as_success(self, send):
        first=self.api.post(self.url,self.payload,format='json')
        self.assertEqual(first.status_code,502,first.data)
        self.assertNotIn('private server secret',str(first.data))
        self.assertEqual(self.api.post(self.url,self.payload,format='json').status_code,502)
        self.assertEqual(send.call_count,1)
