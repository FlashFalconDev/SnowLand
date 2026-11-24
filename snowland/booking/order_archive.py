import hashlib
import json
from dataclasses import dataclass

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from Coach.models import Coach, PayrollLine, PayrollStatement, StaffIncentiveLine, StaffIncentiveStatement
from Coach.vehicle_models import VehicleCharge, VehicleDeduction, VehicleExpense, VehicleTrip
from Resorts.models import Campus

from .course_cache import clear_course_data_cache
from .discount_usage import rebuild_discount_usage
from .loyalty import rebuild_tenant_loyalty
from .models import (
    Booking, CancellationRequest, CourseEvaluation, MemberCourseDocumentRevision, MemberDetail,
    MemberLoyaltyEntry, NotificationDelivery, OrderAmendment, OrderAmendmentEvent, OrderLoyalty,
    OrderRevision, ParticipantInvitation, Payment, Reservation, ReservationGroup, SharedCourseClass,
    TenantOrderArchiveBatch,
)


class ArchiveError(ValueError):
    pass


@dataclass(frozen=True)
class TenantLink:
    lookup: str
    optional: str = ''

    def condition(self, tenant):
        match = Q(**{self.lookup: tenant.pk})
        if self.optional:
            match |= Q(**{f'{self.optional}__isnull': True})
        return match


@dataclass(frozen=True)
class Scope:
    model: type
    owner: str
    links: tuple = ()
    valid_relationship: Q = Q()

    @property
    def label(self):
        return self.model._meta.label

    def rows(self):
        return self.model.all_objects.order_by('pk')

    def tenant_rows(self, tenant):
        return self.rows().filter(**{self.owner: tenant.pk})

    def valid_rows(self, tenant):
        rows = self.tenant_rows(tenant).filter(
            self.valid_relationship, *(link.condition(tenant) for link in self.links),
        )
        if self.model is VehicleTrip:
            rows = rows.exclude(participants__in=Coach._base_manager.exclude(client=tenant))
        return rows

    def inbound_conflicts(self, tenant):
        """Rows reached through the tenant's secondary links with a different owner."""
        if not self.links:
            return self.rows().none()
        related = Q()
        for link in self.links:
            related |= Q(**{link.lookup: tenant.pk})
        rows = self.rows().filter(related).exclude(**{self.owner: tenant.pk})
        if self.model in (ReservationGroup, NotificationDelivery):
            rows = rows.filter(**{f'{self.owner}__isnull': False})
        return rows


SCOPES = (
    Scope(ReservationGroup, 'client_id', (
        TenantLink('campus__client_id', 'campus_id'),
        TenantLink('newebpay_merchant__client_id', 'newebpay_merchant_id'),
    )),
    Scope(SharedCourseClass, 'client_id', (
        TenantLink('campus__client_id'), TenantLink('resort__client_id'),
        TenantLink('template__course_type__category__client_id'),
    )),
    Scope(PayrollStatement, 'campus__client_id', (TenantLink('coach__client_id'),)),
    Scope(StaffIncentiveStatement, 'campus__client_id'),
    Scope(VehicleTrip, 'campus__client_id', (
        TenantLink('driver__client_id'), TenantLink('vehicle__campus__client_id', 'vehicle_id'),
        TenantLink('resort__client_id', 'resort_id'),
    )),
    Scope(Reservation, 'group__client_id', (
        TenantLink('shared_course_class__client_id', 'shared_course_class_id'),
        TenantLink('resort__client_id', 'resort_id'),
        TenantLink('preferred_coach__client_id', 'preferred_coach_id'),
    )),
    Scope(Booking, 'reservation__group__client_id'),
    Scope(MemberDetail, 'reservation__group__client_id'),
    Scope(Payment, 'reservation_group__client_id', (TenantLink('payment_account__client_id', 'payment_account_id'),)),
    Scope(CancellationRequest, 'group__client_id'),
    Scope(OrderRevision, 'group__client_id'),
    Scope(OrderAmendment, 'group__client_id', (TenantLink('revision__group__client_id'),),
          Q(revision__group_id=F('group_id'))),
    Scope(OrderAmendmentEvent, 'amendment__group__client_id'),
    Scope(MemberCourseDocumentRevision, 'member__reservation__group__client_id',
          (TenantLink('revision__group__client_id'),), Q(revision__group_id=F('member__reservation__group_id'))),
    Scope(ParticipantInvitation, 'member__reservation__group__client_id'),
    Scope(NotificationDelivery, 'group__client_id', (TenantLink('template__client_id'),)),
    Scope(OrderLoyalty, 'group__client_id', (
        TenantLink('account__client_id'), TenantLink('referrer__client_id', 'referrer_id'),
    )),
    Scope(MemberLoyaltyEntry, 'order__group__client_id', (TenantLink('account__client_id'),),
          Q(account_id=F('order__account_id')) | Q(account_id=F('order__referrer_id'))),
    Scope(CourseEvaluation, 'booking__reservation__group__client_id', (
        TenantLink('member__reservation__group__client_id'), TenantLink('coach__client_id', 'coach_id'),
    ), Q(member__reservation_id=F('booking__reservation_id'))),
    Scope(PayrollLine, 'statement__campus__client_id',
          (TenantLink('booking__reservation__group__client_id', 'booking_id'),)),
    Scope(StaffIncentiveLine, 'statement__campus__client_id', (
        TenantLink('group__client_id'), TenantLink('cancellation__group__client_id', 'cancellation_id'),
        TenantLink('source_line__statement__campus__client_id', 'source_line_id'),
    ), Q(cancellation_id=None) | Q(cancellation__group_id=F('group_id'))),
    Scope(VehicleExpense, 'trip__campus__client_id'),
    Scope(VehicleCharge, 'trip__campus__client_id', (TenantLink('coach__client_id'),)),
    Scope(VehicleDeduction, 'charge__trip__campus__client_id', (TenantLink('statement__campus__client_id'),)),
)


