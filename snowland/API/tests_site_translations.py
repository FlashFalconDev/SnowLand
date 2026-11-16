from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from Client.models import Client, RecruitmentForm, SiteContent
from Control.models import TenantStaffMembership
from Coursekit.models import CourseCategory, CourseType, CourseTemplate


class SiteTranslationsTests(TestCase):
    admin_url = '/api/admin/trans-a/site-translations/entries/'
    public_url = '/booking/trans-a/api/site-translations/'

    def setUp(self):
        self.school = Client.objects.create(internal_code='trans-a', name='Translation A')
        self.other = Client.objects.create(internal_code='trans-b', name='Translation B')
        self.admin = APIClient()
        self.admin.force_login(User.objects.create_superuser('translation-admin', 'admin@example.test', 'QA'))
        self.public = APIClient()

    def entries(self, scope):
        return self.admin.get(self.admin_url, {'scope': scope})

    def save(self, scope, *updates, revision=None):
        current = self.entries(scope)
        self.assertEqual(current.status_code, 200, current.data)
        return self.admin.put(self.admin_url + f'?scope={scope}',
                              {'revision': revision or current.data['revision'], 'updates': updates}, format='json')

    @staticmethod
    def entry(key, source, **values):
        return {'key': key, 'source': source, 'values': {'zh-Hant': '', 'en': '', 'ja': '', **values}}

    def test_ui_override_is_tenant_scoped_and_can_restore_original(self):
        source = '預約 {count} 堂課'
        revision = self.entries('ui').data['revision']
        bad = self.save('ui', self.entry(source, source, en='Book lessons'))
        self.assertEqual(bad.status_code, 400)
        changed = self.save('ui', self.entry(source, source, en='Book {count} lessons', ja=''))
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(self.public.get(self.public_url).data['scopes']['ui'][source]['values']['en'], 'Book {count} lessons')
        self.assertEqual(self.public.get('/booking/trans-b/api/site-translations/').data, {'scopes': {}})
        stale = self.save('ui', self.entry(source, source, en=''), revision=revision)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.save('ui', self.entry(source, source)).status_code, 200)
        self.assertEqual(self.public.get(self.public_url).data['scopes']['ui'][source]['values']['en'], '')

    def test_navigation_and_interface_text_can_use_different_translations(self):
        source = '會員專區'
        self.assertEqual(self.save('ui', self.entry(source, source, en='Membership')).status_code, 200)
        self.assertEqual(self.save('navigation', self.entry(source, source, en='Member area')).status_code, 200)
        scopes = self.public.get(self.public_url).data['scopes']
        self.assertEqual(scopes['ui'][source]['values']['en'], 'Membership')
        self.assertEqual(scopes['navigation'][source]['values']['en'], 'Member area')

    def test_editor_lists_article_text_and_preserves_link_markup_and_fallback(self):
        article = SiteContent.objects.create(client=self.school, content_type='article', location_key='guides.articles',
            title='準備裝備', summary='摘要', status='active',
            metadata={'article': {'html': '<h2 id="gear">基本裝備</h2><p>請準備 <a href="/guides">滑雪板</a></p>'
                                         '<table><tr><td>尺寸</td></tr></table>'}})
        scope = f'content:{article.pk}'
        fields = {row['source']: row['key'] for row in self.entries(scope).data['fields']}
        self.assertIn('基本裝備', fields)
        self.assertIn('尺寸', fields)
        self.assertEqual(self.save(scope,
            self.entry('title', '準備裝備', en='Get your equipment ready'),
            self.entry(fields['滑雪板'], '滑雪板', en='<Gear & board>'),
        ).status_code, 200)
        url = '/booking/trans-a/api/site-content/'
        params = {'location_key': 'guides.articles', 'content_id': article.pk}
        result = self.public.get(url, {**params, 'locale': 'en'}).data[0]
        self.assertEqual(result['title'], 'Get your equipment ready')
        self.assertEqual(result['summary'], '摘要')
        self.assertIn('<a href="/guides">&lt;Gear &amp; board&gt;</a>', result['metadata']['article']['html'])
        self.assertIn('<h2 id="gear">基本裝備</h2>', result['metadata']['article']['html'])
        self.assertEqual(self.public.get(url, {**params, 'locale': 'ja'}).data[0]['title'], '準備裝備')
        self.assertNotIn(scope, self.public.get(self.public_url).data['scopes'])
        article.title = '新標題'
        article.save(update_fields=['title'])
        self.assertEqual(self.public.get(url, {**params, 'locale': 'en'}).data[0]['title'], '新標題')
        self.assertEqual(self.save(scope, self.entry('title', '準備裝備', en='Stale')).status_code, 409)

    def test_course_and_recruitment_use_stable_scopes_and_current_sources(self):
        category = CourseCategory.objects.create(client=self.school, name='滑雪')
        course_type = CourseType.objects.create(category=category, name='入門')
        course = CourseTemplate.objects.create(course_type=course_type, name='入門三小時', duration_hours=3)
        scope = f'template:{course.pk}'
        self.assertEqual(self.save(scope, self.entry('name', course.name, en='Three-hour introductory lesson')).status_code, 200)
        form = RecruitmentForm.objects.create(client=self.school, enabled=False, fields=[
            {'id': 'experience', 'label': '滑雪經驗', 'type': 'single', 'required': True, 'options': ['初級', '進階']},
        ])
        self.assertEqual(self.save('recruitment', self.entry('experience.label', '滑雪經驗', en='Skiing experience'),
                                    self.entry('experience.option.0', '初級', en='Beginner')).status_code, 200)
        scopes = self.public.get(self.public_url).data['scopes']
        self.assertEqual(scopes[scope]['name']['values']['en'], 'Three-hour introductory lesson')
        self.assertNotIn('recruitment', scopes)
        form.enabled = True
        form.save(update_fields=['enabled'])
        published = self.public.get(self.public_url).data['scopes']['recruitment']
        self.assertEqual(published['experience.option.0']['values']['en'], 'Beginner')
        public_form = self.public.get('/booking/trans-a/api/recruitment/').data
        self.assertEqual(public_form['fields'][0]['options'], ['初級', '進階'])
        course.is_active = False
        course.save(update_fields=['is_active'])
        self.assertNotIn(scope, self.public.get(self.public_url).data['scopes'])

    def test_admin_permissions_and_published_article_boundaries(self):
        row = SiteContent.objects.create(client=self.other, content_type='article', location_key='guides.articles',
                                         title='Other tenant content', status='draft')
        self.assertEqual(self.entries(f'content:{row.pk}').status_code, 404)
        self.assertEqual(self.public.get(self.admin_url, {'scope': 'ui'}).status_code, 403)
        worker = User.objects.create_user('translation-worker')
        TenantStaffMembership.objects.create(user=worker, client=self.school, is_manager=True,
                                             role='web_editor', all_campuses=True, admin_permissions=['site_guides'])
        self.admin.force_login(worker)
        self.assertEqual(self.entries('ui').status_code, 403)
