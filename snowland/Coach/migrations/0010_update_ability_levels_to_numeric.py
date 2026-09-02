from django.db import migrations
import multiselectfield.db.fields


LEGACY_ABILITY_MAP = {
    "entry": "level1",
    "basic": "level2",
    "intermediate": "level3",
    "advanced": "level4",
    "expert": "level6",
}

ABILITY_CHOICES = [
    ("no_exp", "等級 0"),
    ("level1", "等級 1"),
    ("level2", "等級 2"),
    ("level3", "等級 3"),
    ("level4", "等級 4"),
    ("level5", "等級 5"),
    ("level6", "等級 6"),
]


def normalize_course_level_abilities(apps, schema_editor):
    CoachCourseLevel = apps.get_model("Coach", "CoachCourseLevel")
    for course_level in CoachCourseLevel.objects.all():
        raw_levels = course_level.ability_levels or []
        if isinstance(raw_levels, str):
            levels = [item.strip() for item in raw_levels.split(",") if item.strip()]
        else:
            levels = [str(item or "").strip() for item in raw_levels if str(item or "").strip()]

        normalized = []
        for level in levels:
            next_level = LEGACY_ABILITY_MAP.get(level, level)
            if next_level and next_level not in normalized:
                normalized.append(next_level)

        if normalized != list(levels):
            course_level.ability_levels = normalized
            course_level.save(update_fields=["ability_levels"])


class Migration(migrations.Migration):

    dependencies = [
        ("Coach", "0009_coachresort_assignment_score"),
    ]

    operations = [
        migrations.RunPython(normalize_course_level_abilities, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="coachcourselevel",
            name="ability_levels",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=ABILITY_CHOICES,
                max_length=48,
                null=True,
                verbose_name="可接課等級",
            ),
        ),
    ]
