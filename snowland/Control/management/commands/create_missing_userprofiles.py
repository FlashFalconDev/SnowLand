from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Control.models import UserProfile


class Command(BaseCommand):
    help = '為所有缺少 UserProfile 的 User 創建對應的設定檔'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只顯示將要創建的 UserProfile，不實際執行',
        )

    def handle(self, *args, **options):
        # 找出所有沒有 UserProfile 的 User
        users_without_profile = User.objects.filter(userprofile__isnull=True)
        
        if not users_without_profile.exists():
            self.stdout.write(
                self.style.SUCCESS('所有 User 都已經有對應的 UserProfile 了！')
            )
            return

        self.stdout.write(
            f'找到 {users_without_profile.count()} 個缺少 UserProfile 的 User：'
        )
        
        for user in users_without_profile:
            self.stdout.write(f'  - {user.username} (ID: {user.id})')

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING('這是試運行模式，沒有實際創建 UserProfile')
            )
            return

        # 為每個沒有 UserProfile 的 User 創建一個
        created_count = 0
        for user in users_without_profile:
            try:
                UserProfile.objects.create(user=user)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 已為 {user.username} 創建 UserProfile')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ 為 {user.username} 創建 UserProfile 時出錯: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n完成！成功創建了 {created_count} 個 UserProfile')
        ) 

#python manage.py create_missing_userprofiles