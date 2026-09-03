from datetime import time, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from Client.models import Client
from Coach.models import (
    Coach,
    CoachCourseLevel,
    CoachPayRule,
    CoachResort,
    StaffIncentiveRule,
)
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from Resorts.models import Campus, OperatingPolicy, PaymentAccount, Resorts
from booking.models import (
    Booking,
    CancellationRequest,
    CourseEvaluation,
    MemberDetail,
    MemberProfile,
    NotificationDelivery,
    NotificationTemplate,
    OrderRevision,
    Payment,
    Reservation,
    ReservationGroup,
    StaffBookingLink,
)
from Coach.payroll import calculate_payroll_statement


class Command(BaseCommand):
    help = "建立 SnowLand Console UX 驗收用的完整本機假資料（可安全重跑）"

    def _assert_local_test_database(self):
        db = connection.settings_dict
        if not settings.DEBUG:
            raise CommandError("此命令只能在 DEBUG 模式執行")
        if db.get("HOST") not in {"127.0.0.1", "localhost", "::1"}:
            raise CommandError("此命令只能寫入本機資料庫")
        if not str(db.get("NAME") or "").startswith("test_"):
            raise CommandError("資料庫名稱必須以 test_ 開頭")

    @transaction.atomic
    def handle(self, *args, **options):
        self._assert_local_test_database()
        call_command("seed_minimal_local", verbosity=0)

        today = timezone.localdate()
        now = timezone.now()
        client = Client.objects.get(internal_code="snowland")

        # 早期本機資料曾另外建立 hq，合併回既有 main，避免畫面出現兩個「總部」。
        Campus.objects.filter(client=client, code="hq", name="北海道營運總部").delete()

        resort_specs = [
            ("tomamu", "星野 Tomamu"),
            ("furano", "富良野 Furano"),
            ("niseko", "二世谷 Niseko"),
        ]
        resorts = {}
        for code, display_name in resort_specs:
            resorts[code], _ = Resorts.objects.update_or_create(
                name=code,
                defaults={"client": client, "display_name": display_name, "auto_scheduling_enabled": True},
            )

        campus_specs = [
            ("main", "北海道營運總部", ["tomamu", "furano", "niseko"], "統一查看所有校區，不直接取代各校區管理。"),
            ("east", "道東校區", ["tomamu", "furano"], "負責星野與富良野雪場。"),
            ("west", "道央校區", ["furano", "niseko"], "負責富良野與二世谷雪場。"),
        ]
        campuses = {}
        for order, (code, name, resort_codes, description) in enumerate(campus_specs):
            campus, _ = Campus.objects.update_or_create(
                client=client,
                code=code,
                defaults={
                    "name": name,
                    "description": description,
                    "is_active": True,
                    "display_order": order,
                },
            )
            campus.resorts.set([resorts[item] for item in resort_codes])
            campuses[code] = campus
            OperatingPolicy.objects.update_or_create(
                client=client,
                campus=campus,
                defaults={
                    "unpaid_hold_days": 3,
                    "provisional_extra_groups": 3,
                    "cancellation_fee_percent": 5,
                    "leave_advance_days": 3,
                    "leave_daily_coach_limit": 2,
                    "leave_max_consecutive_days": 2,
                    "course_reminder_days": [7, 3, 1],
                },
            )

        account_specs = [
            ("DEMO｜全公司台幣帳戶", "main", None, True),
            ("DEMO｜道東雪場帳戶", "east", "tomamu", False),
            ("DEMO｜道央雪場帳戶", "west", "niseko", False),
        ]
        accounts = {}
        for order, (name, campus_code, resort_code, is_default) in enumerate(account_specs):
            account, _ = PaymentAccount.objects.update_or_create(
                client=client,
                name=name,
                defaults={
                    "bank_name": "DEMO BANK",
                    "bank_branch": "本機測試分行",
                    "account_number": f"DEMO-000{order + 1}",
                    "account_holder": "SnowLand DEMO",
                    "is_default": is_default,
                    "is_active": True,
                    "display_order": order,
                },
            )
            account.campuses.set([campuses[campus_code]])
            account.resorts.set([resorts[resort_code]] if resort_code else [])
            accounts[campus_code] = account

        users = {}
        staff_specs = [
            ("demo-hq-admin", "總部管理員", "hq_admin", ["main", "east", "west"], True, False),
            ("demo-marketing", "行銷小編", "marketing", ["main"], True, False),
            ("demo-east-manager", "道東主管", "campus_manager", ["east"], True, False),
            ("demo-west-principal", "道央校長", "campus_principal", ["west"], True, False),
            ("demo-insurance", "保險專員", "insurance", ["east", "west"], True, False),
            ("demo-coach-aki", "Aki 教練", "coach", ["east"], False, True),
            ("demo-coach-yuki", "Yuki 教練", "coach", ["east", "west"], False, True),
            ("demo-coach-ken", "Ken 教練", "coach", ["west"], False, True),
        ]
        all_permissions = [
            "dashboard", "campuses", "staff", "orders", "notifications", "evaluations",
            "insurance_records", "payroll", "payment_accounts", "course_types",
        ]
        for username, display_name, role, campus_codes, is_manager, is_coach in staff_specs:
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "first_name": display_name,
                    "email": f"{username}@demo.local",
                    "is_active": True,
                },
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
            profile = user.userprofile
            profile.role = role
            profile.is_manager = is_manager
            profile.is_coach = is_coach
            profile.admin_permissions = all_permissions if role == "hq_admin" else None
            profile.save()
            profile.campuses.set([campuses[code] for code in campus_codes])
            users[username] = user

        categories = list(CourseCategory.objects.filter(client=client).order_by("display_order"))
        for category in categories:
            category.available_resorts.set(resorts.values())
            for course_type in category.types.all():
                course_type.available_resorts.set(resorts.values())
                for template in course_type.templates.all():
                    template.resorts.set(resorts.values())

        course_types = list(CourseType.objects.filter(category__client=client).order_by("id"))
        templates = list(CourseTemplate.objects.filter(course_type__category__client=client).order_by("id"))
        coach_specs = [
            ("demo-coach-aki", "Aki 教練", ["east"], ["tomamu", "furano"], "Lv2", "active"),
            ("demo-coach-yuki", "Yuki 教練", ["east", "west"], ["furano", "niseko"], "Lv3", "active"),
            ("demo-coach-ken", "Ken 教練", ["west"], ["niseko"], "director", "passive"),
        ]
        coaches = {}
        for index, (username, name, campus_codes, resort_codes, price_level, availability) in enumerate(coach_specs):
            coach, _ = Coach.objects.update_or_create(
                client=client,
                user=users[username],
                defaults={
                    "name": name,
                    "languages": ["zh", "en"] if index < 2 else ["zh"],
                    "availability_status": availability,
                    "assignment_score": index * 2,
                    "website_enabled": True,
                    "website_slug": username.removeprefix("demo-coach-"),
                    "website_sort_order": index,
                    "website_card_bio": "DEMO 教練資料，僅供本機操作測試。",
                    "certifications": [{
                        "category": "snowboard",
                        "certificate": "CASI" if index == 0 else "JSBA",
                        "level": "Level 2" if index == 0 else "Level 1",
                        "note": "",
                        "show_on_website": True,
                    }],
                },
            )
            coach.campuses.set([campuses[code] for code in campus_codes])
            for priority, resort_code in enumerate(resort_codes):
                CoachResort.objects.update_or_create(
                    coach=coach,
                    resort=resorts[resort_code],
                    defaults={"resort_priority": priority, "assignment_score": index},
                )
            for course_type in course_types:
                CoachCourseLevel.objects.update_or_create(
                    coach=coach,
                    course_type=course_type,
                    defaults={
                        "ability_levels": ["no_exp", "level1", "level2"],
                        "price_level": price_level,
                        "course_order": index,
                    },
                )
            CoachPayRule.objects.update_or_create(
                coach=coach,
                course_type=None,
                discipline="snowboard",
                certification_level=price_level,
                defaults={
                    "hourly_rate": 1200 + index * 200,
                    "specified_fee": 500 + index * 250,
                    "referral_percent": 10,
                    "assistance_hour_factor": 0.5,
                    "supervisor_allowance": 500 if price_level == "director" else 0,
                    "is_active": True,
                },
            )
            coaches[username] = coach

        StaffIncentiveRule.objects.update_or_create(
            user=users["demo-east-manager"], campus=campuses["east"],
            defaults={"completed_order_percent": 2, "is_active": True},
        )

        customer_specs = [
            ("demo-customer-lin", "小林", "lin.customer@demo.local", "gold", 3200),
            ("demo-customer-chen", "小陳", "chen.customer@demo.local", "silver", 1200),
            ("demo-customer-wang", "小王", "wang.customer@demo.local", "new", 100),
            ("demo-customer-lee", "小李", "lee.customer@demo.local", "alumni", 600),
            ("demo-customer-chang", "小張", "chang.customer@demo.local", "new", 0),
            ("demo-customer-ho", "小何", "ho.customer@demo.local", "silver", 850),
        ]
        customers = {}
        for username, name, email, level, points in customer_specs:
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={"first_name": name, "email": email, "is_active": True},
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
            MemberProfile.objects.update_or_create(
                user=user,
                defaults={"level": level, "points": points, "alumni_verified": level != "new"},
            )
            customers[username] = user

        order_specs = [
            ("DEMO-001", "林小姐｜星野單板全天", "east", "tomamu", "demo-customer-lin", "demo-coach-aki", "completed", "paid", "credit_card", -1, "Instagram", 2),
            ("DEMO-002", "陳先生｜富良野雙板上午", "east", "furano", "demo-customer-chen", "demo-coach-yuki", "auto_assigned", "paid", "TT", 4, "朋友介紹", 3),
            ("DEMO-003", "王小姐｜二世谷單板下午", "west", "niseko", "demo-customer-wang", "demo-coach-ken", "manual_assignment_needed", "pending", "TT", 7, "Google", 1),
            ("DEMO-004", "李先生｜富良野單板全天", "west", "furano", "demo-customer-lee", "demo-coach-yuki", "created", "unpaid", "credit_card", 15, "官方網站", 4),
            ("DEMO-005", "張小姐｜星野雙板上午", "east", "tomamu", "demo-customer-chang", "demo-coach-aki", "cancelled", "refunded", "credit_card", 22, "Facebook", 2),
            ("DEMO-006", "何先生｜二世谷單板全天", "west", "niseko", "demo-customer-ho", "demo-coach-ken", "pending_coach_confirmation", "expired", "TT", 30, "合作旅行社", 2),
        ]
        created_groups = []
        for index, (order_number, name, campus_code, resort_code, customer_name, coach_name, status, payment_status, payment_method, day_offset, source, people) in enumerate(order_specs):
            customer = customers[customer_name]
            coach = coaches[coach_name]
            group, _ = ReservationGroup.objects.update_or_create(
                client=client,
                order_number=order_number,
                defaults={
                    "campus": campuses[campus_code],
                    "name": name,
                    "marketing_source": source,
                    "marketing_source_detail": "DEMO UX 驗收資料",
                    "user": customer,
                    "source_country": "TW",
                    "line_group_url": "https://example.test/demo-line-group",
                },
            )
            ReservationGroup.objects.filter(pk=group.pk).update(created_at=now - timedelta(days=index))
            course_type = course_types[index % len(course_types)]
            template = templates[index % len(templates)]
            reservation, _ = Reservation.objects.update_or_create(
                group=group,
                defaults={
                    "resort": resorts[resort_code],
                    "course_type": course_type,
                    "course_template": template,
                    "preferred_coach": coach,
                    "is_preferred_coach": index % 2 == 0,
                    "status": status,
                    "number_of_people": people,
                    "language": "zh",
                    "course_fee": 12000 + index * 1000,
                    "coach_fee": 1000 if index % 2 == 0 else 0,
                    "equipment_rental_fee": 1500 if index in (1, 3) else 0,
                    "discount_amount": 1000 if index == 0 else 0,
                    "discount_code": "DEMO1000" if index == 0 else "",
                },
            )
            booking, _ = Booking.objects.update_or_create(
                reservation=reservation,
                date=today + timedelta(days=day_offset),
                defaults={
                    "course_type": course_type.category.name,
                    "course_name": template.name,
                    "start_time": time(9 if index % 2 == 0 else 13),
                    "end_time": time(15 if index % 2 == 0 else 16),
                    "is_scheduled": status not in {"created", "manual_assignment_needed", "cancelled"},
                },
            )
            payment, _ = Payment.objects.update_or_create(
                reservation_group=group,
                defaults={
                    "user": customer,
                    "status": payment_status,
                    "payment_method": payment_method,
                    "payment_account": accounts[campus_code],
                    "expires_at": now + timedelta(days=3) if payment_status in {"unpaid", "pending"} else None,
                    "DataJSON": {"contact": {"email": customer.email, "name": customer.first_name}, "demo": True},
                },
            )
            member, _ = MemberDetail.objects.update_or_create(
                reservation=reservation,
                user=customer,
                defaults={
                    "age_range": "25-35y",
                    "snowboard_skills": ["雪場C turn"] if index % 2 == 0 else ["無經驗"],
                    "ski_skills": ["雪場全制動轉彎"] if index % 2 else ["無經驗"],
                    "insurance_completed_at": now if index not in (2, 5) else None,
                    "waiver_completed_at": now if index not in (3, 5) else None,
                },
            )
            OrderRevision.objects.update_or_create(
                group=group,
                version=1,
                defaults={
                    "change_type": "create",
                    "snapshot": {"order_number": order_number, "status": status, "amount": reservation.payment_amount},
                    "created_by": users["demo-hq-admin"],
                    "reason": "DEMO 初始訂單",
                },
            )
            if status == "cancelled":
                CancellationRequest.objects.update_or_create(
                    group=group,
                    defaults={
                        "status": "refunded",
                        "reason": "schedule",
                        "reason_note": "DEMO：行程變更",
                        "original_amount": reservation.payment_amount,
                        "days_before": 22,
                        "refund_percent": 80,
                        "handling_fee_percent": 5,
                        "refund_amount": int(reservation.payment_amount * 0.75),
                        "reviewed_by": users["demo-hq-admin"],
                        "reviewed_at": now,
                    },
                )
            if status == "completed":
                CourseEvaluation.objects.update_or_create(
                    booking=booking,
                    member=member,
                    defaults={
                        "coach": coach,
                        "self_assessment": {"confidence": 4, "turning": 3},
                        "coach_assessment": {"balance": 4, "turning": 4, "safety": 5},
                        "learning_progress": {"before": "level1", "after": "level2"},
                        "trail_names": ["Beginner Course", "Silver Bell"],
                        "coach_notes": "DEMO：已能穩定完成連續轉彎，下次可練習速度控制。",
                        "completed_at": now,
                    },
                )
            created_groups.append(group)

        template_specs = [
            ("DEMO｜付款完成 Email", "payment_confirmed", "email", "付款完成", "您好，已收到付款。", 0, None),
            ("DEMO｜課前 7 天 LINE", "pre_course", "line", "課前提醒", "請確認集合時間與裝備。", 7, "east"),
            ("DEMO｜資料未完成提醒", "missing_documents", "in_app", "資料待補", "請補齊保險與聲明書。", 3, "west"),
        ]
        notification_templates = []
        for name, event, channel, subject, body, days_before, campus_code in template_specs:
            template, _ = NotificationTemplate.objects.update_or_create(
                client=client,
                name=name,
                defaults={
                    "campus": campuses[campus_code] if campus_code else None,
                    "event": event,
                    "channel": channel,
                    "subject": subject,
                    "body": body,
                    "days_before": days_before,
                    "is_active": True,
                },
            )
            notification_templates.append(template)

        delivery_specs = [
            (notification_templates[0], created_groups[0], "sent", -1, ""),
            (notification_templates[1], created_groups[1], "scheduled", 1, ""),
            (notification_templates[2], created_groups[2], "failed", 0, "DEMO：LINE 尚未綁定"),
        ]
        for template, group, status, hour_offset, error in delivery_specs:
            NotificationDelivery.objects.update_or_create(
                template=template,
                group=group,
                recipient=group.user.email,
                defaults={
                    "scheduled_at": now + timedelta(hours=hour_offset),
                    "sent_at": now if status == "sent" else None,
                    "status": status,
                    "error_message": error,
                    "payload": {"demo": True, "order_number": group.order_number},
                },
            )

        StaffBookingLink.objects.update_or_create(
            client=client,
            title="DEMO｜道東櫃台代客下單",
            defaults={
                "campus": campuses["east"],
                "created_by": users["demo-east-manager"],
                "cart_snapshot": [{"resortId": resorts["tomamu"].id, "people": 2}],
                "expires_at": now + timedelta(days=7),
                "is_active": True,
                "used_at": None,
                "used_by": None,
            },
        )

        for coach_key, campus_code in (("demo-coach-aki", "east"), ("demo-coach-yuki", "east"), ("demo-coach-ken", "west")):
            coach = coaches[coach_key]
            campus = campuses[campus_code]
            statement = calculate_payroll_statement(
                coach=coach,
                campus=campus,
                period_start=today.replace(day=1),
                period_end=today,
            )
            statement.notes = "DEMO｜本機 UX 驗收薪資單"
            statement.save(update_fields=["notes"])

        self.stdout.write(self.style.SUCCESS(
            "Console DEMO 資料完成：3 校區、3 雪場、8 員工、3 教練、6 訂單、3 通知、3 薪資單。"
        ))
