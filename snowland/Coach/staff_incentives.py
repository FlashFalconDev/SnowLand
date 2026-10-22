"""Monthly administrative bonuses. Records accounting only; never transfers money."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

from Resorts.models import Campus
from booking.models import CancellationRequest, ReservationGroup
from .models import StaffIncentiveLine, StaffIncentiveRule, StaffIncentiveStatement


def _next_month(day):
    return date(day.year + (day.month == 12), 1 if day.month == 12 else day.month + 1, 1)


def _money(amount):
    return int(Decimal(amount).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _lock_statement(statement, actor=None):
    user_ids = {statement.user_id}
    if actor is not None:
        user_ids.add(actor.pk)
    list(User.objects.select_for_update().filter(pk__in=user_ids).order_by('pk'))
    Campus.objects.select_for_update().get(pk=statement.campus_id)
    return StaffIncentiveStatement.objects.select_for_update().get(pk=statement.pk)


def _totals(statement):
    statement.total_amount = statement.earned_amount - statement.refund_deduction + statement.adjustment
    statement.save()
    return statement


@transaction.atomic
def calculate_staff_incentive(*, user, campus, month):
    if type(month) is not date or month.day != 1:
        raise ValueError('結算月份請使用每月1日')
    if month > timezone.localdate().replace(day=1):
        raise ValueError('不能計算未來月份的員工獎金')
    user = User.objects.select_for_update().get(pk=user.pk)
    campus = Campus.objects.select_for_update().get(pk=campus.pk)
    rule = StaffIncentiveRule.objects.filter(user=user, campus=campus).first()
    paid_sources = StaffIncentiveLine.objects.filter(
        statement__user=user, statement__campus=campus, statement__status='paid',
        statement__month__lt=month, line_type='earning',
    ).select_related('statement', 'group').order_by('pk')
    if not rule and not paid_sources.exists():
        raise ValueError('請先設定這位員工在此校區的獎金比例')
    percent = rule.completed_order_percent if rule and rule.is_active else Decimal(0)
    if not percent.is_finite() or not 0 <= percent <= 100:
        raise ValueError('獎金比例須為0～100%，請先修正原設定')
    statement, _ = StaffIncentiveStatement.objects.get_or_create(user=user, campus=campus, month=month,
        defaults={'user_name': user.get_full_name() or user.username, 'campus_name': campus.name})
    statement = StaffIncentiveStatement.objects.select_for_update().get(pk=statement.pk)
    if statement.status != 'draft':
        raise ValueError('已確認或已記錄發放的員工獎金不能重新計算')
    statement.lines.all().delete()
    statement.percent = percent
    statement.user_name = user.get_full_name() or user.username
    statement.campus_name = campus.name
    statement.revenue = statement.earned_amount = statement.refund_deduction = 0
    if rule and rule.is_active and user.is_active and campus.is_active:
        groups = ReservationGroup.objects.filter(client_id=campus.client_id, campus=campus).annotate(
            completion_date=Max('reservations__bookings__date', filter=~Q(reservations__status='deleted')),
        ).filter(completion_date__gte=month, completion_date__lt=_next_month(month)).prefetch_related('reservations__bookings', 'payments').order_by('pk')
        for group in groups:
            reservations = [item for item in group.reservations.all() if item.status != 'deleted']
            payment = max(group.payments.all(), key=lambda item: (item.created_at, item.pk), default=None)
            if not reservations or any(item.status != 'completed' or not item.bookings.all() for item in reservations):
                continue
            if not payment or payment.status != 'paid':
                continue
            key = f'earning:{user.pk}:{group.pk}'
            previous = StaffIncentiveLine.objects.filter(group=group,
                statement__user=user, line_type='earning').select_related('statement').first()
            if previous:
                if previous.statement.status == 'draft':
                    raise ValueError(f'訂單 {group.order_number} 已在其他月份草稿，請先重算原月份')
                continue
            base = sum(item.payment_amount for item in reservations)
            statement.revenue += base
            # Allocate integer rounding across orders so lines sum to monthly revenue × rate.
            cumulative = _money(Decimal(statement.revenue) * percent / 100)
            amount = cumulative - statement.earned_amount
            statement.earned_amount = cumulative
            StaffIncentiveLine.objects.create(statement=statement, group=group, entry_key=key,
                line_type='earning', order_number=group.order_number, event_date=group.completion_date,
                base_amount=base, percent=percent, amount=amount)
    for source in paid_sources:
        previous = source.refund_lines.exclude(statement=statement).aggregate(amount=Sum('amount'), base=Sum('base_amount'))
        remaining_amount = max(source.amount + (previous['amount'] or 0), 0)
        remaining_base = max(source.base_amount - (previous['base'] or 0), 0)
        for cancellation in CancellationRequest.objects.filter(group=source.group, status='refunded').order_by('reviewed_at', 'pk'):
            if cancellation.reviewed_at is None:
                raise ValueError(f'訂單 {source.order_number} 的退款缺少完成日期，請先核對退款紀錄')
            refunded_day = timezone.localtime(cancellation.reviewed_at).date()
            if _next_month(refunded_day.replace(day=1)) > month:
                continue
            key = f'refund:{source.pk}:{cancellation.pk}'
            if StaffIncentiveLine.objects.filter(entry_key=key).exists():
                continue
            base = min(cancellation.refund_amount, remaining_base)
            if not base:
                continue
            # Round the cumulative refunded base, not each small refund separately.
            # Keep zero-valued lines so later months retain that refunded base.
            cumulative_base = source.base_amount - remaining_base + base
            deducted_amount = source.amount - remaining_amount
            # A full refund also recovers any cent allocated by monthly rounding.
            target_amount = (source.amount if cumulative_base == source.base_amount else
                _money(Decimal(cumulative_base) * source.percent / 100))
            amount = max(min(target_amount - deducted_amount, remaining_amount), 0)
            StaffIncentiveLine.objects.create(statement=statement, group=source.group, cancellation=cancellation,
                source_line=source, entry_key=key, line_type='refund', order_number=source.order_number,
                event_date=refunded_day, base_amount=base, percent=source.percent, amount=-amount)
            remaining_base -= base
            remaining_amount -= amount
            statement.refund_deduction += amount
    return _totals(statement)


@transaction.atomic
def confirm_staff_incentive(statement, *, actor, expected_updated_at=None):
    statement = _lock_statement(statement, actor)
    if statement.status in ('confirmed', 'paid'):
        return statement
    if expected_updated_at is not None and statement.updated_at != expected_updated_at:
        raise ValueError('這張月結已被更新，請重新載入並核對最新金額後再確認')
    if _next_month(statement.month) > timezone.localdate():
        raise ValueError('請等結算月份結束後再確認')
    if not statement.lines.exists() and not statement.adjustment:
        raise ValueError('沒有獎金或扣回明細，不能確認空白結算')
    statement.status = 'confirmed'
    statement.confirmed_at = timezone.now()
    statement.confirmed_by = actor
    statement.save(update_fields=['status', 'confirmed_at', 'confirmed_by', 'updated_at'])
    return statement


@transaction.atomic
def mark_staff_incentive_paid(statement, *, actor, expected_updated_at=None):
    statement = _lock_statement(statement, actor)
    if statement.status == 'paid':
        return statement
    if expected_updated_at is not None and statement.updated_at != expected_updated_at:
        raise ValueError('這張月結已被更新，請重新載入並核對最新狀態後再記錄發放')
    if statement.status != 'confirmed':
        raise ValueError('請先確認員工獎金，再記錄發放；系統不會實際轉帳')
    statement.status = 'paid'
    statement.paid_at = timezone.now()
    statement.paid_by = actor
    statement.save(update_fields=['status', 'paid_at', 'paid_by', 'updated_at'])
    return statement


@transaction.atomic
def adjust_staff_incentive(statement, *, amount, note):
    statement = _lock_statement(statement)
    if statement.status != 'draft':
        raise ValueError('只有草稿可以人工調整')
    if type(amount) is not int or not -2147483648 <= amount <= 2147483647:
        raise ValueError('人工調整金額請填有效整數')
    if not isinstance(note, str) or not note.strip() or len(note.strip()) > 300:
        raise ValueError('請填寫300字內的人工調整原因')
    statement.adjustment = amount
    statement.adjustment_note = note.strip()
    return _totals(statement)


@transaction.atomic
def delete_staff_incentive_draft(statement):
    statement = _lock_statement(statement)
    if statement.status != 'draft':
        raise ValueError('只能刪除草稿；已確認或已記錄發放的員工獎金須保留')
    statement.delete()
