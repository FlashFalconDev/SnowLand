import booking.media_files
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('booking', '0022_notificationdelivery_sending')]
    operations = [migrations.AddField(
        model_name='reservationgroup', name='line_group_qr',
        field=models.FileField(blank=True, storage=booking.media_files.PrivateCourseMediaStorage(), upload_to='class_group_qr', verbose_name='上課群組 QR 碼'),
    )]
