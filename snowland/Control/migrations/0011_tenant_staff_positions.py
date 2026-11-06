import json

import django.db.models.deletion
from django.db import migrations, models


def backfill_positions(apps, schema_editor):
    Membership = apps.get_model('Control', 'TenantStaffMembership')
    Position = apps.get_model('Control', 'TenantStaffPosition')
    alias = schema_editor.connection.alias
    labels = dict(Membership._meta.get_field('role').choices)
    labels['coach'] = '教練兼任後台'
    global_roles = {'hq_admin', 'marketing', 'web_editor', 'insurance', 'assistant'}
    positions = {}
    counters = {}

    for member in Membership.objects.using(alias).filter(is_manager=True).order_by('pk').iterator():
        campuses = tuple(member.campuses.using(alias).filter(client_id=member.client_id).order_by('id').values_list('id', flat=True))
        all_campuses = member.all_campuses
        if all_campuses is None:
            all_campuses = member.role in global_roles or (not member.role and member.admin_permissions is None)
        if all_campuses:
            campuses = ()
        permissions = member.admin_permissions
        permission_signature = sorted({key for key in permissions if isinstance(key, str)}) if isinstance(permissions, list) else permissions
        signature = (member.client_id, member.role, all_campuses, campuses, json.dumps(permission_signature, sort_keys=True))
        if signature not in positions:
            label = labels.get(member.role, '一般後台人員')
            counter_key = (member.client_id, label)
            count = counters.get(counter_key, 0) + 1
            counters[counter_key] = count
            position = Position.objects.using(alias).create(
                client_id=member.client_id, name=label if count == 1 else f'{label}（{count}）',
                role=member.role, permissions=permissions, all_campuses=all_campuses,
            )
            position.campuses.set(campuses)
            positions[signature] = position
        member.positions.add(positions[signature])


class Migration(migrations.Migration):
    dependencies = [('Control', '0010_tenantstaffmembership_all_campuses')]

    operations = [
        migrations.CreateModel(
            name='TenantStaffPosition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('role', models.CharField(blank=True, default='', max_length=30)),
                ('permissions', models.JSONField(blank=True, default=list, null=True)),
                ('all_campuses', models.BooleanField(default=False)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staff_positions', to='Client.client')),
                ('campuses', models.ManyToManyField(blank=True, related_name='staff_positions', to='Resorts.campus')),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('client', 'name'), name='unique_staff_position_name')]},
        ),
        migrations.AddField(
            model_name='tenantstaffmembership', name='positions',
            field=models.ManyToManyField(blank=True, related_name='memberships', to='Control.tenantstaffposition'),
        ),
        migrations.RunPython(backfill_positions, migrations.RunPython.noop),
    ]
