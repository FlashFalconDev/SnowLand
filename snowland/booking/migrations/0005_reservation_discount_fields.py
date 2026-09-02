from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0004_reservation_equipment_assistance_time"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="discount_amount",
            field=models.PositiveIntegerField(default=0, verbose_name="折扣金額"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="discount_code",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="折扣碼"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="discount_name",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="折扣名稱"),
        ),
    ]
