import os
import runpy
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from booking.api_views import GoogleLoginAPI
from snowland import settings as settings_module


class GoogleLoginConfigurationTests(SimpleTestCase):
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
        request = APIRequestFactory().post(
            '/booking/api/google-login/',
            {'credential': 'test-token'},
            format='json',
        )

        response = GoogleLoginAPI.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['msg'], 'Google token 中缺少 email')
        self.assertEqual(verify_token.call_args.args[2], settings.GOOGLE_OAUTH_CLIENT_ID)
