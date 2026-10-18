import uuid
import os
import runpy
from pathlib import Path
from unittest.mock import patch
from datetime import timedelta
from django.contrib.auth.models import User
from django.core import mail
from django.http import HttpRequest
from django.middleware.csrf import get_token
from django.test import TestCase, Client as BrowserClient, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from API import tests_operations as fixtures
from booking.models import NotificationDelivery, Payment, ReservationGroup


@override_settings(SNOWLAND_PUBLIC_PAYMENT_URL='https://booking.example.test/snowland/payment')
class LegacyPaymentEmailTests(TestCase):
    setUp = fixtures.OperationsTests.setUp
    url = '/booking/api/payment_gmail/'

    def payload(self):
        return {'gmail': self.user.email,
                'payment_url': f'https://attacker.invalid/payment?reservation_group={self.group.pk}',
                'request_key': str(uuid.uuid4())}

    def api(self, user):
        api = APIClient(); api.force_authenticate(user); return api

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_owner_mail_uses_server_payment_url_and_records_member_copy(self, transport):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='unpaid')
        response = self.api(self.user).post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 200, response.data if hasattr(response, 'data') else response.content)
        self.assertNotIn('attacker.invalid', transport.call_args.args[1])
        self.assertIn(f'https://booking.example.test/snowland/payment?reservation_group={self.group.pk}', transport.call_args.args[1])
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 1)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_other_member_cannot_send_link_for_someone_elses_order(self, transport):
        response = self.api(self.coach_user).post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 404)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_unknown_email_cannot_turn_endpoint_into_mail_relay(self, transport):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='unpaid')
        response = self.api(self.user).post(self.url, {**self.payload(), 'gmail': 'unknown@example.test'}, format='json')
        self.assertEqual(response.status_code, 403)
        transport.assert_not_called()
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_original_order_contact_allowed_but_only_owner_gets_inbox_copy(self, transport):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='unpaid', DataJSON={'contact': {'email': 'contact@example.test'}})
        stranger = User.objects.create_user('payment-contact-stranger', email='contact@example.test')
        data = {**self.payload(), 'gmail': 'contact@example.test'}
        response = self.api(self.user).post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(list(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').values_list('recipient', flat=True)), [str(self.user.pk)])
        self.assertNotEqual(self.user.pk, stranger.pk)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_stable_request_key_sends_once_and_returns_same_receipt(self, transport):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='unpaid')
        api = self.api(self.user); data = self.payload()
        first = api.post(self.url, data, format='json'); second = api.post(self.url, data, format='json')
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.json()['data']['delivery_id'], first.json()['data']['delivery_id'])
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(NotificationDelivery.objects.count(), 2)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_inactive_tenant_and_guest_order_are_not_owned(self, transport):
        guest = ReservationGroup.objects.create(client=self.client_tenant)
        self.assertEqual(self.api(self.user).post(self.url, {**self.payload(), 'group_id': guest.pk, 'payment_url': ''}, format='json').status_code, 404)
        self.client_tenant.is_active = False; self.client_tenant.save()
        self.assertEqual(self.api(self.user).post(self.url, self.payload(), format='json').status_code, 404)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_paid_pending_expired_and_refunded_orders_cannot_request_payment_mail(self, transport):
        payment = Payment.objects.create(reservation_group=self.group, user=self.user)
        for status in ['paid', 'pending', 'expired', 'refunded']:
            payment.status = status; payment.save()
            self.assertEqual(self.api(self.user).post(self.url, self.payload(), format='json').status_code, 409)
        payment.status = 'unpaid'; payment.expires_at = timezone.now() - timedelta(seconds=1); payment.save()
        self.assertEqual(self.api(self.user).post(self.url, self.payload(), format='json').status_code, 409)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_cancelled_no_payment_or_pending_coach_order_cannot_mail(self, transport):
        self.assertEqual(self.api(self.user).post(self.url, self.payload(), format='json').status_code, 409)
        Payment.objects.create(reservation_group=self.group, user=self.user)
        for status in ['cancelled', 'deleted', 'pending_coach_confirmation', 'auto_assignment_failed']:
            self.reservation.status = status; self.reservation.save()
            self.assertEqual(self.api(self.user).post(self.url, self.payload(), format='json').status_code, 409)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_invalid_ids_email_url_shape_and_request_key_do_not_send(self, transport):
        Payment.objects.create(reservation_group=self.group, user=self.user)
        for change in [{'payment_url': ''}, {'group_id': -1}, {'group_id': 2**70},
                       {'group_id': self.group.pk + 1}, {'payment_url': 'https://example.test/?reservation_group=1&reservation_group=2'},
                       {'payment_url': []}, {'gmail': 'invalid'}, {'request_key': 'invalid'}]:
            response = self.api(self.user).post(self.url, {**self.payload(), **change}, format='json')
            self.assertEqual(response.status_code, 400, (change, response.content))
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_public_payment_url_must_be_trusted_configuration(self, transport):
        Payment.objects.create(reservation_group=self.group, user=self.user)
        for url in ['', 'http://example.test/snowland/payment', 'https://example.test/other/payment',
                    'https://name:secret@example.test/snowland/payment', 'https://example.test/snowland/payment?x=1',
                    'https://example.test:bad/snowland/payment', 'https://example.test/snowland/payment#fake']:
            with self.settings(SNOWLAND_PUBLIC_PAYMENT_URL=url):
                self.assertEqual(self.api(self.user).post(self.url, self.payload(), format='json').status_code, 503)
        transport.assert_not_called()
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    @patch('booking.scheduler.send_gmail', side_effect=RuntimeError('secret SMTP diagnostic'))
    def test_failure_is_recorded_redacted_and_not_retried(self, transport):
        Payment.objects.create(reservation_group=self.group, user=self.user)
        api = self.api(self.user); data = self.payload()
        response = api.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('secret SMTP', str(response.content))
        self.assertEqual(api.post(self.url, data, format='json').status_code, 502)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(NotificationDelivery.objects.filter(status='failed').count(), 1)
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 0)

    def test_uncertain_send_is_not_2xx_success_and_same_key_never_resends(self):
        Payment.objects.create(reservation_group=self.group, user=self.user)
        api = self.api(self.user); data = self.payload()
        with patch('booking.scheduler.send_gmail', side_effect=SystemExit('QA interrupted mail')):
            with self.assertRaises(SystemExit):
                api.post(self.url, data, format='json')
        with patch('booking.scheduler.send_gmail') as retry:
            response = api.post(self.url, data, format='json')
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['result'], 'pending')
            retry.assert_not_called()

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_real_django_mail_has_local_test_receipt_and_independent_inbox_copy(self):
        Payment.objects.create(reservation_group=self.group, user=self.user)
        response = self.api(self.user).post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('attacker.invalid', mail.outbox[0].body)
        self.assertIn('未對外寄送', response.json()['message'])
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 1)

    @patch('booking.scheduler.send_gmail')
    def test_forged_legacy_identity_and_unauthed_calls_never_send(self, transport):
        for headers in [{}, {'HTTP_JWT': 'ignored|' + self.user.email}]:
            response = APIClient().post(self.url, self.payload(), format='json', **headers)
            self.assertIn(response.status_code, [401, 403])
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail')
    def test_actual_session_still_requires_csrf(self, transport):
        browser = BrowserClient(enforce_csrf_checks=True); browser.force_login(self.user)
        self.assertEqual(browser.post(self.url, self.payload()).status_code, 403)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail')
    def test_zero_amount_is_not_a_payment_request(self, transport):
        Payment.objects.create(reservation_group=self.group, user=self.user)
        self.reservation.course_fee = self.reservation.coach_fee = self.reservation.discount_amount = 0
        self.reservation.save()
        self.assertEqual(self.api(self.user).post(self.url, self.payload(), format='json').status_code, 409)
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_actual_proxy_origin_accepts_valid_csrf_but_not_untrusted_origin(self, transport):
        from django.conf import settings
        Payment.objects.create(reservation_group=self.group, user=self.user)
        browser = BrowserClient(enforce_csrf_checks=True); browser.force_login(self.user)
        request = HttpRequest(); token = get_token(request)
        browser.cookies[settings.CSRF_COOKIE_NAME] = request.META['CSRF_COOKIE']
        response = browser.post(self.url, self.payload(), HTTP_X_CSRFTOKEN=token,
                                HTTP_ORIGIN='http://127.0.0.1:3000', HTTP_HOST='localhost:8999')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(browser.post(self.url, self.payload(), HTTP_X_CSRFTOKEN=token,
                                     HTTP_ORIGIN='https://untrusted.example.test', HTTP_HOST='localhost:8999').status_code, 403)
        self.assertEqual(transport.call_count, 1)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_shared_email_does_not_break_authenticated_user_identity(self, transport):
        User.objects.create_user('same-email-other-account', email=self.user.email)
        Payment.objects.create(reservation_group=self.group, user=self.user)
        browser = BrowserClient(); browser.force_login(self.user)
        response = browser.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(list(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').values_list('recipient', flat=True)), [str(self.user.pk)])

    def test_local_payment_url_default_never_applies_to_remote_or_real_database(self):
        for host, name, expected in [('127.0.0.1', 'test_snowland', 'http://127.0.0.1:3000/snowland/payment'),
                                     ('production.invalid', 'SLDB', ''), ('127.0.0.1', 'SLDB', ''),
                                     ('production.invalid', 'test_snowland', '')]:
            with self.subTest(host=host, database=name), patch.dict(os.environ, {
                'Mysql_HOST': host, 'Mysql_NAME': name, 'SNOWLAND_PUBLIC_PAYMENT_URL': '',
            }), patch('dotenv.load_dotenv'), patch('dotenv.dotenv_values', return_value={}):
                config = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'snowland' / 'settings.py'))
                self.assertEqual(config['SNOWLAND_PUBLIC_PAYMENT_URL'], expected)
