from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from chatbooking.models import ChatBookingSession


class Command(BaseCommand):
    help = "Expire old chat sessions and purge terminal chat data after the retention period."

    def add_arguments(self, parser):
        parser.add_argument("--retention-days", type=int, default=180)
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        retention_days = options["retention_days"]
        if retention_days < 30:
            raise ValueError("retention-days 不可小於 30")

        now = timezone.now()
        expired_queryset = ChatBookingSession.objects.filter(
            expires_at__lte=now,
            status__in=[
                ChatBookingSession.STATUS_ACTIVE,
                ChatBookingSession.STATUS_AWAITING_CONFIRMATION,
                ChatBookingSession.STATUS_ESCALATED,
            ],
        )
        purge_before = now - timedelta(days=retention_days)
        purge_queryset = ChatBookingSession.objects.filter(
            status__in=[
                ChatBookingSession.STATUS_EXPIRED,
                ChatBookingSession.STATUS_CANCELLED,
                ChatBookingSession.STATUS_COMPLETED,
            ],
            updated_at__lt=purge_before,
        )

        expire_count = expired_queryset.count()
        purge_count = purge_queryset.count()
        if options["dry_run"]:
            self.stdout.write(
                f"dry-run: expire={expire_count}, purge={purge_count}, retention_days={retention_days}"
            )
            transaction.set_rollback(True)
            return

        expired_queryset.update(status=ChatBookingSession.STATUS_EXPIRED, updated_at=now)
        purge_queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"expired={expire_count}, purged={purge_count}, retention_days={retention_days}"
            )
        )
