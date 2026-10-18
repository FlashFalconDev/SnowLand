from copy import deepcopy
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.guide_links import rewrite_guide_links
from Client.models import Client, SiteContent


class GuideLinkRewriteTests(SimpleTestCase):
    index = ('/snowland',{'/coach':'/coach','/tomamu':'/course/tomamu','/old':'/guides/articles/5'},{'完整原標題':'/guides/articles/5'})

    def test_rewrite_only_known_links_preserving_images_fragments_and_external_destinations(self):
        html='<a href="https://land110602.com/old/?utm_source=test#section-1"><img src="https://land110602.com/cover.jpg">原文</a><a href="https://other.test/old/">外站</a><a href="https://land110602.com/archive/">歷史原站</a>'
        result=rewrite_guide_links(html,self.index)
        self.assertIn('href="/snowland/guides/articles/5#section-1"',result)
        self.assertIn('src="https://land110602.com/cover.jpg"',result)
        self.assertIn('href="https://other.test/old/"',result)
        self.assertIn('href="https://land110602.com/archive/"',result)
        self.assertEqual(rewrite_guide_links('<a href="https://land110602.com/alias/"><strong>完整原標題</strong></a>',self.index),'<a href="/snowland/guides/articles/5"><strong>完整原標題</strong></a>')

    def test_href_text_inside_title_or_body_is_not_an_attribute(self):
        html='<a title="href=\'https://land110602.com/tomamu/\'" href="https://land110602.com/coach/">教練</a>'
        result=rewrite_guide_links(html,self.index)
        self.assertIn('href="/snowland/coach"',result)
        self.assertNotIn('/snowland/course/tomamu',result)
        text='<a>文字 href="https://land110602.com/coach/"</a>'
        self.assertEqual(rewrite_guide_links(text,self.index),text)


class GuideCardProjectionTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.metadata={'category':'滑雪初心者','date':'2026.8.18','article_mode':'internal','blocks':[{'type':'paragraph','text':'原正文'}],
                       'article':{'title':'完整原文','html':'<p>全文</p><a href="https://land110602.com/coach/">教練</a>'}}
        self.row=SiteContent.objects.create(client=self.tenant,content_type='article',location_key='guides.articles',status='active',
            title='完整原文',link_url='https://land110602.com/old/',body='原文字備份',metadata=self.metadata)
        self.api=APIClient()
        self.url='/booking/snowland/api/site-content/?location_key=guides.articles'

    def test_cards_exclude_full_body_but_keep_category_mode_and_default_detail_compatible(self):
        cards=self.api.get(self.url+'&view=cards')
        self.assertEqual(cards.status_code,200)
        self.assertEqual(cards.data[0]['body'],'')
        self.assertNotIn('article',cards.data[0]['metadata'])
        self.assertNotIn('blocks',cards.data[0]['metadata'])
        self.assertEqual(cards.data[0]['metadata']['category'],'滑雪初心者')
        self.assertEqual(cards.data[0]['metadata']['article_mode'],'internal')
        full=self.api.get(self.url+f'&content_id={self.row.pk}')
        self.assertIn('href="/snowland/coach"',full.data[0]['metadata']['article']['html'])
        self.row.refresh_from_db();self.assertEqual(self.row.metadata,self.metadata)

    def test_card_view_preserves_legacy_body_based_mode_and_visibility(self):
        self.row.metadata={};self.row.save()
        self.assertEqual(self.api.get(self.url+'&view=cards').data[0]['metadata']['article_mode'],'internal')
        other=Client.objects.create(name='Other',internal_code='other')
        SiteContent.objects.create(client=other,content_type='article',location_key='guides.articles',title='不得洩漏',status='active')
        for status in ('draft','hidden'):
            self.row.status=status;self.row.save()
            self.assertEqual(self.api.get(self.url+'&view=cards').data,[])
        self.row.status='active';self.row.start_at=timezone.now()+timedelta(days=1);self.row.save()
        self.assertEqual(self.api.get(self.url+'&view=cards').data,[])
        self.assertEqual(self.api.get(self.url+'&view=bad').status_code,400)
        self.assertEqual(self.api.get('/booking/snowland/api/site-content/?location_key=offers.earlybird&view=cards').status_code,400)

    def test_links_to_hidden_own_articles_stay_local_without_disclosing_hidden_body(self):
        hidden=SiteContent.objects.create(client=self.tenant,content_type='article',location_key='guides.articles',status='hidden',
            title='已隱藏',link_url='https://land110602.com/hidden/',metadata={'article_mode':'internal','article':{'html':'秘密正文'}})
        self.row.metadata=deepcopy(self.metadata)
        self.row.metadata['article']['html']='<a href="https://land110602.com/hidden/">原有文章連結</a>'
        self.row.save()
        response=self.api.get(self.url+f'&content_id={self.row.pk}')
        self.assertIn(f'href="/snowland/guides/articles/{hidden.pk}"',response.data[0]['metadata']['article']['html'])
        self.assertNotIn('秘密正文',str(response.data))
        self.assertEqual(self.api.get(self.url+f'&content_id={hidden.pk}').data,[])

    def test_original_special_pages_and_related_links_use_same_read_time_mapping(self):
        original={'article':{'title':'原獨立頁','html':'<a href="https://land110602.com/coach/">教練</a>',
                             'relatedLinks':[{'title':'完整原文','url':self.row.link_url}]}}
        special=SiteContent.objects.create(client=self.tenant,content_type='article',location_key='guides.article-pages',status='active',metadata=original)
        result=self.api.get('/booking/snowland/api/site-content/?location_key=guides.article-pages').data[0]
        self.assertIn('href="/snowland/coach"',result['metadata']['article']['html'])
        self.assertEqual(result['metadata']['article']['relatedLinks'][0]['url'],f'/snowland/guides/articles/{self.row.pk}')
        special.refresh_from_db();self.assertEqual(special.metadata,original)

    def test_link_prefix_uses_current_tenant_not_snowland_and_never_foreign_article_ids(self):
        tenant=Client.objects.create(name='Other',internal_code='other')
        SiteContent.objects.create(client=tenant,content_type='article',location_key='guides.articles',status='active',metadata=self.metadata)
        response=self.api.get('/booking/other/api/site-content/?location_key=guides.articles')
        self.assertEqual(response.status_code,200)
        self.assertIn('href="/other/coach"',response.data[0]['metadata']['article']['html'])
        self.assertNotIn('/snowland/',str(response.data))
