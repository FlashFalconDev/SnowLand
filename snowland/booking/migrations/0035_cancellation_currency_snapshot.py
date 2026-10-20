from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[('booking','0034_orderamendment_currency_snapshot')]
    operations=[
        migrations.AddField(model_name='cancellationrequest',name='currency_snapshot',field=models.JSONField(default=dict,blank=True,editable=False,verbose_name='取消時原幣退款快照')),
        migrations.AddField(model_name='cancellationrequest',name='refund_overseas_details',field=models.TextField(blank=True,default='')),
    ]
