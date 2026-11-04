from decimal import Decimal

from django.db.models import Sum

from Client.models import ClientMemberProfile

from .models import MemberLoyaltyAccount, MemberLoyaltyEntry, MemberLoyaltyPolicy, OrderLoyalty, Reservation, ReservationGroup


DEFAULT_RULES = {
    'enabled': False,
    'earn_on': 'completed',
    'points_per_twd': '1',
    'rewards_per_twd': '0.04',
    'twd_per_reward': '1',
    'referrer_rewards': 500,
    'new_member_rewards': 500,
    'refund_rule': 'proportional',
    'levels': [{'label': f'Lv{i:02}', 'minimum_points': amount}
               for i, amount in enumerate((10000, 50000, 100000, 300000, 500000), 1)],
}


def get_loyalty_policy(tenant):
    policy = MemberLoyaltyPolicy.objects.filter(client=tenant).first()
    return policy.revision if policy else 0, {**DEFAULT_RULES, **(policy.rules if policy else {})}


def level_label(account, rules):
    if not rules['enabled']:
        return ''
    return next((row['label'] for row in reversed(rules['levels']) if account.points >= row['minimum_points']), '')


def add_entry(order, account, kind, *, points=0, rewards=0):
    """Call with the account locked. A signed reward balance preserves refund debt."""
    if not (points or rewards):
        return
    if account.client_id != order.group.client_id:
        raise ValueError('不能跨學校變更紅利')
    account.points += points
    account.reward_balance += rewards
    account.save(update_fields=['points', 'reward_balance', 'updated_at'])
    MemberLoyaltyEntry.objects.create(account=account, order=order, kind=kind, points_delta=points, rewards_delta=rewards)


def start_order_loyalty(group, revision, rules, *, spent=0, discount=0, referrer_user_id=None):
    if not rules['enabled']:
        return None
    account, _ = MemberLoyaltyAccount.objects.select_for_update().get_or_create(client_id=group.client_id, user_id=group.user_id)
    referrer = None
    if referrer_user_id:
        referrer, _ = MemberLoyaltyAccount.objects.get_or_create(client_id=group.client_id, user_id=referrer_user_id)
    if spent and spent > account.reward_balance:
        raise ValueError('紅利餘額已變更，請重新試算')
    order = OrderLoyalty.objects.create(group=group, account=account, rules=rules, policy_revision=revision,
                                       rewards_spent=spent, discount_floor=discount, referrer=referrer)
    add_entry(order, account, 'redemption', rewards=-spent)
    return order


def checkout_rewards(tenant, user, summary, requested, referral_code):
    """Quote against the post-discount price. Recompute under the tenant lock at checkout."""
    revision, rules = get_loyalty_policy(tenant)
    if type(requested) is not int or not 0 <= requested <= 2147483647:
        raise ValueError('請輸入有效的折抵紅利整數')
    if not isinstance(referral_code, str) or len(referral_code) > 32:
        raise ValueError('推薦碼格式不正確')
    code = referral_code.strip().upper()
    available = 0
    if rules['enabled'] and user:
        balance = MemberLoyaltyAccount.objects.filter(client=tenant, user=user).values_list('reward_balance', flat=True).first()
        available = max(0, balance or 0)
    if (requested or code) and (not rules['enabled'] or not user):
        raise ValueError('請先登入並確認此學校已開放紅利方案')
    if not requested and not code:
        return revision, rules, [], available
    rate = Decimal(rules['twd_per_reward'])
    if requested and (not rate or requested > available):
        raise ValueError('可用紅利不足或此學校未開放折抵')
    referrer_id = None
    if code:
        if not (rules['referrer_rewards'] or rules['new_member_rewards']):
            raise ValueError('此學校尚未開放推薦活動')
        prior = ReservationGroup.objects.filter(client=tenant, user=user)
        if (prior.filter(payments__status__in=('paid', 'pending', 'refunded')).exists()
                or Reservation.objects.filter(group__in=prior).exclude(status__in=('cancelled', 'deleted')).exists()):
            raise ValueError('推薦碼限本校首次訂課使用')
        referrer_id = ClientMemberProfile.objects.filter(client=tenant, referral_code=code).exclude(user=user).values_list('user_id', flat=True).first()
        if not referrer_id:
            raise ValueError('找不到此學校的推薦碼')
    allocations = []
    units_left = requested
    for index, (subtotal, ordinary_discount) in enumerate(zip(summary['item_subtotals'], summary['item_discount_amounts'])):
        # The existing payment flow requires a positive cash balance for each order.
        capacity = max(0, subtotal - ordinary_discount - 1)
        referral_discount = min(capacity, int(rules['new_member_rewards'] * rate)) if referrer_id and index == 0 else 0
        capacity -= referral_discount
        spent = min(units_left, int(Decimal(capacity) / rate)) if units_left else 0
        discount = int(spent * rate)
        if not discount:
            spent = 0
        units_left -= spent
        allocations.append({'spent': spent, 'discount': discount + referral_discount,
                            'referrer_user_id': referrer_id if index == 0 else None})
    if units_left:
        raise ValueError('本次折抵超過可折抵金額，或換算後不足新台幣 1 元')
    return revision, rules, allocations, available


