from django.db import migrations


def backfill_staff(apps, schema_editor):
    Legacy = apps.get_model('Control', 'UserProfile')
    Membership = apps.get_model('Control', 'TenantStaffMembership')
    Coach = apps.get_model('Coach', 'Coach')
    alias = schema_editor.connection.alias
    for old in Legacy.objects.using(alias).all().iterator():
        coaches = list(Coach.objects.using(alias).filter(user_id=old.user_id, client_id__isnull=False)) if old.is_coach else []
        schools = {coach.client_id for coach in coaches}
        if old.is_manager and old.manager_client_id:
            schools.add(old.manager_client_id)
        for school_id in schools:
            manager = old.is_manager and old.manager_client_id == school_id
            own_coaches = [coach for coach in coaches if coach.client_id == school_id]
            row, created = Membership.objects.using(alias).get_or_create(client_id=school_id, user_id=old.user_id, defaults={
                'is_manager':manager, 'is_coach':bool(own_coaches),
                'role':old.role if manager else 'coach',
                'admin_permissions':old.admin_permissions if manager else [],
            })
            if created:
                campus_ids = set(old.campuses.using(alias).filter(client_id=school_id).values_list('pk',flat=True)) if manager else set()
                for coach in own_coaches:
                    campus_ids.update(coach.campuses.using(alias).filter(client_id=school_id).values_list('pk',flat=True))
                row.campuses.set(campus_ids)


class Migration(migrations.Migration):
    dependencies = [('Control','0008_tenantstaffmembership'), ('Coach','0020_payroll_settlement')]
    operations = [migrations.RunPython(backfill_staff, migrations.RunPython.noop)]
