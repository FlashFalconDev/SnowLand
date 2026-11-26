from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0048_reservationgroup_test_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffbookinglink',
            name='snapshot_version',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='staffbookinglink',
            name='quoted_total',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
