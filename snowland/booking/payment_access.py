"""Access links for orders created without a member account."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.core import signing


PAYMENT_LINK_SALT = 'snowland-guest-payment-v1'
PAYMENT_LINK_MAX_AGE = 30 * 24 * 60 * 60


def payment_access_token(group):
    return signing.dumps((group.client_id, group.pk), salt=PAYMENT_LINK_SALT)


def can_access_payment(group, user, token=''):
    if group.user_id:
        return group.user_id == getattr(user, 'id', None)
    if not token:
        return False
    try:
        return tuple(signing.loads(
            token, salt=PAYMENT_LINK_SALT, max_age=PAYMENT_LINK_MAX_AGE,
        )) == (group.client_id, group.pk)
    except (signing.BadSignature, ValueError, TypeError):
        return False


def payment_url_for_group(base_url, group):
    parts = urlsplit(base_url)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params['reservation_group'] = str(group.pk)
    if not group.user_id:
        params['access_token'] = payment_access_token(group)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))
