from django.db import migrations, models


KNOWN_WEBSITE_COACHES = [
    ("cash", ["Cash"], 10),
    ("lily", ["Lily"], 20),
    ("qizhen", ["七針"], 30),
    ("dylan", ["Dylan"], 40),
    ("eric", ["Eric"], 50),
    ("vicky", ["Vicky"], 60),
    ("lin", ["小霖"], 70),
    ("karen", ["Karen"], 80),
    ("naomi", ["Naomi"], 90),
    ("bernie", ["Bernie"], 100),
]


def seed_website_coaches(apps, schema_editor):
    Coach = apps.get_model("Coach", "Coach")

    for slug, tokens, sort_order in KNOWN_WEBSITE_COACHES:
        coach_ids = set()
        for token in tokens:
            coach_ids.update(Coach.objects.filter(name__icontains=token).values_list("id", flat=True))

        for coach in Coach.objects.filter(id__in=coach_ids):
            coach.website_enabled = True
            coach.website_slug = coach.website_slug or slug
            coach.website_sort_order = coach.website_sort_order or sort_order
            coach.save(update_fields=["website_enabled", "website_slug", "website_sort_order"])


class Migration(migrations.Migration):

    dependencies = [
        ("Coach", "0006_coach_client"),
    ]

    operations = [
        migrations.AddField(
            model_name="coach",
            name="website_enabled",
            field=models.BooleanField(db_index=True, default=False, verbose_name="官網顯示"),
        ),
        migrations.AddField(
            model_name="coach",
            name="website_slug",
            field=models.SlugField(blank=True, db_index=True, default="", max_length=80, verbose_name="官網代號"),
        ),
        migrations.AddField(
            model_name="coach",
            name="website_sort_order",
            field=models.IntegerField(default=0, verbose_name="官網排序"),
        ),
        migrations.AddField(
            model_name="coach",
            name="website_card_bio",
            field=models.CharField(blank=True, default="", max_length=160, verbose_name="官網卡片簡介"),
        ),
        migrations.RunPython(seed_website_coaches, migrations.RunPython.noop),
    ]
