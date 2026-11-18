import base64
import hashlib
import hmac
import json
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from Client.models import Client
from chatbooking.models import LineChannelBinding, MetaPageBinding


class SocialChannelTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(internal_code='qa-social', name='QA Social')
        self.other = Client.objects.create(internal_code='qa-social-other', name='QA Other')
        self.admin = User.objects.create_superuser('qa-social-admin')
        self.client.force_login(self.admin)
        self.base = '/api/admin/qa-social/instagram-sync/'
        env = patch.dict('os.environ', {
            'SNOWLAND_SOCIAL_CREDENTIAL_KEY': Fernet.generate_key().decode(),
            'SNOWLAND_META_APP_ID': '12345', 'SNOWLAND_META_APP_SECRET': 'qa-meta-secret',
            'SNOWLAND_META_CONFIG_ID': '67890', 'SNOWLAND_META_GRAPH_VERSION': 'v27.0',
            'SNOWLAND_META_REDIRECT_URI': 'https://qa.example.test' + reverse('meta-social-callback'),
        })
        env.start()
        self.addCleanup(env.stop)

    def test_line_only_verifies_the_right_destination_and_tenant(self):
        url = self.base + 'line-channel/'
        bot = 'U' + 'a' * 32
        secret, token = '1' * 32, 'qa-line-token' * 3
        info = Mock(status_code=200)
        info.json.return_value = {'userId': bot, 'displayName': 'QA Official'}
        with patch('chatbooking.channel_binding.requests.get', return_value=info) as line:
            result = self.client.put(url, {'channel_secret': secret, 'access_token': token}, content_type='application/json')
            self.assertEqual(result.status_code, 200, result.content)
            self.assertFalse(result.json()['data']['verified'])
            self.assertIn('api.line.me/v2/bot/info', line.call_args.args[0])
            self.assertNotContains(result, token)
            duplicate = self.client.put(url.replace('qa-social/', 'qa-social-other/'),
                {'channel_secret': secret, 'access_token': token}, content_type='application/json')
            self.assertEqual(duplicate.status_code, 400)
        stored = LineChannelBinding.objects.get(client=self.tenant)
        self.assertNotIn(secret, stored.credentials)
        self.assertNotIn(token, stored.credentials)

        def signed(destination):
            body = json.dumps({'destination': destination, 'events': []}).encode()
            signature = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
            return self.client.post(result.json()['data']['webhook_path'], body, content_type='application/json',
                                    HTTP_X_LINE_SIGNATURE=signature)

        self.assertEqual(signed('U' + 'b' * 32).status_code, 401)
        self.assertFalse(self.client.get(url).json()['data']['verified'])
        self.assertEqual(signed(bot).status_code, 200)
        self.assertTrue(self.client.get(url).json()['data']['verified'])
        with patch('chatbooking.channel_binding.requests.get', return_value=info):
            changed = self.client.put(url, {'channel_secret': '2' * 32, 'access_token': token},
                                      content_type='application/json')
        self.assertEqual(changed.status_code, 400)
        self.assertTrue(self.client.get(url).json()['data']['verified'])
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(signed(bot).status_code, 401)

    @override_settings(LINE_CLIENT_CODE='qa-social', LINE_CHANNEL_SECRET='a' * 32,
                       LINE_CHANNEL_ACCESS_TOKEN='qa-legacy-access-token')
    def test_legacy_line_stays_active_and_cannot_be_claimed_by_another_tenant(self):
        url = self.base + 'line-channel/'
        status = self.client.get(url).json()['data']
        self.assertTrue(status['legacy'])
        secret, token = 'a' * 32, 'qa-replacement-token'
        payload = {'channel_secret': secret, 'access_token': token}
        bot = Mock(status_code=200)
        bot.json.return_value = {'userId': 'U' + 'a' * 32, 'displayName': 'Platform LINE'}
        with patch('chatbooking.channel_binding.requests.get', return_value=bot) as get_info:
            self.assertEqual(self.client.put(url, payload, content_type='application/json').status_code, 400)
            get_info.assert_not_called()
            other = url.replace('qa-social/', 'qa-social-other/')
            self.assertEqual(self.client.put(other, payload, content_type='application/json').status_code, 400)
            self.assertEqual(get_info.call_count, 2)
        self.assertFalse(LineChannelBinding.objects.exists())
        body = b'{"events":[]}'
        signature = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
        self.assertEqual(self.client.post(status['webhook_path'], body, content_type='application/json',
                                          HTTP_X_LINE_SIGNATURE=signature).status_code, 200)

    def test_meta_oauth_uses_selected_page_and_rejects_replay(self):
        url = self.base + 'meta-channel/'
        page = {'id': '1122', 'name': 'QA Page', 'access_token': 'private-page-token', 'tasks': ['MESSAGING'],
                'instagram_business_account': {'id': '3344', 'username': 'qa-instagram'}}
        with patch('chatbooking.meta_binding._graph', side_effect=[{'access_token':'private-user-token'}, {'data':[page]}]) as graph:
            started = self.client.post(url, {'page_id': '1122'}, content_type='application/json')
            self.assertEqual(started.status_code, 200, started.content)
            target = urlsplit(started.json()['data']['authorization_url'])
            self.assertEqual(target.hostname, 'www.facebook.com')
            state = parse_qs(target.query)['state'][0]
            callback = reverse('meta-social-callback')
            self.assertEqual(self.client.get(callback, {'state': 'x' * 43}).status_code, 400)
            done = self.client.get(callback, {'state': state, 'code':'test-auth-code'})
            self.assertRedirects(done, '/qa-social/console/social-sync?meta=bound', fetch_redirect_response=False)
            self.assertEqual(self.client.get(callback, {'state': state, 'code':'test-auth-code'}).status_code, 400)
            self.assertEqual(graph.call_count, 2)
        bound = self.client.get(url)
        self.assertEqual(bound.json()['data']['instagram_name'], 'qa-instagram')
        self.assertNotContains(bound, 'private-page-token')
        self.assertNotIn('private-page-token', MetaPageBinding.objects.get().credentials)
        self.assertFalse(self.client.get(url.replace('qa-social/', 'qa-social-other/')).json()['data']['page_id'])
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertFalse(MetaPageBinding.objects.exists())

    def test_meta_authorizes_before_choosing_a_page(self):
        url = self.base + 'meta-channel/'
        pages = [
            {'id': '1122', 'name': 'QA One', 'access_token': 'qa-page-one', 'tasks': ['MESSAGING']},
            {'id': '3344', 'name': 'QA Two', 'access_token': 'qa-page-two', 'tasks': ['MESSAGING'],
             'instagram_business_account': {'id': '5566', 'username': 'qa-snow'}},
            {'id': '7788', 'name': 'QA No permission', 'access_token': 'qa-page-other', 'tasks': ['ANALYZE']},
        ]
        with patch('chatbooking.meta_binding._graph', side_effect=[
            {'access_token': 'qa-only-user-token'}, {'data': pages}, {'data': pages},
        ]) as graph:
            started = self.client.post(url, {}, content_type='application/json')
            self.assertEqual(started.status_code, 200)
            state = parse_qs(urlsplit(started.json()['data']['authorization_url']).query)['state'][0]
            callback = self.client.get(reverse('meta-social-callback'), {'state': state, 'code':'test-auth-code'})
            self.assertRedirects(callback, '/qa-social/console/social-sync?meta=choose', fetch_redirect_response=False)
            self.assertFalse(MetaPageBinding.objects.exists())
            pending = self.client.get(url)
            self.assertEqual([page['id'] for page in pending.json()['data']['available_pages']], ['1122', '3344'])
            self.assertNotContains(pending, 'qa-only-user-token')
            self.assertNotContains(pending, 'qa-page-two')
            other = url.replace('qa-social/', 'qa-social-other/')
            self.assertEqual(self.client.get(other).json()['data']['available_pages'], [])
            for target, page in [(other, '3344'), (url, '7788')]:
                response = self.client.put(target, {'page_id': page}, content_type='application/json')
                self.assertEqual(response.status_code, 409)
            selected = self.client.put(url, {'page_id': '3344'}, content_type='application/json')
            self.assertEqual(selected.status_code, 200, selected.content)
            self.assertEqual(selected.json()['data']['instagram_name'], 'qa-snow')
            self.assertEqual(selected.json()['data']['available_pages'], [])
            self.assertEqual(self.client.put(url, {'page_id': '1122'}, content_type='application/json').status_code, 409)
            self.assertEqual(graph.call_count, 3)
