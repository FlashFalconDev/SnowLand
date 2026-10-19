from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('booking', '0030_member_loyalty_accounts')]

    operations = [
        migrations.AddField(
            model_name='memberdetail', name='waiver_resign_required',
            field=models.BooleanField(default=False, verbose_name='課程變更須重新簽署'),
        ),
        migrations.CreateModel(
            name='MemberCourseDocumentRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('snapshot', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('amendment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_revisions', to='booking.orderamendment')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_document_revisions', to='booking.memberdetail')),
            ],
        ),
    ]
