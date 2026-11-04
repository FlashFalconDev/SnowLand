from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.memberships import member_profile
from Client.models import Client

from .loyalty import DEFAULT_RULES, checkout_rewards, get_loyalty_policy, release_unpaid_redemption, start_order_loyalty, sync_order_loyalty
from .models import MemberLoyaltyAccount, MemberLoyaltyEntry, MemberLoyaltyPolicy, OrderAmendment, OrderRevision, Reservation, ReservationGroup


class TenantLoyaltyTests(TestCase):
    def setUp(self):
        self.school = Client.objects.create(name='甲校', internal_code='school-a')
        self.other = Client.objects.create(name='乙校', internal_code='school-b')
        self.user = User.objects.create_user('member')
        self.referrer = User.objects.create_user('referrer')
        self.rules = {**DEFAULT_RULES, 'enabled': True, 'earn_on': 'paid'}
        self.policy = MemberLoyaltyPolicy.objects.create(client=self.school, revision=1, rules=self.rules)

    def order(self, status='created'):
        group = ReservationGroup.objects.create(client=self.school, user=self.user)
        Reservation.objects.create(group=group, status=status, payment_amount=1000)
        return group

    def test_tenant_configuration_is_versioned_and_member_cannot_write_it(self):
        api = APIClient()
        api.force_authenticate(User.objects.create_superuser('hq'))
        url = '/api/admin/school-a/customers/loyalty-policy/'
        changed = api.put(url, {**self.rules, 'revision': 1, 'rewards_per_twd': '0.05'}, format='json')
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(get_loyalty_policy(self.school)[0], 2)
        self.assertFalse(get_loyalty_policy(self.other)[1]['enabled'])
        self.assertEqual(api.put(url, {**self.rules, 'revision': 1}, format='json').status_code, 409)
        api.force_authenticate(self.user)
        self.assertEqual(api.put(url, {**self.rules, 'revision': 2}, format='json').status_code, 403)

    def test_payment_retry_and_partial_refund_use_the_original_rules(self):
        group = self.order()
        order = start_order_loyalty(group, 1, self.rules)
        for _ in range(2):
            sync_order_loyalty(group, confirmed_base=1000)
        self.assertEqual(order.entries.count(), 1)
        self.policy.rules = {**self.rules, 'points_per_twd': '9'}
        self.policy.save()
        for _ in range(2):
            sync_order_loyalty(group, refund=250)
        order.account.refresh_from_db()
        self.assertEqual((order.account.points, order.account.reward_balance), (750, 30))
        self.assertEqual(order.entries.count(), 2)
        self.assertFalse(MemberLoyaltyAccount.objects.filter(client=self.other).exists())

    def test_completion_award_and_confirmed_amendment_only(self):
        group = self.order()
        order = start_order_loyalty(group, 1, {**self.rules, 'earn_on': 'completed'})
        sync_order_loyalty(group, confirmed_base=1000)
        self.assertFalse(order.entries.exists())
        group.reservations.update(status='completed')
        sync_order_loyalty(group)
        order.account.refresh_from_db()
        self.assertEqual(order.account.points, 1000)
        revision = OrderRevision.objects.create(group=group, version=1)
        change = OrderAmendment.objects.create(group=group, revision=revision, request_key=uuid4(), request_fingerprint='qa',
            previous_total=1000, new_total=900, difference_amount=-100, balance_amount=-100, status='refund_due')
        sync_order_loyalty(group)
        order.account.refresh_from_db()
        self.assertEqual(order.account.points, 1000)
        change.status = 'settled'
        change.settled_at = timezone.now()
        change.save()
        sync_order_loyalty(group)
        order.account.refresh_from_db()
        self.assertEqual((order.account.points, order.account.reward_balance), (900, 36))

    def test_same_school_code_hold_and_restore_are_scoped(self):
        profile = member_profile(self.referrer, self.school)
        foreign = member_profile(self.referrer, self.other)
        MemberLoyaltyAccount.objects.create(client=self.school, user=self.user, reward_balance=60)
        summary = {'item_subtotals': [1000], 'item_discount_amounts': [100]}
        with self.assertRaises(ValueError):
            checkout_rewards(self.school, self.user, summary, 20, foreign.referral_code)
        revision, rules, allocations, _ = checkout_rewards(self.school, self.user, summary, 20, profile.referral_code)
        self.assertEqual(allocations[0]['discount'], 520)
        group = self.order()
        order = start_order_loyalty(group, revision, rules, **allocations[0])
        order.account.refresh_from_db()
        self.assertEqual(order.account.reward_balance, 40)
        for _ in range(2):
            release_unpaid_redemption(group)
        order.account.refresh_from_db()
        self.assertEqual(order.account.reward_balance, 60)
        self.assertEqual(MemberLoyaltyEntry.objects.filter(order=order).count(), 2)
