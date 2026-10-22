from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0012_memberdetail_pre_course_forms'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberdetail',
            name='waiver_document_version',
            field=models.CharField(blank=True, default='', max_length=80, verbose_name='聲明書版本'),
        ),
        migrations.AddField(
            model_name='memberdetail',
            name='waiver_document_snapshot',
            field=models.TextField(blank=True, default='', verbose_name='簽署時聲明書內容'),
        ),
        migrations.AddField(
            model_name='memberdetail',
            name='media_consent',
            field=models.CharField(blank=True, choices=[('agree', '同意公開宣傳'), ('decline', '不同意公開宣傳')], default='', max_length=10, verbose_name='宣傳影像授權'),
        ),
    ]
