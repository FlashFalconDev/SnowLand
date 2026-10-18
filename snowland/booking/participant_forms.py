from datetime import date

from django.utils import timezone


# Customer's current declaration / slide 16 rule, not inferred from age buckets.
GUARDIAN_AGE_LIMIT = 18


def participant_age(birth_date, reference_date=None):
    if not birth_date:
        return None
    try:
        birth = date.fromisoformat(birth_date)
        if birth.isoformat() != birth_date:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError('請填寫有效的出生日期（年-月-日）')
    today = reference_date or timezone.localdate()
    if birth > today:
        raise ValueError('出生日期不能晚於今天')
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def signer_details_complete(data):
    try:
        age = participant_age(data.get('birth_date'))
    except ValueError:
        return False
    if age is None:
        return False
    role = data.get('waiver_signer_role') or 'self'
    if age < GUARDIAN_AGE_LIMIT or role == 'guardian':
        return bool(
            role == 'guardian'
            and str(data.get('guardian_name') or '').strip()
            and str(data.get('guardian_relationship') or '').strip()
        )
    return role == 'self'


def insurance_details_complete(data):
    return bool(
        all(str(data.get(key) or '').strip() for key in ('full_name', 'birth_date', 'id_number', 'phone'))
        and signer_details_complete(data)
    )
