import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0035_cancellation_currency_snapshot'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MemberWaiverSignature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signer_name', models.CharField(max_length=120)),
                ('signer_role', models.CharField(max_length=10)),
                ('signed_at', models.DateTimeField()),
                ('document_version', models.CharField(max_length=80)),
                ('document_snapshot', models.TextField()),
                ('course_revision', models.PositiveBigIntegerField(default=0)),
                ('media_consent', models.CharField(max_length=10)),
                ('strokes', models.JSONField()),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='online_waiver_signatures', to='booking.memberdetail')),
                ('signer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
