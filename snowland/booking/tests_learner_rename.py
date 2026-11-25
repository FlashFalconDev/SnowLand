from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting

from .models import LearnerProfile, MemberDetail, MemberWaiverSignature, Reservation, ReservationGroup


class LearnerRenameTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = Client.objects.create(name='QA School A', internal_code='school-a')
        cls.other_school = Client.objects.create(name='QA School B', internal_code='school-b')
        cls.module = ModuleInfo.objects.create(module_sid='booking', module_name='預約')
        cls.owner = User.objects.create_user('qa-profile-owner')
        cls.other_user = User.objects.create_user('qa-profile-other')
        cls.profile = LearnerProfile.objects.create(client=cls.school, owner=cls.owner, name='原姓名')

    def setUp(self):
        self.api = APIClient()
        self.api.force_login(self.owner)

    def profiles_path(self, school=None):
        return f'/booking/{(school or self.school).internal_code}/api/learner-profiles/'

    def list_profiles(self, school=None):
        response = self.api.get(self.profiles_path(school))
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id']: row for row in response.data['profiles']}

    def rename(self, profile=None, *, name='新姓名', school=None):
        return self.api.post(self.profiles_path(school), {
            'action': 'rename', 'profile_id': (profile or self.profile).pk, 'name': name,
        }, format='json')

    def set_policy(self, policy, school=None):
        return ModuleSetting.objects.update_or_create(
            client=school or self.school, module=self.module, defaults={'settings': {'learner_rename_policy': policy}},
        )[0]

    def make_place(self, profile, *, archived_order=False, **values):
        group = ReservationGroup.objects.create(
            client=profile.client, user=profile.owner, is_deleted=archived_order,
            booking_contact={'name': '訂單聯絡人', 'email': 'qa@example.test'},
        )
        reservation = Reservation.objects.create(group=group, status='completed')
        return MemberDetail.all_objects.create(reservation=reservation, user=profile.owner, learner=profile, **values)

    def test_disabled_and_missing_or_invalid_settings_deny_rename(self):
        def assert_denied():
            self.assertEqual(self.list_profiles()[self.profile.pk], {
                'id': self.profile.pk, 'name': '原姓名', 'can_rename': False,
            })
            self.assertEqual(self.rename().status_code, 403)

        assert_denied()
        self.assertFalse(ModuleSetting.objects.exists())
        for settings in ({}, {'learner_rename_policy': None}, {'learner_rename_policy': ''},
                         {'learner_rename_policy': 'unknown'}, {'learner_rename_policy': 'disabled'}, ['owner_all']):
            with self.subTest(settings=settings):
                ModuleSetting.objects.update_or_create(client=self.school, module=self.module, defaults={'settings': settings})
                assert_denied()
        row = self.set_policy('owner_all')
        row.is_active = False
        row.save(update_fields=['is_active'])
        assert_denied()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, '原姓名')

    def test_unlinked_policy_checks_live_places_again_on_rename(self):
        self.set_policy('unlinked_only')
        unlinked = LearnerProfile.objects.create(client=self.school, owner=self.owner, name='原姓名二')
        self.assertTrue(self.list_profiles()[self.profile.pk]['can_rename'])
        self.make_place(self.profile)
        profiles = self.list_profiles()
        self.assertFalse(profiles[self.profile.pk]['can_rename'])
        self.assertTrue(profiles[unlinked.pk]['can_rename'])
        self.assertEqual(self.rename().status_code, 403)
        self.assertEqual(self.rename(unlinked, name='  新姓名二　').data, {
            'id': unlinked.pk, 'name': '新姓名二', 'can_rename': True,
        })
        self.assertEqual(self.list_profiles()[unlinked.pk]['name'], '新姓名二')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, '原姓名')

    def test_inactive_and_soft_deleted_places_do_not_block_rename(self):
        self.set_policy('unlinked_only')
        self.make_place(self.profile, is_active=False, archived_at=timezone.now())
        self.make_place(self.profile, is_deleted=True)
        self.make_place(self.profile, archived_order=True)
        self.assertTrue(self.list_profiles()[self.profile.pk]['can_rename'])
        self.assertEqual(self.rename().status_code, 200)

    def test_owner_all_changes_linked_profile_without_rewriting_legal_or_order_data(self):
        self.set_policy('owner_all')
        signed_at = timezone.now()
        place = self.make_place(
            self.profile, insurance_data={'full_name': '保險姓名', 'notes': '原投保資料'},
            waiver_signature='簽署姓名', waiver_document_snapshot='已簽聲明書',
            waiver_document_version='QA1', waiver_completed_at=signed_at, media_consent='decline',
        )
        signature = MemberWaiverSignature.objects.create(
            member=place, signer=self.owner, signer_name='簽署姓名', signer_role='self', signed_at=signed_at,
            document_version='QA1', document_snapshot='已簽聲明書', form_snapshot={'full_name': '保險姓名'},
            course_revision=1, media_consent='decline', strokes=[[[20, 30], [70, 60]]],
        )
        place_row = MemberDetail.all_objects.values().get(pk=place.pk)
        signature_row = MemberWaiverSignature.objects.values().get(pk=signature.pk)
        group_id = place.reservation.group_id
        contact = ReservationGroup.objects.get(pk=group_id).booking_contact

        self.assertTrue(self.list_profiles()[self.profile.pk]['can_rename'])
        self.assertEqual(self.rename().status_code, 200)
        self.assertEqual(self.list_profiles()[self.profile.pk]['name'], '新姓名')
        self.assertEqual(MemberDetail.all_objects.values().get(pk=place.pk), place_row)
        self.assertEqual(MemberWaiverSignature.objects.values().get(pk=signature.pk), signature_row)
        self.assertEqual(ReservationGroup.objects.get(pk=group_id).booking_contact, contact)

    def test_tenant_lists_and_policies_are_independent(self):
        other_profile = LearnerProfile.objects.create(client=self.other_school, owner=self.owner, name='乙校姓名')
        self.set_policy('owner_all')
        self.assertEqual(set(self.list_profiles()), {self.profile.pk})
        self.assertEqual(self.list_profiles(self.other_school), {
            other_profile.pk: {'id': other_profile.pk, 'name': '乙校姓名', 'can_rename': False},
        })
        self.assertEqual(self.rename(other_profile, school=self.other_school).status_code, 403)
        self.assertEqual(self.rename(school=self.other_school).status_code, 404)
        self.assertEqual(self.rename(other_profile).status_code, 404)
        self.profile.refresh_from_db()
        other_profile.refresh_from_db()
        self.assertEqual((self.profile.name, other_profile.name), ('原姓名', '乙校姓名'))

    def test_another_owner_gets_same_response_as_missing_profile(self):
        self.set_policy('owner_all')
        self.api.force_login(self.other_user)
        self.assertEqual(self.list_profiles(), {})
        foreign = self.rename()
        missing = self.api.post(self.profiles_path(), {
            'action': 'rename', 'profile_id': self.profile.pk + 1000, 'name': '新姓名',
        }, format='json')
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual((foreign.status_code, foreign.data), (missing.status_code, missing.data))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, '原姓名')

    def test_name_is_trimmed_and_must_have_1_to_120_characters(self):
        self.set_policy('owner_all')
        for name in ('　 ', '字' * 121, None, 42):
            with self.subTest(name=name):
                self.assertEqual(self.rename(name=name).status_code, 400)
        self.assertEqual(self.list_profiles()[self.profile.pk]['name'], '原姓名')
        max_name = '字' * 120
        self.assertEqual(self.rename(name=f' {max_name} ').status_code, 200)
        self.assertEqual(self.list_profiles()[self.profile.pk]['name'], max_name)

    def test_rename_requires_authenticated_session_and_csrf_token(self):
        self.set_policy('owner_all')
        api = APIClient(enforce_csrf_checks=True)
        path = self.profiles_path()
        payload = {'action': 'rename', 'profile_id': self.profile.pk, 'name': '新姓名'}
        self.assertEqual(api.get(path).status_code, 403)
        self.assertEqual(api.post(path, payload, format='json').status_code, 403)
        api.force_login(self.owner)
        self.assertEqual(api.get(path).status_code, 200)
        self.assertEqual(api.post(path, payload, format='json').status_code, 403)
        self.assertEqual(self.list_profiles()[self.profile.pk]['name'], '原姓名')
        self.assertEqual(api.post(path, payload, format='json', HTTP_X_CSRFTOKEN=api.cookies['csrftoken'].value).status_code, 200)
