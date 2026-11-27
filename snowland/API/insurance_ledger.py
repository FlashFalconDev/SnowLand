from datetime import date
from decimal import Decimal

from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from booking.insurance_ledger import (
    Kind, account_for_update, deposit, entry_change, ledger_writable, month_bounds,
    reconciliation_totals, replay_entry, require_writable, reverse_entry,
)
from booking.models import InsuranceLedgerEntry, InsurancePrepaidAccount, InsuranceReconciliation
from Client.models import Client
from Client.tenant_settings import insurance_ledger_settings
from Control.tenant_memberships import staff_profile

from .admin_permissions import user_has_admin_permission
from .admin_views import IsTenantManager
from .order_amendments import StrictInput, amendment_digest
from .payroll_security import PayrollCsrfMixin


class DepositInput(StrictInput):
    kind = serializers.ChoiceField(choices=[Kind.OPENING, Kind.TOP_UP])
    amount = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=Decimal('0.01'))
    reference = serializers.CharField(max_length=200)
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    idempotency_key = serializers.UUIDField()


class ReversalInput(StrictInput):
    reference = serializers.CharField(max_length=200)
    note = serializers.CharField(max_length=1000)
    idempotency_key = serializers.UUIDField()


class MonthInput(StrictInput):
    month = serializers.RegexField(r'^[0-9]{4}-(0[1-9]|1[0-2])\Z')

    def validate_month(self, value):
        try:
            month = date.fromisoformat(f'{value}-01')
        except ValueError:
            raise ValidationError('請輸入有效年月。')
        if not 1900 <= month.year < 9999:
            raise ValidationError('請輸入有效年月。')
        return month


class ConfirmMonthInput(MonthInput):
    cutoff_sequence = serializers.IntegerField(min_value=0)
    statement_balance = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=Decimal('0.00'))
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)


def validated(serializer_class, data):
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def money(value):
    return format(value, '.2f')


def actor_name(actor):
    return actor.get_full_name() or actor.username


def entry_data(entry, reversed_ids=()):
    return {
        'id': entry.pk, 'sequence': entry.sequence, 'kind': entry.kind,
        'amount': money(entry_change(entry.kind, entry.amount, entry.reverses)),
        'balance_after': money(entry.balance_after), 'created_at': entry.created_at,
        'actor': actor_name(entry.actor), 'reference': entry.reference, 'note': entry.note,
        'member_id': entry.member_record_id, 'order_id': entry.order_id,
        'reverses_id': entry.reverses_id, 'reversed': entry.pk in reversed_ids,
    }


def month_data(month, totals, snapshot=None):
    return {
        'month': month.strftime('%Y-%m'), 'cutoff_sequence': totals['cutoff_sequence'],
        **{key: money(totals[key]) for key in ('opening', 'top_ups', 'deductions', 'reversals', 'closing')},
        'confirmed_at': snapshot.confirmed_at if snapshot else None,
        'confirmed_by': actor_name(snapshot.confirmed_by) if snapshot else None,
        'note': snapshot.note if snapshot else '',
    }


def saved_month_data(snapshot):
    keys = ('opening', 'top_ups', 'deductions', 'reversals', 'closing', 'cutoff_sequence')
    return month_data(snapshot.month, {key: getattr(snapshot, key) for key in keys}, snapshot)


def reconciliation_data(account, month):
    snapshot = account.reconciliations.filter(month=month).select_related('confirmed_by').first()
    return saved_month_data(snapshot) if snapshot else month_data(month, reconciliation_totals(account, month))


