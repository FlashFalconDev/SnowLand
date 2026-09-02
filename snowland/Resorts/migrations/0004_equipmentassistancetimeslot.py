# Generated manually for equipment assistance time slot settings.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("Resorts", "0003_equipmentpricingtier"),
    ]

    operations = [
        migrations.CreateModel(
            name="EquipmentAssistanceTimeSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(max_length=120, verbose_name="Label")),
                ("start_time", models.TimeField(blank=True, null=True, verbose_name="Start time")),
                ("end_time", models.TimeField(blank=True, null=True, verbose_name="End time")),
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                ("display_order", models.IntegerField(default=0, verbose_name="Display order")),
                ("description", models.TextField(blank=True, verbose_name="Description")),
                (
                    "resort",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="equipment_assistance_time_slots",
                        to="Resorts.resorts",
                        verbose_name="Resort",
                    ),
                ),
            ],
            options={
                "verbose_name": "Equipment assistance time slot",
                "verbose_name_plural": "Equipment assistance time slots",
                "ordering": ["resort", "display_order", "start_time", "id"],
                "unique_together": {("resort", "label")},
            },
        ),
    ]
