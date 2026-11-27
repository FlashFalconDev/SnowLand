"""Member reports and staff bookkeeping only. Never transfers money or changes original Payment."""
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from API.manual_notifications import NotificationConflict
from API.order_amendments import StrictInput, WholeNumber, amendment_digest
from Client.models import Client
from Client.tenant_settings import order_refund_charge_enabled
from .amendment_workflow import (
    ACTION_PERMISSIONS, CANCELLATION_STATUSES, REFUND_ACTIONS, apply_workflow, cash_amount,
    payment_allows_workflow, refund_event, require_workflow_access,
)
from .currency import PAYMENT_CURRENCY_CODES, foreign_currency
from .models import OrderAmendment, OrderAmendmentEvent, ReservationGroup


class RefundAccountInput(StrictInput):
    bank_name=serializers.CharField(max_length=100)
    account_number=serializers.CharField(max_length=80)
    account_holder=serializers.CharField(max_length=100)
    overseas_details=serializers.CharField(max_length=1000,required=False,allow_blank=True)


class BalanceActionInput(StrictInput):
    amendment_id=WholeNumber(min_value=1)
    request_key=serializers.UUIDField()
    expected_updated_at=serializers.DateTimeField()
    action=serializers.ChoiceField(choices=['report_topup','refund_account','confirm_topup','reject_topup','confirm_refund'])
    reference=serializers.RegexField(regex=r'^[0-9]{5}$',required=False,error_messages={'invalid':'請填寫匯款帳號末五碼（5位數字）'})
    bank=RefundAccountInput(required=False)
    note=serializers.CharField(max_length=1000,required=False)
    confirmed=serializers.BooleanField(required=False)
    currency=serializers.ChoiceField(choices=PAYMENT_CURRENCY_CODES,required=False)
    expected_amount=WholeNumber(min_value=0,max_value=9007199254740991,required=False)


def balance_data(row, *, staff=False):
    from .amendment_notifications import notice_receipt
    latest_event=row.events.exclude(action__in=ACTION_PERMISSIONS).order_by('-created_at','-pk').first()
    result={**({'settlement':row.currency_snapshot} if row.currency_snapshot else {}),'id':row.pk,'version':row.revision.version,'previous_total':row.previous_total,'new_total':row.new_total,
        'difference_amount':row.difference_amount,'balance_amount':row.balance_amount,'status':row.status,
        'updated_at':row.updated_at,'settled_at':row.settled_at,'bank_snapshot':row.bank_snapshot,
        'topup_reference':row.topup_reference,'refund_bank':row.refund_bank,'notification':notice_receipt(row,latest_event)}
    last_rejection=row.events.filter(action='reject_topup').order_by('-created_at','-pk').first() if row.status=='topup_due' else None
    result['review_message']=last_rejection.payload.get('note','') if last_rejection else ''
    if not staff and row.status in ('refund_account_due', 'refund_due'):
        current_refund = refund_event(row)
        result['refund_account_locked'] = bool(current_refund and current_refund.action == 'approve_refund')
    if staff:
        events = list(row.events.select_related('actor'))
        result['events'] = [
            {'action': event.action, 'previous_status': event.previous_status, 'status': event.status,
             'note': event.payload.get('note', ''), 'reference': event.payload.get('reference', ''),
             'external_reference': event.payload.get('external_reference', ''),
             'settlement': event.payload.get('settlement'), 'created_at': event.created_at,
             'actor': (event.actor.get_full_name() or event.actor.username) if event.actor else '已移除帳號'}
            for event in events
        ]
        result['refund_action'] = next((event.action for event in reversed(events) if event.action in REFUND_ACTIONS), None)
        result['topup_notified'] = any(event.action == 'mark_topup_notified' for event in events)
    return result


def group_balances(group, *, staff=False):
    return [balance_data(row,staff=staff) for row in group.amendments.select_related('revision').order_by('-created_at','-pk')]


