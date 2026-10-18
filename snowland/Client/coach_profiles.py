"""Rich website copy stored in the existing CMS, bound to a real coach ID."""
from copy import deepcopy
from django.db import transaction
from Coach.models import Coach
from .models import SiteContent

PROFILE_LOCATION='coach.profiles'


def coach_profile_record(coach):
    return SiteContent.objects.filter(client_id=coach.client_id,content_type='page',
        location_key=PROFILE_LOCATION,external_id=str(coach.pk)).order_by('-updated_at','-pk').first()


def read_coach_profile(coach):
    row=coach_profile_record(coach)
    profile=row.metadata.get('profile') if row and isinstance(row.metadata,dict) else None
    return deepcopy(profile) if isinstance(profile,dict) else {}


@transaction.atomic
def save_coach_profile(coach, profile, *, overwrite=False):
    if not isinstance(profile,dict):
        raise ValueError('教練介紹必須是物件')
    coach=Coach.objects.select_for_update().get(pk=coach.pk,client_id=coach.client_id)
    row=coach_profile_record(coach)
    if row and not overwrite:
        return row,False
    if row is None:
        row=SiteContent(client_id=coach.client_id,content_type='page',location_key=PROFILE_LOCATION,
            external_id=str(coach.pk),title=coach.name,source='coach-profile')
    metadata=row.metadata if isinstance(row.metadata,dict) else {}
    row.metadata={**metadata,'profile':deepcopy(profile)}
    # Only the enabled coach's public endpoint may publish this copy. The raw
    # generic CMS endpoint must not expose a disabled coach's stored profile.
    row.status='hidden'
    row.save()
    return row,True
