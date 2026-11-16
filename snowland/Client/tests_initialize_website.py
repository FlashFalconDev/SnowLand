from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from Client.management.commands.initialize_snowland_website import read_fixture
from Client.models import Client, SiteContent


class InitializeSnowLandWebsiteTests(TestCase):
    def test_preview_and_repeatable_import_preserve_public_edits_and_other_clients(self):
        tenant = Client.objects.create(name='SnowLand', internal_code='snowland', is_active=True)
        other = Client.objects.create(name='Other', internal_code='other', is_active=True)
        article = read_fixture('customer_guide_articles.json')['articles'][0]['card']
        edited_article = SiteContent.objects.create(
            client=tenant, location_key='guides.articles', content_type='article',
            external_id='edited-article', title=article['title'], body='官網編輯的文章正文',
            status='active', metadata={'article_mode': 'internal'},
        )
        edited_offer = SiteContent.objects.create(
            client=tenant, location_key='homepage.offers', content_type='offer',
            external_id='seed-home-offer-earlybird', title='26-27 正式優惠',
            link_url='/specialoffers/earlybird', status='active',
        )
        edited_photo = SiteContent.objects.create(
            client=tenant, location_key='photography.winter', content_type='page',
            title='既有攝影頁', body='後台自訂正文', status='active',
        )
        old_price = next(row for row in read_fixture('site_content_defaults.json')
                         if row['location_key'] == 'course.pricing' and row['external_id'] == 'tomamu')
        SiteContent.objects.create(client=tenant, **old_price)
        edited_price = SiteContent.objects.create(
            client=tenant, location_key='course.pricing', content_type='setting',
            external_id='rusutsu', status='active', metadata={'pricing': {'season_label': '客戶自訂'}},
        )
        other_row = SiteContent.objects.create(client=other, location_key='homepage.hero', title='Other')
        preview = StringIO()
        call_command('initialize_snowland_website', client='snowland', stdout=preview)
        self.assertEqual(tenant.site_contents.count(), 5)
        self.assertIn('可更新 1 筆', preview.getvalue())

        call_command('initialize_snowland_website', client='snowland', apply=True, stdout=StringIO())
        expected_counts = {
            'homepage.courses': 4, 'course.areas': 4, 'course.resorts': 14,
            'course.resort-pages': 13, 'course.pricing': 15, 'guides.faq': 28,
            'guides.articles': 75, 'guides.article-pages': 2, 'photography.gallery': 76,
            'photography.summer': 1, 'about.snowland': 1, 'about.join-us': 1,
        }
        for location, count in expected_counts.items():
            with self.subTest(location=location):
                self.assertEqual(tenant.site_contents.filter(location_key=location).count(), count)
        self.assertEqual(tenant.site_contents.filter(location_key='guides.articles', title=article['title']).count(), 1)
        self.assertEqual(tenant.site_contents.filter(location_key='homepage.offers', link_url=edited_offer.link_url).count(), 1)
        edited_article.refresh_from_db()
        edited_photo.refresh_from_db()
        edited_price.refresh_from_db()
        self.assertEqual(edited_article.body, '官網編輯的文章正文')
        self.assertEqual(edited_photo.body, '後台自訂正文')
        self.assertIn('photography', edited_photo.metadata)
        self.assertEqual(edited_price.metadata['pricing']['season_label'], '客戶自訂')
        self.assertEqual(list(other.site_contents.values_list('pk', flat=True)), [other_row.pk])

        response = self.client.get('/booking/snowland/api/site-content/', {'location_key': 'course.pricing'})
        self.assertEqual(response.status_code, 200)
        by_slug = {row['external_id']: row['metadata']['pricing'] for row in response.json()}
        self.assertEqual(by_slug['tomamu']['plans']['regular']['rows'][1]['full'], 21700)
        self.assertEqual(by_slug['off-piste-guide']['plans']['discount']['rows'][1]['half'], 39600)
        self.assertEqual(by_slug['furano']['plans']['discount']['rows'][0]['half'], 10800)
        saved = list(tenant.site_contents.order_by('pk').values())
        call_command('initialize_snowland_website', client='snowland', apply=True, stdout=StringIO())
        self.assertEqual(list(tenant.site_contents.order_by('pk').values()), saved)
