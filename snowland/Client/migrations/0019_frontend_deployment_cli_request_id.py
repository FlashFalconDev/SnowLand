from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Client', '0018_site_translation')]

    operations = [
        migrations.AddField(
            model_name='frontenddeployment',
            name='cli_request_id',
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]
