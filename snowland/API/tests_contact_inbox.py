from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from Client.models import Client, ContactInboxSettings, ContactMessage, SiteContent
from Client.contact_inbox import send_contact_notification
from API.contact_inbox import ContactPublicThrottle
from Resorts.models import Campus


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='qa@example.test')
class ContactInboxTests(TestCase):
    def setUp(self):
        cache.clear()
        self.rate=patch.object(ContactPublicThrottle,'rate','1000/min');self.rate.start();self.addCleanup(self.rate.stop)
        self.client_a=Client.objects.create(internal_code='snowland',name='SnowLand')
        self.client_b=Client.objects.create(internal_code='other',name='Other')
        self.config=ContactInboxSettings.objects.create(client=self.client_a,enabled=True)
        self.public=APIClient();self.api=APIClient()
        self.admin=User.objects.create_superuser('contact-hq',password='qa-only');self.api.force_authenticate(self.admin)
        self.url='/booking/snowland/api/contact/'
        self.inbox='/api/admin/snowland/contact-inbox/'
        self.settings=self.inbox+'settings/'
        self.payload={'submission_id':str(uuid4()),'name':'QA訪客','email':'visitor@example.test','phone':'+886 900000000','subject':'QA課程詢問','message':'這是本機測試留言。\n第二段。'}

    def post(self,data=None):
        return self.public.post(self.url,self.payload if data is None else data,format='json')

    def user(self,role,permissions=None,tenant=None):
        user=User.objects.create_user('contact-'+role+'-'+str(User.objects.count()),password='qa-only')
        p=user.userprofile;p.is_manager=True;p.manager_client=tenant or self.client_a;p.role=role;p.admin_permissions=permissions;p.save()
        p.campuses.add(Campus.objects.create(client=p.manager_client,name=role,code=str(user.pk)))
        return user

    def test_public_settings_only_enabled_and_missing_settings_closed(self):
        self.config.notify_emails=['private@example.test'];self.config.save()
        self.assertEqual(self.public.get(self.url).data,{'enabled':True})
        self.assertEqual(self.public.get('/booking/other/api/contact/').data,{'enabled':False})
        self.assertEqual(self.public.get('/booking/missing/api/contact/').status_code,404)
        self.assertEqual(self.public.post('/booking/missing/api/contact/',self.payload,format='json').status_code,404)
        self.assertEqual(self.public.get(self.inbox).status_code,403)

    def test_disabled_does_not_store(self):
        self.config.enabled=False;self.config.save()
        self.assertEqual(self.post().status_code,503);self.assertEqual(ContactMessage.objects.count(),0)

    def test_validation_rejects_missing_invalid_or_oversized_without_partial_rows(self):
        for change in [{'name':''},{'email':'bad'},{'message':' '},{'subject':'x'*201},{'message':'x'*10001},{'name':'bad\x00name'},{'submission_id':'bad'},{'phone':'x'*51}]:
            with self.subTest(change=change):self.assertEqual(self.post({**self.payload,**change}).status_code,400)
        self.assertEqual(self.post([]).status_code,400);self.assertEqual(ContactMessage.objects.count(),0)

    def test_submission_idempotency_preserves_original_and_returns_no_personal_data(self):
        first=self.post();second=self.post()
        self.assertEqual((first.status_code,second.status_code),(201,200));self.assertEqual(ContactMessage.objects.count(),1)
        self.assertEqual(set(first.data),{'ok','reference','message'})
        self.assertEqual(self.post({**self.payload,'message':'不同原文'}).status_code,409)
        row=ContactMessage.objects.get();self.assertEqual(row.message,self.payload['message']);self.assertEqual(row.notification_status,'off')

    def test_same_uuid_in_another_tenant_is_separate(self):
        self.post();ContactInboxSettings.objects.create(client=self.client_b,enabled=True)
        result=self.public.post('/booking/other/api/contact/',self.payload,format='json')
        self.assertEqual(result.status_code,201);self.assertEqual(ContactMessage.objects.count(),2)
        self.assertEqual(self.api.get(self.inbox).data['data']['total'],1)

    def test_notify_sends_once_without_visitor_content_and_does_not_publish_cms(self):
        self.config.notify_enabled=True;self.config.notify_emails=['operator@example.test'];self.config.save()
        with self.captureOnCommitCallbacks(execute=True):self.assertEqual(self.post().status_code,201)
        self.assertEqual(len(mail.outbox),1);self.assertEqual(mail.outbox[0].to,['operator@example.test'])
        self.assertNotIn('visitor@example.test',mail.outbox[0].body);self.assertNotIn(self.payload['message'],mail.outbox[0].body)
        self.assertEqual(ContactMessage.objects.get().notification_status,'sent')
        send_contact_notification(ContactMessage.objects.get().pk)
        self.post();self.assertEqual(len(mail.outbox),1);self.assertEqual(SiteContent.objects.count(),0)

    def test_email_failure_keeps_message_and_can_manually_retry(self):
        self.config.notify_enabled=True;self.config.notify_emails=['operator@example.test'];self.config.save()
        with patch('Client.contact_inbox.EmailMessage.send',side_effect=RuntimeError('QA SMTP unavailable')):
            with self.captureOnCommitCallbacks(execute=True):result=self.post()
        self.assertEqual(result.status_code,201);row=ContactMessage.objects.get();self.assertEqual(row.notification_status,'failed')
        with self.captureOnCommitCallbacks(execute=True):
            retry=self.api.post(f'{self.inbox}{row.pk}/retry-notification/',{},format='json')
        self.assertEqual(retry.status_code,200);row.refresh_from_db();self.assertEqual(row.notification_status,'sent')
        self.assertEqual(self.api.post(f'{self.inbox}{row.pk}/retry-notification/',{},format='json').status_code,409)
        self.assertEqual(len(mail.outbox),1)

    def test_notification_switch_off_before_delivery_skips_email(self):
        row=ContactMessage.objects.create(client=self.client_a,**self.payload,notification_status='pending')
        send_contact_notification(row.pk);row.refresh_from_db();self.assertEqual(row.notification_status,'off')
        self.assertEqual(len(mail.outbox),0)

    def test_processing_notes_and_original_text_cannot_be_rewritten(self):
        self.post();row=ContactMessage.objects.get();url=f'{self.inbox}{row.pk}/'
        result=self.api.patch(url,{'status':'processing','admin_note':'行政已聯繫'},format='json')
        self.assertEqual(result.status_code,200,result.data);row.refresh_from_db()
        self.assertEqual(row.status,'processing');self.assertEqual(row.updated_by,self.admin)
        self.assertEqual(self.api.patch(url,{'status':'resolved'},format='json').status_code,200)
        self.assertEqual(self.api.patch(url,{'status':'invalid'},format='json').status_code,400)
        self.assertEqual(self.api.patch(url,{'message':'不可改原文','status':'new'},format='json').status_code,400)
        row.refresh_from_db();self.assertEqual(row.message,self.payload['message']);self.assertEqual(row.status,'resolved')
        self.assertEqual(self.api.delete(url).status_code,405)

    def test_list_filter_search_and_page_validation(self):
        self.post()
        self.assertEqual(self.api.get(self.inbox,{'search':'QA課程','status':'new'}).data['data']['total'],1)
        self.assertEqual(self.api.get(self.inbox,{'status':'resolved'}).data['data']['total'],0)
        self.assertEqual(self.api.get(self.inbox,{'page':2}).data['data']['list'],[])
        for params in [{'status':'bad'},{'page':'bad'}]:self.assertEqual(self.api.get(self.inbox,params).status_code,400)

    def test_cross_tenant_read_write_not_found_and_foreign_staff_forbidden(self):
        self.post();row=ContactMessage.objects.get()
        self.assertEqual(self.api.get(f'/api/admin/other/contact-inbox/{row.pk}/').status_code,404)
        self.assertEqual(self.api.patch(f'/api/admin/other/contact-inbox/{row.pk}/',{'status':'resolved'},format='json').status_code,404)
        self.api.force_authenticate(self.user('assistant',tenant=self.client_b))
        self.assertEqual(self.api.get(self.inbox).status_code,403)

    def test_roles_and_hq_only_settings(self):
        self.post()
        for role,permissions in [('web_editor',None),('coach',['contact_inbox']),('campus_manager',['contact_inbox']),('campus_principal',['contact_inbox'])]:
            self.api.force_authenticate(self.user(role,permissions));self.assertEqual(self.api.get(self.inbox).status_code,403,role)
        self.api.force_authenticate(self.user('assistant'));self.assertEqual(self.api.get(self.inbox).status_code,200)
        self.assertEqual(self.api.patch(self.settings,{'enabled':False},format='json').status_code,403)
        self.api.force_authenticate(self.user('assistant',[]));self.assertEqual(self.api.get(self.inbox).status_code,403)

    def test_settings_validate_and_preserve_existing_when_invalid(self):
        for data in [{'notify_enabled':True},{'notify_emails':['bad']},{'notify_emails':['a@example.test']*11}]:
            self.assertEqual(self.api.patch(self.settings,data,format='json').status_code,400)
        result=self.api.patch(self.settings,{'notify_enabled':True,'notify_emails':['a@example.test','a@example.test']},format='json')
        self.assertEqual(result.status_code,200,result.data);self.assertEqual(result.data['data']['notify_emails'],['a@example.test'])
        self.assertNotIn('notify_emails',self.public.get(self.url).data)
        self.assertEqual(self.api.patch(self.settings,{'notify_emails':[]},format='json').status_code,400)
        self.config.refresh_from_db();self.assertTrue(self.config.enabled);self.assertEqual(self.config.notify_emails,['a@example.test'])

    def test_rate_limit_ignores_spoofed_forwarded_ip_and_does_not_store_sixth(self):
        with patch.object(ContactPublicThrottle,'rate','2/min'):
            self.assertEqual(self.post().status_code,201)
            self.assertEqual(self.public.post(self.url,{**self.payload,'submission_id':str(uuid4())},format='json',HTTP_X_FORWARDED_FOR='1.2.3.4').status_code,201)
            self.assertEqual(self.public.post(self.url,{**self.payload,'submission_id':str(uuid4())},format='json',HTTP_X_FORWARDED_FOR='8.8.8.8').status_code,429)
        self.assertEqual(ContactMessage.objects.count(),2)

    def test_pagination_twenty_rows_and_no_private_cms_exposure(self):
        ContactMessage.objects.bulk_create([ContactMessage(client=self.client_a,**{**self.payload,'submission_id':uuid4(),'subject':f'QA批次{i}'}) for i in range(21)])
        first=self.api.get(self.inbox).data['data'];second=self.api.get(self.inbox,{'page':2}).data['data']
        self.assertEqual(first['total'],21);self.assertEqual(len(first['list']),20);self.assertEqual(len(second['list']),1)
        self.assertFalse({r['id'] for r in first['list']} & {r['id'] for r in second['list']})
        public=self.public.get('/booking/snowland/api/site-content/',{'location_key':'contact-inbox'})
        self.assertEqual(public.status_code,200);self.assertEqual(public.data,[])

    @override_settings(SNOWLAND_CONTACT_TRUSTED_PROXY_IPS=['127.0.0.1'])
    def test_trusted_proxy_uses_rightmost_untrusted_visitor_not_spoofed_prefix(self):
        with patch.object(ContactPublicThrottle,'rate','1/min'):
            first=self.public.post(self.url,self.payload,format='json',HTTP_X_FORWARDED_FOR='1.1.1.1, 198.51.100.7')
            self.assertEqual(first.status_code,201)
            repeat=self.public.post(self.url,{**self.payload,'submission_id':str(uuid4())},format='json',HTTP_X_FORWARDED_FOR='8.8.8.8, 198.51.100.7')
            self.assertEqual(repeat.status_code,429)
            other=self.public.post(self.url,{**self.payload,'submission_id':str(uuid4())},format='json',HTTP_X_FORWARDED_FOR='198.51.100.8')
            self.assertEqual(other.status_code,201)
