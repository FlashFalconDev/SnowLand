"""
建立後台 demo 資料
用法：python manage.py seed_admin_demo

會建立：
  - 5 個雪場（如果沒有）
  - 6 個教練（含雪場關聯、課程等級）
  - 課程大類 / 類型 / 模板 / 時段
  - 5 筆訂單（含 ReservationGroup + Reservation + Booking + Payment）
  - 1 筆教練請假申請
"""
from datetime import date, time, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from Client.models import Client
from Resorts.models import Resorts
from Coach.models import Coach, CoachResort, CoachCourseLevel, CoachLeaveRequest
from Coursekit.models import CourseCategory, CourseType, CourseTemplate, CourseSession
from booking.models import ReservationGroup, Reservation, Booking, Payment, MemberDetail


class Command(BaseCommand):
    help = '為 SnowLand 後台建立 demo 資料'

    def add_arguments(self, parser):
        parser.add_argument('--client', default='snowland', help='client internal_code')

    @transaction.atomic
    def handle(self, *args, **opts):
        client_code = opts['client']
        try:
            client = Client.objects.get(internal_code=client_code)
        except Client.DoesNotExist:
            self.stderr.write(f'❌ Client {client_code} 不存在，請先建立')
            return

        self.stdout.write(f'🎿 為 {client.name} 建立 demo 資料...\n')

        # ========== 1. 雪場 ==========
        resorts_data = [
            ('tomamu', '星野 Tomamu'),
            ('furano', '富良野'),
            ('sapporo_kokusai', '札幌國際'),
            ('rusutsu', '留壽都'),
            ('sahoro', '佐幌'),
        ]
        resorts = {}
        for code, name in resorts_data:
            r, created = Resorts.objects.get_or_create(
                client=client, name=code,
                defaults={'display_name': name, 'auto_scheduling_enabled': True},
            )
            resorts[code] = r
            self.stdout.write(f'  {"✨" if created else "↻"} 雪場 {name}')

        # ========== 2. 課程大類 / 類型 / 模板 ==========
        cat_ski, _ = CourseCategory.objects.get_or_create(
            client=client, name='滑雪課程',
            defaults={'display_order': 1},
        )
        cat_ski.available_resorts.set([resorts['tomamu'], resorts['furano'], resorts['sapporo_kokusai']])

        cat_off, _ = CourseCategory.objects.get_or_create(
            client=client, name='野雪嚮導',
            defaults={'display_order': 2},
        )
        cat_off.available_resorts.set([resorts['tomamu']])

        # 類型
        type_snowboard, _ = CourseType.objects.get_or_create(
            category=cat_ski, name='單板課程',
            defaults={'display_order': 1},
        )
        type_snowboard.available_resorts.set([resorts['tomamu'], resorts['furano']])

        type_ski, _ = CourseType.objects.get_or_create(
            category=cat_ski, name='雙板課程',
            defaults={'display_order': 2},
        )
        type_ski.available_resorts.set([resorts['tomamu'], resorts['sapporo_kokusai']])

        type_offpiste, _ = CourseType.objects.get_or_create(
            category=cat_off, name='野雪嚮導',
            defaults={'display_order': 1},
        )
        type_offpiste.available_resorts.set([resorts['tomamu']])

        # 模板
        templates_data = [
            (type_snowboard, '單板全天', 5, 6),
            (type_snowboard, '單板半天', 3, 6),
            (type_ski, '雙板全天', 5, 6),
            (type_ski, '雙板半天', 3, 6),
            (type_offpiste, '野雪全天', 6, 4),
        ]
        for ct, name, hours, cap in templates_data:
            tmpl, created = CourseTemplate.objects.get_or_create(
                course_type=ct, name=name,
                defaults={'duration_hours': hours, 'max_capacity': cap, 'is_active': True},
            )
            tmpl.resorts.set([resorts['tomamu'], resorts['furano']])
            # 加時段
            CourseSession.objects.get_or_create(
                template=tmpl, start_time=time(9, 0),
                defaults={'end_time': time(12, 0) if hours <= 3 else time(15, 0), 'is_active': True},
            )
            if hours > 3:
                CourseSession.objects.get_or_create(
                    template=tmpl, start_time=time(13, 0),
                    defaults={'end_time': time(16, 0), 'is_active': True},
                )
            self.stdout.write(f'  {"✨" if created else "↻"} 課程模板 {name}')

        # ========== 3. 教練 ==========
        coaches_data = [
            ('Cash 校長', ['zh', 'en', 'yue'], 'active', '/coach-images/Cash 校長.jpg', 'director'),
            ('Lily 總監', ['zh', 'en'], 'active', '/coach-images/Lily 總監.jpg', 'director'),
            ('七針', ['zh', 'en'], 'active', '/coach-images/七針.jpg', 'Lv3'),
            ('Dylan', ['zh', 'en'], 'active', '/coach-images/Dylan.jpg', 'Lv2'),
            ('Eric', ['zh'], 'passive', '/coach-images/Eric.jpg', 'Lv2'),
            ('Naomi', ['zh'], 'active', '/coach-images/Naomi.jpg', 'Lv1'),
        ]
        coaches = {}
        for i, (name, langs, status, img, price_lv) in enumerate(coaches_data):
            coach, created = Coach.objects.get_or_create(
                client=client, name=name,
                defaults={
                    'languages': langs,
                    'availability_status': status,
                    'assignment_score': i * 5,
                    'img': img,
                },
            )
            coaches[name] = coach

            # 雪場關聯
            CoachResort.objects.get_or_create(
                coach=coach, resort=resorts['tomamu'],
                defaults={'resort_priority': 1},
            )
            if name in ('Cash 校長', '七針'):
                CoachResort.objects.get_or_create(
                    coach=coach, resort=resorts['furano'],
                    defaults={'resort_priority': 2},
                )

            # 課程等級
            CoachCourseLevel.objects.get_or_create(
                coach=coach, course_type=type_snowboard,
                defaults={
                    'ability_levels': ['no_exp', 'level1', 'level2', 'level3'],
                    'price_level': price_lv,
                    'course_order': i,
                },
            )

            self.stdout.write(f'  {"✨" if created else "↻"} 教練 {name}')

        # ========== 4. 訂單（ReservationGroup + Reservation + Booking + Payment）==========
        # 找一個 user 當 customer
        try:
            demo_user = User.objects.filter(is_superuser=False).first()
            if not demo_user:
                demo_user = User.objects.create_user(
                    username='demo_student', email='demo@example.com', password='demo1234',
                    first_name='Demo', last_name='Student',
                )
                self.stdout.write(f'  ✨ 建立 demo user: demo_student')
        except Exception as e:
            self.stderr.write(f'  ⚠️ 無法建立 demo user: {e}')
            demo_user = None

        # 訂單樣本
        order_samples = [
            (resorts['tomamu'], type_snowboard, 'level3', 2, coaches['Cash 校長'], 'paid', 8500),
            (resorts['furano'], type_ski, 'level2', 1, None, 'pending', 4500),
            (resorts['tomamu'], type_offpiste, 'level4', 3, coaches['Cash 校長'], 'paid', 12000),
            (resorts['tomamu'], type_snowboard, 'no_exp', 4, None, 'unpaid', 8500),
            (resorts['sapporo_kokusai'], type_ski, 'level2', 2, None, 'paid', 7800),
        ]

        for i, (resort, ct, level, ppl, coach, payment_status, fee) in enumerate(order_samples):
            group, created = ReservationGroup.objects.get_or_create(
                client=client, name=f'demo-order-{i+1}',
                defaults={'user': demo_user},
            )
            if not created:
                continue

            res = Reservation.objects.create(
                group=group,
                preferred_coach=coach,
                is_preferred_coach=bool(coach),
                resort=resort,
                course_type=ct,
                max_ability_level=level,
                number_of_people=ppl,
                language='zh',
                status='auto_assigned' if coach else 'created',
                total_fee=fee,
                payment_amount=fee,
            )

            # 加幾個 booking
            base_date = date.today() + timedelta(days=10 + i * 3)
            Booking.objects.create(
                reservation=res,
                course_name=f'{ct.name}',
                course_type=ct.name,
                date=base_date,
                start_time=time(9, 0),
                end_time=time(12, 0),
                is_scheduled=bool(coach),
            )

            # Payment
            Payment.objects.create(
                reservation_group=group,
                user=demo_user,
                status=payment_status,
                payment_method='TT' if payment_status == 'paid' else 'newebpay',
            )

            self.stdout.write(f'  ✨ 訂單 SL-{group.id} ({resort.display_name} / {ct.name})')

        # ========== 5. 教練請假 ==========
        leave, created = CoachLeaveRequest.objects.get_or_create(
            coach=coaches['Cash 校長'],
            start_date=date.today() + timedelta(days=15),
            defaults={
                'end_date': date.today() + timedelta(days=17),
                'reason': '家中有事，需請假處理',
                'status': 'pending',
            },
        )
        if created:
            self.stdout.write(f'  ✨ 教練請假：Cash 校長')

        self.stdout.write(self.style.SUCCESS('\n✅ Demo 資料建立完成！'))
        self.stdout.write('  重新整理 /snowland/admin 應該就能看到資料了')
