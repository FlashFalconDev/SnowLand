from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Client', '0012_backfill_school_members')]

    operations = [
        migrations.CreateModel(
            name='FrontendRelease',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255)),
                ('archive_name', models.CharField(max_length=255)),
                ('sha256', models.CharField(max_length=64)),
                ('size', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_current', models.BooleanField(default=False)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='frontend_releases', to='Client.client')),
            ],
            options={
                'ordering': ['-id'],
                'constraints': [models.UniqueConstraint(fields=('client', 'sha256'), name='unique_frontend_release_archive')],
            },
        ),
    ]
