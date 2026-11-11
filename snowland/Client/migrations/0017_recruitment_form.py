from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Client', '0016_frontend_deployment')]

    operations = [
        migrations.CreateModel(
            name='RecruitmentForm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=False)),
                ('fields', models.JSONField(default=list)),
                ('client', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='recruitment_form', to='Client.client')),
            ],
        ),
        migrations.CreateModel(
            name='RecruitmentApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submission_id', models.UUIDField()),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('fields', models.JSONField()),
                ('answers', models.JSONField()),
                ('attachments', models.JSONField(default=dict)),
                ('fingerprint', models.CharField(max_length=64)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='recruitment_applications', to='Client.client')),
            ],
            options={
                'ordering': ['-id'],
                'constraints': [models.UniqueConstraint(fields=('client', 'submission_id'), name='unique_recruitment_submission')],
            },
        ),
    ]
