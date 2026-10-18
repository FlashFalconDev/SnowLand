from django.contrib.auth.models import User
from django.test import TestCase
from django.apps import apps
from django.db import connection
from importlib import import_module
from rest_framework.test import APIClient

from Client.models import Client
from Resorts.models import Campus
from booking.models import MemberLoyaltyAccount, MemberLoyaltyReview, MemberProfile, ReservationGroup


class MemberLoyaltyTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.other = Client.objects.create(name='Other', internal_code='other')
        self.campus = Campus.objects.create(client=self.tenant, code='a', name='A')
        self.root = User.objects.create_superuser('root', 'root@example.test', 'test-password')
        self.member = User.objects.create_user('old-student', 'old@example.test', 'test-password')
        self.account = MemberLoyaltyAccount.objects.create(client=self.tenant, user=self.member, points=20)
        self.api = APIClient()
        self.api.force_authenticate(self.root)
        self.url = f'/api/admin/snowland/customers/{self.member.pk}/loyalty/'

    def payload(self, **changes):
        self.account.refresh_from_db()
        return {'alumni_verified': True, 'previous_points': 100, 'reason': 'QA核對舊季紀錄',
                'expected_updated_at': self.account.updated_at.isoformat(), **changes}

    def test_registered_member_without_order_can_be_reviewed_and_sees_result(self):
        listed = self.api.get('/api/admin/snowland/customers/')
        self.assertIn(self.member.pk, [item['id'] for item in listed.data['data']['list']])
        result = self.api.post(self.url, self.payload(), format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['data']['points'], 120)
        self.assertEqual(result.data['data']['level'], 'alumni')
        self.assertEqual(len(result.data['data']['history']), 1)
        member_api = APIClient(); member_api.force_authenticate(self.member)
        summary = member_api.get('/booking/snowland/api/member-center/')
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertTrue(summary.data['alumni_verified'])
        self.assertEqual(summary.data['points'], 120)
        self.assertEqual(summary.data['previous_points'], 100)
        self.assertNotIn('history', summary.data)

    def test_total_replacement_not_repeated_increment_and_preserves_other_points(self):
        self.assertEqual(self.api.post(self.url, self.payload(), format='json').status_code, 200)
        self.assertEqual(self.api.post(self.url, self.payload(), format='json').status_code, 200)
        self.assertEqual(MemberLoyaltyReview.objects.count(), 1)
        self.assertEqual(self.api.post(self.url, self.payload(previous_points=50), format='json').status_code, 200)
        self.account.refresh_from_db(); self.assertEqual(self.account.points, 70)
        audit = self.account.reviews.first()
        self.assertEqual(audit.before['points'], 120); self.assertEqual(audit.after['points'], 70)
        self.assertEqual(audit.reviewed_by, self.root)

    def test_invalid_values_cannot_change_status_points_or_audit(self):
        invalid = [dict(previous_points=x) for x in [-1, 0.5, True, '1.0', '１', 2147483648, None]]
        invalid += [{'reason': ''}, {'alumni_verified': False}, {'expected_updated_at': ''}]
        for changes in invalid:
            result = self.api.post(self.url, self.payload(**changes), format='json')
            self.assertEqual(result.status_code, 400, result.data)
        self.account.refresh_from_db()
        self.assertEqual(self.account.points, 20); self.assertFalse(self.account.alumni_verified)
        self.assertEqual(self.account.reviews.count(), 0)

    def test_stale_form_cannot_override_another_review(self):
        stale = self.payload()
        self.api.post(self.url, self.payload(), format='json')
        result = self.api.post(self.url, {**stale, 'previous_points': 200}, format='json')
        self.assertEqual(result.status_code, 409)
        self.account.refresh_from_db(); self.assertEqual(self.account.points, 120)

    def test_member_coach_and_campus_manager_cannot_review(self):
        for role in ('', 'coach', 'campus_manager'):
            user = User.objects.create_user('role-'+(role or 'member'), password='test-password')
            profile = user.userprofile
            profile.is_manager = role == 'campus_manager'; profile.is_coach = role == 'coach'
            profile.manager_client = self.tenant if profile.is_manager else None
            profile.role = role; profile.admin_permissions = ['customers']; profile.save()
            profile.campuses.add(self.campus)
            self.api.force_authenticate(user)
            self.assertEqual(self.api.post(self.url, self.payload(), format='json').status_code, 403)
        self.assertEqual(self.account.reviews.count(), 0)

    def test_hq_still_needs_customers_permission(self):
        user = User.objects.create_user('hq', password='test-password')
        profile = user.userprofile; profile.role = 'hq_admin'; profile.is_manager = True
        profile.manager_client = self.tenant; profile.admin_permissions = []; profile.save()
        self.api.force_authenticate(user)
        self.assertEqual(self.api.post(self.url, self.payload(), format='json').status_code, 403)
        profile.admin_permissions = ['customers']; profile.save()
        self.assertEqual(self.api.post(self.url, self.payload(), format='json').status_code, 200)

    def test_other_school_and_selected_campus_never_expose_unassociated_members(self):
        other_member = User.objects.create_user('outsider')
        MemberLoyaltyAccount.objects.create(client=self.other, user=other_member, points=800)
        result = self.api.get('/api/admin/snowland/customers/')
        self.assertNotIn(other_member.pk, [item['id'] for item in result.data['data']['list']])
        self.assertEqual(self.api.post(f'/api/admin/snowland/customers/{other_member.pk}/loyalty/', self.payload(), format='json').status_code, 404)
        self.assertEqual(self.api.get(self.url, HTTP_X_CAMPUS_ID=str(self.campus.pk)).status_code, 404)
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus, user=self.member)
        self.assertEqual(self.api.get(self.url, HTTP_X_CAMPUS_ID=str(self.campus.pk)).status_code, 200)

    def test_shared_login_points_and_verification_are_tenant_scoped(self):
        self.api.post(self.url, self.payload(), format='json')
        member_api = APIClient(); member_api.force_authenticate(self.member)
        other = member_api.get('/booking/other/api/member-center/')
        self.assertEqual(other.status_code, 200, other.data)
        self.assertEqual(other.data['points'], 0); self.assertFalse(other.data['alumni_verified'])
        self.assertEqual(MemberLoyaltyAccount.objects.filter(user=self.member).count(), 2)

    def test_unreviewing_requires_removing_old_total_but_not_other_points(self):
        self.api.post(self.url, self.payload(), format='json')
        self.assertEqual(self.api.post(self.url, self.payload(alumni_verified=False, previous_points=0), format='json').status_code, 200)
        self.account.refresh_from_db(); self.assertEqual(self.account.points, 20)
        self.assertEqual(self.account.level, 'new'); self.assertFalse(self.account.alumni_verified)

    def test_csrf_is_required_even_with_forced_authentication(self):
        client = APIClient(enforce_csrf_checks=True); client.force_authenticate(self.root)
        self.assertEqual(client.post(self.url, self.payload(), format='json').status_code, 403)

    def test_member_center_creates_only_current_tenant_account(self):
        new_member = User.objects.create_user('new-no-order')
        member_api = APIClient(); member_api.force_authenticate(new_member)
        result = member_api.get('/booking/snowland/api/member-center/')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(MemberLoyaltyAccount.objects.filter(client=self.tenant, user=new_member).exists())
        self.assertFalse(MemberLoyaltyAccount.objects.filter(client=self.other, user=new_member).exists())

    def test_backfill_copies_only_unambiguous_ownership_and_is_idempotent(self):
        exclusive = User.objects.create_user('exclusive-history')
        ambiguous = User.objects.create_user('ambiguous-history')
        unassociated = User.objects.create_user('unassociated-history')
        for user in (exclusive, ambiguous, unassociated):
            MemberProfile.objects.create(user=user, points=80, previous_points=60, alumni_verified=True, level='alumni')
        ReservationGroup.objects.create(client=self.tenant, user=exclusive)
        ReservationGroup.objects.create(client=self.tenant, user=ambiguous)
        ReservationGroup.objects.create(client=self.other, user=ambiguous)
        migrate = import_module('booking.migrations.0030_member_loyalty_accounts').migrate_unambiguous_profiles
        class Editor:
            pass
        editor = Editor(); editor.connection = connection
        migrate(apps, editor); migrate(apps, editor)
        account = MemberLoyaltyAccount.objects.get(user=exclusive)
        self.assertEqual(account.client, self.tenant)
        self.assertEqual((account.points, account.previous_points, account.alumni_verified), (80, 60, True))
        self.assertFalse(MemberLoyaltyAccount.objects.filter(user__in=[ambiguous, unassociated]).exists())
        self.assertEqual(MemberProfile.objects.get(user=ambiguous).points, 80)
        self.assertEqual(MemberProfile.objects.get(user=unassociated).points, 80)

    def test_existing_higher_tier_not_overwritten_and_total_cannot_overflow(self):
        self.account.level='gold'; self.account.points=2147483640; self.account.save()
        self.assertEqual(self.api.post(self.url, self.payload(), format='json').status_code, 400)
        self.assertEqual(self.api.post(self.url, self.payload(previous_points=0), format='json').status_code, 200)
        self.account.refresh_from_db(); self.assertEqual(self.account.level, 'gold')