def sync_order_loyalty(group, *, confirmed_base=None, refund=None, actual_received_amount=None):
    """Reconcile one order under its caller's order lock and transaction."""
    order = OrderLoyalty.objects.select_for_update().filter(group=group).first()
    if order is None:
        return
    if refund is None and group.cancellation_requests.filter(status='refunded').exists():
        return
    if order.paid_base is None and confirmed_base is not None:
        order.paid_base = confirmed_base
    if order.paid_base is None:
        return
    rules = order.rules
    amendments = group.amendments.filter(status='settled', settled_at__isnull=False)
    eligible = rules['earn_on'] == 'paid' or (
        group.reservations.filter(status='completed').exists()
        and not group.reservations.exclude(status__in=('completed', 'cancelled', 'deleted')).exists()
    )
    if refund is not None:
        # A cancellation can mark all reservations cancelled after they earned points.
        eligible = eligible or bool(order.points_earned or order.rewards_earned or order.referral_earned)
    if eligible or refund is not None:
        accounts = {row.pk: row for row in MemberLoyaltyAccount.objects.select_for_update().filter(
            pk__in=[order.account_id, order.referrer_id],
        ).order_by('pk')}
        account = accounts[order.account_id]
        confirmed_adjustments = amendments.aggregate(total=Sum('balance_amount'))['total'] or 0
        cash_received = (actual_received_amount if refund is not None and actual_received_amount is not None
                         else max(0, order.paid_base + confirmed_adjustments))
        if rules['refund_rule'] == 'proportional':
            net = max(0, cash_received - (refund or 0))
        else:
            adjustment = amendments.filter(balance_amount__gt=0).aggregate(total=Sum('balance_amount'))['total'] or 0
            net = order.paid_base + adjustment
        points = int(net * Decimal(rules['points_per_twd'])) if eligible else 0
        rewards = int(net * Decimal(rules['rewards_per_twd'])) if eligible else 0
        add_entry(order, account, 'refund' if refund is not None or net < order.paid_base else 'purchase',
                  points=points - order.points_earned, rewards=rewards - order.rewards_earned)
        order.points_earned = points
        order.rewards_earned = rewards
        if order.referrer_id and eligible:
            referral = rules['referrer_rewards']
            if refund is not None and rules['refund_rule'] == 'proportional':
                referral = referral * net // cash_received if cash_received else 0
            add_entry(order, accounts[order.referrer_id], 'referral', rewards=referral - order.referral_earned)
            order.referral_earned = referral
        if refund is not None and cash_received:
            restore = order.rewards_spent * min(refund, cash_received) // cash_received
            if restore > order.rewards_restored:
                add_entry(order, account, 'return_redemption', rewards=restore - order.rewards_restored)
                order.rewards_restored = restore
    order.save(update_fields=['paid_base', 'points_earned', 'rewards_earned', 'referral_earned', 'rewards_restored'])


def release_unpaid_redemption(group):
    order = OrderLoyalty.objects.select_for_update().filter(group=group, paid_base__isnull=True).first()
    if order and order.rewards_spent > order.rewards_restored:
        account = MemberLoyaltyAccount.objects.select_for_update().get(pk=order.account_id)
        add_entry(order, account, 'release_redemption', rewards=order.rewards_spent - order.rewards_restored)
        order.rewards_restored = order.rewards_spent
        order.save(update_fields=['rewards_restored'])
