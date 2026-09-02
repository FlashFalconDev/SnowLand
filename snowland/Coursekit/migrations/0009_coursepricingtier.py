# Generated manually for people-count pricing tiers.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Coursekit", "0008_alter_coursecategory_client"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoursePricingTier",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("min_people", models.PositiveIntegerField(verbose_name="Minimum people")),
                ("max_people", models.PositiveIntegerField(verbose_name="Maximum people")),
                ("price", models.PositiveIntegerField(verbose_name="Off-peak total price")),
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                ("display_order", models.IntegerField(default=0, verbose_name="Display order")),
                (
                    "pricing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="people_tiers",
                        to="Coursekit.coursepricing",
                        verbose_name="Course pricing",
                    ),
                ),
            ],
            options={
                "verbose_name": "Course pricing people tier",
                "verbose_name_plural": "Course pricing people tiers",
                "ordering": ["pricing", "display_order", "min_people", "max_people", "id"],
                "unique_together": {("pricing", "min_people", "max_people")},
            },
        ),
    ]
