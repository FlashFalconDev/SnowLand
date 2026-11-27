from django.db import migrations


BASE_PERMISSIONS = ['insurance_records']
DEDUCT_PERMISSIONS = [*BASE_PERMISSIONS, 'insurance_ledger_deduct']


def update_defaults(apps, schema_editor, previous, current):
    alias = schema_editor.connection.alias
    Position = apps.get_model('Control', 'TenantStaffPosition')
    positions = Position.objects.using(alias).filter(
        client__internal_code='snowland', name='保險人員（預設）', role='insurance',
        all_campuses=True, permissions=previous,
    )
    for position in positions:
        position.memberships.using(alias).filter(
            client_id=position.client_id, role='insurance', is_manager=True, admin_permissions=previous,
        ).update(admin_permissions=current)
        position.permissions = current
        position.save(using=alias, update_fields=['permissions'])


def grant(apps, schema_editor):
    update_defaults(apps, schema_editor, BASE_PERMISSIONS, DEDUCT_PERMISSIONS)


def revoke(apps, schema_editor):
    update_defaults(apps, schema_editor, DEDUCT_PERMISSIONS, BASE_PERMISSIONS)


class Migration(migrations.Migration):
    dependencies = [('Control', '0012_seed_snowland_staff_positions')]
    operations = [migrations.RunPython(grant, revoke)]
