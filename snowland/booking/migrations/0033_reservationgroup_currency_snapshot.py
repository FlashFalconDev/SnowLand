from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('booking', '0032_document_history_order_revision'), ('Resorts', '0012_paymentaccount_currency')]
    operations = [migrations.AddField(
        model_name='reservationgroup', name='currency_snapshot',
        field=models.JSONField(blank=True, default=dict, editable=False, verbose_name='成立時收款幣別與匯率'),
    )]
