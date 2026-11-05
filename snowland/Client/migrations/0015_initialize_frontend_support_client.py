from django.contrib.auth.hashers import make_password
from django.db import migrations


def initialize_support_client(apps, schema_editor):
    Client = apps.get_model('Client', 'Client')
    Client.objects.using(schema_editor.connection.alias).get_or_create(
        internal_code='flashfalcon',
        defaults={
            'name': 'FlashFalcon',
            'is_active': True,
            'password': make_password(None),
        },
    )


class Migration(migrations.Migration):
    dependencies = [('Client', '0014_merge_order_email_frontend_release')]

    operations = [
        migrations.RunPython(initialize_support_client, migrations.RunPython.noop),
    ]
