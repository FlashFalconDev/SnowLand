import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0018_coursemedia_file'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='ParticipantInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('expires_at', models.DateTimeField()),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('binding_role', models.CharField(blank=True, choices=[('self', '學員本人'), ('guardian', '家長／監護人')], default='', max_length=10)),
                ('member', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='invitation', to='booking.memberdetail')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='participant_invitations_created', to=settings.AUTH_USER_MODEL)),
                ('accepted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='participant_invitations_accepted', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
