from django.db import migrations, models
import django.db.models.deletion
import booking.media_files


class Migration(migrations.Migration):
    dependencies = [('Coach', '0017_payroll_review'), ('Client', '0001_initial')]
    operations = [
        migrations.CreateModel(name='PayrollDocumentSettings', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('title', models.CharField(default='勞務報酬單', max_length=100)),
            ('body', models.TextField(blank=True, default='')),
            ('is_active', models.BooleanField(default=False)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('client', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payroll_document_settings', to='Client.client')),
        ]),
        migrations.AddField(model_name='payrollstatement', name='document_snapshot', field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='payrollstatement', name='signature_file', field=models.FileField(blank=True, max_length=240, storage=booking.media_files.PrivateCourseMediaStorage(), upload_to='payroll-signatures')),
        migrations.AddField(model_name='payrollstatement', name='signature_sha256', field=models.CharField(blank=True, default='', max_length=64)),
        migrations.AddField(model_name='payrollstatement', name='signer_name', field=models.CharField(blank=True, default='', max_length=100)),
        migrations.AddField(model_name='payrollstatement', name='signed_at', field=models.DateTimeField(blank=True, null=True)),
    ]
