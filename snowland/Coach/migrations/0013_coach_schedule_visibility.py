from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Coach', '0012_payrollstatement_payrollline_coachpayrule_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='coach',
            name='schedule_visibility',
            field=models.CharField(
                choices=[('ten_days', '過往及未來 10 天'), ('full', '全部課程')],
                default='ten_days',
                max_length=20,
                verbose_name='課程可見範圍',
            ),
        ),
    ]
