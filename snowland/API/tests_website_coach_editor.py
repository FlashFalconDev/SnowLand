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

    def test_photo_accepts_site_paths_and_http_urls(self):
        for photo in ['/snowland/vite.svg', 'https://example.com/coach.jpg', 'http://example.com/coach.jpg', '']:
            with self.subTest(photo=photo):
                result=self.api.patch(self.detail,{'img':photo},format='json')
                self.assertEqual(result.status_code,200,result.data)
                self.coach.refresh_from_db()
                self.assertEqual(self.coach.img,photo)

    def test_unsafe_photo_does_not_partially_update_profile(self):
        for photo in ['//example.com/coach.jpg', '/\\example.com/coach.jpg',
                      'javascript:alert(1)', 'data:image/svg+xml,test', 'https://', '/photo\n.jpg']:
            with self.subTest(photo=photo):
                result=self.api.patch(self.detail,{'img':photo,'website_card_bio':'不應殘留'},format='json')
                self.assertEqual(result.status_code,400,result.data)
                self.coach.refresh_from_db()
                self.assertEqual(self.coach.website_card_bio,'')

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


class WebsiteCoachPhotoUploadTests(TestCase):
    """S3 一律 mock；不得打真實 AWS。"""
    def setUp(self):
        from django.test import override_settings
        self.settings=override_settings(COACH_PHOTO_BUCKET='qa-bucket',COACH_PHOTO_REGION='ap-northeast-1',
                                        COACH_PHOTO_PREFIX='coach-photos',COACH_PHOTO_PUBLIC_BASE_URL='',COACH_PHOTO_MAX_BYTES=1024*1024)
        self.settings.enable();self.addCleanup(self.settings.disable)
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.other=Client.objects.create(name='Other',internal_code='other')
        self.user=User.objects.create_user('photo-editor',password='test-password')
        profile=self.user.userprofile;profile.is_manager=True;profile.manager_client=self.tenant
        profile.role='web_editor';profile.admin_permissions=['cms'];profile.save()
        self.coach=Coach.objects.create(client=self.tenant,name='真正教練',website_slug='real')
        self.foreign=Coach.objects.create(client=self.other,name='其他公司',website_slug='other')
        self.api=APIClient();self.api.force_authenticate(self.user)
        self.url=f'/api/admin/snowland/website-coach-editor/{self.coach.pk}/upload-photo/'

    def _image(self,fmt='PNG',name='a.png',content_type='image/png'):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        buf=io.BytesIO();Image.new('RGB',(4,4),'red').save(buf,fmt)
        return SimpleUploadedFile(name,buf.getvalue(),content_type=content_type)

    def test_upload_sends_validated_image_to_mocked_s3_and_returns_public_url(self):
        from unittest import mock
        client=mock.Mock()
        with mock.patch('API.coach_photo_storage._s3_client',return_value=client):
            result=self.api.post(self.url,{'photo':self._image()},format='multipart')
        self.assertEqual(result.status_code,200,result.data)
        args,kwargs=client.upload_fileobj.call_args
        self.assertEqual(args[1],'qa-bucket');self.assertEqual(kwargs['ExtraArgs']['ContentType'],'image/png')
        self.assertNotIn('ACL',kwargs['ExtraArgs'])
        key=args[2];self.assertRegex(key,rf'^coach-photos/{self.tenant.pk}/{self.coach.pk}/[0-9a-f]{{32}}\.png$')
        self.assertEqual(result.data['data']['url'],f'https://qa-bucket.s3.ap-northeast-1.amazonaws.com/{key}')
        self.assertLessEqual(len(result.data['data']['url']),200)
        self.coach.refresh_from_db();self.assertFalse(self.coach.img)  # 儲存時才由 PATCH 寫入

    def test_uploaded_url_can_be_saved_into_img_field(self):
        url='https://qa-bucket.s3.ap-northeast-1.amazonaws.com/coach-photos/1/1/x.png'
        result=self.api.patch(f'/api/admin/snowland/website-coach-editor/{self.coach.pk}/',{'img':url},format='json')
        self.assertEqual(result.status_code,200,result.data);self.coach.refresh_from_db();self.assertEqual(self.coach.img,url)

    def test_rejects_invalid_files_without_calling_s3(self):
        from unittest import mock
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad=[SimpleUploadedFile('a.png',b'not an image',content_type='image/png'),
             self._image('GIF','a.gif','image/gif'),
             SimpleUploadedFile('a.png',b'\x89PNG'+b'0'*(1024*1024+1),content_type='image/png')]
        with mock.patch('API.coach_photo_storage._s3_client') as factory:
            for upload in bad:
                self.assertEqual(self.api.post(self.url,{'photo':upload},format='multipart').status_code,400)
            self.assertEqual(self.api.post(self.url,{},format='multipart').status_code,400)
        factory.assert_not_called()

    def test_permission_and_tenant_scope(self):
        from unittest import mock
        with mock.patch('API.coach_photo_storage._s3_client') as factory:
            anon=APIClient()
            self.assertIn(anon.post(self.url,{'photo':self._image()},format='multipart').status_code,(401,403))
            plain=User.objects.create_user('plain',password='x');client=APIClient();client.force_authenticate(plain)
            self.assertIn(client.post(self.url,{'photo':self._image()},format='multipart').status_code,(401,403,404))
            foreign=f'/api/admin/snowland/website-coach-editor/{self.foreign.pk}/upload-photo/'
            self.assertEqual(self.api.post(foreign,{'photo':self._image()},format='multipart').status_code,404)
        factory.assert_not_called()

    def test_unconfigured_bucket_and_s3_failure_return_503(self):
        from unittest import mock
        from django.test import override_settings
        with override_settings(COACH_PHOTO_BUCKET=''),mock.patch('API.coach_photo_storage._s3_client') as factory:
            self.assertEqual(self.api.post(self.url,{'photo':self._image()},format='multipart').status_code,503)
        factory.assert_not_called()
        client=mock.Mock();client.upload_fileobj.side_effect=RuntimeError('boom')
        with mock.patch('API.coach_photo_storage._s3_client',return_value=client):
            result=self.api.post(self.url,{'photo':self._image()},format='multipart')
        self.assertEqual(result.status_code,503);self.assertNotIn('boom',str(result.data))

    def test_null_or_none_img_is_blank_and_create_is_blocked(self):
        Coach.objects.filter(pk=self.coach.pk).update(img=None)
        row=self.api.get('/api/admin/snowland/website-coach-editor/').data['data']['list'][0]
        self.assertEqual(row['img'],'')
        self.assertEqual(self.api.post('/api/admin/snowland/website-coach-editor/',{'name':'x'},format='json').status_code,405)
        config=self.api.get('/api/admin/snowland/website-coach-editor/photo-upload-config/').data['data']
        self.assertTrue(config['enabled'])
