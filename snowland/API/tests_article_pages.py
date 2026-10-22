from copy import deepcopy
import json
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, SiteContent


class ArticlePageTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        defaults = json.loads((Path(__file__).parents[1]/'Client/fixtures/site_content_defaults.json').read_text(encoding='utf-8'))
        original = next(row for row in defaults if row['location_key']=='guides.article-pages' and row['external_id']=='packing-checklist')
        self.row = SiteContent.objects.create(client=self.tenant, **original)
        self.original = deepcopy(self.row.metadata)
        self.api = APIClient()
        self.api.force_authenticate(User.objects.create_superuser('article-hq', password='qa-only'))
        self.url = f'/api/admin/snowland/site-content/{self.row.pk}/'

    def test_original_html_can_be_edited_without_changing_storage_or_other_metadata(self):
        metadata = deepcopy(self.original)
        metadata['article']['lead'] = '後台修改的開頭說明'
        response = self.api.patch(self.url, {'metadata':metadata}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.row.refresh_from_db()
        self.assertEqual(self.row.location_key, 'guides.article-pages')
        self.assertEqual(self.row.external_id, 'packing-checklist')
        self.assertEqual(self.row.metadata['article']['html'], self.original['article']['html'])
        public = APIClient().get('/booking/snowland/api/site-content/?location_key=guides.article-pages')
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.data[0]['metadata']['article']['lead'], '後台修改的開頭說明')
        self.assertEqual(SiteContent.objects.count(), 1)

    def test_invalid_html_images_or_structure_are_rejected_without_partial_write(self):
        variants = [None, [], {'title':{}},
                    {**self.original['article'],'heroImage':'javascript:alert(1)'},
                    {**self.original['article'],'html':'<script>alert(1)</script>'},
                    {**self.original['article'],'html':'<img src="/qa.svg" onerror="alert(1)">'},
                    {**self.original['article'],'html':'<img src="javascript:alert(1)">'},
                    {**self.original['article'],'html':'<img src="/qa.svg" srcset="javascript:alert(1) 2x">'},
                    {**self.original['article'],'html':'<a href="java&#x73;cript:alert(1)">bad</a>'},
                    {**self.original['article'],'html':'<img src="">'},
                    {**self.original['article'],'html':'<img src>'},
                    {**self.original['article'],'html':'<div style="background:url(javascript:alert(1))">x</div>'},
                    {**self.original['article'],'relatedLinks':[{'title':'bad','url':'javascript:alert(1)'}]}]
        title = self.row.title
        for article in variants:
            response = self.api.patch(self.url, {'title':'不得半寫','metadata':{'article':article}}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.row.refresh_from_db()
            self.assertEqual(self.row.title,title)
            self.assertEqual(self.row.metadata,self.original)

    def test_draft_can_be_incomplete_but_publishing_requires_content(self):
        self.assertEqual(self.api.patch(self.url, {'status':'draft','metadata':{'article':{}}}, format='json').status_code,200)
        self.assertEqual(self.api.patch(self.url, {'status':'active'}, format='json').status_code,400)

    def test_foreign_tenant_and_review_only_staff_cannot_modify_article(self):
        other = Client.objects.create(name='Other',internal_code='other')
        self.assertEqual(self.api.patch(self.url.replace('/snowland/','/other/'), {'title':'bad'}, format='json').status_code,404)
        user = User.objects.create_user('review-only')
        profile=user.userprofile;profile.is_manager=True;profile.manager_client=self.tenant
        profile.admin_permissions=['reviews'];profile.save()
        self.api.force_authenticate(user)
        self.assertEqual(self.api.patch(self.url, {'title':'bad'}, format='json').status_code,403)
