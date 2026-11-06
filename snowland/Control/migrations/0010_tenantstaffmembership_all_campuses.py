from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Control', '0009_backfill_tenant_staff')]

    operations = [
        migrations.AddField(
            model_name='tenantstaffmembership',
            name='all_campuses',
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
    ]
