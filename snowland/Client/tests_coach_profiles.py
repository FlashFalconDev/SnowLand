from copy import deepcopy
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from Client.models import Client,SiteContent
from Client.coach_profiles import read_coach_profile,save_coach_profile,PROFILE_LOCATION
from Coach.models import Coach


class CoachProfilePreservationTests(TestCase):
    def setUp(self):
        self.tenant=Client.objects.create(name='SnowLand',internal_code='snowland')
        self.other=Client.objects.create(name='Other',internal_code='other')
        self.coach=Coach.objects.create(client=self.tenant,name='目前教練姓名',website_slug='cash')
        self.foreign=Coach.objects.create(client=self.other,name='Other',website_slug='cash')

    def run_import(self):
        call_command('import_coach_profile_defaults',client='snowland',stdout=StringIO())

    def test_import_preserves_public_copy_without_changing_operational_coach(self):
        self.run_import()
        self.assertEqual(Coach.objects.count(),2)
        self.coach.refresh_from_db();self.assertEqual(self.coach.name,'目前教練姓名')
        row=SiteContent.objects.get(client=self.tenant,location_key=PROFILE_LOCATION)
        self.assertEqual(row.external_id,str(self.coach.pk));self.assertEqual(row.status,'hidden')
        profile=read_coach_profile(self.coach)
        self.assertEqual(profile['slug'],'cash');self.assertEqual(len(profile['videos']),9)
        self.assertEqual(len(profile['reviews']),29);self.assertEqual(len(profile['sections']),5)
        self.assertIn('snowboard',profile['abilityTags'])
        self.assertEqual(read_coach_profile(self.foreign),{})

    def test_reimport_never_overwrites_editor_changes(self):
        self.run_import();profile=read_coach_profile(self.coach)
        profile['sections']=[{'title':'教學理念','lines':['QA新版文案']}]
        save_coach_profile(self.coach,profile,overwrite=True)
        self.run_import()
        self.assertEqual(read_coach_profile(self.coach)['sections'][0]['lines'],['QA新版文案'])
        self.assertEqual(SiteContent.objects.filter(location_key=PROFILE_LOCATION).count(),1)

    def test_duplicate_slug_rolls_back_instead_of_guessing_identity(self):
        # Cash is imported first; the later ambiguous Lily must roll all of it back.
        Coach.objects.create(client=self.tenant,name='Lily A',website_slug='lily')
        Coach.objects.create(client=self.tenant,name='Lily B',website_slug='lily')
        with self.assertRaises(CommandError):self.run_import()
        self.assertFalse(SiteContent.objects.filter(location_key=PROFILE_LOCATION).exists())

    def test_snapshot_and_reads_do_not_alias_mutable_objects(self):
        profile={'sections':[{'title':'QA','lines':['original']}]}
        expected=deepcopy(profile);save_coach_profile(self.coach,profile)
        profile['sections'][0]['lines'].append('not saved')
        read_coach_profile(self.coach)['sections'].clear()
        self.assertEqual(read_coach_profile(self.coach),expected)

    def test_disabled_coach_profile_is_not_exposed_by_generic_public_cms(self):
        save_coach_profile(self.coach,{'sections':[{'title':'QA隱藏文案'}]})
        response=self.client.get('/booking/snowland/api/site-content/',{'location_key':PROFILE_LOCATION,'include_ended':'true'})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('QA隱藏文案',str(response.data))

    def test_public_detail_profile_requires_enabled_same_tenant_coach_and_exact_slug(self):
        self.run_import();self.coach.website_enabled=True;self.coach.save()
        self.foreign.website_enabled=True;self.foreign.save()
        url='/booking/snowland/api/website-coaches/'
        cards=self.client.get(url).data['data']['list']
        self.assertNotIn('profile',cards[0])
        detail=self.client.get(url,{'slug':'cash','include_profile':'1'}).data['data']['list']
        self.assertEqual([item['id'] for item in detail],[self.coach.pk])
        self.assertEqual(detail[0]['name'],'目前教練姓名')
        self.assertEqual(len(detail[0]['profile']['videos']),9)
        self.assertEqual(self.client.get(url,{'slug':'missing','include_profile':'1'}).data['data']['list'],[])
        self.coach.website_enabled=False;self.coach.save()
        self.assertEqual(self.client.get(url,{'slug':'cash','include_profile':'1'}).data['data']['list'],[])
