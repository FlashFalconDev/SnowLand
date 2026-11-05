from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('Client', '0015_initialize_frontend_support_client'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(
        name='FrontendDeployment',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('operation', models.CharField(default='publish', max_length=12)),
            ('status', models.CharField(db_index=True, default='queued', max_length=20)),
            ('message', models.CharField(blank=True, default='', max_length=500)),
            ('target', models.JSONField(default=dict)),
            ('backup_headers', models.JSONField(default=dict)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('finished_at', models.DateTimeField(blank=True, null=True)),
            ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='frontend_deployments', to='Client.client')),
            ('release', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='deployments', to='Client.frontendrelease')),
            ('backup', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='backup_jobs', to='Client.frontendrelease')),
            ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-id']},
    )]
