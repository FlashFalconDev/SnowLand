from io import StringIO
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient
from Client.models import Client, SiteContent
from Resorts.models import Campus


class CourseAreaTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.other = Client.objects.create(name='Other', internal_code='other')
        self.api = APIClient()
        self.url = '/booking/snowland/api/site-content/?content_type=page&location_key=course.areas'
        self.campus = Campus.objects.create(client=self.tenant, code='keep', name='營運校區不變')
        for slug in ['tomamu','sahoro','mt-racey','furano','kamui','pippu','asahikawasantapresentpark','canmore','teine','sapporo-kokusai','onze','asari','rusutsu','kiroro']:
            SiteContent.objects.create(client=self.tenant,location_key='course.resorts',content_type='page',external_id=slug,title=slug,status='active')

    def initialize(self, apply=False):
        call_command('initialize_course_areas', client='snowland', apply=apply, stdout=StringIO())

    def login(self):
        self.api.force_authenticate(User.objects.create_superuser('areas-hq',password='qa-only'))

    def test_preview_source_groups_and_preserve_edits(self):
        self.initialize(); self.assertFalse(SiteContent.objects.filter(location_key='course.areas').exists())
        self.initialize(True)
        result=self.api.get(self.url)
        self.assertEqual(result.status_code,200)
        self.assertEqual([r['external_id'] for r in result.data],['tomamu-area','furano-area','sapporo-area','rusutsu-area'])
        self.assertEqual(result.data[1]['metadata']['resort_slugs'],['furano','kamui','pippu','asahikawasantapresentpark','canmore'])
        row=SiteContent.objects.get(external_id='rusutsu-area'); row.title='自訂名稱';row.status='hidden';row.metadata={'resort_slugs':['tomamu'],'custom':'保留'};row.save()
        self.initialize(True);row.refresh_from_db()
        self.assertEqual(row.title,'自訂名稱');self.assertEqual(row.status,'hidden');self.assertEqual(row.metadata['custom'],'保留')
        self.assertEqual(Campus.objects.count(),1);self.campus.refresh_from_db();self.assertEqual(self.campus.name,'營運校區不變')

    def test_cms_update_order_public_scope_and_hidden(self):
        self.initialize(True);self.login()
        row=SiteContent.objects.get(external_id='rusutsu-area');url=f'/api/admin/snowland/site-content/{row.pk}/'
        result=self.api.patch(url,{'title':'QA新名稱','display_order':-1,'metadata':{'resort_slugs':['kiroro','tomamu'],'custom':'保留'}},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(self.api.get(self.url).data[0]['title'],'QA新名稱')
        SiteContent.objects.create(client=self.other,location_key='course.areas',content_type='page',external_id='private-area',title='不可見',status='active')
        self.assertEqual(len(self.api.get(self.url).data),4)
        self.assertEqual(self.api.patch(url,{'status':'hidden'},format='json').status_code,200)
        self.assertEqual(len(self.api.get(self.url).data),3)

    def test_invalid_changes_no_partial_write_and_no_anonymous_write(self):
        self.initialize(True);row=SiteContent.objects.get(external_id='tomamu-area');url=f'/api/admin/snowland/site-content/{row.pk}/'
        self.assertIn(self.api.patch(url,{'title':'禁止'},format='json').status_code,(401,403))
        self.login()
        for data in [{'external_id':'other-area'},{'metadata':{'resort_slugs':'tomamu'}},{'metadata':{'resort_slugs':['tomamu','tomamu']}},{'metadata':{'resort_slugs':['other-tenant-only']}},{'metadata':{'resort_slugs':[]}},{'title':' '},{'content_type':'review'}]:
            with self.subTest(data=data): self.assertEqual(self.api.patch(url,data,format='json').status_code,400)
        row.refresh_from_db();self.assertEqual(row.title,'星野校區');self.assertEqual(row.metadata['resort_slugs'],['tomamu','sahoro','mt-racey'])

    def test_duplicate_create_and_foreign_tenant_resort_rejected(self):
        self.initialize(True);self.login()
        url='/api/admin/snowland/site-content/'
        base={'location_key':'course.areas','content_type':'page','external_id':'new-area','title':'新區','status':'active','metadata':{'resort_slugs':['tomamu']}}
        self.assertEqual(self.api.post(url,base,format='json').status_code,201)
        self.assertEqual(self.api.post(url,base,format='json').status_code,400)
        SiteContent.objects.create(client=self.other,location_key='course.resorts',content_type='page',external_id='only-other')
        self.assertEqual(self.api.post(url,{**base,'external_id':'foreign-area','metadata':{'resort_slugs':['only-other']}},format='json').status_code,400)
        for slug in ['javascript:bad','../bad-area','wrong','bad/area']:
            self.assertEqual(self.api.post(url,{**base,'external_id':slug},format='json').status_code,400)

    def test_initializer_conflict_is_atomic(self):
        SiteContent.objects.create(client=self.tenant,location_key='course.areas',external_id='rusutsu-area',content_type='review')
        with self.assertRaises(CommandError):self.initialize(True)
        self.assertEqual(SiteContent.objects.filter(location_key='course.areas').count(),1)

    def test_removed_resort_reference_preserved_then_can_be_unchecked(self):
        self.initialize(True);self.login()
        row=SiteContent.objects.get(external_id='tomamu-area')
        SiteContent.objects.filter(client=self.tenant,location_key='course.resorts',external_id='sahoro').delete()
        url=f'/api/admin/snowland/site-content/{row.pk}/'
        self.assertEqual(self.api.patch(url,{'title':'保留原失效參照'},format='json').status_code,200)
        self.assertEqual(self.api.patch(url,{'metadata':{'resort_slugs':['tomamu','mt-racey']}},format='json').status_code,200)
        row.refresh_from_db();self.assertEqual(row.metadata['resort_slugs'],['tomamu','mt-racey'])
