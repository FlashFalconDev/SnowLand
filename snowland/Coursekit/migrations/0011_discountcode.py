from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("Coursekit", "0010_coursecategory_service_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="DiscountCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, verbose_name="折扣碼")),
                ("name", models.CharField(blank=True, max_length=100, verbose_name="活動名稱")),
                ("description", models.TextField(blank=True, verbose_name="備註")),
                (
                    "discount_type",
                    models.CharField(
                        choices=[("percent", "百分比折扣"), ("amount", "固定金額折扣")],
                        default="amount",
                        max_length=20,
                        verbose_name="折扣類型",
                    ),
                ),
                ("discount_value", models.PositiveIntegerField(default=0, verbose_name="折扣數值")),
                ("max_discount_amount", models.PositiveIntegerField(blank=True, null=True, verbose_name="最高折抵金額")),
                ("min_order_amount", models.PositiveIntegerField(default=0, verbose_name="最低訂單金額")),
                (
                    "apply_scope",
                    models.CharField(
                        choices=[
                            ("all", "全部訂單"),
                            ("ski", "滑雪課程"),
                            ("photo", "攝影服務"),
                            ("bundle", "課程搭配/組合"),
                        ],
                        default="all",
                        max_length=20,
                        verbose_name="適用範圍",
                    ),
                ),
                ("require_multiple_items", models.BooleanField(default=False, verbose_name="需搭配多項課程或服務")),
                ("can_combine", models.BooleanField(default=False, verbose_name="可與其他優惠並用")),
                ("usage_limit", models.PositiveIntegerField(blank=True, null=True, verbose_name="使用上限")),
                ("used_count", models.PositiveIntegerField(default=0, verbose_name="已使用次數")),
                ("start_at", models.DateTimeField(blank=True, null=True, verbose_name="開始時間")),
                ("end_at", models.DateTimeField(blank=True, null=True, verbose_name="結束時間")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否啟用")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="建立時間")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新時間")),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="discount_codes",
                        to="Client.client",
                        verbose_name="所屬客戶",
                    ),
                ),
            ],
            options={
                "verbose_name": "7. 優惠折扣碼",
                "verbose_name_plural": "7. 優惠折扣碼",
                "ordering": ["-is_active", "-created_at", "code"],
                "unique_together": {("client", "code")},
            },
        ),
    ]
