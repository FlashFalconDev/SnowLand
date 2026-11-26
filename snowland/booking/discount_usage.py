from uuid import uuid4

from django.db.models import Count, Q

from Coursekit.models import DiscountCode

from .models import OrderDiscountUsage, Reservation
from .order_testing import exclude_test_orders


def rebuild_discount_usage(tenant, rule_ids=None):
    """Reconcile under the tenant lock shared by checkout and archiving."""
    rules = DiscountCode.objects.select_for_update().filter(client=tenant)
    if rule_ids is not None:
        rules = rules.filter(pk__in=rule_ids)
    rules = list(rules.order_by('pk'))
    if not rules:
        return

    legacy = Reservation.all_objects.filter(
        Q(discount_code__gt='') | ~Q(discount_name__in=['', '會員紅利／推薦折抵']),
        group__client=tenant, discount_amount__gt=0, discount_usages__isnull=True,
    )
    # Historical counters only identify checkout totals. The original cart
    # boundaries cannot be reconstructed from individual reservation rows.
    legacy_is_archived = legacy.exists() and not legacy.live().exclude(status='deleted').exists()
    uses = exclude_test_orders(OrderDiscountUsage.objects.all(), 'reservation__group').filter(
        Reservation.live_filter('reservation'),
        reservation__group__client=tenant, rule_id__in=[rule.pk for rule in rules],
    ).exclude(reservation__status='deleted')
    active_counts = dict(uses.order_by().values('rule_id').annotate(
        count=Count('checkout_key', distinct=True),
    ).values_list('rule_id', 'count'))
    changed_rules = []
    for rule in rules:
        baseline = rule.legacy_used_count
        if baseline is None:
            baseline = rule.used_count
        total = active_counts.get(rule.pk, 0) + (0 if legacy_is_archived else baseline)
        if (total, baseline) != (rule.used_count, rule.legacy_used_count):
            rule.used_count = total
            rule.legacy_used_count = baseline
            changed_rules.append(rule)
    DiscountCode.objects.bulk_update(changed_rules, ['used_count', 'legacy_used_count'])


def record_checkout_discount_usage(tenant, reservation_rules):
    checkout_key = uuid4()
    uses = [
        OrderDiscountUsage(reservation_id=reservation_id, rule_id=rule_id, checkout_key=checkout_key)
        for reservation_id, rule_ids in reservation_rules.items()
        for rule_id in rule_ids
    ]
    if uses:
        OrderDiscountUsage.objects.bulk_create(uses)
        rebuild_discount_usage(tenant, {use.rule_id for use in uses})
