"""Explicit, expiring invitations; never claim an order merely by matching email."""
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from .models import MemberDetail, ParticipantInvitation
from .participant_forms import GUARDIAN_AGE_LIMIT, participant_age


class InvitationError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def check_invitable_course(member):
    if not member.is_active:
        raise InvitationError('此學員名額已退出，無法重新綁定',404)
    if member.reservation.status in {'cancelled', 'deleted'}:
        raise InvitationError('此課程已取消，無法綁定學員')
    payment = member.reservation.group.payments.order_by('-created_at').first()
    if not payment or payment.status != 'paid':
        raise InvitationError('訂單付款完成後才可邀請同行學員綁定')


def binding_status(member):
    invitation = getattr(member, 'invitation', None)
    if (invitation and invitation.accepted_at) or member.guardian_id or (
        member.user_id and member.user_id != member.reservation.group.user_id
    ):
        return 'bound'
    if invitation and invitation.expires_at > timezone.now():
        return 'pending'
    return 'unbound'


@transaction.atomic
def issue_invitation(tenant, organizer, member_id, *, revoke=False):
    member = MemberDetail.objects.select_for_update().select_related('reservation__group').filter(
        pk=member_id, reservation__group__client=tenant, reservation__group__user=organizer,
    ).first()
    if not member:
        raise InvitationError('找不到可邀請的學員', 404)
    if binding_status(member) == 'bound':
        raise InvitationError('此學員已綁定帳號，不能重新邀請或撤銷綁定', 409)
    if revoke:
        ParticipantInvitation.objects.filter(member=member, accepted_at__isnull=True).delete()
        return None
    check_invitable_course(member)
    invitation, _ = ParticipantInvitation.objects.update_or_create(member=member, defaults={
        'token': uuid4(), 'created_by': organizer, 'expires_at': timezone.now()+timedelta(days=7),
    })
    return invitation


def check_invitation(invitation, user):
    if not invitation.member.is_active:
        raise InvitationError('此學員名額已退出，無法重新綁定',404)
    if invitation.accepted_at:
        if invitation.accepted_by_id != user.pk:
            raise InvitationError('此邀請已完成綁定，請向訂購人索取自己的邀請連結', 409)
        return
    if invitation.expires_at <= timezone.now():
        raise InvitationError('邀請連結已過期，請訂購人重新產生連結', 410)
    if binding_status(invitation.member) == 'bound':
        raise InvitationError('此學員已綁定帳號', 409)
    check_invitable_course(invitation.member)


@transaction.atomic
def accept_invitation(tenant, user, token, role):
    initial = ParticipantInvitation.objects.filter(token=token, member__reservation__group__client=tenant).first()
    if not initial:
        raise InvitationError('找不到邀請連結，可能已撤銷或重新產生', 404)
    # Both issue and accept lock the learner first, so a rotated/revoked invitation cannot race acceptance.
    member = MemberDetail.objects.select_for_update().select_related('reservation__group').filter(pk=initial.member_id).first()
    if not member:
        raise InvitationError('找不到邀請連結，可能已撤銷或重新產生', 404)
    invitation = ParticipantInvitation.objects.select_for_update().filter(pk=initial.pk, token=token).first()
    if not invitation:
        raise InvitationError('找不到邀請連結，可能已撤銷或重新產生', 404)
    invitation.member = member
    check_invitation(invitation, user)
    if invitation.accepted_at:
        return invitation
    if role not in {'self', 'guardian'}:
        raise InvitationError('請選擇學員本人或家長／監護人')
    insurance = member.insurance_data if isinstance(member.insurance_data, dict) else {}
    try:
        age = participant_age(str(insurance.get('birth_date') or '').strip())
    except ValueError:
        age = None  # Legacy invalid dates remain editable in the authenticated course form.
    if role == 'self' and age is not None and age < GUARDIAN_AGE_LIMIT:
        raise InvitationError(f'未滿 {GUARDIAN_AGE_LIMIT} 歲請由家長／監護人綁定')
    member.user = user if role == 'self' else None
    member.guardian = user if role == 'guardian' else None
    member.save(update_fields=['user', 'guardian'])
    invitation.accepted_by = user
    invitation.accepted_at = timezone.now()
    invitation.binding_role = role
    invitation.save(update_fields=['accepted_by', 'accepted_at', 'binding_role'])
    return invitation
