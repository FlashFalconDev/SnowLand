from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('Coach', '0018_payroll_documents'), ('booking', '0023_reservationgroup_line_group_qr'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name='StaffIncentiveStatement', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('month', models.DateField()),
            ('user_name', models.CharField(max_length=301)),
            ('campus_name', models.CharField(max_length=100)),
            ('percent', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
            ('revenue', models.PositiveBigIntegerField(default=0)),
            ('earned_amount', models.PositiveBigIntegerField(default=0)),
            ('refund_deduction', models.PositiveBigIntegerField(default=0)),
            ('adjustment', models.IntegerField(default=0)),
            ('adjustment_note', models.CharField(blank=True, default='', max_length=300)),
            ('total_amount', models.BigIntegerField(default=0)),
            ('status', models.CharField(choices=[('draft', '草稿'), ('confirmed', '已確認'), ('paid', '已記錄發放')], default='draft', max_length=20)),
            ('confirmed_at', models.DateTimeField(blank=True, null=True)),
            ('paid_at', models.DateTimeField(blank=True, null=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='staff_incentive_statements', to=settings.AUTH_USER_MODEL)),
            ('campus', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='staff_incentive_statements', to='Resorts.campus')),
            ('confirmed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_staff_incentives', to=settings.AUTH_USER_MODEL)),
            ('paid_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_staff_incentive_payments', to=settings.AUTH_USER_MODEL)),
        ], options={'unique_together': {('user', 'campus', 'month')}}),
        migrations.CreateModel(name='StaffIncentiveLine', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('entry_key', models.CharField(max_length=150, unique=True)),
            ('line_type', models.CharField(choices=[('earning', '完成訂單獎金'), ('refund', '已發獎金退款扣回')], max_length=10)),
            ('order_number', models.CharField(max_length=40)),
            ('event_date', models.DateField()),
            ('base_amount', models.PositiveBigIntegerField()),
            ('percent', models.DecimalField(decimal_places=2, max_digits=5)),
            ('amount', models.BigIntegerField()),
            ('statement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='Coach.staffincentivestatement')),
            ('group', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='staff_incentive_lines', to='booking.reservationgroup')),
            ('cancellation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='staff_incentive_lines', to='booking.cancellationrequest')),
            ('source_line', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='refund_lines', to='Coach.staffincentiveline')),
        ]),
    ]
