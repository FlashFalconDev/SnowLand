from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Client', '0008_contact_inbox')]
    operations = [migrations.CreateModel(name='InstagramConnection', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('expected_username', models.CharField(blank=True, default='', max_length=30)),
        ('username', models.CharField(blank=True, default='', max_length=30)),
        ('account_id', models.CharField(blank=True, default='', max_length=40)),
        ('encrypted_token', models.TextField(blank=True, default='', editable=False)),
        ('token_expires_at', models.DateTimeField(blank=True, null=True)),
        ('token_refreshed_at', models.DateTimeField(blank=True, null=True)),
        ('enabled', models.BooleanField(default=False)),
        ('last_synced_at', models.DateTimeField(blank=True, null=True)),
        ('last_error', models.CharField(blank=True, default='', max_length=200)),
        ('client', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='instagram_connection', to='Client.client')),
    ]), migrations.AlterField(model_name='sitecontent', name='image_url',
        field=models.CharField(blank=True, default='', max_length=2000, verbose_name='圖片網址'))]
