"""Resolve course reminder recipients from current learner ownership, not a saved email list."""
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from .legal_documents import get_current_waiver
from .models import MemberDetail
from .participant_forms import insurance_details_complete, signer_details_complete


COURSE_RECIPIENT_EVENTS = {'pre_course', 'missing_documents', 'line_group'}


def documents_missing(member, version):
    insurance = member.insurance_data if isinstance(member.insurance_data, dict) else {}
    return not (
        member.insurance_completed_at and insurance_details_complete(insurance)
        and member.waiver_completed_at and member.waiver_signature and not member.waiver_resign_required
        and member.waiver_document_version == version and signer_details_complete(insurance)
    )


def group_documents_missing(group):
    version = get_current_waiver(group.client)['version']
    today = timezone.localdate()
    reservations = group.reservations.exclude(status__in=['cancelled', 'deleted']).filter(
        bookings__date__gte=today,
    ).prefetch_related('members').distinct()
    for reservation in reservations:
        members = list(reservation.members.all())
        if reservation.number_of_people > len(members) or any(documents_missing(member, version) for member in members):
            return True
    return False


def channel_recipient(channel, value):
    value = str(value or '').strip()
    if not value or len(value) > 200:
        return ''
    if channel == 'email':
        try:
            validate_email(value)
        except ValidationError:
            return ''
        return value.casefold()
    return value


def account_recipient(user, channel):
    if not user or not user.is_active:
        return ''
    if channel == 'email':
        return channel_recipient(channel, user.email)
    if channel == 'line':
        profile = getattr(user, 'snowland_member_profile', None)
        return channel_recipient(channel, profile.line_user_id if profile else '')
    if channel == 'in_app':
        return str(user.pk)
    return ''


def course_notification_recipients(group, template, *, channel=None):
    """Return canonical destination -> current audience, date and non-personal delivery metadata."""
    channel = channel or template.channel
    if (template.event not in COURSE_RECIPIENT_EVENTS or template.client_id != group.client_id
            or not template.is_active or (template.campus_id and template.campus_id != group.campus_id)):
        return {}
    payment = group.payments.order_by('-created_at', '-pk').first()
    if not payment or payment.status != 'paid':
        return {}
    if template.event == 'line_group':
        # Lazy import keeps URL validation in its existing single implementation.
        from .operations import validate_class_group_url
        try:
            if not validate_class_group_url(group.line_group_url) and not group.line_group_qr:
                return {}
        except ValueError:
            return {}
    today = timezone.localdate()
    reservations = group.reservations.exclude(status__in=['cancelled', 'deleted']).filter(
        bookings__date__gte=today,
    ).distinct()
    selected_templates = list(template.course_templates.values_list('pk', flat=True))
    if selected_templates:
        reservations = reservations.filter(course_template_id__in=selected_templates)
    reservations = list(reservations.prefetch_related('bookings', 'members'))
    if not reservations:
        return {}
    first_dates = {
        reservation.pk: min(booking.date for booking in reservation.bookings.all() if booking.date >= today)
        for reservation in reservations
    }
    members = list(MemberDetail.objects.filter(reservation_id__in=first_dates).select_related(
        'user__snowland_member_profile', 'guardian__snowland_member_profile',
    ))
    version = get_current_waiver(group.client)['version'] if template.event == 'missing_documents' else ''
    contact_data = payment.DataJSON if isinstance(payment.DataJSON, dict) else {}
    contact = contact_data.get('contact') if isinstance(contact_data.get('contact'), dict) else {}
    booking_contact = group.booking_contact if isinstance(group.booking_contact, dict) else {}
    primary = {
        'email': contact.get('email') or booking_contact.get('email') or (group.user.email if group.user_id else ''),
        'line': contact.get('messenger_id') or account_recipient(group.user, 'line'),
        'in_app': str(group.user_id or ''),
    }.get(channel, '')
    destinations = {}

    def add(recipient, member=None, *, organizer=False, first_date=None):
        recipient = channel_recipient(channel, recipient)
        if not recipient:
            return
        first_date = first_date or (first_dates[member.reservation_id] if member else min(first_dates.values()))
        context = destinations.setdefault(recipient, {'first_course': first_date, 'payload': {'audience': 'participant'}})
        context['first_course'] = min(context['first_course'], first_date)
        if organizer:
            context['payload'] = {}

    owned_members = [member for member in members if group.user_id and (
        member.user_id == group.user_id or member.guardian_id == group.user_id
        or (not member.user_id and not member.guardian_id)
    )]
    owner_missing_courses = {
        member.reservation_id for member in owned_members if template.event == 'missing_documents' and documents_missing(member, version)
    } | {reservation.pk for reservation in reservations if reservation.number_of_people > len(reservation.members.all())}
    if template.event != 'missing_documents':
        add(primary, organizer=True)
    elif owner_missing_courses:
        add(primary, organizer=True, first_date=min(first_dates[pk] for pk in owner_missing_courses))
    for member in members:
        if template.event == 'missing_documents' and not documents_missing(member, version):
            continue
        for user in [member.user, member.guardian]:
            if user and user.pk != group.user_id:
                add(account_recipient(user, channel), member)
    return destinations


def email_notification_account_ids(delivery):
    """Resolve only currently entitled, explicitly related accounts; never claim users by email alone."""
    from django.contrib.auth.models import User

    group = delivery.group
    if delivery.template.event not in COURSE_RECIPIENT_EVENTS:
        return [group.user_id] if group.user_id and group.user.is_active else []
    entitled = course_notification_recipients(group, delivery.template, channel='in_app')
    target = channel_recipient('email', delivery.recipient)
    result = []
    for user in User.objects.filter(pk__in=entitled, is_active=True):
        if user.pk == group.user_id:
            # The organizer's order contact can differ from their account email.
            if (delivery.payload or {}).get('audience') != 'participant':
                result.append(user.pk)
        elif account_recipient(user, 'email') == target:
            result.append(user.pk)
    return result
