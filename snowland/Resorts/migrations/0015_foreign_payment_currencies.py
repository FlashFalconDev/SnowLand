from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Resorts', '0014_resorts_display_order')]

    operations = [
        migrations.AddField(
            model_name='paymentcurrencysettings',
            name='foreign_rates',
            field=models.JSONField(blank=True, default=dict, verbose_name='其他匯款幣別與匯率'),
        ),
        migrations.AlterField(
            model_name='paymentaccount',
            name='currency',
            field=models.CharField(choices=[('TWD', '台幣'), ('JPY', '日幣'), ('USD', '美元'), ('HKD', '港幣'), ('CNY', '人民幣')],
                                   default='TWD', max_length=3, verbose_name='收款幣別'),
        ),
    ]
