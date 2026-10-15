from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from booking.api_views import GoogleLoginAPI


class GoogleLoginConfigurationTests(SimpleTestCase):
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
