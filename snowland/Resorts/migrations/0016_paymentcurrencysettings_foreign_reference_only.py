from django.db import migrations, models


def enable_snowland_reference_prices(apps, schema_editor):
    alias = schema_editor.connection.alias
    client = apps.get_model('Client', 'Client').objects.using(alias).filter(internal_code='snowland').first()
    if client:
        apps.get_model('Resorts', 'PaymentCurrencySettings').objects.using(alias).update_or_create(
            client_id=client.pk, defaults={'foreign_reference_only': True},
        )


class Migration(migrations.Migration):
    dependencies = [('Resorts', '0015_foreign_payment_currencies')]

    operations = [
        migrations.AddField(
            model_name='paymentcurrencysettings',
            name='foreign_reference_only',
            field=models.BooleanField(default=False, verbose_name='外幣僅供參考，訂單只收台幣'),
        ),
        migrations.RunPython(enable_snowland_reference_prices, migrations.RunPython.noop),
    ]
