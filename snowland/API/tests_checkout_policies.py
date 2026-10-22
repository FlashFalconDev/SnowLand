from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from Client.models import Client, SiteContent


class CheckoutPolicyTests(TestCase):
    url = '/booking/snowland/api/checkout-policies/'

    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.api = APIClient()

    def test_public_documents_are_versioned_and_match_existing_policy_pages(self):
        response = self.api.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data['documents']), {'terms', 'privacy'})
        self.assertEqual(len(response.data['pages']), 3)
        for document in response.data['documents'].values():
            self.assertTrue(document['body'])
            self.assertEqual(len(document['version']), 64)
        self.assertEqual(response.data, self.api.get(self.url).data)
        self.assertIn('no-store', response['Cache-Control'])

    def test_published_changes_invalidate_old_acceptance_without_touching_old_snapshot(self):
        from booking.checkout_policies import accepted_checkout_policies, checkout_policy_payload
        original = self.api.get(self.url).data
        proof = {'terms': True, 'privacy': True, 'terms_version': original['documents']['terms']['version'],
                 'privacy_version': original['documents']['privacy']['version']}
        snapshot = accepted_checkout_policies(self.tenant, proof)
        row = SiteContent.objects.create(client=self.tenant, content_type='page', status='draft',
            location_key='policy.privacy-policy', title='QA privacy', body='QA NON-BINDING PRIVACY')
        self.assertEqual(checkout_policy_payload(self.tenant), original)
        row.status = 'active'; row.save(update_fields=['status'])
        current = checkout_policy_payload(self.tenant)
        self.assertNotEqual(current['documents']['privacy']['version'], proof['privacy_version'])
        with self.assertRaisesRegex(ValueError, '更新'):
            accepted_checkout_policies(self.tenant, proof)
        self.assertEqual(snapshot['privacy']['version'], proof['privacy_version'])
        self.assertNotIn('QA NON-BINDING PRIVACY', snapshot['privacy']['body'])
        old_version = current['documents']['privacy']['version']
        row.title = 'QA revised title'; row.save(update_fields=['title'])
        revised = checkout_policy_payload(self.tenant)['documents']['privacy']
        self.assertNotEqual(revised['version'], old_version)
        self.assertIn(row.title, revised['body'])

    def test_explicit_two_boolean_consents_and_both_current_versions_are_required(self):
        from booking.checkout_policies import accepted_checkout_policies
        documents = self.api.get(self.url).data['documents']
        valid = {'terms': True, 'privacy': True, 'terms_version': documents['terms']['version'],
                 'privacy_version': documents['privacy']['version']}
        for invalid in [None, [], {}, {**valid, 'terms': False}, {**valid, 'privacy': 1},
                        {**valid, 'terms_version': ''}, {**valid, 'privacy_version': 'old'}]:
            with self.assertRaises(ValueError):
                accepted_checkout_policies(self.tenant, invalid)
        result = accepted_checkout_policies(self.tenant, valid)
        self.assertEqual(result['terms']['version'], valid['terms_version'])
        self.assertTrue(result['privacy']['body'])

    def test_incomplete_active_document_fails_closed_and_draft_restores_default(self):
        row = SiteContent.objects.create(client=self.tenant,content_type='page',status='active',
            location_key='policy.privacy-policy',title='QA incomplete',body=' ')
        self.assertEqual(self.api.get(self.url).status_code, 503)
        row.status='draft'; row.save(update_fields=['status'])
        self.assertEqual(self.api.get(self.url).status_code, 200)

    def test_tenants_and_unsafe_markup_are_isolated(self):
        other = Client.objects.create(name='Other', internal_code='other')
        SiteContent.objects.create(client=other, content_type='page', status='active',
            location_key='policy.privacy-policy', title='Other policy', body='<script>private()</script>')
        own = self.api.get(self.url).data
        self.assertNotIn('private()', str(own))
        foreign = self.api.get('/booking/other/api/checkout-policies/').data
        self.assertNotIn('<script>', foreign['pages']['privacyPolicy']['html'])
        self.assertEqual(self.api.get('/booking/missing/api/checkout-policies/').status_code, 404)

    def test_only_headquarters_can_publish_legal_documents_and_invalid_edits_do_not_save(self):
        endpoint = '/api/admin/snowland/site-content/'
        hq = User.objects.create_superuser('policy-hq', password='qa-only')
        self.api.force_authenticate(hq)
        data = {'content_type': 'page', 'location_key': 'policy.privacy-policy', 'title': 'QA privacy', 'body': 'QA privacy body', 'status': 'draft'}
        created = self.api.post(endpoint, data, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        row = SiteContent.objects.get(location_key=data['location_key'])
        url = f'{endpoint}{row.pk}/'
        for invalid in ({'body': ' '}, {'title': ''}, {'content_type': 'setting'}, {'location_key': 'homepage.test'}):
            self.assertEqual(self.api.patch(url, invalid, format='json').status_code, 400)
        self.assertEqual(self.api.patch(url, {'status': 'active'}, format='json').status_code, 200)
        self.assertEqual(self.api.get(self.url).data['pages']['privacyPolicy']['body'], data['body'])
        editor = User.objects.create_user('policy-editor', password='qa-only')
        profile = editor.userprofile
        profile.is_manager = True; profile.role = 'web_editor'; profile.manager_client = self.tenant
        profile.admin_permissions = ['cms']; profile.save()
        self.api.force_authenticate(editor)
        self.assertEqual(self.api.patch(url, {'body': 'cannot publish'}, format='json').status_code, 403)
        self.assertEqual(self.api.delete(url).status_code, 403)
        self.assertEqual(self.api.post(endpoint, {**data, 'location_key': 'policy.membership-terms'}, format='json').status_code, 403)
        row.refresh_from_db(); self.assertEqual(row.body, data['body'])
