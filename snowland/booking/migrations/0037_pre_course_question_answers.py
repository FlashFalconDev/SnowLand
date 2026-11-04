from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('booking', '0036_memberwaiversignature')]
    operations = [
        migrations.AddField('memberdetail', 'pre_course_answers', models.JSONField(default=dict, blank=True)),
        migrations.AddField('memberwaiversignature', 'form_snapshot', models.JSONField(default=dict, blank=True)),
    ]
