from django.db import migrations, models
from django.utils import timezone


def populate_updated_at(apps, schema_editor):
    event_model = apps.get_model("chatbooking", "ChatBookingEvent")
    event_model.objects.filter(updated_at__isnull=True).update(
        updated_at=timezone.now()
    )


class Migration(migrations.Migration):

    dependencies = [
        ("chatbooking", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatbookingevent",
            name="updated_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(
            populate_updated_at,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="chatbookingevent",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
