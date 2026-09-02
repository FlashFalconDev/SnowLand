"""
清除課程資料快取的管理命令

使用方式：
python manage.py clear_course_cache

用途：
當課程資料有更新時（新增課程、修改時段等），需要清除快取讓新資料生效
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    help = '清除課程資料快取，強制重新載入最新資料'

    def handle(self, *args, **options):
        cache_key = 'course_data_optimized_v1'

        if cache.delete(cache_key):
            self.stdout.write(
                self.style.SUCCESS(f'成功清除快取: {cache_key}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'快取不存在或已被清除: {cache_key}')
            )
