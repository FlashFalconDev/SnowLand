from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Client', '0017_recruitment_form')]

    operations = [
        migrations.CreateModel(
            name='SiteTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(max_length=40)),
                ('entries', models.JSONField(default=dict)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='site_translations', to='Client.client')),
            ],
            options={'constraints': [
                models.UniqueConstraint(fields=('client', 'scope'), name='unique_site_translation_scope'),
            ]},
        ),
    ]
