from django.db import migrations


def initialize_campus_scope(apps, schema_editor):
    Client = apps.get_model('Client', 'Client')
    Resorts = apps.get_model('Resorts', 'Resorts')
    Campus = apps.get_model('Resorts', 'Campus')
    PaymentAccount = apps.get_model('Resorts', 'PaymentAccount')
    OperatingPolicy = apps.get_model('Resorts', 'OperatingPolicy')
    ReservationGroup = apps.get_model('booking', 'ReservationGroup')
    UserProfile = apps.get_model('Control', 'UserProfile')
    Coach = apps.get_model('Coach', 'Coach')

    for client in Client.objects.all():
        campus, _ = Campus.objects.get_or_create(
            client=client,
            code='main',
            defaults={'name': '主要校區', 'description': '系統自動建立，可在後台改名。'},
        )
        client_resorts = Resorts.objects.filter(client=client)
        campus.resorts.add(*client_resorts)
        OperatingPolicy.objects.get_or_create(client=client, campus=None)

        if client.bank_account_number:
            account, _ = PaymentAccount.objects.get_or_create(
                client=client,
                name='公司預設帳戶',
                defaults={
                    'bank_name': client.bank_name,
                    'bank_branch': client.bank_branch,
                    'account_number': client.bank_account_number,
                    'account_holder': client.bank_account_holder,
                    'is_default': True,
                },
            )
            account.campuses.add(campus)
            account.resorts.add(*client_resorts)

        for coach in Coach.objects.filter(client=client):
            if not coach.campuses.exists():
                coach.campuses.add(campus)
            if coach.user_id:
                profile = UserProfile.objects.filter(user_id=coach.user_id).first()
                if profile:
                    profile.is_coach = True
                    if not profile.role:
                        profile.role = 'coach'
                    profile.save(update_fields=['is_coach', 'role'])
                    profile.campuses.add(campus)

        groups = ReservationGroup.objects.filter(client=client).prefetch_related('reservations__resort')
        for group in groups:
            if not group.campus_id:
                resort_ids = [r.resort_id for r in group.reservations.all() if r.resort_id]
                matched = Campus.objects.filter(client=client, resorts__id__in=resort_ids).distinct().first()
                group.campus = matched or campus
            if not group.order_number:
                date_value = group.created_at.strftime('%Y%m%d') if group.created_at else 'LEGACY'
                group.order_number = f'SL-{date_value}-{group.pk:06d}'
            group.save(update_fields=['campus', 'order_number'])

    for profile in UserProfile.objects.filter(is_manager=True, role=''):
        profile.role = 'hq_admin'
        profile.save(update_fields=['role'])


class Migration(migrations.Migration):
    dependencies = [
        ('Resorts', '0008_campus_operatingpolicy_paymentaccount_and_more'),
        ('Control', '0006_userprofile_campuses_userprofile_role'),
        ('Coach', '0011_coach_campuses'),
        ('booking', '0008_reservationgroup_campus_and_more'),
    ]

    operations = [
        migrations.RunPython(initialize_campus_scope, migrations.RunPython.noop),
    ]
