from io import StringIO
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient
from Client.models import Client, SiteContent


class HomepagePresentationTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.api=APIClient()
        self.public='/booking/snowland/api/site-content/'

    def initialize(self,apply=False):
        call_command('initialize_homepage_presentation',client='snowland',apply=apply,stdout=StringIO())

    def staff(self):
        self.api.force_authenticate(User.objects.create_superuser('home-presentation-hq',password='qa-only'))

    def test_preview_original_source_and_idempotent_preserve(self):
        self.initialize();self.assertEqual(SiteContent.objects.count(),0)
        self.initialize(True);self.assertEqual(SiteContent.objects.count(),4)
        row=SiteContent.objects.get(location_key='homepage.hero')
        self.assertEqual(row.title,'北海道星野TOMAMU\n官方許可滑雪學校');self.assertEqual(row.metadata['youtube_id'],'m-4vgzqVNqI')
        row.title='自行修改';row.status='hidden';row.metadata={'media_type':'none','custom':'保留'};row.save()
        self.initialize(True);row.refresh_from_db();self.assertEqual(row.title,'自行修改');self.assertEqual(row.status,'hidden');self.assertEqual(row.metadata['custom'],'保留')

    def test_initializer_conflict_prevents_partial_write(self):
        SiteContent.objects.create(client=self.tenant,location_key='homepage.intro',content_type='review')
        with self.assertRaises(CommandError):self.initialize(True)
        self.assertFalse(SiteContent.objects.filter(location_key='homepage.hero').exists())

    def test_existing_page_type_is_preserved_and_remains_editable(self):
        row=SiteContent.objects.create(client=self.tenant,location_key='homepage.hero',content_type='page',title='舊首頁資料',status='active')
        self.initialize(True);row.refresh_from_db();self.assertEqual(row.content_type,'page');self.assertEqual(row.title,'舊首頁資料')
        self.staff();result=self.api.patch(f'/api/admin/snowland/site-content/{row.pk}/',{'title':'舊資料可正常更新'},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(self.api.get(self.public,{'location_key':'homepage.hero'}).data[0]['title'],'舊資料可正常更新')

    def test_cms_real_fields_update_then_public_reflect_and_hide(self):
        self.initialize(True);self.staff()
        row=SiteContent.objects.get(location_key='homepage.hero');url=f'/api/admin/snowland/site-content/{row.pk}/'
        metadata={**row.metadata,'media_type':'image','custom':'保留','button_text':'QA聯絡'}
        response=self.api.patch(url,{'title':'QA新標題\n第二行','image_url':'/vite.svg','link_url':'/contact','metadata':metadata},format='json')
        self.assertEqual(response.status_code,200,response.data)
        public=self.api.get(self.public,{'location_key':'homepage.hero','content_type':'setting'})
        self.assertEqual(public.data[0]['title'],'QA新標題\n第二行');self.assertEqual(public.data[0]['image_url'],'/vite.svg');self.assertEqual(public.data[0]['metadata']['custom'],'保留')
        self.assertEqual(self.api.patch(url,{'status':'hidden'},format='json').status_code,200)
        self.assertEqual(self.api.get(self.public,{'location_key':'homepage.hero'}).data,[])

    def test_invalid_urls_video_types_and_text_do_not_partially_write(self):
        self.initialize(True);self.staff();row=SiteContent.objects.get(location_key='homepage.hero');url=f'/api/admin/snowland/site-content/{row.pk}/'
        for data in [{'image_url':'javascript:alert(1)'},{'link_url':'//evil.test'},{'metadata':{'media_type':'youtube','youtube_id':'https://evil.test'}},{'metadata':{'media_type':'youtube','youtube_id':''}},{'metadata':{'media_type':'image'}},{'metadata':{'media_type':'iframe'}},{'title':' '},{'content_type':'page'},{'metadata':{'button_text':{'invalid':'object'}}},{'metadata':{'extra_paragraphs':'text'}}]:
            with self.subTest(data=data):self.assertEqual(self.api.patch(url,{'summary':'不可半寫',**data},format='json').status_code,400)
        row.refresh_from_db();self.assertNotEqual(row.summary,'不可半寫')

    def test_intro_text_blank_media_and_unknown_fields_preserved(self):
        self.initialize(True);self.staff();row=SiteContent.objects.get(location_key='homepage.intro');url=f'/api/admin/snowland/site-content/{row.pk}/'
        metadata={**row.metadata,'opening_text':'QA介紹','extra_paragraphs':['QA完整段落','<script>只當文字</script>'],'custom':'保留'}
        self.assertEqual(self.api.patch(url,{'metadata':metadata},format='json').status_code,200)
        public=self.api.get(self.public,{'location_key':'homepage.intro'}).data[0]
        self.assertEqual(public['metadata']['extra_paragraphs'][1],'<script>只當文字</script>')
        self.assertEqual(self.api.patch(url,{'metadata':{**metadata,'image_asset':'unknown'}},format='json').status_code,400)
        self.assertEqual(self.api.patch(url,{'metadata':{**metadata,'image_asset':''},'image_url':'','link_url':''},format='json').status_code,200)

    def test_tenant_isolation_anonymous_write_and_duplicate_setting(self):
        self.initialize(True);row=SiteContent.objects.get(location_key='homepage.hero');url=f'/api/admin/snowland/site-content/{row.pk}/'
        self.assertIn(self.api.patch(url,{'title':'匿名不能改'},format='json').status_code,(401,403))
        other=Client.objects.create(name='other',internal_code='other')
        SiteContent.objects.create(client=other,location_key='homepage.hero',content_type='setting',title='別家公司',status='active')
        self.assertEqual(len(self.api.get(self.public,{'location_key':'homepage.hero'}).data),1)
        self.staff();self.assertEqual(self.api.post('/api/admin/snowland/site-content/',{'location_key':'homepage.hero','content_type':'setting','title':'重複','status':'draft'},format='json').status_code,400)

    def test_youtube_urls_convert_to_safe_video_id(self):
        self.initialize(True);self.staff();row=SiteContent.objects.get(location_key='homepage.hero');url=f'/api/admin/snowland/site-content/{row.pk}/'
        for value in ['https://youtu.be/m-4vgzqVNqI?t=3','https://www.youtube.com/watch?v=m-4vgzqVNqI','https://youtube.com/shorts/m-4vgzqVNqI','https://www.youtube.com/embed/m-4vgzqVNqI']:
            response=self.api.patch(url,{'metadata':{**row.metadata,'youtube_id':value}},format='json')
            self.assertEqual(response.status_code,200,response.data);row.refresh_from_db();self.assertEqual(row.metadata['youtube_id'],'m-4vgzqVNqI')
        for value in ['https://youtube.com.evil.test/watch?v=m-4vgzqVNqI','https://www.youtube.com@evil.test/watch?v=m-4vgzqVNqI','https://youtu.be/m-4vgzqVNqI/extra','http://youtu.be/m-4vgzqVNqI','https://youtube.com/watch?v=m-4vgzqVNqI&v=abcdefghijk']:
            self.assertEqual(self.api.patch(url,{'metadata':{**row.metadata,'youtube_id':value}},format='json').status_code,400)
        response=self.api.patch(url,{'image_url':'/vite.svg','metadata':{**row.metadata,'media_type':'image','youtube_id':'未使用的舊輸入'}},format='json')
        self.assertEqual(response.status_code,200,response.data)

    def test_coach_heading_and_contact_banner_reflect_changes_hide_and_preserve(self):
        self.initialize(True);self.staff()
        for location,title in [('homepage.coaches','QA教練區'),('homepage.contact','QA諮詢區')]:
            row=SiteContent.objects.get(location_key=location);url=f'/api/admin/snowland/site-content/{row.pk}/'
            data={'title':title,'summary':'QA說明\n第二行','subtitle':'QA EN','link_url':'/booking','metadata':{'button_text':'QA預約','custom':'保留'}}
            response=self.api.patch(url,data,format='json');self.assertEqual(response.status_code,200,response.data)
            published=self.api.get(self.public,{'location_key':location}).data
            self.assertEqual(len(published),1);self.assertEqual(published[0]['title'],title)
            self.assertEqual(published[0]['metadata']['custom'],'保留')
            self.assertEqual(self.api.patch(url,{'status':'hidden'},format='json').status_code,200)
            self.assertEqual(self.api.get(self.public,{'location_key':location}).data,[])
            self.initialize(True);row.refresh_from_db();self.assertEqual(row.title,title);self.assertEqual(row.status,'hidden')

    def test_coach_contact_invalid_links_and_duplicate_settings_are_rejected_without_partial_write(self):
        self.initialize(True);self.staff()
        for location in ['homepage.coaches','homepage.contact']:
            row=SiteContent.objects.get(location_key=location);url=f'/api/admin/snowland/site-content/{row.pk}/'
            for patch in [{'link_url':'javascript:alert(1)'},{'link_url':'//evil.test'},{'image_url':'data:image/svg+xml,evil'},{'title':' '}]:
                response=self.api.patch(url,{'summary':'不可半寫',**patch},format='json')
                self.assertEqual(response.status_code,400,(location,patch,response.data))
            row.refresh_from_db();self.assertNotEqual(row.summary,'不可半寫')
            duplicate=self.api.post('/api/admin/snowland/site-content/',{'location_key':location,'content_type':'setting','title':'重複','status':'draft'},format='json')
            self.assertEqual(duplicate.status_code,400,duplicate.data)
