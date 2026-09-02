# Generated manually for selected equipment assistance time on reservations.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("Resorts", "0004_equipmentassistancetimeslot"),
        ("booking", "0003_reservationgroup_client"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="equipment_assistance_time_label",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="Equipment assistance time label"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="equipment_assistance_time_slot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reservations",
                to="Resorts.equipmentassistancetimeslot",
                verbose_name="Equipment assistance time slot",
            ),
        ),
    ]
