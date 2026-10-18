from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_campus_scope as fixtures
from booking.models import Booking, MemberDetail, NotificationTemplate, ParticipantInvitation, Payment, Reservation, ReservationGroup
from booking.notification_recipients import course_notification_recipients
from booking.participant_invitations import InvitationError, issue_invitation
from booking.participants import ensure_reservation_members


class AmendmentParticipantArchiveTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)
        self.student=User.objects.create_user('archived-learner',email='archived@example.test')
        self.group=ReservationGroup.objects.create(client=self.tenant,campus=self.campus_a,user=self.superuser)
        self.reservation=Reservation.objects.create(group=self.group,resort=self.resort_a,number_of_people=1)
        Booking.objects.create(reservation=self.reservation,date=timezone.localdate()+timedelta(days=5),start_time='09:00',end_time='12:00')
        Payment.objects.create(reservation_group=self.group,user=self.superuser,status='paid')
        self.active=MemberDetail.objects.create(reservation=self.reservation,user=self.superuser)
        self.archived=MemberDetail.objects.create(reservation=self.reservation,user=self.student,is_active=False,archived_at=timezone.now(),
            insurance_data={'full_name':'QA舊學員'},waiver_signature='QA舊簽名',waiver_document_snapshot='QA舊文件')
        self.api=APIClient();self.api.force_authenticate(self.student)

    def test_archived_rows_and_signed_data_survive_but_normal_course_members_exclude_them(self):
        self.assertEqual(self.reservation.members.count(),1)
        self.assertFalse(MemberDetail.objects.filter(pk=self.archived.pk).exists())
        old=MemberDetail.all_objects.get(pk=self.archived.pk)
        self.assertEqual(old.insurance_data,{'full_name':'QA舊學員'})
        self.assertEqual(old.waiver_signature,'QA舊簽名');self.assertEqual(old.waiver_document_snapshot,'QA舊文件')
        self.assertEqual(MemberDetail.all_objects.filter(reservation=self.reservation).count(),2)
        self.assertEqual([member.pk for member in ensure_reservation_members(self.reservation)],[self.active.pk])

    def test_removed_student_cannot_keep_viewing_current_participant_course_or_forms(self):
        response=self.api.get('/booking/snowland/api/member-center/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['participant_courses'],[])
        self.assertEqual(response.data['pre_course_forms'],[])

    def test_removed_student_is_not_a_course_reminder_recipient(self):
        template=NotificationTemplate.objects.create(client=self.tenant,name='QA課前',event='pre_course',channel='in_app',body='QA')
        targets=course_notification_recipients(self.group,template,channel='in_app')
        self.assertNotIn(str(self.student.pk),targets)
        self.assertIn(str(self.superuser.pk),targets)

    def test_old_accepted_invitation_does_not_restore_archived_participation(self):
        invitation=ParticipantInvitation.objects.create(member=self.archived,expires_at=timezone.now()+timedelta(days=7),accepted_at=timezone.now(),accepted_by=self.student,binding_role='self')
        self.assertEqual(self.api.get(f'/booking/snowland/api/participant-invitations/{invitation.token}/').status_code,404)
        with self.assertRaises(InvitationError):issue_invitation(self.tenant,self.superuser,self.archived.pk)

    def test_insurance_list_and_detail_do_not_expose_archived_current_course_documents(self):
        self.api.force_authenticate(self.superuser)
        self.assertEqual(self.api.get(f'/api/admin/snowland/insurance-records/{self.archived.pk}/').status_code,404)
        rows=self.api.get('/api/admin/snowland/insurance-records/?status=all').data['data']['list']
        self.assertEqual([row['id'] for row in rows],[self.active.pk])