@transaction.atomic
def process_balance(group, actor, data, *, staff=False, scope=None, workflow=False):
    Client.objects.select_for_update().get(pk=group.client_id)
    groups=ReservationGroup.objects.live().select_for_update().filter(client_id=group.client_id)
    groups=groups.filter(pk__in=scope.values('pk')) if staff else groups.filter(user=actor)
    group=get_object_or_404(groups,pk=group.pk)
    action = data['action']
    if workflow:
        require_workflow_access(actor, group.client, ACTION_PERMISSIONS[action])
    elif group.is_test:
        raise NotificationConflict('測試訂單不能進行正式差額核對')
    row=get_object_or_404(OrderAmendment.objects.select_for_update().select_related('revision'),group=group,pk=data['amendment_id'])
    fingerprint=amendment_digest({'group':group.pk,'actor':actor.pk,'staff':staff,'data':data})
    previous_event=OrderAmendmentEvent.all_objects.filter(request_key=data['request_key']).first()
    if previous_event:
        if previous_event.is_deleted or previous_event.amendment_id!=row.pk or previous_event.request_fingerprint!=fingerprint:
            raise NotificationConflict('此差額處理識別碼已使用，請重新載入')
        return row,True,previous_event
    payment=group.payments.live().order_by('-created_at','-pk').first()
    if not payment_allows_workflow(group, payment):
        raise NotificationConflict('原訂單付款狀態已變更，請聯絡 SnowLand 先核對原付款')
    if group.cancellation_requests.filter(status__in=CANCELLATION_STATUSES).exists():
        raise NotificationConflict('訂單已有取消／退款流程，請先由 SnowLand 核對，不會重複處理差額')
    if row.updated_at!=data['expected_updated_at']:raise NotificationConflict('差額狀態已更新，請重新載入後核對')
    settlement=row.currency_snapshot or {}
    if not workflow and foreign_currency(settlement.get('currency')):
        if data.get('currency')!=settlement['currency'] or data.get('expected_amount')!=abs(settlement['balance_amount']):
            raise NotificationConflict('請重新核對本筆差額的原幣及金額；這次未記錄收退款')
    elif not workflow and data.get('currency','TWD')!='TWD':
        raise NotificationConflict('此差額是台幣，請重新載入確認幣別後再處理')
    old=row.status
    if not staff and action not in {'report_topup','refund_account'}:raise PermissionDenied('會員只能回報補款或退款帳戶，不能自行核對結清')
    if set(data)&({'reference','bank'} if staff else {'note','confirmed'}):
        raise serializers.ValidationError({'action':'這項操作包含不適用的資料欄位，請重新載入後再試'})
    if workflow:
        apply_workflow(row, payment, data)
    elif staff:
        if action not in {'confirm_topup','reject_topup','confirm_refund'}:
            raise serializers.ValidationError({'action':'請使用會員入口回報匯款或退款帳戶'})
        if not data.get('note'):raise serializers.ValidationError({'note':'請留下核對依據或退回原因'})
        if action=='confirm_topup' and old=='topup_reported' and row.balance_amount>0:
            if not data.get('confirmed'):raise serializers.ValidationError({'confirmed':'請確認已在銀行查核到這筆補款，系統不會代收款'})
            row.status='settled'
        elif action=='reject_topup' and old=='topup_reported' and row.balance_amount>0:row.status='topup_due'
        elif action=='confirm_refund' and old=='refund_due' and row.balance_amount<0:
            if order_refund_charge_enabled(group.client) or row.events.filter(action__in=REFUND_ACTIONS).exists():
                raise PermissionDenied('請透過差額退款申請及審核流程記錄結果')
            if not data.get('confirmed'):raise serializers.ValidationError({'confirmed':'請確認已於系統外完成實際退款，這裡只記錄核對結果'})
            row.status='settled'
        else:raise NotificationConflict('目前差額狀態不能執行這項核對，請重新載入')
    else:
        if action=='report_topup' and old=='topup_due' and row.balance_amount>0:
            if not data.get('reference'):raise serializers.ValidationError({'reference':'請填寫匯款帳號末五碼'})
            row.topup_reference=data['reference'];row.status='topup_reported'
        elif action=='refund_account' and old in {'refund_account_due','refund_due'} and row.balance_amount<0:
            latest = refund_event(row)
            if latest and latest.action == 'approve_refund':
                raise NotificationConflict('差額退款已核准，退款帳戶暫停變更，請聯絡客服')
            if not data.get('bank'):raise serializers.ValidationError({'bank':'請填寫退款銀行、帳號及戶名'})
            row.refund_bank=data['bank'];row.status='refund_due'
        else:raise NotificationConflict('目前差額狀態不能回報此資料，請重新載入')
    row.updated_at=timezone.now()
    if row.status == 'settled':
        row.settled_at = row.updated_at
        row.settled_by = actor
    row.save(update_fields=['status','topup_reference','refund_bank','updated_at','settled_at','settled_by'])
    if row.status == 'settled':
        from .loyalty import sync_order_loyalty
        sync_order_loyalty(group)
    payload={key:data[key] for key in ('reference', 'bank', 'note', 'external_reference') if key in data}
    if settlement or workflow:
        currency, amount = cash_amount(row)
        payload['settlement']={'currency':currency,'amount':abs(amount),'rate':settlement.get('rate', '1.00000000'),
            'base_currency':'TWD','base_amount':abs(row.balance_amount),'recorded_at':row.updated_at.isoformat()}
    try:
        with transaction.atomic():
            event=OrderAmendmentEvent.objects.create(amendment=row,request_key=data['request_key'],request_fingerprint=fingerprint,
                actor=actor,action=action,previous_status=old,status=row.status,payload=payload)
    except IntegrityError:raise NotificationConflict('處理識別碼已使用，請重新載入確認；不會重複核對')
    if not workflow:
        from .amendment_notifications import prepare_amendment_notice
        prepare_amendment_notice(row,actor,event)
    return row,False,event
