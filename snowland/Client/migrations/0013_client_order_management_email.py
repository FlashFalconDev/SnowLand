from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Client', '0012_backfill_school_members')]

    operations = [
        migrations.AddField(
            model_name='client',
            name='order_management_email',
            field=models.EmailField(max_length=200, blank=True, default='', verbose_name='訂單管理通知信箱'),
        ),
    ]
