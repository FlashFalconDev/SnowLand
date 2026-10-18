from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from Client.models import Client
from Coach.models import Coach


class WebsiteCoachEditorTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.other=Client.objects.create(name='Other',internal_code='other')
        self.user=User.objects.create_user('website-editor',password='test-password')
        profile=self.user.userprofile;profile.is_manager=True;profile.manager_client=self.tenant
        profile.role='web_editor';profile.admin_permissions=['cms'];profile.save()
        self.coach=Coach.objects.create(client=self.tenant,name='真正教練',website_slug='real',website_enabled=False)
        self.foreign=Coach.objects.create(client=self.other,name='其他公司',website_slug='other')
        self.api=APIClient();self.api.force_authenticate(self.user)
        self.url='/api/admin/snowland/website-coach-editor/'
        self.detail=f'{self.url}{self.coach.pk}/'

    def test_cms_reads_real_coaches_without_operational_fields(self):
        result=self.api.get(self.url);self.assertEqual(result.status_code,200,result.data)
        self.assertEqual([row['id'] for row in result.data['data']['list']],[self.coach.pk])
        self.assertEqual(set(result.data['data']['list'][0]),{'id','name','can_manage','img','website_enabled','website_slug','website_sort_order','website_card_bio','website_profile'})

    def test_edit_reload_and_public_api_share_same_coach(self):
        result=self.api.patch(self.detail,{'website_enabled':True,'website_card_bio':'QA新簡介','website_sort_order':7},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.coach.refresh_from_db();self.assertEqual(self.coach.website_card_bio,'QA新簡介')
        self.assertEqual(self.api.get(self.url).data['data']['list'][0]['website_sort_order'],7)
        public=self.api.get('/booking/snowland/api/website-coaches/').data['data']['list']
        self.assertEqual(public[0]['id'],self.coach.pk);self.assertEqual(public[0]['card_bio'],'QA新簡介')
        self.assertEqual(self.api.patch(self.detail,{'website_enabled':False},format='json').status_code,200)
        self.assertEqual(self.api.get('/booking/snowland/api/website-coaches/').data['data']['list'],[])

    def test_invalid_fields_or_slug_do_not_modify_coach(self):
        Coach.objects.create(client=self.tenant,name='第二位',website_slug='taken')
        for body in [{'website_enabled':True,'website_slug':''},{'website_slug':'TAKEN'},
                     {'website_card_bio':'x'*161},{'name':'擅改姓名'},{'auto_assignment_enabled':False},{'user_id':self.user.pk},
                     {'website_profile':[]},{'website_profile':{'text':'x'*250001}}]:
            result=self.api.patch(self.detail,body,format='json')
            self.assertEqual(result.status_code,400,result.data)
            self.coach.refresh_from_db();self.assertEqual(self.coach.name,'真正教練')
            self.assertEqual(self.coach.website_slug,'real');self.assertFalse(self.coach.website_enabled)
        self.assertEqual(self.api.patch(self.detail,[{}],format='json').status_code,400)

    def test_rich_profile_edit_is_same_source_as_public_detail(self):
        from Client.coach_profiles import read_coach_profile
        profile={'sections':[{'title':'教學理念','lines':['QA改後端介紹']}],'videos':[{'src':'https://www.youtube.com/embed/QA'}]}
        result=self.api.patch(self.detail,{'website_enabled':True,'website_profile':profile},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(read_coach_profile(self.coach),profile)
        self.assertEqual(self.api.get(self.url).data['data']['list'][0]['website_profile'],profile)
        result=self.api.get('/booking/snowland/api/website-coaches/',{'slug':'real','include_profile':'1'})
        self.assertEqual(result.data['data']['list'][0]['profile'],{**profile,'reviews':[]})

    def test_profile_storage_failure_rolls_back_basic_website_changes(self):
        from unittest.mock import patch
        from Client.models import SiteContent
        with patch.object(SiteContent,'save',side_effect=RuntimeError('QA profile write failure')):
            with self.assertRaisesRegex(RuntimeError,'QA profile write failure'):
                self.api.patch(self.detail,{'website_card_bio':'不應殘留','website_profile':{'sections':[]}},format='json')
        self.coach.refresh_from_db();self.assertEqual(self.coach.website_card_bio,'')
        self.assertFalse(SiteContent.objects.filter(client=self.tenant,location_key='coach.profiles').exists())

    def test_campus_editor_cannot_modify_shared_or_other_campus_coach(self):
        from Resorts.models import Campus
        a=Campus.objects.create(client=self.tenant,name='A',code='a')
        b=Campus.objects.create(client=self.tenant,name='B',code='b')
        self.coach.campuses.add(a,b)
        other=Coach.objects.create(client=self.tenant,name='B教練',website_slug='b')
        other.campuses.add(b)
        profile=self.user.userprofile;profile.role='campus_manager';profile.save();profile.campuses.add(a)
        listed=self.api.get(self.url)
        self.assertEqual(listed.status_code,200,listed.data)
        self.assertEqual([row['id'] for row in listed.data['data']['list']],[self.coach.pk])
        self.assertFalse(listed.data['data']['list'][0]['can_manage'])
        self.assertEqual(self.api.patch(self.detail,{'website_enabled':True},format='json').status_code,400)
        self.assertEqual(self.api.patch(f'{self.url}{other.pk}/',{'website_enabled':True},format='json').status_code,404)
        self.coach.campuses.remove(b)
        self.assertEqual(self.api.patch(self.detail,{'website_enabled':True},format='json').status_code,200)

    def test_cannot_read_or_modify_other_tenant(self):
        for response in [self.api.get(f'{self.url}{self.foreign.pk}/'),
            self.api.patch(f'{self.url}{self.foreign.pk}/',{'website_enabled':True},format='json')]:
            self.assertEqual(response.status_code,404,response.data)
        self.assertEqual(self.api.get(self.url.replace('/snowland/','/other/')).status_code,403)

    def test_cms_cannot_create_or_delete_operational_coaches(self):
        self.assertEqual(self.api.post(self.url,{'name':'假教練'},format='json').status_code,405)
        self.assertEqual(self.api.delete(self.detail).status_code,405)
        self.assertTrue(Coach.objects.filter(pk=self.coach.pk).exists())

    def test_reviews_only_and_ordinary_member_are_denied(self):
        profile=self.user.userprofile;profile.admin_permissions=['reviews'];profile.save()
        self.assertEqual(self.api.get(self.url).status_code,403)
        self.api.force_authenticate(User.objects.create_user('ordinary-member'))
        self.assertEqual(self.api.get(self.url).status_code,403)

    def test_real_session_requires_csrf(self):
        browser=APIClient(enforce_csrf_checks=True);browser.force_login(self.user)
        self.assertEqual(browser.patch(self.detail,{'website_enabled':True},format='json').status_code,403)
        self.assertEqual(browser.get(self.url).status_code,200)
        self.assertTrue('csrftoken' in browser.cookies)
        token=browser.cookies['csrftoken'].value
        self.assertEqual(browser.patch(self.detail,{'website_enabled':True},format='json',HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN='https://not-snowland.invalid').status_code,403)
        self.assertEqual(browser.patch(self.detail,{'website_enabled':True},format='json',HTTP_X_CSRFTOKEN=token).status_code,200)
