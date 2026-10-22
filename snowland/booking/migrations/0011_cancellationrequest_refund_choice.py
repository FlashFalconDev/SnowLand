from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0010_memberdetail_guardian_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='cancellationrequest',
            name='calculation_mode',
            field=models.CharField(choices=[('auto', '依訂單日期'), ('rule', '指定退費方案'), ('manual', '特殊金額')], default='auto', max_length=10),
        ),
        migrations.AddField(
            model_name='cancellationrequest',
            name='selected_rule_days_before',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
