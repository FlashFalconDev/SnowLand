from datetime import date, time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from Client.models import Client
from Coursekit.models import (
    CourseCategory,
    CoursePricing,
    CoursePricingTier,
    CourseSession,
    CourseTemplate,
    CourseType,
    SeasonSetting,
)
from Resorts.models import ResortFee, Resorts


class Command(BaseCommand):
    help = "建立可操作 SnowLand 本機前後台的最小非個資測試資料"

    @transaction.atomic
    def handle(self, *args, **options):
        db = connection.settings_dict
        if not settings.DEBUG:
            raise CommandError("此命令只能在 DEBUG 模式執行")
        if db.get("HOST") not in {"127.0.0.1", "localhost", "::1"}:
            raise CommandError("此命令只能寫入本機資料庫")
        if not str(db.get("NAME") or "").startswith("test_"):
            raise CommandError("資料庫名稱必須以 test_ 開頭")

        client, _ = Client.objects.update_or_create(
            internal_code="snowland",
            defaults={"name": "SnowLand 本機測試", "is_active": True},
        )
        resort, _ = Resorts.objects.update_or_create(
            name="tomamu",
            defaults={
                "client": client,
                "display_name": "星野 Tomamu",
                "auto_scheduling_enabled": True,
            },
        )

        categories = [
            ("單板 Snowboard", 1),
            ("雙板 Ski", 2),
        ]
        template_specs = [
            ("全天課程", 5, time(9, 0), time(15, 0), 12000),
            ("半天上午", 3, time(9, 0), time(12, 0), 9000),
            ("半天下午", 3, time(13, 0), time(16, 0), 9000),
        ]

        for category_name, category_order in categories:
            category, _ = CourseCategory.objects.update_or_create(
                client=client,
                name=category_name,
                defaults={"display_order": category_order, "service_type": "ski"},
            )
            category.available_resorts.set([resort])

            course_type, _ = CourseType.objects.update_or_create(
                category=category,
                name="一般課程",
                defaults={"display_order": 1},
            )
            course_type.available_resorts.set([resort])

            for template_order, (name, hours, start, end, base_price) in enumerate(template_specs, 1):
                template, _ = CourseTemplate.objects.update_or_create(
                    course_type=course_type,
                    name=name,
                    defaults={
                        "duration_hours": hours,
                        "max_capacity": 6,
                        "display_order": template_order,
                        "is_active": True,
                        "booking_open_date": date(2026, 9, 1),
                        "booking_close_date": date(2027, 4, 30),
                        "course_start_date": date(2026, 11, 20),
                        "course_end_date": date(2027, 4, 30),
                    },
                )
                template.resorts.set([resort])
                CourseSession.objects.update_or_create(
                    template=template,
                    start_time=start,
                    defaults={"end_time": end, "is_active": True},
                )

                pricing = CoursePricing.objects.filter(resort=resort, templates=template).first()
                if pricing is None:
                    pricing = CoursePricing.objects.create(
                        resort=resort,
                        base_price_off_peak=base_price,
                        peak_season_surcharge=2000,
                        additional_person_fee=2000,
                        max_capacity=6,
                        is_active=True,
                    )
                    pricing.templates.add(template)
                else:
                    pricing.base_price_off_peak = base_price
                    pricing.peak_season_surcharge = 2000
                    pricing.additional_person_fee = 2000
                    pricing.max_capacity = 6
                    pricing.is_active = True
                    pricing.save()

                for people in range(1, 7):
                    CoursePricingTier.objects.update_or_create(
                        pricing=pricing,
                        min_people=people,
                        max_people=people,
                        defaults={
                            "price": base_price + (people - 1) * 2000,
                            "is_active": True,
                            "display_order": people,
                        },
                    )

        SeasonSetting.objects.update_or_create(
            name="2026–2027 測試旺季",
            defaults={
                "season_type": "peak",
                "start_date": date(2026, 12, 20),
                "end_date": date(2027, 1, 10),
            },
        )
        for fee_type, price in (
            ("coach_general", 0),
            ("coach_lv2", 2000),
            ("coach_director", 4000),
            ("language_zh", 0),
            ("language_en", 1000),
            ("language_yue", 1000),
        ):
            ResortFee.objects.update_or_create(
                resort=resort,
                fee_type=fee_type,
                defaults={"price": price, "is_active": True, "description": "本機測試資料"},
            )

        self.stdout.write(self.style.SUCCESS(
            "SnowLand 最小本機資料已就緒：1 租戶、1 雪場、2 類別、2 類型、6 模板、6 時段。"
        ))
