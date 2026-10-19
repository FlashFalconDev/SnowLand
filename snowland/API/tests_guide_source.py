from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase

from Client.article_pages import validate_article_metadata
from Client.guide_source import convert_reference_article
from Client.models import Client, SiteContent


class GuideSourceConversionTests(SimpleTestCase):
    def article(self, html):
        return {'title':'原文章', 'heroImage':'https://example.test/cover.jpg', 'html':html}

    def test_full_text_tables_images_links_and_youtube_are_preserved(self):
        html = '<section><h2>原標題</h2><p>完整<strong>正文</strong></p><table><tr><td>費用</td></tr></table><img src="/qa.jpg" alt="原圖"><iframe src="https://www.youtube.com/embed/ouVZgVr3HJ4?feature=oembed" allow="autoplay"></iframe></section>'
        result = convert_reference_article(self.article(html))
        for value in ['原標題','完整','正文','<table>','費用','src="/qa.jpg"','alt="原圖"','https://www.youtube.com/embed/ouVZgVr3HJ4']:
            self.assertIn(value,result['html'])
        self.assertNotIn('autoplay',result['html'])
        self.assertEqual(validate_article_metadata({'article':result},True)['article'],result)

    def test_old_global_css_and_microdata_do_not_execute_or_leak(self):
        result = convert_reference_article(self.article('<style>body{display:none}</style><article itemscope itemtype="old"><time datetime="old">日期</time><p onclick="bad()" data-created_by="old">原文</p></article>'))
        self.assertEqual(result['html'],'<div><span>日期</span><p>原文</p></div>')

    def test_executable_unknown_tags_and_untrusted_video_origins_fail_closed(self):
        for html in ['<script>bad()</script>', '<iframe src="https://evil.test/embed/ouVZgVr3HJ4"></iframe>', '<iframe src="https://www.youtube.com.evil.test/embed/ouVZgVr3HJ4"></iframe>', '<iframe src="https://www.youtube.com/embed/../bad"></iframe>', '<img src="javascript:bad()">']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                convert_reference_article(self.article(html))

    def test_editor_cannot_add_arbitrary_iframe_attributes_or_sources(self):
        for html in ['<iframe src="https://evil.test/embed/ouVZgVr3HJ4"></iframe>', '<iframe src="https://www.youtube.com/embed/ouVZgVr3HJ4" srcdoc="bad"></iframe>', '<iframe src="https://www.youtube.com/embed/ouVZgVr3HJ4" onload="bad()"></iframe>', '<iframe src="https://evil.test/embed/ouVZgVr3HJ4" src="https://www.youtube.com/embed/ouVZgVr3HJ4"></iframe>', '<iframe src="https://www.youtube.com/embed/'+'中'*11+'"></iframe>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                validate_article_metadata({'article':self.article(html)},True)


class GuideSourceImportTests(TestCase):
    def setUp(self):
        self.client_row = Client.objects.create(name='SnowLand',internal_code='snowland')
        defaults = json.loads((Path(__file__).parents[1]/'Client/fixtures/site_content_defaults.json').read_text(encoding='utf-8'))
        self.originals = [row for row in defaults if row['location_key']=='guides.articles']
        SiteContent.objects.bulk_create([SiteContent(client=self.client_row,**row) for row in self.originals])

    def run_import(self, **options):
        output = StringIO()
        call_command('initialize_guide_articles',client='snowland',stdout=output,**options)
        return output.getvalue()

    def test_preview_then_apply_preserves_all_original_cards_and_is_idempotent(self):
        before = list(SiteContent.objects.order_by('id').values())
        self.assertIn('僅預覽，未寫入',self.run_import())
        self.assertEqual(list(SiteContent.objects.order_by('id').values()),before)
        self.assertIn('新增1、補全文71',self.run_import(apply=True))
        self.assertEqual(SiteContent.objects.count(),75)
        for original in self.originals:
            row = SiteContent.objects.get(external_id=original['external_id'])
            for field in ('title','summary','image_url','link_url','status','tags'):
                self.assertEqual(getattr(row,field),original[field])
        family = SiteContent.objects.get(link_url='https://land110602.com/hokkaido-family-ski-lessons/')
        self.assertIn('小朋友幾歲適合開始滑雪',family.metadata['article']['html'])
        after = list(SiteContent.objects.order_by('id').values())
        self.assertIn('新增0、補全文0',self.run_import(apply=True))
        self.assertEqual(list(SiteContent.objects.order_by('id').values()),after)

    def test_manual_edits_intentional_empty_blocks_and_hidden_state_are_preserved(self):
        rows = list(SiteContent.objects.order_by('id')[:4])
        for row, patch in zip(rows,[{'blocks':[]},{'article_mode':'external'},{'article':{'html':'自訂文章'}}]):
            row.metadata={**row.metadata,**patch};row.save()
        rows[3].status='hidden'; rows[3].title='自訂卡片標題'; rows[3].summary='自訂摘要';rows[3].save()
        originals = {row.id:deepcopy(row.metadata) for row in rows[:3]}
        self.run_import(apply=True)
        for row in rows[:3]:
            row.refresh_from_db();self.assertEqual(row.metadata,originals[row.id])
        rows[3].refresh_from_db()
        self.assertEqual(rows[3].status,'hidden')
        self.assertEqual(rows[3].metadata['article']['title'],'自訂卡片標題')
        self.assertEqual(rows[3].metadata['article']['lead'],'自訂摘要')

    def test_foreign_tenant_is_untouched_and_duplicate_match_rolls_back(self):
        other=Client.objects.create(name='Other',internal_code='other')
        foreign=SiteContent.objects.create(client=other,**self.originals[0])
        before=deepcopy(foreign.metadata)
        self.run_import(apply=True)
        foreign.refresh_from_db();self.assertEqual(foreign.metadata,before)
        duplicate=deepcopy(self.originals[-1]);duplicate['external_id']='duplicate-test'
        SiteContent.objects.create(client=self.client_row,**duplicate)
        before=list(SiteContent.objects.order_by('id').values())
        with self.assertRaises(CommandError):self.run_import(apply=True)
        self.assertEqual(list(SiteContent.objects.order_by('id').values()),before)

    def test_invalid_last_article_rejects_whole_snapshot_before_any_write(self):
        snapshot=json.loads((Path(__file__).parents[1]/'Client/fixtures/customer_guide_articles.json').read_text(encoding='utf-8'))
        snapshot['articles'][-1]['article']['html']='<script>bad()</script>'
        before=list(SiteContent.objects.order_by('id').values())
        with TemporaryDirectory() as directory:
            target=Path(directory)/'invalid.json';target.write_text(json.dumps(snapshot),encoding='utf-8')
            with self.assertRaises(CommandError):self.run_import(apply=True,snapshot=target)
        self.assertEqual(list(SiteContent.objects.order_by('id').values()),before)

    def test_empty_article_catalog_receives_all_75_cards_without_cross_tenant_copy(self):
        other = Client.objects.create(name='Empty catalog',internal_code='empty-catalog')
        call_command('initialize_guide_articles',client=other.internal_code,apply=True,stdout=StringIO())
        cards=SiteContent.objects.filter(client=other,location_key='guides.articles')
        self.assertEqual(cards.count(),75)
        self.assertEqual(sum('article' in row.metadata for row in cards),72)
        self.assertEqual(SiteContent.objects.filter(client=self.client_row).count(),74)
