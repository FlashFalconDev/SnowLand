from datetime import time, timedelta
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from booking.models import Booking, CourseEvaluation, MemberDetail, Payment, Reservation, ReservationGroup


class ParticipantInvitationTests(TestCase):
    center = '/booking/snowland/api/member-center/'

    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.owner = User.objects.create_user('invite-organizer')
        self.participant = User.objects.create_user('invite-participant')
        self.stranger = User.objects.create_user('invite-stranger')
        self.group = ReservationGroup.objects.create(client=self.tenant, user=self.owner)
        self.reservation = Reservation.objects.create(group=self.group, status='auto_assigned', number_of_people=2)
        Booking.objects.create(reservation=self.reservation, date=timezone.localdate()+timedelta(days=10), start_time=time(9), end_time=time(12))
        self.member = MemberDetail.objects.create(reservation=self.reservation, user=self.owner, insurance_data={'full_name': 'Already entered', 'id_number': 'PRIVATE'})
        self.other = MemberDetail.objects.create(reservation=self.reservation, user=self.owner)
        self.payment = Payment.objects.create(reservation_group=self.group, user=self.owner, status='paid', expires_at=timezone.now()+timedelta(days=3))
        self.api = APIClient()
        self.api.force_authenticate(self.owner)

    def issue(self, member=None, expected=201):
        response = self.api.post(self.center, {'action': 'invite_participant', 'member_id': (member or self.member).pk}, format='json')
        self.assertEqual(response.status_code, expected, response.data)
        return response.data

    def url(self, token):
        return f'/booking/snowland/api/participant-invitations/{token}/'

    def accept(self, token, user=None, role='self', expected=200):
        client = APIClient()
        client.force_authenticate(user or self.participant)
        response = client.post(self.url(token), {'confirmed': True, 'role': role}, format='json')
        self.assertEqual(response.status_code, expected, response.data)
        return response

    def test_paid_owner_invites_and_authenticated_confirmation_transfers_only_one_students_access(self):
        invitation = self.issue()
        client = APIClient()
        self.assertEqual(client.get(self.url(invitation['token'])).status_code, 401)
        client.force_authenticate(self.participant)
        preview = client.get(self.url(invitation['token']))
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['student_number'], 1)
        self.assertNotIn('PRIVATE', str(preview.data))
        self.assertNotIn('Already entered', str(preview.data))
        self.assertEqual(client.post(self.url(invitation['token']), {'role': 'self'}, format='json').status_code, 400)
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, self.owner.pk)
        self.accept(invitation['token'])
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, self.participant.pk)
        self.assertEqual(self.member.insurance_data['id_number'], 'PRIVATE')
        owner_forms = self.api.get(self.center).data['pre_course_forms']
        self.assertEqual([row['id'] for row in owner_forms], [self.other.pk])
        self.assertEqual(owner_forms[0]['student_number'], 2)
        own_forms = client.get(self.center).data['pre_course_forms']
        self.assertEqual([row['id'] for row in own_forms], [self.member.pk])
        self.assertEqual(own_forms[0]['student_number'], 1)
        roster = self.api.get(self.center).data['orders'][0]['reservations'][0]['participants']
        self.assertEqual(roster[0]['binding_status'], 'bound')
        self.assertNotIn('insurance_data', roster[0])
        self.assertNotIn('email', roster[0])
        self.issue(expected=409)

    def test_expiry_rotation_cancellation_and_other_tenant_reject_without_binding(self):
        old = self.issue()['token']
        new = self.issue()['token']
        self.assertNotEqual(old, new)
        self.accept(old, expected=404)
        self.member.invitation.expires_at = timezone.now()-timedelta(seconds=1)
        self.member.invitation.save(update_fields=['expires_at'])
        self.accept(new, expected=410)
        new = self.issue()['token']
        other_tenant = Client.objects.create(name='Other', internal_code='other')
        client = APIClient(); client.force_authenticate(self.participant)
        self.assertEqual(client.get(f'/booking/{other_tenant.internal_code}/api/participant-invitations/{new}/').status_code, 404)
        self.reservation.status = 'cancelled'; self.reservation.save(update_fields=['status'])
        self.accept(new, expected=400)
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, self.owner.pk)

    def test_only_paid_order_owner_can_issue_and_pending_link_can_be_revoked(self):
        self.api.force_authenticate(self.stranger)
        self.issue(expected=404)
        self.api.force_authenticate(self.owner)
        self.payment.status = 'unpaid'; self.payment.save(update_fields=['status'])
        self.issue(expected=400)
        self.payment.status = 'paid'; self.payment.save(update_fields=['status'])
        token = self.issue()['token']
        response = self.api.post(self.center, {'action': 'revoke_participant_invitation', 'member_id': self.member.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.accept(token, expected=404)

    def test_replay_is_idempotent_for_recipient_but_cannot_be_claimed_by_someone_else(self):
        token = self.issue()['token']
        self.accept(token)
        self.accept(token)
        self.accept(token, user=self.stranger, expected=409)
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, self.participant.pk)
        self.assertIsNotNone(self.member.invitation.accepted_at)
        self.assertEqual(self.api.post(self.center, {'action': 'revoke_participant_invitation', 'member_id': self.member.pk}, format='json').status_code, 409)

    def test_child_must_bind_to_guardian_and_guardian_can_manage_child_not_other_students(self):
        self.member.insurance_data['birth_date'] = (timezone.localdate()-timedelta(days=365*10)).isoformat()
        self.member.save(update_fields=['insurance_data'])
        token = self.issue()['token']
        self.accept(token, expected=400)
        self.accept(token, role='guardian')
        self.member.refresh_from_db()
        self.assertIsNone(self.member.user_id)
        self.assertEqual(self.member.guardian_id, self.participant.pk)
        guardian = APIClient(); guardian.force_authenticate(self.participant)
        forms = guardian.get(self.center).data['pre_course_forms']
        self.assertEqual([row['id'] for row in forms], [self.member.pk])

    def test_binding_keeps_historical_signature_and_learning_record_but_changes_viewer(self):
        self.member.waiver_signature = 'Original signer'
        self.member.waiver_document_snapshot = 'Original legal document'
        self.member.save(update_fields=['waiver_signature', 'waiver_document_snapshot'])
        self.reservation.status = 'completed'; self.reservation.save(update_fields=['status'])
        booking = self.reservation.bookings.get()
        booking.date = timezone.localdate()-timedelta(days=1); booking.save(update_fields=['date'])
        evaluation = CourseEvaluation.objects.create(booking=booking, member=self.member, coach_notes='Private progress')
        self.accept(self.issue()['token'])
        self.member.refresh_from_db()
        self.assertEqual(self.member.waiver_signature, 'Original signer')
        self.assertEqual(self.member.waiver_document_snapshot, 'Original legal document')
        self.assertNotIn(evaluation.pk, [record['id'] for record in self.api.get(self.center).data['learning_records']])
        self.assertEqual(APIClient().get(self.url(uuid4())).status_code, 401)

    def test_invalid_member_input_is_400_not_500(self):
        for value in [None, 'bad', {}, [], True, 1.5, '²', '9'*5000, '0', -1]:
            response = self.api.post(self.center, {'action': 'invite_participant', 'member_id': value}, format='json')
            self.assertEqual(response.status_code, 400, response.data)

    def test_binding_failure_rolls_back_identity_and_keeps_pending_invitation(self):
        from booking.participant_invitations import accept_invitation
        invitation = self.issue()
        with patch('booking.models.ParticipantInvitation.save', side_effect=RuntimeError('QA save failure')):
            with self.assertRaises(RuntimeError):
                accept_invitation(self.tenant, self.participant, invitation['token'], 'self')
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, self.owner.pk)
        self.assertIsNone(self.member.invitation.accepted_at)
        self.accept(invitation['token'])

    def test_bound_participant_gets_own_course_schedule_not_organizers_order_or_payment_access(self):
        self.group.line_group_url = 'https://line.me/ti/g/QA-ONLY'
        self.group.save(update_fields=['line_group_url'])
        self.accept(self.issue()['token'])
        client = APIClient(); client.force_authenticate(self.participant)
        center = client.get(self.center).data
        self.assertEqual(center['orders'], [])
        courses = center['participant_courses']
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]['id'], self.reservation.pk)
        self.assertEqual(courses[0]['student_names'], ['Already entered'])
        self.assertEqual(courses[0]['line_group_url'], self.group.line_group_url)
        self.assertEqual(courses[0]['bookings'][0]['start_time'], '09:00')
        for private_key in ['total_amount', 'payment_url', 'insurance_data', 'participants']:
            self.assertNotIn(private_key, courses[0])
        self.assertEqual(client.post(self.center, {'quick_rebook_group_id': self.group.pk}, format='json').status_code, 404)
        self.assertEqual(client.get(f'/booking/snowland/api/member-cancellations/{self.group.pk}/').status_code, 404)
        self.reservation.status = 'cancelled'; self.reservation.save(update_fields=['status'])
        # Another active course in the order must not give the cancelled attendee a group link.
        Reservation.objects.create(group=self.group, status='auto_assigned')
        course = client.get(self.center).data['participant_courses'][0]
        self.assertEqual(course['status'], 'cancelled')
        self.assertEqual(course['line_group_url'], '')

    def test_parent_with_two_children_gets_one_course_and_only_own_children_names(self):
        for member in [self.member, self.other]:
            self.accept(self.issue(member)['token'], role='guardian')
        client = APIClient(); client.force_authenticate(self.participant)
        courses = client.get(self.center).data['participant_courses']
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]['student_count'], 2)
        self.assertEqual(len(courses[0]['student_names']), 2)
        self.payment.status = 'refunded'; self.payment.save(update_fields=['status'])
        course = client.get(self.center).data['participant_courses'][0]
        self.assertEqual(course['payment_status'], 'refunded')
        self.assertEqual(course['line_group_url'], '')
