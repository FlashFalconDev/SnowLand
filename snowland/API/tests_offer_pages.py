from copy import deepcopy
import json
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, SiteContent


class OfferPageTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        defaults=json.loads((Path(__file__).parents[1]/'Client/fixtures/site_content_defaults.json').read_text(encoding='utf-8'))
        self.original=next(row for row in defaults if row['location_key']=='offers.earlybird')
        self.row=SiteContent.objects.create(client=self.tenant,**self.original)
        self.api=APIClient();self.api.force_authenticate(User.objects.create_superuser('offer-editor',password='qa-only'))
        self.url=f'/api/admin/snowland/site-content/{self.row.pk}/'

    def test_original_page_blocks_edit_publish_and_hide_without_changing_original_layout(self):
        metadata=deepcopy(self.row.metadata)
        metadata['blocks']=deepcopy(metadata['page']['blocks'])
        metadata['blocks'][5]['text']='QA本季活動說明'
        result=self.api.patch(self.url,{'metadata':metadata},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.row.refresh_from_db()
        self.assertEqual(self.row.metadata['page'],self.original['metadata']['page'])
        self.assertEqual(self.row.metadata['blocks'][4]['level'],1)
        self.assertEqual(self.row.metadata['blocks'][29]['level'],4)
        public=APIClient().get('/booking/snowland/api/site-content/?location_key=offers.earlybird')
        self.assertEqual(public.data[0]['metadata']['blocks'][5]['text'],'QA本季活動說明')
        self.assertEqual(self.api.patch(self.url,{'status':'hidden'},format='json').status_code,200)
        self.assertEqual(APIClient().get('/booking/snowland/api/site-content/?location_key=offers.earlybird').data,[])

    def test_invalid_images_or_blocks_are_rejected_without_partial_write(self):
        for blocks in [[{'type':'image','src':'javascript:alert(1)'}],
                       [{'type':'image','src':''}],
                       [{'type':'image','src':'/valid.jpg','alt':{}}],
                       [{'type':'heading','level':99,'text':'bad'}],
                       [{'type':'paragraph','text':{}}],
                       [{'type':'list','items':None}],None]:
            result=self.api.patch(self.url,{'title':'不得半寫','metadata':{'blocks':blocks}},format='json')
            self.assertEqual(result.status_code,400,result.data)
            self.row.refresh_from_db()
            self.assertEqual(self.row.title,self.original['title'])
            self.assertEqual(self.row.metadata,self.original['metadata'])

    def test_empty_draft_and_safe_paths_are_supported(self):
        self.assertEqual(self.api.patch(self.url,{'status':'draft','metadata':{'blocks':[{'type':'image','src':''}]}},format='json').status_code,200)
        self.assertEqual(self.api.patch(self.url,{'status':'active'},format='json').status_code,400)
        self.assertEqual(self.api.patch(self.url,{'status':'active','metadata':{'blocks':[{'type':'image','src':'/vite.svg','alt':'QA圖片'}]}},format='json').status_code,200)
