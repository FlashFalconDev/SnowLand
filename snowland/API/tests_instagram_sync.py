from datetime import timedelta
from io import StringIO
import time
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client, InstagramConnection, SiteContent
from Client.instagram_sync import InstagramError, authorization_url, connect_account, run_sync

KEY = Fernet.generate_key().decode()
CONFIG = dict(SNOWLAND_INSTAGRAM_APP_ID='12345', SNOWLAND_INSTAGRAM_APP_SECRET='qa-app-secret',
    SNOWLAND_INSTAGRAM_REDIRECT_URI='https://example.test/api/admin/snowland/instagram-sync/callback/',
    SNOWLAND_INSTAGRAM_TOKEN_KEY=KEY, SNOWLAND_INSTAGRAM_API_VERSION='v23.0')


def response(data, status=200):
    return Mock(status_code=status, json=Mock(return_value=data))


@override_settings(**CONFIG)
class InstagramSyncTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.other=Client.objects.create(name='Other',internal_code='other')
        self.admin=User.objects.create_superuser('ig-hq',password='qa-only')
        self.api=APIClient();self.api.force_authenticate(self.admin)
        self.url='/api/admin/snowland/instagram-sync/'
        self.row=InstagramConnection.objects.create(client=self.tenant,expected_username='snowlandcz',username='snowlandcz',
            account_id='123',enabled=True,encrypted_token=Fernet(KEY.encode()).encrypt(b'qa-access-token').decode(),
            token_expires_at=timezone.now()+timedelta(days=60),token_refreshed_at=timezone.now())
        self.item={'id':'456','caption':'QA公開貼文','media_type':'IMAGE',
            'media_url':'https://scontent.cdninstagram.com/qa.jpg', 'permalink':'https://www.instagram.com/p/QA/',
            'timestamp':'2026-10-19T00:00:00+0000'}

    def test_authorization_requests_only_read_scope_and_does_not_expose_secrets(self):
        url=authorization_url('qa-state')
        values=parse_qs(urlsplit(url).query)
        self.assertEqual(values['scope'],['instagram_business_basic'])
        self.assertEqual(values['state'],['qa-state'])
        self.assertNotIn('qa-app-secret',url);self.assertNotIn(KEY,url)

    def test_connect_exchanges_token_and_verifies_expected_official_identity(self):
        with patch('Client.instagram_sync.requests.request',side_effect=[response({'access_token':'short'}),
            response({'access_token':'qa-new-token','expires_in':5184000}),response({'user_id':'321','username':'snowlandcz'})]):
            row=connect_account(self.tenant,'qa-code')
        self.assertNotEqual(row.encrypted_token,'qa-new-token')
        self.assertEqual(Fernet(KEY.encode()).decrypt(row.encrypted_token.encode()),b'qa-new-token')
        self.assertEqual(row.account_id,'321');self.assertTrue(row.enabled)

    def test_wrong_account_does_not_overwrite_existing_connection(self):
        original=self.row.encrypted_token
        with patch('Client.instagram_sync.requests.request',side_effect=[response({'access_token':'short'}),
            response({'access_token':'wrong-token','expires_in':5184000}),response({'user_id':'999','username':'someone_else'})]):
            with self.assertRaisesMessage(InstagramError,'不符'):
                connect_account(self.tenant,'qa-code')
        self.row.refresh_from_db();self.assertEqual(self.row.encrypted_token,original)

    def test_repeat_sync_updates_only_owned_posts_and_preserves_manual_hidden_and_other_tenant(self):
        manual=SiteContent.objects.create(client=self.tenant,content_type='social',location_key='news.social',title='Manual',source='instagram',external_id='123:456')
        foreign=SiteContent.objects.create(client=self.other,content_type='social',location_key='news.social',title='Other',source='instagram_api',external_id='123:456')
        with patch('Client.instagram_sync.requests.request',return_value=response({'data':[self.item]})) as http:
            self.assertEqual(run_sync(self.row.pk),1)
            imported=SiteContent.objects.get(client=self.tenant,source='instagram_api')
            imported.status='hidden';imported.save()
            self.assertEqual(run_sync(self.row.pk),1)
            self.assertTrue(all(call.kwargs['allow_redirects'] is False for call in http.call_args_list))
        imported.refresh_from_db();manual.refresh_from_db();foreign.refresh_from_db()
        self.assertEqual(imported.status,'hidden');self.assertEqual(manual.title,'Manual');self.assertEqual(foreign.title,'Other')
        self.assertEqual(SiteContent.objects.filter(client=self.tenant,source='instagram_api').count(),1)

    def test_video_uses_thumbnail_and_supports_signed_cdn_urls(self):
        item={**self.item,'media_type':'VIDEO','media_url':'https://scontent.cdninstagram.com/movie.mp4',
            'thumbnail_url':'https://scontent.cdninstagram.com/frame.jpg?sig='+'a'*700}
        with patch('Client.instagram_sync.requests.request',return_value=response({'data':[item]})):
            self.assertEqual(run_sync(self.row.pk),1)
        self.assertIn('frame.jpg',SiteContent.objects.get(source='instagram_api').image_url)

    def test_new_posts_precede_old_imports_without_deleting_or_republishing(self):
        old=SiteContent.objects.create(client=self.tenant,source='instagram_api',external_id='123:111',
            content_type='social',location_key='news.social',status='hidden',display_order=0)
        with patch('Client.instagram_sync.requests.request',return_value=response({'data':[self.item]})):
            run_sync(self.row.pk)
        old.refresh_from_db()
        self.assertEqual(old.display_order,1000);self.assertEqual(old.status,'hidden')
        self.assertEqual(SiteContent.objects.get(external_id='123:456').display_order,0)
        with patch('Client.instagram_sync.requests.request',return_value=response({'data':[]})):
            run_sync(self.row.pk)
        self.assertEqual(SiteContent.objects.filter(source='instagram_api').count(),2)

    def test_disconnect_or_newer_success_wins_while_provider_response_is_pending(self):
        def disconnected(*args, **kwargs):
            InstagramConnection.objects.filter(pk=self.row.pk).update(enabled=False,encrypted_token='')
            return response({'data':[self.item]})
        with patch('Client.instagram_sync.requests.request',side_effect=disconnected):
            self.assertEqual(run_sync(self.row.pk),0)
        self.assertFalse(SiteContent.objects.filter(source='instagram_api').exists())

    def test_failed_old_sync_does_not_replace_new_success_status(self):
        now=timezone.now()
        def newer_success(*args, **kwargs):
            InstagramConnection.objects.filter(pk=self.row.pk).update(last_synced_at=now,last_error='')
            return response({},status=503)
        with patch('Client.instagram_sync.requests.request',side_effect=newer_success):
            with self.assertRaises(InstagramError):run_sync(self.row.pk)
        self.row.refresh_from_db();self.assertEqual(self.row.last_error,'')
        self.assertEqual(self.row.last_synced_at,now)

    def test_invalid_or_hostile_response_rolls_back_entire_batch(self):
        for url in ('javascript:alert(1)','http://scontent.cdninstagram.com/a','https://cdninstagram.com.evil.test/a',
                    'https://scontent.cdninstagram.com:bad/a','https://[bad/a'):
            with self.subTest(url=url),patch('Client.instagram_sync.requests.request',return_value=response({'data':[self.item,{**self.item,'id':'789','media_url':url}]})):
                with self.assertRaises(InstagramError):run_sync(self.row.pk)
                self.assertFalse(SiteContent.objects.filter(source='instagram_api').exists())

    def test_expired_token_does_not_call_provider_or_hide_previous_posts(self):
        self.row.token_expires_at=timezone.now()-timedelta(seconds=1);self.row.save()
        with patch('Client.instagram_sync.requests.request') as http:
            result=self.api.post(self.url+'sync/',{},format='json')
        self.assertEqual(result.status_code,409);http.assert_not_called()
        self.row.refresh_from_db();self.assertIn('到期',self.row.last_error)
        self.assertNotIn('qa-access-token',str(result.data))

    def test_hourly_sync_does_not_call_provider_when_not_due_and_dry_run_never_calls(self):
        self.row.last_synced_at=timezone.now();self.row.save()
        with patch('Client.instagram_sync.requests.request') as http:
            self.assertEqual(run_sync(self.row.pk,due_only=True),0)
            call_command('sync_instagram',client='snowland',dry_run=True,stdout=StringIO())
        http.assert_not_called()

    def test_near_expiry_refreshes_and_keeps_new_token_server_side(self):
        self.row.token_expires_at=timezone.now()+timedelta(days=2)
        self.row.token_refreshed_at=timezone.now()-timedelta(days=2);self.row.save()
        with patch('Client.instagram_sync.requests.request',side_effect=[response({'access_token':'renewed','expires_in':5184000}),response({'data':[]})]):
            self.assertEqual(run_sync(self.row.pk),0)
        self.row.refresh_from_db()
        self.assertEqual(Fernet(KEY.encode()).decrypt(self.row.encrypted_token.encode()),b'renewed')
        public=self.api.get(self.url)
        self.assertNotIn('renewed',str(public.data));self.assertNotIn('encrypted_token',str(public.data))

    def test_no_configuration_is_explicit_and_does_not_create_connection_or_auth_state(self):
        self.row.delete()
        with override_settings(SNOWLAND_INSTAGRAM_TOKEN_KEY=''):
            result=self.api.post(self.url+'connect/',{'expected_username':'snowlandcz'},format='json')
        self.assertEqual(result.status_code,409);self.assertIn('TOKEN_KEY',result.data['msg'])
        self.assertFalse(InstagramConnection.objects.exists());self.assertNotIn('instagram_oauth',self.api.session)

    def test_connect_state_is_bound_to_user_tenant_and_callback_is_one_use(self):
        result=self.api.post(self.url+'connect/',{'expected_username':'snowlandcz'},format='json')
        self.assertEqual(result.status_code,200)
        session=self.api.session;state=session['instagram_oauth']['state']
        with patch('API.instagram_sync.connect_account',return_value=self.row) as connect:
            done=self.api.get(self.url+'callback/',{'state':state,'code':'qa-code'})
            self.assertEqual(done.status_code,302);self.assertIn('ig=connected',done.url)
            repeat=self.api.get(self.url+'callback/',{'state':state,'code':'qa-code'})
            self.assertIn('ig=invalid_state',repeat.url);self.assertEqual(connect.call_count,1)

    def test_wrong_or_timed_out_state_never_calls_provider(self):
        for state,age in [('wrong',0),('correct',601)]:
            session=self.api.session;session['instagram_oauth']={'state':'correct','client':self.tenant.pk,'user':self.admin.pk,'created_at':time.time()-age};session.save()
            with patch('API.instagram_sync.connect_account') as connect:
                result=self.api.get(self.url+'callback/',{'state':state,'code':'qa-code'})
            self.assertIn('ig=invalid_state',result.url);connect.assert_not_called()

    def test_non_hq_and_other_tenant_managers_cannot_manage_authorization(self):
        user=User.objects.create_user('ig-editor')
        profile=user.userprofile;profile.is_manager=True;profile.manager_client=self.tenant
        profile.role='web_editor';profile.save()
        self.api.force_authenticate(user)
        for endpoint in ('', 'connect/', 'sync/', 'disconnect/'):
            result=self.api.get(self.url) if not endpoint else self.api.post(self.url+endpoint,{'expected_username':'snowlandcz'},format='json')
            self.assertEqual(result.status_code,403)

    def test_disconnect_erases_local_access_but_keeps_imported_posts(self):
        post=SiteContent.objects.create(client=self.tenant,source='instagram_api',content_type='social',location_key='news.social')
        result=self.api.post(self.url+'disconnect/',{},format='json')
        self.assertEqual(result.status_code,200);self.row.refresh_from_db()
        self.assertFalse(self.row.enabled);self.assertEqual(self.row.encrypted_token,'')
        self.assertTrue(SiteContent.objects.filter(pk=post.pk).exists())

    def test_real_session_mutations_require_csrf(self):
        api=APIClient(enforce_csrf_checks=True);self.assertTrue(api.login(username='ig-hq',password='qa-only'))
        self.assertEqual(api.post(self.url+'disconnect/',{},format='json').status_code,403)
        self.assertEqual(api.get(self.url).status_code,200)
        token=api.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertEqual(api.post(self.url+'disconnect/',{},format='json',HTTP_X_CSRFTOKEN=token).status_code,200)
