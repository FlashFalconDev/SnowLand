from collections import Counter

from django.db import migrations


TENANT_POSITIONS = (
    ('行銷人員（預設）', 'marketing', ['analytics']),
    ('網頁人員（預設）', 'web_editor', [
        'site_home', 'site_courses', 'site_photography', 'site_guides', 'site_news',
        'site_about', 'site_coaches', 'site_campaigns', 'site_reviews', 'site_media',
    ]),
    ('保險人員（預設）', 'insurance', ['insurance_records']),
    ('行政小幫手（預設）', 'assistant', [
        'order_view', 'order_payments', 'scheduling', 'insurance_records',
        'evaluations', 'site_reviews', 'coach_leaves', 'booking_links',
    ]),
)

CAMPUS_PAGES = ['order_view', 'scheduling', 'coach_leaves', 'evaluations']
CAMPUS_POSITIONS = (
    ('校區校長', 'campus_principal', [*CAMPUS_PAGES, 'analytics']),
    ('校區主管', 'campus_manager', CAMPUS_PAGES),
)


def seed_snowland_positions(apps, schema_editor):
    alias = schema_editor.connection.alias
    Client = apps.get_model('Client', 'Client')
    Campus = apps.get_model('Resorts', 'Campus')
    Position = apps.get_model('Control', 'TenantStaffPosition')
    tenant_id = Client.objects.using(alias).filter(internal_code='snowland').values_list('pk', flat=True).first()
    if tenant_id is None:
        return

    positions = Position.objects.using(alias)
    for name, role, permissions in TENANT_POSITIONS:
        positions.get_or_create(client_id=tenant_id, name=name, defaults={
            'role': role, 'permissions': permissions, 'all_campuses': True,
        })

    campuses = list(Campus.objects.using(alias).filter(client_id=tenant_id, is_active=True).order_by('id'))
    campus_names = Counter(campus.name[:38] for campus in campuses)
    for campus in campuses:
        label = campus.name[:38]
        if campus_names[label] > 1:
            label = f'{label}／{campus.code}'
        for role_name, role, permissions in CAMPUS_POSITIONS:
            position, created = positions.get_or_create(
                client_id=tenant_id, name=f'{role_name}（{label}）', defaults={
                    'role': role, 'permissions': permissions, 'all_campuses': False,
                },
            )
            if created:
                position.campuses.add(campus)


class Migration(migrations.Migration):
    dependencies = [('Control', '0011_tenant_staff_positions')]

    # The templates may be edited or assigned after deployment; rollback keeps those records.
    operations = [migrations.RunPython(seed_snowland_positions, migrations.RunPython.noop)]
