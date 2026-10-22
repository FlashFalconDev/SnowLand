from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('booking', '0028_orderamendmentevent')]
    operations = [
        migrations.AddField(model_name='cancellationrequest',name='requires_cash_review',field=models.BooleanField(default=False)),
        migrations.AddField(model_name='cancellationrequest',name='actual_received_amount',field=models.PositiveIntegerField(null=True,blank=True)),
        migrations.AddField(model_name='cancellationrequest',name='cash_review_note',field=models.TextField(blank=True,default='')),
        migrations.AddField(model_name='cancellationrequest',name='cash_review_snapshot',field=models.JSONField(blank=True,default=dict)),
        migrations.AlterField(model_name='orderamendment',name='status',field=models.CharField(max_length=24,default='no_difference',choices=[('included_in_order','併入原訂單付款'),('no_difference','無待收退差額'),('topup_due','待補款'),('topup_reported','補款待核對'),('refund_account_due','待填退款帳戶'),('refund_due','待退款'),('settled','已結清'),('superseded','已由新版取代'),('cancelled','已併入取消結算')])),
    ]
