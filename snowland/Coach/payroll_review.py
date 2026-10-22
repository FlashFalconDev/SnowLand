"""Publish/confirm payroll only; never pays funds or signs a document."""
import uuid

from django.db import transaction
from django.utils import timezone

from .models import PayrollStatement


@transaction.atomic
def publish_statement(statement, deadline, expected_reviewed_at=None):
    statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
    if statement.status != 'draft':
        raise ValueError('只能送出草稿薪資單，請重新載入目前狀態')
    if deadline < timezone.localdate() or deadline <= statement.period_end:
        raise ValueError('確認截止日不能早於今天，且必須晚於結算結束日')
    if not statement.lines.exists() or statement.total_amount < 0:
        raise ValueError('請先完成薪資計算並核對明細後再送出')
    if not statement.settlement_snapshot:
        raise ValueError('請先保存稅金與發放幣別核對結果；無扣項也須明確確認')
    if statement.settlement_snapshot.get('base_amount') != statement.total_amount:
        raise ValueError('薪資已變更，請重新核對稅金與發放幣別後再送出')
    if expected_reviewed_at is not None and expected_reviewed_at != statement.settlement_snapshot.get('reviewed_at'):
        raise ValueError('稅金核對版本已變更，請重新載入核對後再送出')
    statement.status = 'review'
    statement.published_at = timezone.now()
    statement.confirmation_deadline = deadline
    statement.review_token = uuid.uuid4()
    statement.confirmed_at = None
    statement.confirmed_by = None
    statement.confirmation_method = ''
    statement.save()
    return statement


def _finish(statement, now, user=None):
    statement.status = 'confirmed'
    statement.confirmed_at = now
    statement.confirmation_method = 'coach' if user else 'automatic'
    statement.confirmed_by = user
    statement.save(update_fields=['status', 'confirmed_at', 'confirmation_method', 'confirmed_by', 'updated_at'])
    from .payroll_documents import ensure_document
    return ensure_document(statement, required=False)


@transaction.atomic
def confirm_statement(statement, user, token):
    statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
    if not token or str(statement.review_token) != str(token):
        raise ValueError('薪資單版本已變更，請重新載入後再確認')
    if statement.coach.user_id != user.pk:
        raise ValueError('只能確認自己的薪資單')
    if statement.status == 'confirmed':
        return statement
    if statement.status != 'review':
        raise ValueError('這張薪資單目前不能確認，請重新載入')
    now = timezone.now()
    if statement.confirmation_deadline < timezone.localdate(now):
        return _finish(statement, now)
    return _finish(statement, now, user)


@transaction.atomic
def withdraw_statement(statement):
    statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
    if statement.status != 'review':
        raise ValueError('只能撤回尚待確認的薪資單')
    if statement.confirmation_deadline < timezone.localdate():
        raise ValueError('已超過確認期限，不能撤回；請重新載入並核對結算')
    statement.status = 'draft'
    statement.review_token = None
    statement.published_at = None
    statement.confirmation_deadline = None
    statement.save(update_fields=['status', 'review_token', 'published_at', 'confirmation_deadline', 'updated_at'])
    return statement


def confirm_due_statements(now=None, dry_run=False):
    now = now or timezone.now()
    ids = list(PayrollStatement.objects.filter(
        status='review', confirmation_deadline__lt=timezone.localdate(now),
        review_token__isnull=False, published_at__isnull=False, coach__client__is_active=True,
    ).values_list('pk', flat=True))
    if dry_run:
        return len(ids)
    count = 0
    for statement_id in ids:
        with transaction.atomic():
            statement = PayrollStatement.objects.select_for_update().filter(pk=statement_id).first()
            if statement and statement.status == 'review' and statement.confirmation_deadline < timezone.localdate(now):
                _finish(statement, now)
                count += 1
    return count
