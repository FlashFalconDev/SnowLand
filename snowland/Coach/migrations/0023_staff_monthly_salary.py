from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Coach', '0022_coachpayrule_effective_from')]

    operations = [
        migrations.AddField(
            model_name='staffincentiverule',
            name='monthly_salary',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='staffincentiverule',
            name='employment_start',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='staffincentiverule',
            name='employment_end',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='staffincentivestatement',
            name='monthly_salary_amount',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='staffincentivestatement',
            name='monthly_salary_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
