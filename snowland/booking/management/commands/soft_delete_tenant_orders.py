import re
from hmac import compare_digest
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from Client.models import Client
from booking.models import TenantOrderArchiveBatch
from booking.order_archive import (
    ArchiveError, apply_archive, build_archive_plan, lock_archive_scope, restore_archive,
)


class Command(BaseCommand):
    help = '預覽、標記或還原一個精確租戶的訂單及其從屬營運資料'

    def add_arguments(self, parser):
        parser.add_argument('--client-code', required=True)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--dry-run', action='store_true')
        mode.add_argument('--apply', action='store_true')
        mode.add_argument('--restore', action='store_true')
        parser.add_argument('--confirm-client-code')
        parser.add_argument('--expected-plan-digest')
        parser.add_argument('--actor-id', type=int)
        parser.add_argument('--batch', type=UUID)

    def handle(self, *args, **options):
        code = options['client_code']
        if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,49}', code):
            raise CommandError('請提供精確租戶代碼，不能使用萬用字元或模糊條件')
        self.validate_mode(options)
        try:
            if options['dry_run']:
                tenant = self.tenant(Client.objects.all(), code)
                plan = build_archive_plan(tenant)
                for label, counts in plan.counts.items():
                    totals = ' '.join(f'{key}={value}' for key, value in counts.items())
                    self.stdout.write(f'{label} {totals}')
                self.stdout.write(f'plan_digest={plan.digest}')
                return
            result = self.write_archive(code, options)
        except ArchiveError as exc:
            raise CommandError(str(exc)) from exc
        except IntegrityError as exc:
            raise CommandError('批次違反既有資料庫約束，所有變更已回滾') from exc
        self.stdout.write(result)

    @staticmethod
    def validate_mode(options):
        # Enforce mutual exclusivity for call_command keyword arguments as well.
        if sum(bool(options[mode]) for mode in ('dry_run', 'apply', 'restore')) != 1:
            raise CommandError('請指定且只指定一個模式')
        if options['apply']:
            digest = options['expected_plan_digest']
            if (options['confirm_client_code'] != options['client_code']
                    or not digest or not re.fullmatch(r'[0-9a-f]{64}', digest)
                    or not options['actor_id'] or options['batch']):
                raise CommandError('--apply 需要相同確認代碼、預覽摘要與操作人 ID')
        elif options['confirm_client_code'] or options['expected_plan_digest']:
            raise CommandError('確認代碼與摘要只供 --apply 使用')
        if options['restore'] and not options['batch']:
            raise CommandError('--restore 需要批次 UUID')
        if options['dry_run'] and (options['actor_id'] or options['batch']):
            raise CommandError('--dry-run 只接受租戶代碼')

    @staticmethod
    def tenant(queryset, code):
        tenant = queryset.filter(internal_code=code).first()
        if tenant is None or tenant.internal_code != code:
            raise CommandError('找不到完全相同的租戶代碼')
        return tenant

    @staticmethod
    @transaction.atomic
    def write_archive(code, options):
        tenant = Command.tenant(Client.objects.select_for_update(), code)
        actor = None
        if options['actor_id'] is not None:
            actor = get_user_model()._base_manager.filter(
                pk=options['actor_id'], is_active=True, is_staff=True, is_superuser=True,
            ).first()
            if actor is None:
                raise CommandError('操作人必須是啟用中的平台管理者')
        lock_archive_scope(tenant)
        if options['restore']:
            batch = TenantOrderArchiveBatch.objects.select_for_update().filter(
                pk=options['batch'], client=tenant,
            ).first()
            if batch is None:
                raise CommandError('此租戶找不到該批次')
            restore_archive(tenant, batch, actor)
            return f'restored_batch={batch.pk}'
        plan = build_archive_plan(tenant)
        if not compare_digest(plan.digest, options['expected_plan_digest']):
            raise CommandError('租戶範圍或計畫已變動，請重新預覽並核准摘要')
        batch = apply_archive(tenant, actor, plan)
        return f'batch={batch.pk}' if batch else 'pending=0'
