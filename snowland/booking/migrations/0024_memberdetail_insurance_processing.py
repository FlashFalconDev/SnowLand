from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('booking', '0023_reservationgroup_line_group_qr'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='memberdetail', name='insurance_processing_status', field=models.CharField(
            max_length=12, default='pending', choices=[('pending','尚未投保'),('checking','對資料中'),('processing','處理中'),('insured','已投保完成')], verbose_name='投保作業狀態')),
        migrations.AddField(model_name='memberdetail', name='insurance_premium_amount', field=models.DecimalField(
            max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='投保金額')),
        migrations.AddField(model_name='memberdetail', name='insurance_premium_currency', field=models.CharField(
            max_length=3, blank=True, default='', verbose_name='投保金額幣別')),
        migrations.AddField(model_name='memberdetail', name='insurance_processing_updated_at', field=models.DateTimeField(
            null=True, blank=True, verbose_name='投保作業更新時間')),
        migrations.AddField(model_name='memberdetail', name='insurance_processing_updated_by', field=models.ForeignKey(
            to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True,
            related_name='updated_insurance_reports', verbose_name='投保作業更新人')),
    ]
