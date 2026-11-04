import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('booking', '0037_pre_course_question_answers')]
    operations = [
        migrations.AlterField('memberloyaltyaccount', 'points', models.PositiveBigIntegerField(default=0)),
        migrations.AddField('memberloyaltyaccount', 'reward_balance', models.BigIntegerField(default=0)),
        migrations.CreateModel(name='MemberLoyaltyPolicy', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('client', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='Client.client')),
            ('revision', models.PositiveIntegerField(default=0)),
            ('rules', models.JSONField(default=dict)),
        ]),
        migrations.CreateModel(name='OrderLoyalty', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('group', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='loyalty', to='booking.reservationgroup')),
            ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='booking.memberloyaltyaccount')),
            ('policy_revision', models.PositiveIntegerField()),
            ('rules', models.JSONField()),
            ('paid_base', models.PositiveIntegerField(null=True)),
            ('points_earned', models.PositiveBigIntegerField(default=0)),
            ('rewards_earned', models.PositiveBigIntegerField(default=0)),
            ('rewards_spent', models.PositiveBigIntegerField(default=0)),
            ('rewards_restored', models.PositiveBigIntegerField(default=0)),
            ('discount_floor', models.PositiveIntegerField(default=0)),
            ('referrer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='referred_orders', to='booking.memberloyaltyaccount')),
            ('referral_earned', models.PositiveIntegerField(default=0)),
        ]),
        migrations.CreateModel(name='MemberLoyaltyEntry', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='entries', to='booking.memberloyaltyaccount')),
            ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='entries', to='booking.orderloyalty')),
            ('kind', models.CharField(max_length=24)),
            ('points_delta', models.BigIntegerField(default=0)),
            ('rewards_delta', models.BigIntegerField(default=0)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ]),
    ]
