from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Coach', '0019_staff_incentive_statements')]
    operations = [migrations.AddField(model_name='payrollstatement', name='settlement_snapshot',
        field=models.JSONField(blank=True, default=dict))]
