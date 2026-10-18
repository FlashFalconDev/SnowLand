from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_unambiguous_profiles(apps, schema_editor):
    Profile = apps.get_model('booking', 'MemberProfile')
    Group = apps.get_model('booking', 'ReservationGroup')
    Account = apps.get_model('booking', 'MemberLoyaltyAccount')
    alias = schema_editor.connection.alias
    for profile in Profile.objects.using(alias).all().iterator():
        clients = list(Group.objects.using(alias).filter(user_id=profile.user_id, client__isnull=False)
                       .values_list('client_id', flat=True).distinct()[:2])
        # No ownership evidence, or multiple schools: preserve the old source;
        # do not assign its points/verification to an arbitrary school.
        if len(clients) == 1:
            Account.objects.using(alias).get_or_create(client_id=clients[0], user_id=profile.user_id, defaults={
                'points': profile.points, 'previous_points': profile.previous_points,
                'level': profile.level, 'alumni_verified': profile.alumni_verified,
            })


class Migration(migrations.Migration):
    dependencies = [('booking', '0029_cancellation_cash_review'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='MemberLoyaltyAccount', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('points', models.PositiveIntegerField(default=0)),
            ('previous_points', models.PositiveIntegerField(default=0)),
            ('level', models.CharField(choices=[('new', '新會員'), ('alumni', '舊生'), ('silver', '銀級'), ('gold', '金級')], default='new', max_length=20)),
            ('alumni_verified', models.BooleanField(default=False)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='Client.client')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [models.UniqueConstraint(fields=('client', 'user'), name='unique_member_loyalty_client_user')]}),
        migrations.CreateModel(name='MemberLoyaltyReview', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('before', models.JSONField(default=dict)), ('after', models.JSONField(default=dict)),
            ('reason', models.CharField(max_length=1000)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='booking.memberloyaltyaccount')),
            ('reviewed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-created_at', '-pk']}),
        migrations.RunPython(migrate_unambiguous_profiles, migrations.RunPython.noop),
    ]
