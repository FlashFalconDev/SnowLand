from django.core.management.base import BaseCommand
from Client.models import Client
from Resorts.models import Resorts
from Coursekit.models import CourseCategory
from Coach.models import Coach
from booking.models import ReservationGroup


class Command(BaseCommand):
    help = '將現有資料關聯到預設客戶（雪域創遊）'

    def handle(self, *args, **options):
        # 取得或建立「雪域創遊」客戶
        client, created = Client.objects.get_or_create(
            internal_code='snowland_chuangyou',
            defaults={
                'name': '雪域創遊',
                'contact_person': '待設定',
                'contact_email': 'contact@snowland.com',
                'is_active': True,
                'sales': '待設定',
                'program': '標準版',
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ 已建立客戶：{client.name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ 找到現有客戶：{client.name}'))

        # 更新所有沒有 client 的 Resorts
        resorts_updated = Resorts.objects.filter(client__isnull=True).update(client=client)
        self.stdout.write(self.style.SUCCESS(f'✓ 已更新 {resorts_updated} 個雪場'))

        # 更新所有沒有 client 的 CourseCategory
        categories_updated = CourseCategory.objects.filter(client__isnull=True).update(client=client)
        self.stdout.write(self.style.SUCCESS(f'✓ 已更新 {categories_updated} 個課程大類'))

        # 更新所有沒有 client 的 Coach
        coaches_updated = Coach.objects.filter(client__isnull=True).update(client=client)
        self.stdout.write(self.style.SUCCESS(f'✓ 已更新 {coaches_updated} 個教練'))

        # 更新所有沒有 client 的 ReservationGroup
        groups_updated = ReservationGroup.objects.filter(client__isnull=True).update(client=client)
        self.stdout.write(self.style.SUCCESS(f'✓ 已更新 {groups_updated} 個預約分組'))

        self.stdout.write(self.style.SUCCESS('\n✓✓✓ 資料遷移完成！✓✓✓'))
        self.stdout.write(self.style.WARNING('\n請檢查資料是否正確：'))
        self.stdout.write(f'  - 客戶名稱：{client.name}')
        self.stdout.write(f'  - 雪場數量：{client.resorts.count()}')
        self.stdout.write(f'  - 課程大類數量：{client.course_categories.count()}')
        self.stdout.write(f'  - 教練數量：{client.coaches.count()}')
        self.stdout.write(f'  - 預約分組數量：{client.reservation_groups.count()}')
