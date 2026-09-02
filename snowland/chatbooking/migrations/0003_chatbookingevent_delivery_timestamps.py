from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbooking", "0002_chatbookingevent_updated_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatbookingevent",
            name="acknowledged_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chatbookingevent",
            name="response_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
