from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from Coach.models import StaffIncentiveLine, StaffIncentiveRule, StaffIncentiveStatement
from Coach.staff_incentives import (
    adjust_staff_incentive, calculate_staff_incentive, confirm_staff_incentive,
    delete_staff_incentive_draft, mark_staff_incentive_paid,
)
from Resorts.models import Campus
from .admin_views import IsTenantManager, _campus_ids, wrap_list
from .payroll_security import PayrollCsrfMixin


class StaffIncentiveLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffIncentiveLine
        fields = ['id', 'line_type', 'order_number', 'event_date', 'base_amount', 'percent', 'amount', 'source_line', 'cancellation']
        read_only_fields = fields


class StaffIncentiveStatementSerializer(serializers.ModelSerializer):
    lines = StaffIncentiveLineSerializer(many=True, read_only=True)
    currency = serializers.SerializerMethodField()

    def get_currency(self, obj):
        return 'TWD'

    class Meta:
        model = StaffIncentiveStatement
        fields = ['id', 'user', 'user_name', 'campus', 'campus_name', 'month', 'percent', 'currency',
                  'revenue', 'earned_amount', 'refund_deduction', 'adjustment', 'adjustment_note',
                  'total_amount', 'status', 'confirmed_at', 'confirmed_by', 'paid_at', 'paid_by',
                  'created_at', 'updated_at', 'lines']
        read_only_fields = fields


class CalculateInput(serializers.Serializer):
    user = serializers.IntegerField(min_value=1)
    campus = serializers.IntegerField(min_value=1)
    month = serializers.DateField()


class AdjustInput(serializers.Serializer):
    amount = serializers.IntegerField(min_value=-2147483648, max_value=2147483647)
    note = serializers.CharField(max_length=300)


class AcknowledgeInput(serializers.Serializer):
    accepted = serializers.BooleanField()
    expected_updated_at = serializers.DateTimeField()


class StaffIncentiveStatementAdminViewSet(PayrollCsrfMixin, ModelViewSet):
    serializer_class = StaffIncentiveStatementSerializer
    permission_classes = [IsTenantManager]
    permission_key = 'payroll'
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def _campuses(self):
        qs = Campus.objects.filter(client=self.request.tenant)
        if not self.request.can_view_all_campuses or self.request.selected_campus_id is not None:
            qs = qs.filter(pk__in=_campus_ids(self.request))
        return qs

    def get_queryset(self):
        return StaffIncentiveStatement.objects.filter(campus__in=self._campuses()).prefetch_related('lines').order_by('-month', 'user_name', 'pk')

    def list(self, request, *args, **kwargs):
        return wrap_list(self.get_queryset(), self.get_serializer_class(), request)

    def create(self, request, *args, **kwargs):
        return Response({'code': 405, 'msg': '請使用員工獎金月結操作'}, status=405)

    def _result(self, operation, *args, **kwargs):
        try:
            statement = operation(*args, **kwargs)
        except ValueError as exc:
            return Response({'code': 400, 'msg': str(exc)}, status=400)
        return Response({'code': 200, 'data': self.get_serializer(statement).data})

    def _acknowledge(self):
        serializer = AcknowledgeInput(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data['accepted']:
            raise ValidationError({'accepted': '請先核對明細並勾選確認；系統不會實際轉帳'})
        return serializer.validated_data['expected_updated_at']

    @action(detail=False, methods=['post'])
    def calculate(self, request, *args, **kwargs):
        serializer = CalculateInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        campus = get_object_or_404(self._campuses(), pk=values['campus'])
        eligible_ids = StaffIncentiveRule.objects.filter(campus=campus).values('user_id')
        historical_ids = StaffIncentiveStatement.objects.filter(campus=campus).values('user_id')
        user = get_object_or_404(User.objects.filter(Q(pk__in=eligible_ids) | Q(pk__in=historical_ids)), pk=values['user'])
        return self._result(calculate_staff_incentive, user=user, campus=campus, month=values['month'])

    @action(detail=True, methods=['post'])
    def recalculate(self, request, *args, **kwargs):
        statement = self.get_object()
        return self._result(calculate_staff_incentive, user=statement.user, campus=statement.campus, month=statement.month)

    @action(detail=True, methods=['post'])
    def adjust(self, request, *args, **kwargs):
        statement = self.get_object()
        serializer = AdjustInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._result(adjust_staff_incentive, statement, **serializer.validated_data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, *args, **kwargs):
        statement = self.get_object()
        expected = self._acknowledge()
        return self._result(confirm_staff_incentive, statement, actor=request.user, expected_updated_at=expected)

    @action(detail=True, methods=['post'], url_path='record-paid')
    def record_paid(self, request, *args, **kwargs):
        statement = self.get_object()
        expected = self._acknowledge()
        return self._result(mark_staff_incentive_paid, statement, actor=request.user, expected_updated_at=expected)

    def perform_destroy(self, instance):
        try:
            delete_staff_incentive_draft(instance)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
