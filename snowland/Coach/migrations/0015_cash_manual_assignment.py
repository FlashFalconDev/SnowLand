from django.db import migrations
from django.db.models import Q


def exclude_cash_from_automatic_assignment(apps, schema_editor):
    Coach = apps.get_model('Coach', 'Coach')
    Coach.objects.filter(client__internal_code='snowland').filter(
        Q(name='Cash') | Q(name__startswith='Cash ')
    ).update(auto_assignment_enabled=False)


class Migration(migrations.Migration):

    dependencies = [
        ('Coach', '0014_coach_auto_assignment_enabled'),
    ]

    operations = [
        migrations.RunPython(exclude_cash_from_automatic_assignment, migrations.RunPython.noop),
    ]
