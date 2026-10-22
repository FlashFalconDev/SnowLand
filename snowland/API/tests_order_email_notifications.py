import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Resorts.models import Campus
from booking.models import MemberDetail, NotificationDelivery, NotificationTemplate, Payment


class OrderEmailNotificationTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.admin = User.objects.create_superuser('email-hq', 'email-hq@example.test', 'test')
        self.api = APIClient(); self.api.force_authenticate(self.admin)
        self.url = f'/api/admin/snowland/orders/{self.group.pk}/send-email/'
        self.data = {'recipient_email': self.user.email, 'subject': '課程提醒', 'message': '請查看最新安排。', 'request_key': str(uuid.uuid4())}

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_selected_other_campus_cannot_send_order_email(self, transport):
        campus = Campus.objects.create(client=self.client_tenant, name='Other campus', code='other')
        response = self.api.post(self.url, self.data, format='json', HTTP_X_CAMPUS_ID=str(campus.pk))
        self.assertEqual(response.status_code, 404, response.data)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_successful_email_is_recorded_and_synced_to_order_owner(self, transport):
        response = self.api.post(self.url, self.data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(NotificationDelivery.objects.filter(template__channel='email', recipient=self.user.email, status='sent').count(), 1)
        self.assertEqual(NotificationDelivery.objects.filter(recipient=str(self.user.pk), payload__has_key='in_app_mirror_of').count(), 1)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_replay_same_request_never_sends_twice_and_does_not_reset_read(self, transport):
        first = self.api.post(self.url, self.data, format='json')
        copy = NotificationDelivery.objects.get(recipient=str(self.user.pk))
        copy.payload['read_at'] = '2026-10-17T00:00:00Z'; copy.save()
        repeated = self.api.post(self.url, self.data, format='json')
        self.assertEqual(repeated.status_code, 200, repeated.data)
        self.assertTrue(repeated.data['data']['duplicate'])
        self.assertEqual(first.data['data']['delivery_id'], repeated.data['data']['delivery_id'])
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(NotificationDelivery.objects.count(), 2)
        copy.refresh_from_db(); self.assertTrue(copy.payload['read_at'])
        changed = self.api.post(self.url, {**self.data, 'subject':'Different'}, format='json')
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(transport.call_count, 1)

    @patch('booking.scheduler.send_gmail', side_effect=RuntimeError('sensitive transport details'))
    def test_failure_is_recorded_without_inbox_copy_or_automatic_retry(self, transport):
        response = self.api.post(self.url, self.data, format='json')
        self.assertEqual(response.status_code, 502, response.data)
        self.assertNotIn('sensitive', str(response.data))
        self.assertEqual(NotificationDelivery.objects.filter(status='failed').count(), 1)
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 0)
        self.assertEqual(self.api.post(self.url, self.data, format='json').status_code, 502)
        self.assertEqual(transport.call_count, 1)

    @patch('booking.scheduler.send_gmail', side_effect=SystemExit('QA interrupted process'))
    def test_interrupted_smtp_is_unconfirmed_and_same_key_never_resends(self, transport):
        with self.assertRaises(SystemExit):
            self.api.post(self.url, self.data, format='json')
        with patch('booking.scheduler.send_gmail') as retry:
            response = self.api.post(self.url, self.data, format='json')
            self.assertEqual(response.status_code, 202, response.data)
            retry.assert_not_called()
        self.assertEqual(NotificationDelivery.objects.get().status, 'sending')

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_selected_contact_email_can_differ_from_account_but_only_owner_is_synced(self, transport):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', DataJSON={'contact':{'email':'contact@example.test'}})
        stranger = User.objects.create_user('same-contact-stranger', email='contact@example.test')
        response = self.api.post(self.url, {**self.data,'recipient_email':'contact@example.test'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        copies = NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of')
        self.assertEqual(list(copies.values_list('recipient', flat=True)), [str(self.user.pk)])
        self.assertNotEqual(copies.get().recipient, str(stranger.pk))

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_unique_bound_parent_receives_copy_not_order_owner(self, transport):
        parent = User.objects.create_user('mail-parent', email='parent@example.test')
        MemberDetail.objects.create(reservation=self.reservation, guardian=parent)
        MemberDetail.objects.create(reservation=self.reservation, guardian=parent)
        response = self.api.post(self.url, {**self.data,'recipient_email':parent.email}, format='json')
        self.assertEqual(response.status_code, 200)
        copies = NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of')
        self.assertEqual(list(copies.values_list('recipient',flat=True)), [str(parent.pk)])

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_ambiguous_shared_mailbox_or_unrelated_address_is_not_shared_to_other_accounts(self, transport):
        for index in range(2):
            user = User.objects.create_user(f'mail-shared-{index}',email='shared@example.test')
            MemberDetail.objects.create(reservation=self.reservation,user=user)
        for recipient in ['shared@example.test','unknown@example.test']:
            response = self.api.post(self.url, {**self.data,'request_key':str(uuid.uuid4()),'recipient_email':recipient}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['data']['synced_count'], 0)
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 0)

    def test_revoked_binding_during_transport_is_not_granted_a_new_copy(self):
        adult = User.objects.create_user('mail-adult',email='adult@example.test')
        member = MemberDetail.objects.create(reservation=self.reservation,user=adult)
        def revoke(*args):
            member.user = None; member.save(update_fields=['user'])
            return 'ok'
        with patch('booking.scheduler.send_gmail', side_effect=revoke):
            response = self.api.post(self.url,{**self.data,'recipient_email':adult.email},format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['synced_count'], 0)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_campus_summary_roles_cannot_send_even_with_orders_permission(self, transport):
        for role in ['campus_manager','campus_principal']:
            staff = User.objects.create_user('email-'+role)
            profile = staff.userprofile; profile.role = role; profile.is_manager = True
            profile.manager_client = self.client_tenant; profile.admin_permissions = ['orders']; profile.save()
            profile.campuses.add(self.campus)
            self.api.force_authenticate(staff)
            self.assertEqual(self.api.post(self.url,self.data,format='json').status_code, 403)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_invalid_inputs_have_no_delivery_or_transport(self, transport):
        for change in [{'recipient_email':'bad'}, {'recipient_email':['a@example.test']}, {'subject':' '},
                       {'subject':'a'*201}, {'message':''}, {'message':'a'*10001}, {'request_key':'bad'}]:
            response = self.api.post(self.url,{**self.data,**change},format='json')
            self.assertEqual(response.status_code,400,(change,response.data))
        transport.assert_not_called()
        self.assertEqual(NotificationTemplate.objects.count(),0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',DEFAULT_FROM_EMAIL='qa-sender@example.test')
    def test_real_configured_local_mail_backend_and_member_inbox(self):
        response = self.api.post(self.url,self.data,format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(mail.outbox[0].to,[self.user.email])
        self.assertIn(self.data['message'],mail.outbox[0].body)
        self.assertIn('SnowLand',mail.outbox[0].body)
        self.assertIn('未對外寄送',response.data['msg'])
        self.api.force_authenticate(self.user)
        inbox = self.api.get('/booking/snowland/api/member-notifications/')
        self.assertEqual(inbox.data['count'],1)
        self.assertEqual(inbox.data['results'][0]['body'],mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_mail_mode_is_safe_and_scoped_without_exposing_credentials(self):
        response = self.api.get(self.url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data,{'code':200,'data':{'local_test':True}})
        campus = Campus.objects.create(client=self.client_tenant,name='Other',code='other')
        self.assertEqual(self.api.get(self.url,HTTP_X_CAMPUS_ID=str(campus.pk)).status_code,404)

    @patch('django.core.mail.send_mail',return_value=0)
    def test_zero_transport_confirmation_is_failure_not_false_success(self, transport):
        response = self.api.post(self.url,self.data,format='json')
        self.assertEqual(response.status_code,502,response.data)
        self.assertEqual(NotificationDelivery.objects.filter(status='failed').count(),1)
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(),0)
