from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0046_payment_bank_posted_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservationgroup',
            name='marketing_source_override',
            field=models.TextField(null=True, blank=True, editable=False, verbose_name='補登客人來源'),
        ),
    ]
