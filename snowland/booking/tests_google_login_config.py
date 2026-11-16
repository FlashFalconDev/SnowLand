import os
import runpy
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from booking.api_views import GoogleLoginAPI
from snowland import settings as settings_module


class GoogleLoginConfigurationTests(TestCase):
    def test_member_google_client_id_has_fallback_without_external_env(self):
        with patch.dict(os.environ, {'GOOGLE_OAUTH_CLIENT_ID': '', 'VITE_GOOGLE_CLIENT_ID': ''}), \
                patch('dotenv.dotenv_values', return_value={}), \
                patch('dotenv.load_dotenv', return_value=None):
            isolated_settings = runpy.run_path(settings_module.__file__)

        self.assertEqual(
            isolated_settings['GOOGLE_OAUTH_CLIENT_ID'],
            '754789081671-np8lbocgau68d4rers83v649bnm993vp.apps.googleusercontent.com',
        )

    @patch('google.oauth2.id_token.verify_oauth2_token', return_value={})
    def test_member_google_login_reaches_token_validation(self, verify_token):
        from Client.models import Client
        Client.objects.create(name='QA',internal_code='snowland')
        request = APIRequestFactory().post(
            '/booking/snowland/api/google-login/',
            {'credential': 'test-token'},
            format='json',
        )

        response = GoogleLoginAPI.as_view()(request, client_code='snowland')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['msg'], 'Google token 中缺少 email')
        self.assertEqual(verify_token.call_args.args[2], settings.GOOGLE_OAUTH_CLIENT_ID)

    @patch('snowland.google_auth.time.sleep')
    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_member_retries_a_small_clock_difference_with_its_own_audience(self, verify_token, sleep):
        from Client.models import Client
        audience = 'qa-tenant.apps.googleusercontent.com'
        Client.objects.create(name='QA', internal_code='snowland', google_oauth_client_id=audience)
        verify_token.side_effect = [ValueError('Token used too early, 100 < 101.'), {}]
        request = APIRequestFactory().post('/booking/snowland/api/google-login/', {'credential': 'qa'}, format='json')

        response = GoogleLoginAPI.as_view()(request, client_code='snowland')

        self.assertEqual(response.data['msg'], 'Google token 中缺少 email')
        self.assertEqual([call.args[2] for call in verify_token.call_args_list], [audience, audience])
        sleep.assert_called_once_with(2)

    @patch('snowland.google_auth.time.sleep')
    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_only_a_small_early_token_error_is_retried(self, verify_token, sleep):
        from snowland.google_auth import verify_google_oauth2_token

        for error in ('Token used too early, 100 < 110.', 'Token expired', 'Wrong audience'):
            with self.subTest(error=error):
                verify_token.reset_mock()
                verify_token.side_effect = ValueError(error)
                with self.assertRaisesMessage(ValueError, error):
                    verify_google_oauth2_token('qa', 'qa-audience')
                verify_token.assert_called_once()
        sleep.assert_not_called()
