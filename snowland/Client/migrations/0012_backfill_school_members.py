from collections import defaultdict
from uuid import uuid4
from django.conf import settings
from django.db import migrations


def backfill_members(apps, schema_editor):
    Profile = apps.get_model('Client','ClientMemberProfile')
    Legacy = apps.get_model('booking','MemberProfile')
    Group = apps.get_model('booking','ReservationGroup')
    Detail = apps.get_model('booking','MemberDetail')
    Account = apps.get_model('booking','MemberLoyaltyAccount')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    alias = schema_editor.connection.alias
    schools = defaultdict(set)
    for user_id, client_id in Group.objects.using(alias).exclude(user_id=None).exclude(client_id=None).values_list('user_id','client_id').iterator():
        schools[user_id].add(client_id)
    for user_id, client_id in Account.objects.using(alias).values_list('user_id','client_id').iterator():
        schools[user_id].add(client_id)
    for user_id, guardian_id, client_id in Detail._base_manager.using(alias).exclude(reservation__group__client_id=None).values_list('user_id','guardian_id','reservation__group__client_id').iterator():
        for account_id in (user_id,guardian_id):
            if account_id:
                schools[account_id].add(client_id)
    for user_id, client_ids in schools.items():
        user = User.objects.using(alias).get(pk=user_id)
        old = Legacy.objects.using(alias).filter(user_id=user_id).first()
        for client_id in client_ids:
            if Profile.objects.using(alias).filter(user_id=user_id,client_id=client_id).exists():
                continue
            code = uuid4().hex[:20].upper()
            line_id = ''
            if old and len(client_ids)==1:
                if old.referral_code and not Profile.objects.using(alias).filter(referral_code=old.referral_code).exists():
                    code = old.referral_code
                line_id = old.line_user_id
            Profile.objects.using(alias).create(user_id=user_id, client_id=client_id,
                display_name=(' '.join(filter(None,[user.first_name,user.last_name])) or user.username)[:150],
                referral_code=code, line_user_id=line_id)


class Migration(migrations.Migration):
    dependencies = [('Client','0011_client_expiry_reminder_days_and_more'), ('booking','0035_cancellation_currency_snapshot')]
    operations = [migrations.RunPython(backfill_members, migrations.RunPython.noop)]
