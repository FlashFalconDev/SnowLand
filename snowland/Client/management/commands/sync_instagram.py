from django.core.management.base import BaseCommand, CommandError
from Client.models import InstagramConnection
from Client.instagram_sync import InstagramError, run_sync


class Command(BaseCommand):
    help = 'Sync enabled official Instagram feeds; tokens/provider errors are never printed.'

    def add_arguments(self, parser):
        parser.add_argument('--client', required=True, help='Exact tenant internal code')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        rows = InstagramConnection.objects.filter(client__internal_code=options['client'], enabled=True)
        if options['dry_run']:
            self.stdout.write(f'DRY RUN: enabled_connections={rows.count()}; no API request or write')
            return
        for row in rows:
            try:
                count = run_sync(row.pk, due_only=True)
            except InstagramError as exc:
                raise CommandError(str(exc)) from None
            self.stdout.write(f'Instagram sync complete: posts={count}')
