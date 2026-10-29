"""Deployment URL regressions; never connect to a database or payment provider."""

import os
import runpy
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import requests
from django.test import RequestFactory, SimpleTestCase, override_settings

from snowland.adapters import MyAccountAdapter, MySocialAccountAdapter


def configured_urls(values=None):
    environment = {'DJANGO_SECRET_KEY': 'isolated-public-url-test-secret'}
    environment.update(values or {})
    with patch.dict(os.environ, environment, clear=True), \
            patch('dotenv.load_dotenv'), \
            patch('dotenv.dotenv_values', return_value={}), \
            patch('requests.put', side_effect=requests.Timeout()):
        return runpy.run_path(str(Path(__file__).with_name('settings.py')))


class PublicURLSettingsTests(SimpleTestCase):
    def test_defaults_use_snowland_not_old_flashfalcon(self):
        config = configured_urls()
        self.assertEqual(config['RUN_HOST'], 'https://snowland.tw')
        self.assertEqual(config['PAYMENT_HOST'], 'https://snowland.tw/booking/payment/')
        self.assertEqual(config['FRONTEND_URL'], 'https://snowland.tw')
        self.assertEqual(config['LOGIN_REDIRECT_URL'], 'https://snowland.tw/auth/callback')
        self.assertNotIn('https://dev.flashfalcon.info', config['CORS_ALLOWED_ORIGINS'])

    def test_environment_overrides_public_urls_and_normalizes_slashes(self):
        config = configured_urls({
            'RUN_HOST': ' https://api.snowland.test/ ',
            'PAYMENT_HOST': ' https://pay.snowland.test/booking/payment ',
            'FRONTEND_URL': ' https://web.snowland.test/ ',
        })
        self.assertEqual(config['RUN_HOST'], 'https://api.snowland.test')
        self.assertEqual(config['PAYMENT_HOST'], 'https://pay.snowland.test/booking/payment/')
        self.assertEqual(config['FRONTEND_URL'], 'https://web.snowland.test')
        self.assertEqual(config['LOGIN_REDIRECT_URL'], 'https://web.snowland.test/auth/callback')

    def test_payment_and_frontend_defaults_follow_run_host(self):
        config = configured_urls({'RUN_HOST': 'http://127.0.0.1:8999/'})
        self.assertEqual(config['PAYMENT_HOST'], 'http://127.0.0.1:8999/booking/payment/')
        self.assertEqual(config['FRONTEND_URL'], 'http://127.0.0.1:8999')

    def test_blank_public_urls_do_not_generate_relative_or_old_domain_links(self):
        config = configured_urls({'RUN_HOST': ' ', 'PAYMENT_HOST': '', 'FRONTEND_URL': ' '})
        self.assertEqual(config['RUN_HOST'], 'https://snowland.tw')
        self.assertEqual(config['PAYMENT_HOST'], 'https://snowland.tw/booking/payment/')
        self.assertEqual(config['FRONTEND_URL'], 'https://snowland.tw')

    def test_cors_origins_are_explicit_trimmed_environment_values(self):
        config = configured_urls({
            'DJANGO_CORS_ALLOWED_ORIGINS': ' https://snowland.tw, ,https://www.snowland.tw ',
        })
        self.assertEqual(config['CORS_ALLOWED_ORIGINS'],
                         ['https://snowland.tw', 'https://www.snowland.tw'])

    def test_cors_can_be_empty_for_same_origin(self):
        self.assertEqual(configured_urls({'DJANGO_CORS_ALLOWED_ORIGINS': ''})['CORS_ALLOWED_ORIGINS'], [])

    def test_default_cors_includes_configured_frontend_and_local_development(self):
        config = configured_urls({'FRONTEND_URL': 'https://web.snowland.test'})
        self.assertIn('https://web.snowland.test', config['CORS_ALLOWED_ORIGINS'])
        self.assertIn('http://localhost:3000', config['CORS_ALLOWED_ORIGINS'])
        self.assertIn('http://127.0.0.1:3000', config['CORS_ALLOWED_ORIGINS'])

    def test_real_cors_preflight_allows_only_configured_frontend(self):
        config = configured_urls({'DJANGO_CORS_ALLOWED_ORIGINS': 'https://www.snowland.tw'})
        with override_settings(CORS_ALLOWED_ORIGINS=config['CORS_ALLOWED_ORIGINS']):
            response = self.client.options('/healthz/', HTTP_ORIGIN='https://www.snowland.tw',
                                           HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Access-Control-Allow-Origin'], 'https://www.snowland.tw')
        self.assertEqual(response['Access-Control-Allow-Credentials'], 'true')

    def test_real_cors_preflight_does_not_allow_old_or_unknown_origins(self):
        config = configured_urls({'DJANGO_CORS_ALLOWED_ORIGINS': 'https://snowland.tw'})
        with override_settings(CORS_ALLOWED_ORIGINS=config['CORS_ALLOWED_ORIGINS']):
            for origin in ('https://dev.flashfalcon.info', 'https://evil.example'):
                with self.subTest(origin=origin):
                    response = self.client.options('/healthz/', HTTP_ORIGIN=origin,
                                                   HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST')
                    self.assertNotIn('Access-Control-Allow-Origin', response)

    def test_actual_payment_link_uses_configured_payment_host(self):
        from booking.payment_access import payment_url_for_group
        config = configured_urls({'PAYMENT_HOST': 'https://snowland.tw/booking/payment/'})
        group = SimpleNamespace(pk=123, user_id=45)
        parts = urlsplit(payment_url_for_group(config['PAYMENT_HOST'], group))
        self.assertEqual((parts.scheme, parts.netloc, parts.path),
                         ('https', 'snowland.tw', '/booking/payment/'))
        self.assertEqual(parse_qs(parts.query), {'reservation_group': ['123']})

    def test_actual_newebpay_payload_uses_configured_notify_origin(self):
        from booking.api_views import ProcessPaymentAPI
        config = configured_urls({'RUN_HOST': 'https://snowland.tw/'})
        user = SimpleNamespace(id=45, email='qa@example.test', is_authenticated=True)
        group = SimpleNamespace(pk=123, user=user, reservations=Mock())
        group.reservations.all.return_value = []
        group.reservations.exclude.return_value = [SimpleNamespace(payment_amount=Decimal('1000'))]
        booking = SimpleNamespace(date=date(2026, 11, 1), course_name='QA lesson')
        with patch('booking.api_views.RUN_HOST', config['RUN_HOST']), \
                patch('booking.api_views.Booking.objects.filter', return_value=[booking]), \
                patch('booking.api_views.neweb_pay_request', return_value='<form>local-only</form>') as pay:
            response = ProcessPaymentAPI()._process_newebpay(SimpleNamespace(user=user), group)
        self.assertEqual(response.status_code, 200)
        body = pay.call_args.args[0]['body']
        self.assertEqual(body['NotifyURL'], 'https://snowland.tw/call_back/NewebPay/?user_id=45')
        self.assertEqual(body['price'], '1000')


@override_settings(
    FRONTEND_URL='https://snowland.tw',
    LOGIN_REDIRECT_URL='https://snowland.tw/auth/callback',
    ALLOWED_HOSTS=['testserver', 'snowland.tw', 'www.snowland.tw', 'api.snowland.test'],
)
class LoginRedirectTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account = MyAccountAdapter()
        self.social = MySocialAccountAdapter()

    def assert_redirects(self, request, expected):
        self.assertEqual(self.account.get_login_redirect_url(request), expected)
        self.assertEqual(self.social.get_login_redirect_url(request, None), expected)
        self.assertEqual(self.social.get_signup_redirect_url(request, None), expected)
        self.assertEqual(self.social.get_redirect_url(request), expected)

    def test_production_login_without_referer_never_returns_localhost(self):
        self.assert_redirects(self.factory.get('/accounts/google/login/callback/', secure=True),
                              'https://snowland.tw/auth/callback')

    def test_production_login_with_snowland_referer(self):
        request = self.factory.get('/accounts/google/login/callback/', secure=True,
                                   HTTP_REFERER='https://snowland.tw/snowland/membership')
        self.assert_redirects(request, 'https://snowland.tw/auth/callback')

    def test_www_login_returns_to_the_configured_canonical_frontend(self):
        request = self.factory.get('/accounts/google/login/callback/', secure=True,
                                   HTTP_HOST='www.snowland.tw')
        self.assert_redirects(request, 'https://snowland.tw/auth/callback')

    @override_settings(FRONTEND_URL='https://web.snowland.test',
                       LOGIN_REDIRECT_URL='https://web.snowland.test/auth/callback')
    def test_separate_frontend_is_configured_not_guessed_from_referer(self):
        request = self.factory.get('/accounts/google/login/callback/', secure=True,
                                   HTTP_REFERER='https://accounts.google.com/')
        self.assert_redirects(request, 'https://web.snowland.test/auth/callback')

    @override_settings(FRONTEND_URL='http://localhost:3000',
                       LOGIN_REDIRECT_URL='http://localhost:3000/auth/callback')
    def test_local_frontend_can_still_be_selected_explicitly(self):
        self.assert_redirects(self.factory.get('/accounts/google/login/callback/'),
                              'http://localhost:3000/auth/callback')

    @override_settings(FRONTEND_URL='https://ffreact.ngrok.io',
                       LOGIN_REDIRECT_URL='https://ffreact.ngrok.io/auth/callback')
    def test_ngrok_remains_available_as_an_explicit_frontend(self):
        self.assert_redirects(self.factory.get('/accounts/google/login/callback/', secure=True),
                              'https://ffreact.ngrok.io/auth/callback')

    def test_safe_relative_next_preserves_requested_member_page(self):
        request = self.factory.get('/accounts/google/login/callback/',
                                   {'next': '/snowland/membership/orders?from=login'}, secure=True)
        self.assert_redirects(request, '/snowland/membership/orders?from=login')

    @override_settings(FRONTEND_URL='https://web.snowland.test',
                       LOGIN_REDIRECT_URL='https://web.snowland.test/auth/callback')
    def test_next_can_target_configured_frontend_or_current_backend(self):
        for target in ('https://web.snowland.test/auth/callback', 'https://api.snowland.test/booking/'):
            with self.subTest(target=target):
                request = self.factory.get('/accounts/google/login/callback/', {'next': target},
                                           secure=True, HTTP_HOST='api.snowland.test')
                self.assert_redirects(request, target)

    def test_untrusted_next_cannot_override_configured_destination(self):
        for target in ('https://evil.example/', '//evil.example/',
                       'https://snowland.tw.evil.example/', 'javascript:alert(1)',
                       'http://snowland.tw/membership', 'https://snowland.tw@evil.example/'):
            with self.subTest(target=target):
                request = self.factory.get('/accounts/google/login/callback/', {'next': target}, secure=True)
                self.assert_redirects(request, 'https://snowland.tw/auth/callback')

    def test_ngrok_substring_in_untrusted_referer_is_not_a_redirect_allowlist(self):
        request = self.factory.get('/accounts/google/login/callback/', secure=True,
                                   HTTP_REFERER='https://evil.example/?next=ngrok.io')
        self.assert_redirects(request, 'https://snowland.tw/auth/callback')
