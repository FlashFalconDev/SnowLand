from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("Coursekit", "0015_coursetemplate_coach_restrictions"),
        ("booking", "0005_reservation_discount_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="course_template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reservations",
                to="Coursekit.coursetemplate",
                verbose_name="課程模板",
            ),
        ),
    ]
