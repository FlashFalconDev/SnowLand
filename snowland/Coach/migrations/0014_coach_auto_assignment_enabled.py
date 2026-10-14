from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Coach', '0013_coach_schedule_visibility'),
    ]

    operations = [
        migrations.AddField(
            model_name='coach',
            name='auto_assignment_enabled',
            field=models.BooleanField(default=True, verbose_name='參與自動排課'),
        ),
    ]
