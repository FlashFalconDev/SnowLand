from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('booking', '0021_notificationtemplate_manual_key_and_more')]
    operations = [migrations.AlterField(model_name='notificationdelivery', name='status',
        field=models.CharField(choices=[('scheduled', '已排程'), ('sending', '發送中／結果待確認'), ('sent', '已發送'),
            ('failed', '發送失敗'), ('cancelled', '已取消')], default='scheduled', max_length=20))]
