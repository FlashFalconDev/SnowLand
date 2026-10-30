"""School membership creation with conservative legacy attribution."""
from uuid import uuid4
from .models import ClientMemberProfile


def member_profile(user, client):
    from booking.models import MemberProfile, MemberLoyaltyAccount, MemberDetail, ReservationGroup
    existing = ClientMemberProfile.objects.filter(user=user, client=client).first()
    if existing:
        return existing
    defaults = {'display_name':(user.get_full_name() or user.username)[:150], 'referral_code':uuid4().hex[:20].upper()}
    # Preserve existing referral/LINE data only when its school is unambiguous.
    legacy = MemberProfile.objects.filter(user=user).first()
    if legacy:
        clients = set(ReservationGroup.objects.filter(user=user).exclude(client=None).values_list('client_id',flat=True))
        clients.update(MemberLoyaltyAccount.objects.filter(user=user).values_list('client_id',flat=True))
        from django.db.models import Q
        clients.update(MemberDetail.all_objects.filter(Q(user=user)|Q(guardian=user)).exclude(reservation__group__client=None).values_list('reservation__group__client_id',flat=True))
        if clients == {client.pk}:
            if not ClientMemberProfile.objects.filter(referral_code=legacy.referral_code).exists():
                defaults['referral_code'] = legacy.referral_code
            defaults['line_user_id'] = legacy.line_user_id
    profile, _ = ClientMemberProfile.objects.get_or_create(client=client,user=user,defaults=defaults)
    return profile
