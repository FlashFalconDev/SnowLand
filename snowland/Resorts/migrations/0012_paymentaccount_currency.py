from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Resorts', '0011_paymentcurrencysettings')]
    operations = [migrations.AddField(
        model_name='paymentaccount', name='currency',
        field=models.CharField(choices=[('TWD', '台幣'), ('JPY', '日幣')], default='TWD', max_length=3, verbose_name='收款幣別'),
    )]
