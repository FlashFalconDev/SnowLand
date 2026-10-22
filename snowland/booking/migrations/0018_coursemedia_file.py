from django.db import migrations, models
import booking.media_files


class Migration(migrations.Migration):
    dependencies = [('booking', '0017_shared_class_ready_notification')]
    operations = [
        migrations.AddField(
            model_name='coursemedia', name='file',
            field=models.FileField(blank=True, default='', max_length=240,
                                   storage=booking.media_files.PrivateCourseMediaStorage(), upload_to='course-records/'),
        ),
    ]
