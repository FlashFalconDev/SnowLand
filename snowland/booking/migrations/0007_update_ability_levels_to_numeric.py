from django.db import migrations, models


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


def normalize_reservation_abilities(apps, schema_editor):
    Reservation = apps.get_model("booking", "Reservation")
    for reservation in Reservation.objects.exclude(max_ability_level__isnull=True):
        next_level = LEGACY_ABILITY_MAP.get(reservation.max_ability_level, reservation.max_ability_level)
        if next_level != reservation.max_ability_level:
            reservation.max_ability_level = next_level
            reservation.save(update_fields=["max_ability_level"])


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0006_reservation_course_template"),
    ]

    operations = [
        migrations.RunPython(normalize_reservation_abilities, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="reservation",
            name="max_ability_level",
            field=models.CharField(
                blank=True,
                choices=ABILITY_CHOICES,
                max_length=20,
                null=True,
                verbose_name="最高滑雪能力",
            ),
        ),
    ]
