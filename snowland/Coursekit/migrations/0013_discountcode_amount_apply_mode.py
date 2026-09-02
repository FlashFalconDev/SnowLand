from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Coursekit", "0012_discountcode_auto_rules"),
    ]

    operations = [
        migrations.AddField(
            model_name="discountcode",
            name="amount_apply_mode",
            field=models.CharField(
                choices=[
                    ("order", "整筆一次"),
                    ("item", "每個項目"),
                    ("course", "每堂課"),
                    ("hour", "每小時"),
                ],
                default="order",
                max_length=20,
                verbose_name="固定金額折扣單位",
            ),
        ),
    ]
