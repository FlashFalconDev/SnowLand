"""Staff workflow for collecting or refunding a frozen order amendment."""
from urllib.parse import urlencode

from django.core import signing
from django.db.models import OuterRef, Subquery
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from API.admin_permissions import user_has_admin_permission
from API.manual_notifications import NotificationConflict
from API.order_amendments import StrictInput, WholeNumber
from Client.tenant_settings import order_refund_charge_enabled
from Control.tenant_memberships import staff_profile
from .currency import PAYMENT_CURRENCY_CODES, foreign_currency, order_settlement, received_settlement_summary
from .models import OrderAmendment, OrderAmendmentEvent, OrderLoyalty
from .payment_access import PAYMENT_LINK_MAX_AGE


ACTION_PERMISSIONS = {
    'mark_topup_notified': 'order_charge_operate',
    'record_topup': 'order_charge_operate',
    'request_refund': 'order_amendment_refund_request',
    'approve_refund': 'order_amendment_refund_review',
    'reject_refund': 'order_amendment_refund_review',
    'record_refund': 'order_amendment_refund_review',
}
REFUND_ACTIONS = ('request_refund', 'approve_refund', 'reject_refund', 'record_refund')
ACTIVE_REFUND_ACTIONS = ('request_refund', 'approve_refund')
TOPUP_STATUSES = ('topup_due', 'topup_reported')
REFUND_STATUSES = ('refund_account_due', 'refund_due')
PENDING_STATUSES = TOPUP_STATUSES + REFUND_STATUSES
TOPUP_LINK_SALT = 'snowland-guest-amendment-topup-v1'
CANCELLATION_STATUSES = ('requested', 'approved', 'refunded')


class WorkflowInput(StrictInput):
    amendment_id = WholeNumber(min_value=1)
    request_key = serializers.UUIDField()
    expected_updated_at = serializers.DateTimeField()
    action = serializers.ChoiceField(choices=ACTION_PERMISSIONS)
    currency = serializers.ChoiceField(choices=PAYMENT_CURRENCY_CODES)
    expected_amount = WholeNumber(min_value=1, max_value=9007199254740991)
    note = serializers.CharField(max_length=1000)
    external_reference = serializers.CharField(max_length=100, required=False)
    confirmed = serializers.BooleanField(required=False)

    def validate(self, data):
        if data['action'] in ('record_topup', 'record_refund'):
            if not data.get('confirmed') or not data.get('external_reference'):
                raise serializers.ValidationError({'external_reference': '請填寫外部交易參考，並確認已查核實際收退款'})
        elif data['action'] == 'reject_refund':
            if not data.get('confirmed') or 'external_reference' in data:
                raise serializers.ValidationError({'confirmed': '請確認尚未退款，再駁回差額退款'})
        elif 'confirmed' in data or 'external_reference' in data:
            raise serializers.ValidationError({'action': '外部交易資料只適用於記錄實際收退款'})
        return data


def require_workflow_access(actor, client, permission):
    if not order_refund_charge_enabled(client):
        raise PermissionDenied('此租戶尚未啟用訂單補款與退款工作流')
    profile = staff_profile(actor, client)
    if (not profile or profile.role in ('coach', 'campus_manager', 'campus_principal')
            or not all(user_has_admin_permission(actor, key, client) for key in ('order_payments', permission))):
        raise PermissionDenied('需要本項差額操作權限')


def cash_amount(row):
    snapshot = row.currency_snapshot or {}
    return snapshot.get('currency', 'TWD'), snapshot.get('balance_amount', row.balance_amount)


def matches_order_currency(group, currency):
    return (group.currency_snapshot or {}).get('currency', 'TWD') == currency


def refund_event(row):
    return row.events.filter(action__in=REFUND_ACTIONS).order_by('-created_at', '-pk').first()


def refund_progress(rows):
    events = OrderAmendmentEvent.objects.filter(amendment_id=OuterRef('pk'), action__in=REFUND_ACTIONS)
    return rows.annotate(refund_action=Subquery(events.order_by('-created_at', '-pk').values('action')[:1]))


def active_refunds(group):
    return refund_progress(group.amendments.filter(status__in=REFUND_STATUSES)).filter(
        refund_action__in=ACTIVE_REFUND_ACTIONS,
    )


def workflow_filter(value):
    rows = OrderAmendment.objects.all()
    if value == 'topup':
        return rows.filter(status__in=TOPUP_STATUSES)
    if value in REFUND_ACTIONS:
        return refund_progress(rows).filter(
            status__in=('settled',) if value == 'record_refund' else REFUND_STATUSES,
            refund_action=value,
        )
    if value == 'refund':
        return rows.filter(status__in=REFUND_STATUSES)
    return rows.none()


def can_rehearse(group, payment):
    return group.is_test and payment and payment.status in ('unpaid', 'paid')


def payment_allows_workflow(group, payment):
    return bool((payment and payment.status == 'paid') or can_rehearse(group, payment))


def has_opposite_balance(row, amount):
    statuses = REFUND_STATUSES if amount > 0 else TOPUP_STATUSES
    return row.group.amendments.exclude(pk=row.pk).filter(status__in=statuses).exists()


