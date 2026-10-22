from io import StringIO
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient
from Client.models import Client, SiteContent


class HomepageCourseTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.api=APIClient()
        self.public='/booking/snowland/api/site-content/?content_type=page&location_key=homepage.courses'

    def initialize(self,apply=False):
        call_command('initialize_homepage_courses',client='snowland',apply=apply,stdout=StringIO())

    def test_dry_run_then_four_defaults_and_idempotent_preserve(self):
        self.initialize();self.assertEqual(SiteContent.objects.count(),0)
        self.initialize(True)
        self.assertEqual(SiteContent.objects.count(),4)
        row=SiteContent.objects.get(external_id='rusutsu');row.title='管理者自訂';row.status='hidden';row.save()
        self.initialize(True);row.refresh_from_db()
        self.assertEqual(row.title,'管理者自訂');self.assertEqual(row.status,'hidden');self.assertEqual(SiteContent.objects.count(),4)
        self.assertEqual([r['external_id'] for r in self.api.get(self.public).data],['tomamu','off-piste-guide','hokkaido'])

    def test_duplicate_or_wrong_type_fails_without_partial_insert(self):
        SiteContent.objects.create(client=self.tenant,content_type='review',location_key='homepage.courses',external_id='rusutsu')
        with self.assertRaises(CommandError):self.initialize(True)
        self.assertEqual(SiteContent.objects.count(),1)

    def test_public_order_tenant_and_state(self):
        self.initialize(True)
        other=Client.objects.create(name='other',internal_code='other')
        SiteContent.objects.create(client=other,content_type='page',location_key='homepage.courses',title='不可見',status='active')
        self.assertEqual([r['external_id'] for r in self.api.get(self.public).data],['tomamu','rusutsu','off-piste-guide','hokkaido'])
        row=SiteContent.objects.get(client=self.tenant,external_id='rusutsu');row.display_order=-1;row.save()
        self.assertEqual(self.api.get(self.public).data[0]['id'],row.pk)

    def test_cms_edits_reflect_and_unsafe_link_does_not_partially_write(self):
        self.initialize(True)
        row=SiteContent.objects.get(external_id='rusutsu')
        self.api.force_authenticate(User.objects.create_superuser('home-courses-hq',password='qa-only'))
        url=f'/api/admin/snowland/site-content/{row.pk}/'
        result=self.api.patch(url,{'summary':'QA後台改字','subtitle':'QA按鈕','image_url':'/vite.svg','link_url':'/booking'},format='json')
        self.assertEqual(result.status_code,200,result.data)
        public=next(r for r in self.api.get(self.public).data if r['id']==row.pk)
        self.assertEqual(public['summary'],'QA後台改字');self.assertEqual(public['link_url'],'/booking')
        self.assertEqual(self.api.patch(url,{'summary':'不可半存','link_url':'javascript:alert(1)'},format='json').status_code,400)
        row.refresh_from_db();self.assertEqual(row.summary,'QA後台改字')

    def test_invalid_card_fields_and_anonymous_write_are_rejected(self):
        self.initialize(True)
        row=SiteContent.objects.get(external_id='rusutsu');url=f'/api/admin/snowland/site-content/{row.pk}/'
        self.assertIn(self.api.patch(url,{'title':'不可匿名修改'},format='json').status_code,(401,403))
        self.api.force_authenticate(User.objects.create_superuser('home-card-validation',password='qa-only'))
        for data in [{'image_url':'data:image/svg+xml,<svg/>'},{'link_url':'//evil.test'},{'link_url':'/\\evil.test'},{'link_url':''},{'title':' '},{'content_type':'review'}]:
            with self.subTest(data=data):self.assertEqual(self.api.patch(url,data,format='json').status_code,400)
        row.refresh_from_db();self.assertEqual(row.title,'留壽都 RUSUTSU')
