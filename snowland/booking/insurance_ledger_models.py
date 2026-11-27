from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class InsurancePrepaidAccount(models.Model):
    client = models.OneToOneField('Client.Client', on_delete=models.PROTECT)
    currency = models.CharField(max_length=3)
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    version = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(balance__gte=0), name='insurance_balance_nonnegative')]


class ImmutableLedgerQuerySet(models.QuerySet):
    def bulk_create(self, *args, **kwargs):
        raise ValidationError('帳務紀錄須逐筆確認及入帳。')

    def update(self, **kwargs):
        raise ValidationError('已入帳或確認的帳務紀錄不可修改。')

    def delete(self):
        raise ValidationError('已入帳或確認的帳務紀錄不可刪除。')


class ImmutableLedgerRecord(models.Model):
    objects = ImmutableLedgerQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding or kwargs.get('force_update'):
            raise ValidationError('已入帳或確認的帳務紀錄不可修改。')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('已入帳或確認的帳務紀錄不可刪除。')


class InsuranceLedgerEntry(ImmutableLedgerRecord):
    class Kind(models.TextChoices):
        OPENING = 'opening', '期初'
        TOP_UP = 'top_up', '儲值'
        DEDUCTION = 'deduction', '扣款'
        REVERSAL = 'reversal', '沖正'

    account = models.ForeignKey(InsurancePrepaidAccount, on_delete=models.PROTECT, related_name='entries')
    sequence = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    balance_after = models.DecimalField(max_digits=16, decimal_places=2)
    member = models.ForeignKey('booking.MemberDetail', null=True, blank=True, on_delete=models.SET_NULL)
    # Preserve source IDs when an archived learner or order is purged.
    member_record_id = models.PositiveBigIntegerField(null=True, blank=True)
    order_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    reverses = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='reversal')
    reference = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=1000, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    idempotency_key = models.UUIDField(default=uuid4, unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'sequence'], name='insurance_entry_account_sequence'),
            models.CheckConstraint(condition=Q(amount__gt=0), name='insurance_entry_positive_amount'),
            models.CheckConstraint(
                condition=Q(kind='reversal', reverses__isnull=False) | (~Q(kind='reversal') & Q(reverses__isnull=True)),
                name='insurance_entry_reversal_source',
            ),
        ]
        indexes = [models.Index(fields=['account', 'created_at'], name='insurance_entry_account_date')]


class InsuranceReconciliation(ImmutableLedgerRecord):
    account = models.ForeignKey(InsurancePrepaidAccount, on_delete=models.PROTECT, related_name='reconciliations')
    month = models.DateField()
    opening = models.DecimalField(max_digits=16, decimal_places=2)
    top_ups = models.DecimalField(max_digits=16, decimal_places=2)
    deductions = models.DecimalField(max_digits=16, decimal_places=2)
    reversals = models.DecimalField(max_digits=16, decimal_places=2)
    closing = models.DecimalField(max_digits=16, decimal_places=2)
    cutoff_sequence = models.PositiveBigIntegerField()
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    confirmed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=1000, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['account', 'month'], name='insurance_reconciliation_month')]
