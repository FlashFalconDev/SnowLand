# Generated manually for people-count equipment pricing tiers.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Resorts", "0002_resorts_client"),
    ]

    operations = [
        migrations.CreateModel(
            name="EquipmentPricingTier",
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
                ("price", models.PositiveIntegerField(verbose_name="Price")),
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                ("display_order", models.IntegerField(default=0, verbose_name="Display order")),
                ("description", models.TextField(blank=True, verbose_name="Description")),
                (
                    "resort",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="equipment_pricing_tiers",
                        to="Resorts.resorts",
                        verbose_name="Resort",
                    ),
                ),
            ],
            options={
                "verbose_name": "Equipment pricing tier",
                "verbose_name_plural": "Equipment pricing tiers",
                "ordering": ["resort", "display_order", "min_people", "max_people", "id"],
                "unique_together": {("resort", "min_people", "max_people")},
            },
        ),
    ]
