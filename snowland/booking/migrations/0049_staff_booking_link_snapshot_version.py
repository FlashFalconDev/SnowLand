# 保留資料庫預設值，讓 EB 滾動部署或回退時，舊版 INSERT 省略新欄位仍能寫入。
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0048_reservationgroup_test_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reservationgroup',
            name='is_test',
            field=models.BooleanField(db_index=True, default=False, db_default=False, editable=False, verbose_name='測試訂單'),
        ),
        migrations.AddField(
            model_name='staffbookinglink',
            name='snapshot_version',
            field=models.PositiveIntegerField(default=0, db_default=0),
        ),
        migrations.AddField(
            model_name='staffbookinglink',
            name='quoted_total',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
