from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0011_cancellationrequest_refund_choice'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberdetail',
            name='insurance_data',
            field=models.JSONField(blank=True, default=dict, verbose_name='保險資料'),
        ),
        migrations.AddField(
            model_name='memberdetail',
            name='waiver_signature',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='聲明書簽署姓名'),
        ),
    ]
