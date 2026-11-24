"""
清除課程資料快取的管理命令

使用方式：
python manage.py clear_course_cache

用途：
當課程資料有更新時（新增課程、修改時段等），需要清除快取讓新資料生效
"""
from django.core.management.base import BaseCommand, CommandError

from Client.models import Client
from booking.course_cache import clear_course_data_cache


class Command(BaseCommand):
    help = '清除課程資料快取，強制重新載入最新資料'

    def add_arguments(self, parser):
        parser.add_argument('--client-code')

    def handle(self, *args, **options):
        code = options['client_code']
        codes = Client.objects.values_list('internal_code', flat=True)
        if code is not None:
            codes = [candidate for candidate in codes.filter(internal_code=code) if candidate == code]
            if not codes:
                raise CommandError('找不到完全相同的租戶代碼')
        clear_course_data_cache(codes, legacy=code is None)
        self.stdout.write(self.style.SUCCESS('已清除所選範圍的課程快取'))
