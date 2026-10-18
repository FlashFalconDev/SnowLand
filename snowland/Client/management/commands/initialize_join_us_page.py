from .initialize_about_page import Command as OriginalPageCommand


class Command(OriginalPageCommand):
    help = 'Initialize existing recruitment layout; dry-run by default, preserve original data.'

    def handle(self, *args, **options):
        return super().handle(*args, **{**options, 'page_key': 'join-us'})
