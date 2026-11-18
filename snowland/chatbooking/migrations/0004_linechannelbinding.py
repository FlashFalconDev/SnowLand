from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Client', '0018_site_translation'), ('chatbooking', '0003_chatbookingevent_delivery_timestamps')]

    operations = [
        migrations.AddField(
            model_name='chatbookingsession', name='line_channel_id',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.CreateModel(
            name='LineChannelBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bot_id', models.CharField(max_length=64, unique=True)),
                ('display_name', models.CharField(max_length=100)),
                ('credentials', models.TextField(blank=True)),
                ('enabled', models.BooleanField(default=False)),
                ('webhook_verified_at', models.DateTimeField(blank=True, null=True)),
                ('client', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='Client.client')),
            ],
        ),
        migrations.CreateModel(
            name='MetaPageBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_id', models.CharField(max_length=32, unique=True)),
                ('page_name', models.CharField(max_length=160)),
                ('instagram_id', models.CharField(blank=True, max_length=32, null=True, unique=True)),
                ('instagram_name', models.CharField(blank=True, max_length=80)),
                ('credentials', models.TextField()),
                ('client', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='Client.client')),
            ],
        ),
    ]
