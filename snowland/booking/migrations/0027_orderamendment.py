from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies=[('booking','0026_memberdetail_archive'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name='OrderAmendment',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('request_key',models.UUIDField(unique=True)),('request_fingerprint',models.CharField(max_length=64)),('reason',models.TextField()),
        ('previous_total',models.PositiveIntegerField()),('new_total',models.PositiveIntegerField()),('difference_amount',models.IntegerField()),
        ('balance_amount',models.IntegerField(default=0)),
        ('status',models.CharField(max_length=24,default='no_difference',choices=[('included_in_order','併入原訂單付款'),('no_difference','無待收退差額'),
            ('topup_due','待補款'),('topup_reported','補款待核對'),('refund_account_due','待填退款帳戶'),('refund_due','待退款'),('settled','已結清'),('superseded','已由新版取代')])),
        ('before_snapshot',models.JSONField(default=dict)),('participant_changes',models.JSONField(default=dict)),('bank_snapshot',models.JSONField(default=dict)),
        ('refund_bank',models.JSONField(default=dict)),('topup_reference',models.CharField(max_length=100,blank=True,default='')),
        ('created_at',models.DateTimeField(default=django.utils.timezone.now)),('updated_at',models.DateTimeField(default=django.utils.timezone.now)),
        ('settled_at',models.DateTimeField(null=True,blank=True)),
        ('group',models.ForeignKey(to='booking.reservationgroup',on_delete=django.db.models.deletion.CASCADE,related_name='amendments')),
        ('revision',models.OneToOneField(to='booking.orderrevision',on_delete=django.db.models.deletion.CASCADE,related_name='amendment')),
        ('created_by',models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.SET_NULL,null=True,related_name='order_amendments_created')),
        ('settled_by',models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.SET_NULL,null=True,blank=True,related_name='order_amendments_settled')),
    ],options={'ordering':['-created_at','-id'],'verbose_name':'訂單修改與差額','verbose_name_plural':'訂單修改與差額'})]
