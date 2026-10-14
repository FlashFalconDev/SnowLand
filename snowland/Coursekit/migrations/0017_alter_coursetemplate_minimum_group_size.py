from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Coursekit', '0016_coursetemplate_billing_mode_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coursetemplate',
            name='minimum_group_size',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='單筆預約最低人數'),
        ),
    ]
