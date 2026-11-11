from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Resorts', '0016_paymentcurrencysettings_foreign_reference_only')]

    operations = [
        migrations.AddField(
            model_name='resorts',
            name='frontend_booking_enabled',
            field=models.BooleanField(default=True, verbose_name='開放前台訂課'),
        ),
    ]
