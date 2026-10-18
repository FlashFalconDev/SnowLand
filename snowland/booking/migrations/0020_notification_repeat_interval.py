from django.core.validators import MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('booking', '0019_participant_invitation')]

    operations = [
        migrations.AddField(
            model_name='notificationtemplate',
            name='repeat_interval_days',
            field=models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(365)], help_text='資料未完成時每隔幾天提醒；0 為只提醒一次'),
        ),
    ]
