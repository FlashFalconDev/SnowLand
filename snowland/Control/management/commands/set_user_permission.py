from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Control.models import UserProfile


class Command(BaseCommand):
    help = '設定使用者權限為 manager 或 coach'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='使用者的 email')
        parser.add_argument(
            '--manager',
            action='store_true',
            help='設定為 manager',
        )
        parser.add_argument(
            '--coach',
            action='store_true',
            help='設定為 coach',
        )

    def handle(self, *args, **options):
        email = options['email']
        is_manager = options['manager']
        is_coach = options['coach']

        try:
            user = User.objects.get(email=email)
            profile, created = UserProfile.objects.get_or_create(user=user)

            if is_manager:
                profile.is_manager = True
            if is_coach:
                profile.is_coach = True

            profile.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f'成功設定 {email} 的權限:\n'
                    f'  is_manager: {profile.is_manager}\n'
                    f'  is_coach: {profile.is_coach}'
                )
            )

        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'找不到 email 為 {email} 的使用者')
            )
