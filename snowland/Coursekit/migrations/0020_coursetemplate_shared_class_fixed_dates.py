from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Coursekit', '0019_coursetemplate_payroll_hours')]
    operations = [
        migrations.AddField(
            model_name='coursetemplate',
            name='shared_class_fixed_dates',
            field=models.BooleanField(default=False, verbose_name='只開放學校指定的團體班日期'),
        ),
    ]
