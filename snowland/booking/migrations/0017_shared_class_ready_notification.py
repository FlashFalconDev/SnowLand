from django.db import migrations, models


def create_snowland_template(apps, schema_editor):
    Client = apps.get_model('Client', 'Client')
    NotificationTemplate = apps.get_model('booking', 'NotificationTemplate')
    alias = schema_editor.connection.alias
    client = Client.objects.using(alias).filter(internal_code='snowland').first()
    if client and not NotificationTemplate.objects.using(alias).filter(
        client_id=client.pk, event='shared_class_ready', channel='email',
    ).exists():
        NotificationTemplate.objects.using(alias).create(
            client_id=client.pk,
            name='團體班成班付款通知',
            event='shared_class_ready',
            channel='email',
            subject='SnowLand 團體班已成班，請完成付款',
            body='您好，團體班已成班。請使用以下專屬連結查看付款資訊：\n{payment_url}\n如有問題請聯絡 SnowLand。',
            days_before=0,
            is_active=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0016_reservationgroup_booking_contact'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificationtemplate',
            name='event',
            field=models.CharField(choices=[
                ('order_created', '訂單成立'),
                ('shared_class_ready', '團體班成班付款'),
                ('payment_confirmed', '付款完成'),
                ('pre_course', '課前提醒'),
                ('missing_documents', '資料未完成'),
                ('line_group', 'LINE 群組邀請'),
                ('evaluation_due', '評量未完成'),
            ], max_length=30),
        ),
        migrations.RunPython(create_snowland_template, migrations.RunPython.noop),
    ]
