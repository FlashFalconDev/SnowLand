from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[('booking','0033_reservationgroup_currency_snapshot')]
    operations=[migrations.AddField(model_name='orderamendment',name='currency_snapshot',
        field=models.JSONField(default=dict,blank=True,editable=False,verbose_name='修改時原幣金額與待收退差額'))]