def topup_is_payable(row):
    group = row.group
    payment = group.payments.live().order_by('-created_at', '-pk').first()
    currency, amount = cash_amount(row)
    return (
        row.status == 'topup_due' and amount > 0 and payment_allows_workflow(group, payment)
        and matches_order_currency(group, currency)
        and group.reservations.live().exclude(status__in=('cancelled', 'deleted')).exists()
        and not group.cancellation_requests.filter(status__in=CANCELLATION_STATUSES).exists()
        and not has_opposite_balance(row, amount)
        and all(row.bank_snapshot.get(key) for key in ('bank_name', 'account_number', 'account_holder'))
    )


def topup_path(row):
    group = row.group
    if not topup_is_payable(row):
        raise NotificationConflict('此筆差額目前無法提供補款連結')
    if group.is_test:
        raise NotificationConflict('測試訂單只可在後台演練')
    prefix = f'/{group.client.internal_code}'
    if group.user_id:
        return f'{prefix}/membership/orders/{group.pk}#amendment-{row.pk}'
    token = signing.dumps((group.client_id, group.pk, row.pk), salt=TOPUP_LINK_SALT)
    return f'{prefix}/amendment-topup/{group.pk}/{row.pk}#{urlencode({"access": token})}'


def valid_topup_token(tenant, group_id, amendment_id, token):
    try:
        return signing.loads(token, salt=TOPUP_LINK_SALT, max_age=PAYMENT_LINK_MAX_AGE) == [tenant.pk, group_id, amendment_id]
    except (signing.BadSignature, ValueError, TypeError):
        return False


def available_refund(group, payment, currency):
    """Original receipt plus settled adjustments in the receipt currency."""
    receipt = received_settlement_summary(group)
    if receipt:
        if receipt['currency'] != currency:
            return 0
        original = receipt['amount']
    elif group.is_test:
        first = group.amendments.exclude(status='included_in_order').order_by('revision__version').first()
        original = order_settlement(group, base_amount=first.previous_total)['amount'] if first else 0
    elif foreign_currency(currency):
        return 0
    else:
        # Older TWD payments may lack a receipt snapshot. Prefer the accounting
        # record or bank/gateway evidence over the first paid amendment's total.
        original = OrderLoyalty.objects.filter(group=group).values_list('paid_base', flat=True).first()
        payload = payment.DataJSON if isinstance(payment.DataJSON, dict) else {}
        gateway = payload.get('gateway_response')
        result = gateway.get('Result') if isinstance(gateway, dict) else None
        amount = str(result.get('Amt', '')) if isinstance(result, dict) else ''
        if amount.isascii() and amount.isdecimal() and len(amount) <= 16:
            original = int(amount)
        if original is None:
            original = group.amendments.exclude(status='included_in_order').order_by(
                'revision__version',
            ).values_list('previous_total', flat=True).first()
    if type(original) is not int or original <= 0:
        return 0
    total = original
    for adjustment in group.amendments.filter(status='settled', settled_at__isnull=False):
        adjustment_currency, amount = cash_amount(adjustment)
        if adjustment_currency != currency or type(amount) is not int:
            return 0
        total += amount
    return max(0, total)


def apply_workflow(row, payment, data):
    """Validate and set the status while the caller holds the order lock."""
    action = data['action']
    currency, amount = cash_amount(row)
    if not matches_order_currency(row.group, currency):
        raise NotificationConflict('差額缺少與訂單一致的原幣紀錄，請先核對原單')
    if not row.group.reservations.live().exclude(status__in=('cancelled', 'deleted')).exists():
        raise NotificationConflict('訂單已沒有可處理的課程，請核對取消狀態')
    if data['currency'] != currency or data['expected_amount'] != abs(amount):
        raise serializers.ValidationError({'expected_amount': '請輸入此筆差額的完整金額及原幣幣別。同一筆差額不能分批處理'})
    if has_opposite_balance(row, amount):
        raise NotificationConflict('訂單同時有待補款和待退款，請先核對差額')
    if 'external_reference' in data and OrderAmendmentEvent.objects.filter(
        amendment__group=row.group, action=action, payload__external_reference=data['external_reference'],
    ).exists():
        raise NotificationConflict('此訂單已記錄相同的外部交易參考，請核對實際收退款')
    if action in ('mark_topup_notified', 'record_topup'):
        if row.status not in TOPUP_STATUSES or amount <= 0:
            raise NotificationConflict('此筆差額目前無法處理補款')
        if action == 'mark_topup_notified':
            if row.status != 'topup_due' or row.events.filter(action=action).exists():
                raise NotificationConflict('此筆差額已通知或已進入核對')
        else:
            if row.group.user_id and not row.group.is_test and row.status != 'topup_reported':
                raise NotificationConflict('請先由會員在會員專區回報補款')
            row.status = 'settled'
        return

    latest = refund_event(row)
    previous = latest.action if latest else None
    allowed = {
        'request_refund': (None, 'reject_refund'),
        'approve_refund': ('request_refund',),
        'reject_refund': ('request_refund', 'approve_refund'),
        'record_refund': ('approve_refund',),
    }
    if row.status not in REFUND_STATUSES or amount >= 0 or previous not in allowed[action]:
        raise NotificationConflict('目前差額狀態不能執行這項退款操作')
    if action != 'reject_refund':
        if active_refunds(row.group).exclude(pk=row.pk).exists():
            raise NotificationConflict('此訂單已有其他差額退款處理中')
        if abs(amount) > available_refund(row.group, payment, currency):
            raise NotificationConflict('退款金額超過可確認的實收餘額，請先核對原收款及已結清差額')
    if action == 'record_refund':
        row.status = 'settled'
