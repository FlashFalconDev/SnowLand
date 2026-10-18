from datetime import timedelta
from io import StringIO
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from Client.models import Client,SiteContent
from Coach.models import Coach


class ReviewPlacementTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.other=Client.objects.create(name='Other',internal_code='other')
        self.editor=User.objects.create_user('review-editor',password='test-password')
        profile=self.editor.userprofile;profile.is_manager=True;profile.manager_client=self.tenant
        profile.role='web_editor';profile.admin_permissions=['reviews'];profile.save()
        self.a=Coach.objects.create(client=self.tenant,name='A教練',website_slug='a',website_enabled=True)
        self.b=Coach.objects.create(client=self.tenant,name='B教練',website_slug='b',website_enabled=True)
        self.foreign=Coach.objects.create(client=self.other,name='外公司',website_slug='other',website_enabled=True)
        self.api=APIClient();self.api.force_authenticate(self.editor)
        self.url='/api/admin/snowland/site-content/'

    def row(self,metadata=None,**changes):
        return SiteContent.objects.create(client=self.tenant,content_type='review',location_key='homepage.reviews',
            title=changes.pop('title','QA評價'),summary='第一段',body='第二段',status=changes.pop('status','active'),metadata=metadata or {},**changes)

    def detail_reviews(self,coach):
        result=self.api.get('/booking/snowland/api/website-coaches/',{'slug':coach.website_slug,'include_profile':'1'})
        self.assertEqual(result.status_code,200,result.data)
        rows=result.data['data']['list']
        return rows[0].get('profile',{}).get('reviews',[]) if rows else []

    def test_home_uses_selection_but_keeps_existing_reviews_without_flag(self):
        legacy=self.row(title='舊評價')
        chosen=self.row({'show_on_homepage':True},title='已選評價')
        self.row({'show_on_homepage':False},title='教練專用')
        self.row({'show_on_homepage':True},status='hidden',title='隱藏')
        self.row({'show_on_homepage':True},title='未開始',start_at=timezone.now()+timedelta(days=1))
        result=self.api.get('/booking/snowland/api/site-content/',{'content_type':'review','location_key':'homepage.reviews'})
        self.assertEqual({row['id'] for row in result.data},{legacy.pk,chosen.pk})

    def test_one_review_can_archive_multiple_coaches_independent_of_home_selection(self):
        row=self.row({'coach_ids':[self.a.pk,self.b.pk],'show_on_homepage':False})
        for coach in [self.a,self.b]:
            reviews=self.detail_reviews(coach);self.assertEqual(len(reviews),1)
            self.assertEqual(reviews[0]['paragraphs'],['第一段','第二段'])
        result=self.api.patch(f'{self.url}{row.pk}/',{'summary':'QA更新','metadata':{'coach_ids':[self.a.pk],'show_on_homepage':True}},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(self.detail_reviews(self.a)[0]['paragraphs'][0],'QA更新')
        self.assertEqual(self.detail_reviews(self.b),[])

    def test_home_selection_works_from_custom_review_location_without_leaking_other_content(self):
        chosen=self.row({'show_on_homepage':True},title='自訂位置已選')
        chosen.location_key='custom.student-feedback';chosen.save()
        unchosen=self.row(title='自訂位置未選')
        unchosen.location_key=chosen.location_key;unchosen.save()
        foreign=self.row({'show_on_homepage':True},title='其他公司')
        foreign.client=self.other;foreign.save()
        article=self.row({'show_on_homepage':True},title='不是評價')
        article.content_type='article';article.save()
        result=self.api.get('/booking/snowland/api/site-content/',{'content_type':'review','location_key':'homepage.reviews'})
        self.assertEqual(result.status_code,200)
        self.assertEqual([row['id'] for row in result.data],[chosen.pk])

    def test_invalid_or_other_tenant_coach_ids_never_create_content(self):
        for ids in [[self.foreign.pk],[999999],['1'],[True],{},[self.a.pk,self.a.pk]]:
            before=SiteContent.objects.count()
            result=self.api.post(self.url,{'content_type':'review','location_key':'homepage.reviews','metadata':{'coach_ids':ids}},format='json')
            self.assertEqual(result.status_code,400,result.data)
            self.assertEqual(SiteContent.objects.count(),before)
        for value in ['false',0,None]:
            result=self.api.post(self.url,{'content_type':'review','location_key':'homepage.reviews','metadata':{'show_on_homepage':value}},format='json')
            self.assertEqual(result.status_code,400,result.data)

    def test_review_role_gets_only_own_company_coach_names_for_assignment(self):
        result=self.api.get(self.url+'review-coaches/')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual({row['id'] for row in result.data['data']['list']},{self.a.pk,self.b.pk})
        self.assertTrue(all(set(row)=={'id','name','website_enabled'} for row in result.data['data']['list']))

    def test_hiding_review_or_coach_removes_it_from_public_detail(self):
        row=self.row({'coach_ids':[self.a.pk]})
        self.assertEqual(len(self.detail_reviews(self.a)),1)
        self.api.patch(f'{self.url}{row.pk}/',{'status':'hidden'},format='json')
        self.assertEqual(self.detail_reviews(self.a),[])
        row.status='active';row.save()
        self.a.website_enabled=False;self.a.save()
        self.assertEqual(self.detail_reviews(self.a),[])

    def test_legacy_import_is_archivable_without_republishing_deleted_reviews(self):
        self.a.website_slug='cash';self.a.save()
        call_command('import_coach_profile_defaults',client='snowland',stdout=StringIO())
        rows=SiteContent.objects.filter(client=self.tenant,content_type='review',source='legacy-coach-review')
        self.assertEqual(rows.count(),29)
        self.assertTrue(all(row.metadata['show_on_homepage'] is False for row in rows))
        self.assertEqual(len(self.detail_reviews(self.a)),29)
        rows.first().delete()
        call_command('import_coach_profile_defaults',client='snowland',stdout=StringIO())
        self.assertEqual(rows.all().count(),28);self.assertEqual(len(self.detail_reviews(self.a)),28)
