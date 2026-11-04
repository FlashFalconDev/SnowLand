from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('booking', '0038_tenant_loyalty')]

    operations = [
        migrations.AddField(
            model_name='booking', name='fee_snapshot',
            field=models.JSONField(blank=True, null=True, verbose_name='堂次計價紀錄'),
        ),
    ]
