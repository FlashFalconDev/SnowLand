from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Coach", "0007_coach_website_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="coach",
            name="certifications",
            field=models.JSONField(blank=True, default=list, verbose_name="教練證照"),
        ),
    ]
