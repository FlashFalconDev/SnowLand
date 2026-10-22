import django.db.models.deletion
from django.db import migrations, models


def bind_existing_managers(apps, schema_editor):
    Client = apps.get_model('Client', 'Client')
    Coach = apps.get_model('Coach', 'Coach')
    UserProfile = apps.get_model('Control', 'UserProfile')
    active_client_ids = list(Client.objects.filter(is_active=True).values_list('id', flat=True))
    only_active_client_id = active_client_ids[0] if len(active_client_ids) == 1 else None

    for profile in UserProfile.objects.filter(is_manager=True).iterator():
        client_ids = set(profile.campuses.values_list('client_id', flat=True))
        client_ids.update(
            Coach.objects.filter(user_id=profile.user_id, client_id__isnull=False)
            .values_list('client_id', flat=True)
        )
        client_ids.discard(None)
        client_id = next(iter(client_ids)) if len(client_ids) == 1 else (
            only_active_client_id if not client_ids else None
        )
        if client_id is not None:
            profile.manager_client_id = client_id
            profile.save(update_fields=['manager_client'])


class Migration(migrations.Migration):
    dependencies = [
        ('Client', '0001_initial'),
        ('Coach', '0006_coach_client'),
        ('Control', '0006_userprofile_campuses_userprofile_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='manager_client',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='Client.client',
            ),
        ),
        migrations.RunPython(bind_existing_managers, migrations.RunPython.noop),
    ]
