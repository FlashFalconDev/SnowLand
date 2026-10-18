from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('Resorts', '0009_remove_operatingpolicy_unique_client_default_operating_policy'),
    ]

    operations = [
        migrations.AddField(
            model_name='resorts',
            name='trail_names',
            field=models.JSONField(blank=True, default=list, verbose_name='課程評量可勾選雪道'),
        ),
    ]
