# Generated manually to allow equipment assistance slots to target course templates.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Coursekit", "0009_coursepricingtier"),
        ("Resorts", "0005_equipmentassistancetimeslot_bindings"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipmentassistancetimeslot",
            name="course_templates",
            field=models.ManyToManyField(
                blank=True,
                related_name="equipment_assistance_time_slots",
                to="Coursekit.coursetemplate",
                verbose_name="Applicable course templates",
            ),
        ),
    ]