class InsuranceLedgerAdminViewSet(PayrollCsrfMixin, GenericViewSet):
    permission_classes = [IsTenantManager]
    permission_key = 'insurance_ledger_finance'

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        profile = staff_profile(request.user, request.tenant)
        if (not profile or profile.role != 'hq_admin' or profile.all_campuses is False
                or not request.can_view_all_campuses or request.selected_campus_id is not None
                or not user_has_admin_permission(request.user, self.permission_key, request.tenant)):
            raise PermissionDenied('請由已獲授權的總部財務選擇全部校區後查閱或操作帳本。')

    def list(self, request, *args, **kwargs):
        config = insurance_ledger_settings(request.tenant)
        today = timezone.localdate(timezone=timezone.get_default_timezone())
        month = validated(MonthInput, {'month': request.query_params.get('month', today.strftime('%Y-%m'))})['month']
        page_number = validated(PageInput, {'page': request.query_params.get('page', 1)})['page']
        account = InsurancePrepaidAccount.objects.filter(client=request.tenant).first()
        page = None
        entries = []
        if account:
            start, end = month_bounds(month)
            rows = account.entries.filter(created_at__gte=start, created_at__lt=end).select_related(
                'actor', 'reverses',
            ).order_by('-sequence')
            page = Paginator(rows, 50).get_page(page_number)
            reversed_ids = set(account.entries.filter(
                reverses_id__in=[entry.pk for entry in page],
            ).values_list('reverses_id', flat=True))
            entries = [entry_data(entry, reversed_ids) for entry in page]
        return Response({'code': 200, 'data': {
            'enabled': config.enabled,
            'writable': ledger_writable(config, account),
            'currency': account.currency if account else config.currency,
            'balance': money(account.balance) if account else None,
            'low_balance': bool(account and config.low_balance is not None and account.balance <= config.low_balance),
            'entries': entries, 'page': page.number if page else 1,
            'pages': page.paginator.num_pages if page else 1,
            'can_confirm_month': bool(account and ledger_writable(config, account) and month < today.replace(day=1)),
        }})

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def deposits(self, request, *args, **kwargs):
        data = validated(DepositInput, request.data)
        config, account = self.locked_account()
        fingerprint = self.fingerprint('deposit', data)
        entry = replay_entry(request.tenant, data['idempotency_key'], fingerprint)
        if entry is None:
            entry = deposit(request.tenant, account, config, request.user, data, fingerprint)
        return Response({'code': 200, 'data': entry_data(entry)})

    @action(detail=False, methods=['post'], url_path=r'entries/(?P<entry_id>[0-9]+)/reverse')
    @transaction.atomic
    def reverse(self, request, entry_id, *args, **kwargs):
        data = validated(ReversalInput, request.data)
        config, account = self.locked_account()
        fingerprint = self.fingerprint('reverse', {**data, 'entry_id': entry_id})
        entry = replay_entry(request.tenant, data['idempotency_key'], fingerprint)
        if entry is None:
            require_writable(config, account)
            target = get_object_or_404(InsuranceLedgerEntry, account=account, pk=entry_id)
            entry = reverse_entry(account, target, request.user, key=data['idempotency_key'],
                                  fingerprint=fingerprint, reference=data['reference'], note=data['note'])
        return Response({'code': 200, 'data': entry_data(entry)})

    @action(detail=False, methods=['get', 'post'])
    @transaction.atomic
    def reconciliation(self, request, *args, **kwargs):
        if request.method == 'GET':
            month = validated(MonthInput, {'month': request.query_params.get('month')})['month']
            account = get_object_or_404(InsurancePrepaidAccount, client=request.tenant)
            return Response({'code': 200, 'data': reconciliation_data(account, month)})
        data = validated(ConfirmMonthInput, request.data)
        config, account = self.locked_account()
        require_writable(config, account)
        if account is None:
            raise ValidationError({'msg': '請先開立預付保費帳戶。'})
        month = data['month']
        if month >= timezone.localdate(timezone=timezone.get_default_timezone()).replace(day=1):
            raise ValidationError({'msg': '請於月份結束後確認對帳。'})
        snapshot = account.reconciliations.filter(month=month).select_related('confirmed_by').first()
        if snapshot:
            if data['cutoff_sequence'] != snapshot.cutoff_sequence or data['statement_balance'] != snapshot.closing:
                raise ValidationError({'msg': '本月已確認，請查看已保存的快照。'})
            return Response({'code': 200, 'data': saved_month_data(snapshot)})
        totals = reconciliation_totals(account, month)
        if data['cutoff_sequence'] != totals['cutoff_sequence'] or data['statement_balance'] != totals['closing']:
            raise ValidationError({'msg': '分錄已變更或對帳單餘額不符，請重新產生快照並核對。'})
        snapshot = InsuranceReconciliation.objects.create(
            account=account, month=month, confirmed_by=request.user, note=data.get('note', ''), **totals,
        )
        return Response({'code': 200, 'data': saved_month_data(snapshot)})

    def locked_account(self):
        client = Client.objects.select_for_update().get(pk=self.request.tenant.pk)
        return insurance_ledger_settings(client), account_for_update(client)

    def fingerprint(self, operation, data):
        return amendment_digest({'operation': operation, 'actor': self.request.user.pk, 'data': data})


class PageInput(serializers.Serializer):
    page = serializers.IntegerField(min_value=1)
