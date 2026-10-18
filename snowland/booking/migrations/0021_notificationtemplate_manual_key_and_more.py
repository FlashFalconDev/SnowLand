import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('booking', '0020_notification_repeat_interval')]

    operations = [
        migrations.AddField(
            model_name='notificationtemplate', name='manual_key',
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='notificationdelivery', name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='notification_deliveries', to='booking.reservationgroup'),
        ),
        migrations.AlterField(
            model_name='notificationtemplate', name='event',
            field=models.CharField(choices=[('order_created', '訂單成立'), ('shared_class_ready', '團體班成班付款'),
                ('payment_confirmed', '付款完成'), ('pre_course', '課前提醒'), ('missing_documents', '資料未完成'),
                ('line_group', 'LINE 群組邀請'), ('evaluation_due', '評量未完成'), ('manual', '手動站內通知')], max_length=30),
        ),
    ]
