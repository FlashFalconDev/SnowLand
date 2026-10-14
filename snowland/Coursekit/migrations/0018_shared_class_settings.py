from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('Coursekit', '0017_alter_coursetemplate_minimum_group_size'),
    ]

    operations = [
        migrations.AddField(
            model_name='coursetemplate',
            name='shared_class_enabled',
            field=models.BooleanField(default=False, verbose_name='開放跨訂單湊班'),
        ),
        migrations.AddField(
            model_name='coursetemplate',
            name='shared_class_minimum_students',
            field=models.PositiveSmallIntegerField(default=3, verbose_name='湊班成班人數'),
        ),
    ]
