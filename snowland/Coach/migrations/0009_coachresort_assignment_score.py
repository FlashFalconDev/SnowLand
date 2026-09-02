from django.db import migrations, models


def copy_global_assignment_score(apps, schema_editor):
    CoachResort = apps.get_model("Coach", "CoachResort")
    for link in CoachResort.objects.select_related("coach"):
        link.assignment_score = getattr(link.coach, "assignment_score", 0) or 0
        link.save(update_fields=["assignment_score"])


class Migration(migrations.Migration):

    dependencies = [
        ("Coach", "0008_coach_certifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="coachresort",
            name="assignment_score",
            field=models.IntegerField(
                default=0,
                help_text="同一位教練在不同雪場的分派優先順序，分數越低越優先。",
                verbose_name="雪場分派權重分數",
            ),
        ),
        migrations.RunPython(copy_global_assignment_score, migrations.RunPython.noop),
    ]
