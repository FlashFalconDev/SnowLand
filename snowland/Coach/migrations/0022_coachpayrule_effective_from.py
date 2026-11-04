from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Coach', '0021_alter_coach_user_coach_unique_coach_client_user')]

    operations = [
        migrations.AddField(
            model_name='coachpayrule',
            name='effective_from',
            field=models.DateField(null=True, blank=True, verbose_name='新薪率生效日'),
        ),
    ]
