from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies=[('booking','0027_orderamendment'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name='OrderAmendmentEvent',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('request_key',models.UUIDField(unique=True)),('request_fingerprint',models.CharField(max_length=64)),
        ('action',models.CharField(max_length=24)),('previous_status',models.CharField(max_length=24)),('status',models.CharField(max_length=24)),
        ('payload',models.JSONField(default=dict)),('created_at',models.DateTimeField(default=django.utils.timezone.now)),
        ('actor',models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.SET_NULL,null=True,related_name='order_amendment_events')),
        ('amendment',models.ForeignKey(to='booking.orderamendment',on_delete=django.db.models.deletion.CASCADE,related_name='events')),
    ],options={'ordering':['created_at','id'],'verbose_name':'訂單差額處理紀錄'})]
