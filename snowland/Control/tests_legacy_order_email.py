from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client as BrowserClient
from API import tests_operations as fixtures
from booking.models import NotificationDelivery
from Client.models import Client
from Resorts.models import Campus
import uuid


class LegacyOrderEmailTests(TestCase):
    setUp = fixtures.OperationsTests.setUp
    url = '/control/api/manager/send_email_form/'

    def payload(self):
        return {'group_id': self.group.pk, 'recipient_email': self.user.email,
                'subject': 'QA old form', 'message': 'QA reminder'}

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_ordinary_logged_in_customer_cannot_send_mail(self, transport):
        browser = BrowserClient(); browser.force_login(self.user)
        response = browser.post(self.url, self.payload())
        self.assertEqual(response.status_code, 403)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_forged_legacy_identity_header_cannot_send(self, transport):
        admin = User.objects.create_superuser('legacy-mail-hq', 'legacy-hq@example.test', 'test')
        response = BrowserClient().post(self.url, self.payload(), HTTP_JWT='ignored|' + admin.email)
        self.assertIn(response.status_code, [401, 403])
        browser = BrowserClient(); session = browser.session
        session['control'] = {'client_sid': admin.email}; session.save()
        response = browser.post(self.url, self.payload())
        self.assertIn(response.status_code, [401, 403])
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_real_admin_old_form_also_records_email_and_member_copy(self, transport):
        admin = User.objects.create_superuser('legacy-mail-hq', 'legacy-hq@example.test', 'test')
        browser = BrowserClient(); browser.force_login(admin)
        response = browser.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['code'], 100)
        self.assertEqual(NotificationDelivery.objects.filter(template__channel='email').count(), 2)
        self.assertEqual(NotificationDelivery.objects.filter(recipient=str(self.user.pk), payload__has_key='in_app_mirror_of').count(), 1)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_selected_other_campus_blocks_post_and_get(self, transport):
        admin = User.objects.create_superuser('legacy-mail-hq', 'legacy-hq@example.test', 'test')
        other = Campus.objects.create(client=self.client_tenant, name='Other', code='other')
        browser = BrowserClient(); browser.force_login(admin)
        self.assertEqual(browser.post(self.url, self.payload(), HTTP_X_CAMPUS_ID=str(other.pk)).status_code, 404)
        self.assertEqual(browser.get(self.url, {'id': self.group.pk}, HTTP_X_CAMPUS_ID=str(other.pk)).status_code, 404)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_other_tenant_manager_and_summary_role_cannot_use_legacy_entry(self, transport):
        other = Client.objects.create(name='Other', internal_code='other')
        for name, role, tenant in [('outside', 'hq_admin', other), ('principal', 'campus_principal', self.client_tenant)]:
            staff = User.objects.create_user('legacy-' + name, email=name+'@example.test')
            profile = staff.userprofile
            profile.is_manager = True; profile.manager_client = tenant
            profile.role = role; profile.admin_permissions = ['orders']; profile.save()
            profile.campuses.add(self.campus)
            browser = BrowserClient(); browser.force_login(staff)
            self.assertEqual(browser.post(self.url, self.payload()).status_code, 403)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_validation_and_stable_request_key_share_new_send_receipt(self, transport):
        admin = User.objects.create_superuser('legacy-mail-hq', 'legacy-hq@example.test', 'test')
        browser = BrowserClient(); browser.force_login(admin)
        for invalid in [None, '', '-1', 'bad', '9'*100]:
            self.assertEqual(browser.post(self.url, {**self.payload(), 'group_id': invalid or ''}).status_code, 400)
        self.assertEqual(browser.post(self.url, {**self.payload(), 'subject': ''}).status_code, 400)
        self.assertEqual(NotificationDelivery.objects.count(), 0)
        data = {**self.payload(), 'request_key': str(uuid.uuid4())}
        first = browser.post(self.url, data); again = browser.post(self.url, data)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(again.json()['data']['delivery_id'], first.json()['data']['delivery_id'])
        self.assertTrue(again.json()['data']['duplicate'])
        self.assertEqual(transport.call_count, 1)

    @patch('booking.scheduler.send_gmail', side_effect=RuntimeError('secret SMTP diagnostic'))
    def test_failure_redacted_with_no_member_copy(self, transport):
        admin = User.objects.create_superuser('legacy-mail-hq', 'legacy-hq@example.test', 'test')
        browser = BrowserClient(); browser.force_login(admin)
        response = browser.post(self.url, self.payload())
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('secret SMTP', str(response.content))
        self.assertEqual(NotificationDelivery.objects.filter(status='failed').count(), 1)
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 0)

    def test_get_redirects_authorized_admin_to_current_order_page(self):
        admin = User.objects.create_superuser('legacy-mail-hq', 'legacy-hq@example.test', 'test')
        browser = BrowserClient(); browser.force_login(admin)
        response = browser.get(self.url, {'id': self.group.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], f'/snowland/console/orders?search={self.group.pk}')
        browser.force_login(self.user)
        self.assertEqual(browser.get(self.url, {'id': self.group.pk}).status_code, 403)

    @patch('booking.scheduler.send_gmail')
    def test_real_session_post_still_requires_csrf(self, transport):
        admin = User.objects.create_superuser('legacy-mail-hq', 'legacy-hq@example.test', 'test')
        browser = BrowserClient(enforce_csrf_checks=True); browser.force_login(admin)
        self.assertEqual(browser.post(self.url, self.payload()).status_code, 403)
        transport.assert_not_called()
