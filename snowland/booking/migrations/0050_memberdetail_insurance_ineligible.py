from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0049_staff_booking_link_snapshot_version'),
    ]

    operations = [
        migrations.AlterField(
            model_name='memberdetail',
            name='insurance_processing_status',
            field=models.CharField(
                choices=[
                    ('pending', '尚未投保'), ('checking', '對資料中'), ('processing', '處理中'),
                    ('insured', '已投保完成'), ('ineligible', '不符投保資格'),
                ],
                default='pending', max_length=12, verbose_name='投保作業狀態',
            ),
        ),
    ]
