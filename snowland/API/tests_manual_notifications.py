import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Client.models import Client
from Resorts.models import Campus
from booking.models import MemberDetail, NotificationDelivery, NotificationTemplate, ReservationGroup


class ManualNotificationTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.admin = User.objects.create_superuser('manual-hq', 'manual-hq@example.test', 'test')
        self.api = APIClient(); self.api.force_authenticate(self.admin)
        self.base = '/api/admin/snowland/notification-deliveries/'
        self.adult = User.objects.create_user('adult', email='shared@example.test')
        self.parent = User.objects.create_user('parent', email='shared@example.test')
        MemberDetail.objects.create(reservation=self.reservation, user=self.adult)
        for name in ['Child A', 'Child B']:
            MemberDetail.objects.create(reservation=self.reservation, guardian=self.parent)
        self.data = {'kind': 'order', 'target_id': self.group.pk, 'audience': 'participants',
                     'subject': '上課時間調整', 'body': '請查看最新課程安排。\n此通知沒有寄 Email。'}
        self.member_api = APIClient(); self.member_api.force_authenticate(self.user)
        self.inbox = '/booking/snowland/api/member-notifications/'

    def send(self, data=None, request_key=None):
        data = dict(data or self.data)
        preview = self.api.post(self.base+'preview/', data, format='json')
        self.assertEqual(preview.status_code, 200, preview.data)
        data.update(request_key=str(request_key or uuid.uuid4()),
                    expected_recipient_ids=[row['id'] for row in preview.data['data']['recipients']])
        return self.api.post(self.base+'send/', data, format='json'), data

    def test_preview_is_read_only_and_deduplicates_parent_but_not_shared_email_accounts(self):
        response = self.api.post(self.base+'preview/', self.data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['count'], 3)
        self.assertEqual({row['id'] for row in response.data['data']['recipients']}, {self.user.pk, self.adult.pk, self.parent.pk})
        self.assertEqual(NotificationDelivery.objects.count(), 0)
        self.assertEqual(NotificationTemplate.objects.count(), 0)

    def test_order_search_accepts_the_number_shown_in_console(self):
        from API.admin_serializers import OrderAdminSerializer
        sn = OrderAdminSerializer().get_sn(self.group)
        response = self.api.get(self.base+'targets/', {'kind':'order', 'q':sn})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row['id'] for row in response.data['data']['list']], [self.group.pk])
        self.assertIn(sn, response.data['data']['list'][0]['label'])
        preview = self.api.post(self.base+'preview/', self.data, format='json')
        self.assertEqual(preview.data['data']['target_label'], sn)

    @patch('booking.management.commands.process_snowland_jobs.send_mail')
    def test_send_publishes_immediately_to_three_inboxes_without_external_transport(self, send_mail):
        response, data = self.send()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['count'], 3)
        for user in [self.user, self.adult, self.parent]:
            self.member_api.force_authenticate(user)
            inbox = self.member_api.get(self.inbox)
            self.assertEqual(inbox.status_code, 200, inbox.data)
            self.assertEqual(inbox.data['unread_count'], 1)
            self.assertEqual(inbox.data['results'][0]['subject'], self.data['subject'])
            self.assertEqual(inbox.data['results'][0]['body'], self.data['body'])
        send_mail.assert_not_called()
        self.assertEqual(NotificationDelivery.objects.filter(status='scheduled').count(), 0)

    def test_owner_only_does_not_send_to_participants(self):
        response, _ = self.send({**self.data, 'audience': 'owner'})
        self.assertEqual(response.data['data']['count'], 1)
        self.assertEqual(NotificationDelivery.objects.get().recipient, str(self.user.pk))

    def test_independent_member_has_no_fake_order_and_independent_read_state(self):
        response, data = self.send({**self.data, 'kind': 'member', 'target_id': self.parent.pk, 'audience': 'owner'})
        self.assertEqual(response.status_code, 200, response.data)
        delivery = NotificationDelivery.objects.get()
        self.assertIsNone(delivery.group_id)
        self.member_api.force_authenticate(self.parent)
        inbox = self.member_api.get(self.inbox)
        self.assertEqual(inbox.data['count'], 1)
        self.assertEqual(inbox.data['results'][0]['action_path'], '')
        read_url = self.inbox+f'{delivery.pk}/read/'
        first = self.member_api.post(read_url)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['unread_count'], 0)
        self.assertEqual(self.member_api.post(read_url).data['read_at'], first.data['read_at'])
        self.member_api.force_authenticate(self.adult)
        self.assertEqual(self.member_api.post(read_url).status_code, 404)
        self.assertEqual(self.member_api.get(self.inbox).data['count'], 0)

    def test_duplicate_request_returns_original_ids_and_never_resets_read(self):
        response, data = self.send()
        first = response.data['data']['ids']
        row = NotificationDelivery.objects.get(recipient=str(self.user.pk))
        row.payload['read_at'] = '2026-10-17T00:00:00+00:00'; row.save()
        duplicate = self.api.post(self.base+'send/', data, format='json')
        self.assertEqual(duplicate.status_code, 200, duplicate.data)
        self.assertTrue(duplicate.data['data']['duplicate'])
        self.assertEqual(duplicate.data['data']['ids'], first)
        row.refresh_from_db(); self.assertTrue(row.payload['read_at'])
        self.assertEqual(NotificationTemplate.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 3)
        data['body'] = '不可用同識別碼換內容'
        self.assertEqual(self.api.post(self.base+'send/', data, format='json').status_code, 409)

    def test_changed_bindings_since_preview_require_repreview_without_partial_publish(self):
        preview = self.api.post(self.base+'preview/', self.data, format='json')
        ids = [row['id'] for row in preview.data['data']['recipients']]
        MemberDetail.objects.filter(user=self.adult).update(user=None)
        response = self.api.post(self.base+'send/', {**self.data, 'request_key': str(uuid.uuid4()), 'expected_recipient_ids': ids}, format='json')
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(NotificationTemplate.objects.count(), 0)
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    def test_invalid_missing_and_unsupported_input_never_publishes(self):
        for data in [{}, {**self.data, 'subject': ' '}, {**self.data, 'body': ''},
                     {**self.data, 'body': 'a'*10001}, {**self.data, 'kind': 'unknown'},
                     {**self.data, 'channel': 'email'}, {**self.data, 'target_id': True},
                     {**self.data, 'request_key': 'bad'}]:
            response = self.api.post(self.base+'preview/', data, format='json')
            self.assertEqual(response.status_code, 400, (data, response.data))
        self.assertEqual(self.api.post(self.base+'send/', self.data, format='json').status_code, 400)
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    def test_foreign_and_unrelated_member_cannot_be_targeted_even_same_email(self):
        stranger = User.objects.create_user('stranger', email=self.parent.email)
        other = Client.objects.create(name='Other', internal_code='other')
        group = ReservationGroup.objects.create(client=other, user=stranger)
        for data in [{**self.data, 'target_id': group.pk},
                     {**self.data, 'kind': 'member', 'target_id': stranger.pk, 'audience': 'owner'}]:
            self.assertEqual(self.api.post(self.base+'preview/', data, format='json').status_code, 404)
        response, _ = self.send()
        self.member_api.force_authenticate(stranger)
        self.assertEqual(self.member_api.get(self.inbox).data['count'], 0)

    def test_scope_filters_targets_send_and_direct_member_queue(self):
        other_campus = Campus.objects.create(client=self.client_tenant, name='Other', code='other')
        response, _ = self.send({**self.data, 'kind': 'member', 'target_id': self.parent.pk, 'audience': 'owner'})
        self.assertEqual(response.status_code, 200)
        self.api.credentials(HTTP_X_CAMPUS_ID=str(other_campus.pk))
        self.assertEqual(self.api.post(self.base+'preview/', self.data, format='json').status_code, 404)
        self.assertEqual(self.api.get(self.base+'targets/?kind=member&q=parent').data['data']['list'], [])
        self.assertEqual(self.api.get(self.base).data['data']['list'], [])

    def test_notifications_permission_does_not_bypass_orders_or_customers(self):
        editor = User.objects.create_user('notification-editor')
        profile = editor.userprofile
        profile.is_manager = True; profile.manager_client = self.client_tenant
        profile.role = 'hq_admin'; profile.admin_permissions = ['notifications']; profile.save()
        self.api.force_authenticate(editor)
        self.assertEqual(self.api.post(self.base+'preview/', self.data, format='json').status_code, 403)
        self.assertEqual(self.api.get(self.base+'targets/?kind=member').status_code, 403)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.post(self.base+'preview/', self.data, format='json').status_code, 403)
        self.api.force_authenticate(None)
        self.assertIn(self.api.post(self.base+'preview/', self.data, format='json').status_code, [401, 403])

    def test_manual_snapshot_is_not_an_editable_automatic_template(self):
        response, _ = self.send()
        template = NotificationTemplate.objects.get()
        self.assertEqual(self.api.get('/api/admin/snowland/notification-templates/').data['data']['list'], [])
        self.assertEqual(self.api.patch(f'/api/admin/snowland/notification-templates/{template.pk}/', {'body':'edit'}, format='json').status_code, 404)
        self.assertEqual(self.api.post('/api/admin/snowland/notification-templates/', {'name':'bad','event':'manual','channel':'email','body':'bad'}, format='json').status_code, 400)
        queue = self.api.get(self.base)
        self.assertEqual(queue.status_code, 200)
        self.assertTrue(queue.data['data']['list'][0]['manual'])

    def test_order_binding_revocation_hides_old_manual_notice(self):
        self.send()
        self.member_api.force_authenticate(self.adult)
        self.assertEqual(self.member_api.get(self.inbox).data['count'], 1)
        MemberDetail.objects.filter(user=self.adult).update(user=None)
        self.assertEqual(self.member_api.get(self.inbox).data['count'], 0)

    def test_mid_publish_failure_rolls_back_snapshot_and_all_recipients(self):
        create = NotificationDelivery.objects.create
        calls = []
        def fail_second(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise RuntimeError('QA local publish interrupted')
            return create(**kwargs)
        with patch('API.manual_notifications.NotificationDelivery.objects.create', side_effect=fail_second):
            with self.assertRaisesMessage(RuntimeError, 'QA local publish interrupted'):
                self.send()
        self.assertEqual(NotificationTemplate.objects.count(), 0)
        self.assertEqual(NotificationDelivery.objects.count(), 0)
        self.assertEqual(self.send()[0].status_code, 200)

    def test_guest_order_and_inactive_recipient_cannot_claim_success(self):
        self.group.user = None; self.group.save(update_fields=['user'])
        response = self.api.post(self.base+'preview/', {**self.data, 'audience': 'owner'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.parent.is_active = False; self.parent.save(update_fields=['is_active'])
        response = self.api.post(self.base+'preview/', {**self.data, 'kind': 'member', 'target_id': self.parent.pk, 'audience': 'owner'}, format='json')
        self.assertEqual(response.status_code, 404, response.data)
        self.assertEqual(NotificationDelivery.objects.count(), 0)
