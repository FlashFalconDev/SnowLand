from django.test import TestCase
from booking import tests_advanced_booking_scope as fixtures
from booking.models import ReservationGroup,Reservation,Booking
from booking.scheduler import assign_coachs
from Coach.models import Coach,CoachResort,CoachCourseLevel,CoachLeaveRequest
from Resorts.models import Campus
from Client.models import Client


class SchedulerScopeLeaveTests(TestCase):
    def setUp(self):
        fixtures.AdvancedBookingScopeTests.setUp(self)
        self.group=ReservationGroup.objects.create(client=self.client_record,campus=self.campus)
        self.row=Reservation.objects.create(group=self.group,resort=self.resort,course_type=self.private_template.course_type,course_template=self.private_template,number_of_people=1,max_ability_level='no_exp',ability_level_counts={'no_exp':1})
        day=self.payload['cart'][0]['courses'][0]['date']
        self.booking=Booking.objects.create(reservation=self.row,date=day,start_time='09:00',end_time='13:00')
        self.booking.refresh_from_db()

    def coach(self,client=None,campus=None):
        coach=Coach.objects.create(client=client or self.client_record,name='QA排課',languages=['zh'],availability_status='active')
        coach.campuses.add(campus or self.campus)
        CoachResort.objects.create(coach=coach,resort=self.resort)
        CoachCourseLevel.objects.create(coach=coach,course_type=self.private_template.course_type,ability_levels=['no_exp'],price_level='Lv1')
        return coach

    def assert_unassigned(self):
        success,_=assign_coachs(reservations_to_assign=[self.row])
        self.assertFalse(success)
        self.row.refresh_from_db();self.booking.refresh_from_db()
        self.assertIsNone(self.row.preferred_coach_id);self.assertFalse(self.booking.is_scheduled)

    def test_stale_foreign_coach_links_cannot_cross_company(self):
        self.coach(client=Client.objects.create(name='Other',internal_code='other'))
        self.assert_unassigned()

    def test_resort_link_does_not_grant_another_campus_assignment(self):
        other=Campus.objects.create(client=self.client_record,name='Other',code='other')
        self.coach(campus=other)
        self.assert_unassigned()

    def test_approved_leave_is_not_automatically_booked(self):
        coach=self.coach()
        CoachLeaveRequest.objects.create(coach=coach,start_date=self.booking.date,end_date=self.booking.date,status='approved',reason='QA')
        self.assert_unassigned()

    def test_pending_or_cancelled_leave_does_not_block_available_coach(self):
        coach=self.coach()
        leave=CoachLeaveRequest.objects.create(coach=coach,start_date=self.booking.date,end_date=self.booking.date,status='pending',reason='QA')
        for state in ['pending','cancelled','rejected']:
            leave.status=state;leave.save()
            success,_=assign_coachs(reservations_to_assign=[self.row]);self.assertTrue(success)

    def test_preferred_coach_also_cannot_bypass_approved_leave(self):
        coach=self.coach();self.row.preferred_coach=coach;self.row.is_preferred_coach=True;self.row.save()
        CoachLeaveRequest.objects.create(coach=coach,start_date=self.booking.date,end_date=self.booking.date,status='approved',reason='QA')
        success,_=assign_coachs(reservations_to_assign=[self.row]);self.assertFalse(success)
        self.booking.refresh_from_db();self.assertFalse(self.booking.is_scheduled)

    def test_cross_day_leave_failure_explains_different_coach_fallback(self):
        from datetime import timedelta
        day2=self.booking.date+timedelta(days=1)
        Booking.objects.create(reservation=self.row,date=day2,start_time='09:00',end_time='13:00')
        first=self.coach();second=self.coach()
        CoachLeaveRequest.objects.create(coach=first,start_date=day2,end_date=day2,status='approved',reason='QA')
        CoachLeaveRequest.objects.create(coach=second,start_date=self.booking.date,end_date=self.booking.date,status='approved',reason='QA')
        success,report=assign_coachs(reservations_to_assign=[self.row])
        self.assertFalse(success);self.assertIn('同一位教練',report['conflict_details']['reason'])
        self.assertIn('進階排課',report['conflict_details']['reason'])

    def test_candidate_lookup_excludes_foreign_coach_despite_stale_links(self):
        from booking.scheduler import get_feasible_coaches
        foreign=self.coach(client=Client.objects.create(name='Other',internal_code='other'))
        own=self.coach()
        candidates=get_feasible_coaches('zh',self.resort,self.row.course_type_id,'no_exp',course_template=self.private_template)
        self.assertIn(own,candidates)
        self.assertNotIn(foreign,candidates)

    def test_date_suggestions_exclude_approved_leave_and_keep_other_days(self):
        from datetime import timedelta
        from booking.scheduler import _generate_suggestion_report
        coach=self.coach()
        CoachLeaveRequest.objects.create(coach=coach,start_date=self.booking.date,end_date=self.booking.date,status='approved',reason='QA')
        report=_generate_suggestion_report([self.booking.date],[coach],{},nearby_days=1)['suggestions']
        self.assertNotIn(str(self.booking.date),report)
        self.assertEqual(report[str(self.booking.date+timedelta(days=1))]['上午']['available_sessions'],1)

    def test_pending_leave_still_allows_date_suggestions(self):
        from booking.scheduler import _generate_suggestion_report
        coach=self.coach()
        CoachLeaveRequest.objects.create(coach=coach,start_date=self.booking.date,end_date=self.booking.date,status='pending',reason='QA')
        report=_generate_suggestion_report([self.booking.date],[coach],{},nearby_days=0)['suggestions']
        self.assertEqual(report[str(self.booking.date)]['全天']['available_sessions'],1)

    def assert_preferred_rejected(self,coach):
        self.row.preferred_coach=coach;self.row.is_preferred_coach=True;self.row.save()
        success,_=assign_coachs(reservations_to_assign=[self.row])
        self.assertFalse(success)
        self.booking.refresh_from_db();self.assertFalse(self.booking.is_scheduled)

    def test_preferred_coach_cannot_bypass_course_qualification(self):
        coach=self.coach()
        CoachCourseLevel.objects.filter(coach=coach).delete()
        self.assert_preferred_rejected(coach)

    def test_preferred_coach_cannot_bypass_requested_language(self):
        coach=self.coach();coach.languages=['en'];coach.save()
        self.assert_preferred_rejected(coach)

    def test_preferred_coach_cannot_bypass_required_ability(self):
        coach=self.coach();self.row.max_ability_level='level3';self.row.save()
        self.assert_preferred_rejected(coach)

    def test_public_booking_with_ineligible_preference_never_opens_payment(self):
        from copy import deepcopy
        from booking.models import Payment
        coach=self.coach();coach.languages=['en'];coach.save()
        self.resort.auto_scheduling_enabled=True;self.resort.save()
        body=deepcopy(self.payload);body['cart'][0]['coach']=coach.pk
        result=self.api.post('/booking/snowland/api/create-reservation/',body,format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertTrue(result.data['scheduling_failed'])
        self.assertFalse(result.data['requires_payment'])
        self.assertIn('語言或學員程度',result.data['conflict_details']['reason'])
        group=ReservationGroup.objects.get(pk=result.data['reservation_group_ids'][0])
        self.assertEqual(group.reservations.get().status,'auto_assignment_failed')
        self.assertFalse(Booking.objects.filter(reservation__group=group,is_scheduled=True).exists())
        self.assertFalse(Payment.objects.filter(reservation_group=group).exists())

    def test_template_named_coaches_are_a_restriction_not_only_priority(self):
        from booking.scheduler import get_feasible_coaches,coach_matches_course_template
        named=self.coach();outside=self.coach()
        self.private_template.allowed_coaches.add(named)
        candidates=get_feasible_coaches('zh',self.resort,self.row.course_type_id,'no_exp',course_template=self.private_template)
        self.assertEqual([coach.pk for coach in candidates],[named.pk])
        self.assertFalse(coach_matches_course_template(outside,self.private_template))
        self.assert_preferred_rejected(outside)

    def test_empty_template_coach_list_keeps_all_qualified_coaches(self):
        from booking.scheduler import get_feasible_coaches
        first=self.coach();second=self.coach()
        candidates=get_feasible_coaches('zh',self.resort,self.row.course_type_id,'no_exp',course_template=self.private_template)
        self.assertEqual({coach.pk for coach in candidates},{first.pk,second.pk})

    def test_public_coach_picker_excludes_template_outsiders(self):
        named=self.coach();self.coach()
        self.private_template.allowed_coaches.add(named)
        self.resort.auto_scheduling_enabled=True;self.resort.save()
        result=self.api.get('/booking/snowland/api/coaches/',{
            'resort':self.resort.name,'courseType':self.row.course_type_id,
            'courseTemplateId':self.private_template.pk,'abilityLevel':'no_exp',
            'campusId':self.campus.pk,
        })
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual([row['pk'] for row in result.data['coach_list']],[named.pk])

    def test_named_coach_leave_does_not_fall_back_to_unlisted_coach(self):
        named=self.coach();self.coach()
        self.private_template.allowed_coaches.add(named)
        CoachLeaveRequest.objects.create(coach=named,start_date=self.booking.date,end_date=self.booking.date,status='approved',reason='QA')
        self.assert_unassigned()
