from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0013_memberdetail_waiver_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='ability_level_counts',
            field=models.JSONField(blank=True, default=dict, verbose_name='各等級學員人數'),
        ),
    ]
