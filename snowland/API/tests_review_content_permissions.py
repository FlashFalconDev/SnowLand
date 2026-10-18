from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, SiteContent
from Resorts.models import Campus


class ReviewContentPermissionTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.other=Client.objects.create(name='Other',internal_code='other')
        self.user=User.objects.create_user('review-editor',password='test-password')
        profile=self.user.userprofile
        profile.is_manager=True;profile.manager_client=self.tenant
        profile.role='photographer';profile.admin_permissions=['reviews'];profile.save()
        campus=Campus.objects.create(client=self.tenant,name='A校區',code='a')
        profile.campuses.add(campus)
        self.api=APIClient();self.api.force_authenticate(self.user)
        self.url='/api/admin/snowland/site-content/'
        self.review=self.content('review','homepage.reviews','QA評價')
        self.media=self.content('media','photography.gallery','QA作品')
        self.page=self.content('page','homepage.hero','QA首頁')
        self.setting=self.content('setting','cms.structure','QA結構')
        self.foreign=SiteContent.objects.create(client=self.other,content_type='review',location_key='homepage.reviews',title='其他公司')

    def content(self,kind,location,title):
        return SiteContent.objects.create(client=self.tenant,content_type=kind,location_key=location,title=title,status='draft')

    def test_reviews_permission_can_list_only_review_and_media_content(self):
        result=self.api.get(self.url)
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual({row['id'] for row in result.data['data']['list']},{self.review.pk,self.media.pk})

    def test_reviews_editor_can_create_edit_and_hide_review_or_gallery(self):
        for kind,location in [('review','homepage.reviews'),('media','photography.gallery')]:
            created=self.api.post(self.url,{'content_type':kind,'location_key':location,'title':'QA新內容'},format='json')
            self.assertEqual(created.status_code,201,created.data)
        result=self.api.patch(f'{self.url}{self.review.pk}/',{'title':'QA已更新','status':'hidden'},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.review.refresh_from_db();self.assertEqual(self.review.status,'hidden')

    def test_reviews_editor_cannot_read_or_edit_pages_settings_or_other_tenant(self):
        for row in [self.page,self.setting,self.foreign]:
            for response in [self.api.get(f'{self.url}{row.pk}/'),self.api.patch(f'{self.url}{row.pk}/',{'title':'錯誤修改'},format='json')]:
                self.assertEqual(response.status_code,404,response.data)
            row.refresh_from_db();self.assertNotEqual(row.title,'錯誤修改')

    def test_reviews_editor_cannot_forge_type_or_protected_location(self):
        for body in [
            {'content_type':'setting','location_key':'cms.structure'},
            {'content_type':'review','location_key':'cms.structure'},
            {'content_type':'media','location_key':'course.pricing'},
            {'content_type':'review','location_key':'homepage.hero'},
        ]:
            before=SiteContent.objects.count()
            result=self.api.post(self.url,body,format='json')
            self.assertEqual(result.status_code,400,result.data)
            self.assertEqual(SiteContent.objects.count(),before)
            result=self.api.patch(f'{self.url}{self.review.pk}/',body,format='json')
            self.assertEqual(result.status_code,400,result.data)
        self.review.refresh_from_db();self.assertEqual(self.review.location_key,'homepage.reviews')

    def test_cms_editor_keeps_full_existing_content_access(self):
        profile=self.user.userprofile;profile.admin_permissions=['cms'];profile.save()
        result=self.api.get(self.url)
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual({row['id'] for row in result.data['data']['list']},{self.review.pk,self.media.pk,self.page.pk,self.setting.pk})
        self.assertEqual(self.api.patch(f'{self.url}{self.page.pk}/',{'title':'QA首頁更新'},format='json').status_code,200)

    def test_unrelated_role_or_other_tenant_has_no_access(self):
        self.assertEqual(self.api.get(self.url.replace('/snowland/','/other/')).status_code,403)
        profile=self.user.userprofile;profile.admin_permissions=['analytics'];profile.save()
        self.assertEqual(self.api.get(self.url).status_code,403)

    def test_cms_defined_review_location_is_supported_without_granting_structure_edit(self):
        self.setting.metadata={'groups':[{'id':'custom','label':'自訂頁','locations':[
            {'key':'custom.student-reviews','label':'自訂評價','type':'review'},
            {'key':'custom.private-page','label':'其他內容','type':'page'},
        ]}]}
        self.setting.save()
        created=self.api.post(self.url,{'content_type':'review','location_key':'custom.student-reviews','title':'QA自訂評價'},format='json')
        self.assertEqual(created.status_code,201,created.data)
        rejected=self.api.post(self.url,{'content_type':'review','location_key':'custom.private-page'},format='json')
        self.assertEqual(rejected.status_code,400,rejected.data)
        self.assertEqual(self.api.patch(f'{self.url}{self.setting.pk}/',{'metadata':{}},format='json').status_code,404)
        options=self.api.get(f'{self.url}review-locations/')
        self.assertEqual(options.status_code,200,options.data)
        locations=[entry for group in options.data['data']['groups'] for entry in group['locations']]
        self.assertIn('custom.student-reviews',[entry['key'] for entry in locations])
        self.assertNotIn('custom.private-page',[entry['key'] for entry in locations])
        self.assertTrue(all(entry['type'] in ['review','media'] for entry in locations))

    def test_session_mutations_need_csrf_and_read_seeds_token(self):
        browser=APIClient(enforce_csrf_checks=True);browser.force_login(self.user)
        body={'content_type':'review','location_key':'homepage.reviews','title':'QA防偽評價'}
        self.assertEqual(browser.post(self.url,body,format='json').status_code,403)
        response=browser.get(self.url);self.assertEqual(response.status_code,200,response.data)
        self.assertTrue('csrftoken' in browser.cookies)
        token=browser.cookies['csrftoken'].value
        self.assertEqual(browser.post(self.url,body,format='json',HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN='https://not-snowland.invalid').status_code,403)
        self.assertEqual(browser.post(self.url,body,format='json',HTTP_X_CSRFTOKEN=token).status_code,201)
