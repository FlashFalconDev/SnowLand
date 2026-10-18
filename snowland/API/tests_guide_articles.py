from copy import deepcopy
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client, SiteContent


class GuideArticleTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.api = APIClient()
        self.api.force_authenticate(User.objects.create_superuser('guide-editor', password='qa-only'))
        self.url = '/api/admin/snowland/site-content/'
        self.payload = {'content_type':'article', 'location_key':'guides.articles', 'title':'QA 新攻略', 'status':'active',
                        'metadata':{'category':'親子滑雪', 'date':'2026-10-18', 'article_mode':'internal',
                                    'blocks':[{'id':'qa-p','type':'paragraph','text':'QA 原創攻略正文'}]}}

    def test_create_edit_category_publish_and_hide_same_article(self):
        result = self.api.post(self.url, self.payload, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        row_id = result.data['data']['id']
        detail = f'{self.url}{row_id}/'
        public_url = f'/booking/snowland/api/site-content/?location_key=guides.articles&content_id={row_id}&limit=1'
        public = APIClient().get(public_url)
        self.assertEqual([row['id'] for row in public.data], [row_id])
        metadata = deepcopy(self.payload['metadata']); metadata['category']='裝備與技巧'
        self.assertEqual(self.api.patch(detail, {'metadata':metadata}, format='json').status_code,200)
        self.assertEqual(APIClient().get(public_url).data[0]['metadata']['category'],'裝備與技巧')
        self.assertEqual(self.api.patch(detail, {'status':'hidden'}, format='json').status_code,200)
        self.assertEqual(APIClient().get(public_url).data,[])
        self.assertEqual(SiteContent.objects.filter(client=self.tenant).count(),1)

    def test_invalid_published_article_rejected_without_creating_or_partial_write(self):
        row = self.api.post(self.url, self.payload, format='json').data['data']
        original = SiteContent.objects.get(pk=row['id'])
        variants = [
            {'title':''},
            {'metadata':{**self.payload['metadata'],'category':''}},
            {'metadata':{**self.payload['metadata'],'category':[]}},
            {'metadata':{**self.payload['metadata'],'category':' All '}},
            {'metadata':{**self.payload['metadata'],'date':'2026-02-30'}},
            {'metadata':{**self.payload['metadata'],'blocks':[]}},
            {'metadata':{**self.payload['metadata'],'blocks':[{'type':'image','src':'javascript:alert(1)'}]}},
            {'metadata':{**self.payload['metadata'],'blocks':[{'type':'paragraph','text':'有效內文'},{'type':'image','src':'/qa.svg','alt':{}}]}},
            {'metadata':{**self.payload['metadata'],'blocks':[{'type':'paragraph','text':{}}]}},
            {'metadata':{**self.payload['metadata'],'article_mode':'external'},'link_url':'javascript:alert(1)'},
        ]
        for patch in variants:
            result=self.api.patch(f"{self.url}{row['id']}/",patch,format='json')
            self.assertEqual(result.status_code,400,result.data)
            current=SiteContent.objects.get(pk=row['id'])
            self.assertEqual(current.title,original.title)
            self.assertEqual(current.metadata,original.metadata)

    def test_draft_external_legacy_and_tenant_visibility(self):
        draft = self.api.post(self.url, {'content_type':'article','location_key':'guides.articles','status':'draft'},format='json')
        self.assertEqual(draft.status_code,201)
        self.assertEqual(self.api.patch(f"{self.url}{draft.data['data']['id']}/",{'status':'active'},format='json').status_code,400)
        payload=deepcopy(self.payload);payload['metadata']={'category':'裝備與技巧','date':'2024.10.01'}
        payload['link_url']='https://example.test/original-article'
        external=self.api.post(self.url,payload,format='json')
        self.assertEqual(external.status_code,201,external.data)
        other=Client.objects.create(name='Other',internal_code='other')
        foreign=SiteContent.objects.create(client=other,**self.payload)
        self.assertEqual(APIClient().get(f'/booking/snowland/api/site-content/?content_id={foreign.pk}').data,[])
        self.assertEqual(APIClient().get('/booking/snowland/api/site-content/?content_id=bad').status_code,400)

    def test_targeted_article_lookup_is_not_lost_after_first_hundred_and_respects_dates(self):
        SiteContent.objects.bulk_create([SiteContent(client=self.tenant,content_type='article',location_key='guides.articles',
                    status='active',title=f'older-{i}',display_order=-100) for i in range(105)])
        row=SiteContent.objects.create(client=self.tenant,**self.payload)
        url=f'/booking/snowland/api/site-content/?location_key=guides.articles&content_id={row.pk}&limit=1'
        self.assertEqual(APIClient().get(url).data[0]['id'],row.pk)
        listing=APIClient().get('/booking/snowland/api/site-content/?location_key=guides.articles&limit=500')
        self.assertEqual(len(listing.data),106)
        row.start_at=timezone.now()+timedelta(days=1);row.save()
        self.assertEqual(APIClient().get(url).data,[])

    def test_reviews_only_staff_cannot_create_articles(self):
        user=User.objects.create_user('guide-review-only')
        profile=user.userprofile;profile.is_manager=True;profile.manager_client=self.tenant
        profile.admin_permissions=['reviews'];profile.save()
        self.api.force_authenticate(user)
        self.assertEqual(self.api.post(self.url,self.payload,format='json').status_code,403)

    def test_invalid_new_article_creates_nothing(self):
        payload=deepcopy(self.payload);payload['metadata']['category']=''
        self.assertEqual(self.api.post(self.url,payload,format='json').status_code,400)
        self.assertEqual(SiteContent.objects.count(),0)
