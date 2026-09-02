from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Coursekit", "0011_discountcode"),
    ]

    operations = [
        migrations.AddField(
            model_name="discountcode",
            name="is_auto_apply",
            field=models.BooleanField(default=False, verbose_name="自動套用"),
        ),
        migrations.AddField(
            model_name="discountcode",
            name="new_customer_only",
            field=models.BooleanField(default=False, verbose_name="限新客"),
        ),
    ]