@dataclass
class ArchivePlan:
    targets: dict
    counts: dict
    digest: str


def build_archive_plan(tenant):
    targets = {}
    counts = {}
    memberships = {}
    for scope in SCOPES:
        tenant_rows = scope.tenant_rows(tenant)
        valid = scope.valid_rows(tenant)
        scoped_flags = list(tenant_rows.values_list('pk', 'is_deleted'))
        inbound = list(scope.inbound_conflicts(tenant).values_list('pk', flat=True))
        conflicts = tenant_rows.count() - valid.count() + len(inbound)
        pending = valid.filter(is_deleted=False)
        if scope.model is SharedCourseClass:
            surviving = Reservation.all_objects.live().exclude(status__in=['cancelled', 'deleted']).exclude(
                group__client_id=tenant.pk,
            )
            pending = pending.filter(opening_mode='customer').exclude(pk__in=surviving.values('shared_course_class_id'))
        ids = list(pending.values_list('pk', flat=True))
        targets[scope.label] = ids
        inflight = 0
        if scope.model is Payment:
            inflight = pending.filter(Q(status='pending') | Q(status='unpaid', reservation_group__newebpay_form_issued=True)).count()
        if scope.model is NotificationDelivery:
            inflight = pending.filter(status='sending').count()
        archived = sum(deleted for _, deleted in scoped_flags)
        counts[scope.label] = {
            'tenant_total': len(scoped_flags), 'already_deleted': archived, 'pending': len(ids),
            'retained': len(scoped_flags) - archived - len(ids), 'conflicts': conflicts, 'in_flight': inflight,
        }
        if scope.model is NotificationDelivery:
            counts[scope.label]['without_group'] = scope.rows().filter(group_id=None, template__client=tenant).count()
            counts[scope.label]['unknown_group_owner'] = scope.rows().filter(
                group_id__isnull=False, group__client_id=None, template__client=tenant,
            ).count()
        memberships[scope.label] = [scoped_flags, inbound]
    digest = hashlib.sha256(json.dumps(
        [tenant.pk, tenant.internal_code, targets, counts, memberships],
        sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    return ArchivePlan(targets, counts, digest)


def lock_archive_scope(tenant):
    # Base rows are locked in a stable order before building the write plan.
    list(Campus.objects.filter(client=tenant).order_by('pk').select_for_update().values_list('pk', flat=True))
    for scope in SCOPES:
        ids = scope.tenant_rows(tenant).order_by().values('pk')
        # A MySQL subquery can lock base rows without introducing locks on its join tables.
        list(scope.rows().filter(pk__in=ids).select_for_update().values_list('pk', flat=True))


def reconcile_archive(tenant):
    rebuild_tenant_loyalty(tenant)
    rebuild_discount_usage(tenant)
    for shared_class in SharedCourseClass.all_objects.live().filter(client=tenant):
        shared_class.refresh_readiness()
    code = tenant.internal_code
    transaction.on_commit(lambda: clear_course_data_cache([code]), robust=True)


def apply_archive(tenant, actor, plan):
    if any(row['conflicts'] or row['in_flight'] for row in plan.counts.values()):
        raise ArchiveError('存在歸戶矛盾或尚未結案的付款／通知，請先核對預覽再執行')
    if not any(plan.targets.values()):
        return None
    batch = mark_archive_rows(tenant, actor, plan.targets, plan.digest)
    reconcile_archive(tenant)
    return batch


def mark_archive_rows(tenant, actor, targets, digest):
    at = timezone.now()
    for scope in reversed(SCOPES):
        ids = targets[scope.label]
        changed = scope.rows().filter(pk__in=ids, is_deleted=False).update(
            is_deleted=True, deleted_at=at, deleted_by=actor,
        )
        if changed != len(ids):
            raise ArchiveError(f'{scope.label} 筆數已變動，請重新預覽')
    return TenantOrderArchiveBatch.objects.create(
        client=tenant, actor=actor, deleted_at=at, plan_digest=digest, targets=targets,
    )


def archive_statement_draft(tenant, actor, statement):
    """Archive the locked draft and the active rows written by that statement."""
    children = {
        PayrollStatement: (PayrollLine, VehicleDeduction),
        StaffIncentiveStatement: (StaffIncentiveLine,),
    }
    targets = {scope.label: [] for scope in SCOPES}
    targets[statement._meta.label] = [statement.pk]
    for model in children[type(statement)]:
        targets[model._meta.label] = list(model.all_objects.live().filter(
            statement=statement,
        ).order_by('pk').values_list('pk', flat=True))
    digest = hashlib.sha256(json.dumps([tenant.pk, targets], sort_keys=True).encode()).hexdigest()
    return mark_archive_rows(tenant, actor, targets, digest)


def archive_failed_order(tenant, actor, group):
    """Keep the records from an unpaid scheduling failure for platform review."""
    targets = {scope.label: [] for scope in SCOPES}
    targets[ReservationGroup._meta.label] = [group.pk]
    for scope in SCOPES:
        if not scope.owner.endswith('group__client_id') or scope.model is StaffIncentiveLine:
            continue
        parent = scope.owner.removesuffix('__client_id')
        related = {f'{parent}_id': group.pk}
        rows = scope.rows().live().filter(**related)
        valid = scope.valid_rows(tenant).live().filter(**related)
        ids = list(valid.values_list('pk', flat=True))
        if len(ids) != rows.count():
            raise ArchiveError(f'{scope.label} 需先確認資料歸戶')
        targets[scope.label] = ids
    digest = hashlib.sha256(json.dumps([tenant.pk, targets], sort_keys=True).encode()).hexdigest()
    return mark_archive_rows(tenant, actor, targets, digest)


def check_restore_conflicts(targets):
    payroll = PayrollStatement.all_objects.filter(pk__in=targets[PayrollStatement._meta.label])
    for statement in payroll:
        if PayrollStatement.all_objects.live().filter(
            coach_id=statement.coach_id, campus_id=statement.campus_id,
            period_start__lte=statement.period_end, period_end__gte=statement.period_start,
        ).exists():
            raise ArchiveError('薪資單的教練、校區及日期與有效期間重疊，無法還原')

    # The unconditional keys remain occupied while archived. Validate the
    # business keys explicitly before restoring the corresponding statements.
    for model, fields in (
        (StaffIncentiveStatement, ('user_id', 'campus_id', 'month')),
        (SharedCourseClass, ('client_id', 'campus_id', 'resort_id', 'template_id',
                             'date', 'start_time', 'end_time', 'ability_level', 'language')),
    ):
        archived = model.all_objects.filter(pk__in=targets[model._meta.label])
        for row in archived.values(*fields):
            if model.all_objects.live().filter(**row).exists():
                raise ArchiveError(f'{model._meta.label} 的既有唯一鍵與有效紀錄衝突')


def restore_archive(tenant, batch, actor):
    if batch.restored_at is not None:
        raise ArchiveError('該批次已還原')
    for scope in SCOPES:
        ids = batch.targets.get(scope.label, [])
        rows = scope.valid_rows(tenant).filter(
            pk__in=ids, is_deleted=True, deleted_at=batch.deleted_at, deleted_by_id=batch.actor_id,
        )
        if rows.count() != len(ids):
            raise ArchiveError(f'{scope.label} 的歸戶、旗標或批次資料已變動')
    check_restore_conflicts(batch.targets)
    for scope in SCOPES:
        ids = batch.targets[scope.label]
        scope.rows().filter(pk__in=ids).update(is_deleted=False, deleted_at=None, deleted_by=None)
    for scope in SCOPES:
        ids = batch.targets[scope.label]
        if scope.rows().live().filter(pk__in=ids).count() != len(ids):
            raise ArchiveError(f'{scope.label} 仍關聯到其他批次的已刪資料')
    reconcile_archive(tenant)
    batch.restored_at = timezone.now()
    batch.restored_by = actor
    batch.save(update_fields=['restored_at', 'restored_by'])
