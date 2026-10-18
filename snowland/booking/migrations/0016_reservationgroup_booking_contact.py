from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0015_shared_course_class'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservationgroup',
            name='booking_contact',
            field=models.JSONField(blank=True, default=dict, verbose_name='訂課聯絡資料'),
        ),
    ]
