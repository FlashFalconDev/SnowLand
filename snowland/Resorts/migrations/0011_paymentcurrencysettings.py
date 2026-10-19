from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Resorts', '0010_resorts_trail_names')]
    operations = [
        migrations.CreateModel(
            name='PaymentCurrencySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jpy_enabled', models.BooleanField(default=False, verbose_name='開放日幣匯款')),
                ('jpy_per_twd', models.DecimalField(blank=True, decimal_places=8, max_digits=17, null=True, verbose_name='1台幣可換日幣')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payment_currency_settings', to='Client.client')),
            ],
        ),
    ]
