import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from API import tests_order_amendments as fixtures
from Resorts.models import PaymentAccount
from booking.models import MemberDetail, OrderAmendment, Payment
from Coach.models import Coach, CoachResort


class OrderAmendmentConfirmTests(TestCase):
    def setUp(self):
        fixtures.OrderAmendmentQuoteTests.setUp(self)
        self.payment=Payment.objects.create(reservation_group=self.group,user=self.manager,status='paid')
        self.bank=PaymentAccount.objects.create(client=self.tenant,name='QA收款',bank_name='QA銀行',account_number='QA-12345',account_holder='QA戶名',is_default=True)
        self.url_confirm=self.url.replace('amendment-quote/','amendment-confirm/')

    def body(self, **changes):
        draft=fixtures.OrderAmendmentQuoteTests.draft(self,**changes)
        people=draft['changes'][0]['number_of_people']
        draft['changes'][0]['ability_level_counts']={'no_exp':people}
        preview=self.api.post(self.url,draft,format='json')
        self.assertEqual(preview.status_code,200,getattr(preview,'data',None))
        return {**draft,'quote_token':preview.data['data']['quote_token'],'request_key':str(uuid.uuid4()),'reason':'QA客人要求修改','confirmed':True}

    def test_editor_options_are_order_scoped_and_do_not_expose_forms(self):
        response=self.api.get(self.url.replace('amendment-quote/','amendment-options/'))
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        item=response.data['data']['items'][0]
        self.assertEqual(item['members'],[{'id':self.member.pk,'name':'QA原學員'}])
        self.assertEqual([row['id'] for row in item['templates']],[self.template.pk])
        self.assertNotIn('insurance_data',str(item));self.assertNotIn('waiver_signature',str(item))
        url=self.url.replace('amendment-quote/','amendment-options/')
        self.assertEqual(self.api.get(url,HTTP_X_CAMPUS_ID=str(self.campus_b.pk)).status_code,404)
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.api.get(url).status_code,403)

    def test_old_editor_cannot_bypass_price_preview_by_changing_date_or_duration(self):
        from datetime import timedelta
        url=self.url.split('amendment-quote/')[0]
        for change in ({'date':str(self.day+timedelta(days=1))},{'end_time':'15:00'}):
            response=self.api.put(url,{'action':'save','payment_status':'refunded','booking_updates':[{'booking_id':self.booking.pk,**change}]},format='json')
            self.assertEqual(response.status_code,400,getattr(response,'data',None))
        self.booking.refresh_from_db();self.payment.refresh_from_db()
        self.assertEqual(self.booking.date,self.day);self.assertEqual(str(self.booking.end_time),'12:00:00');self.assertEqual(self.payment.status,'paid')

    def test_confirm_paid_increase_preserves_original_payment_and_versions(self):
        response=self.api.post(self.url_confirm,self.body(),format='json')
        self.assertEqual(response.status_code,201,getattr(response,'data',None))
        self.reservation.refresh_from_db();self.payment.refresh_from_db()
        self.assertEqual(self.reservation.number_of_people,2);self.assertEqual(self.reservation.payment_amount,11500)
        self.assertEqual(self.reservation.members.count(),2)
        self.assertIsNone(self.reservation.members.exclude(pk=self.member.pk).get().user_id)
        self.assertEqual(self.payment.status,'paid');self.assertEqual(self.group.payments.count(),1)
        row=OrderAmendment.objects.get(group=self.group)
        self.assertEqual((row.difference_amount,row.balance_amount,row.status),(2000,2000,'topup_due'))
        self.assertEqual(row.before_snapshot['reservations'][0]['payable'],9500)
        self.assertEqual(row.revision.snapshot['reservations'][0]['payable'],11500)
        self.assertEqual(self.group.revisions.count(),2)
        detail=self.api.get(self.url.split('amendment-quote/')[0])
        self.assertEqual(detail.status_code,200)
        self.assertEqual(detail.data['data']['amendment_balance'],{'amount':2000,'statuses':['topup_due']})

    def test_same_request_is_idempotent_and_different_reuse_is_rejected(self):
        body=self.body()
        first=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(first.status_code,201,getattr(first,'data',None))
        second=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(second.status_code,200,getattr(second,'data',None))
        self.assertEqual(OrderAmendment.objects.count(),1);self.assertEqual(self.reservation.members.count(),2)
        self.assertEqual(self.api.post(self.url_confirm,{**body,'reason':'different'},format='json').status_code,409)

    def test_stale_price_or_learner_state_cannot_commit(self):
        body=self.body();self.pricing.base_price_off_peak=20000;self.pricing.save()
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,409)
        self.assertEqual(OrderAmendment.objects.count(),0)
        body=self.body();self.member.insurance_data={'full_name':'QA更新資料'};self.member.save()
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,409)
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.number_of_people,1)

    def test_confirmation_and_scope_are_enforced(self):
        body=self.body()
        self.assertEqual(self.api.post(self.url_confirm,{**body,'confirmed':False},format='json').status_code,400)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json',HTTP_X_CAMPUS_ID=str(self.campus_b.pk)).status_code,404)
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,403)
        api=APIClient(enforce_csrf_checks=True);api.force_login(self.superuser)
        self.assertEqual(api.post(self.url_confirm,body,format='json').status_code,403)
        self.assertEqual(OrderAmendment.objects.count(),0)

    def test_decrease_archives_only_unselected_members_without_deleting_signed_history(self):
        self.reservation.number_of_people=3;self.reservation.course_fee=14000;self.reservation.save()
        removed=MemberDetail.objects.create(reservation=self.reservation,insurance_data={'full_name':'QA退出學員'},waiver_signature='QA舊簽名',waiver_document_snapshot='QA舊文件')
        other=MemberDetail.objects.create(reservation=self.reservation)
        body=self.body(number_of_people=1,retained_member_ids=[self.member.pk])
        response=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(response.status_code,201,getattr(response,'data',None))
        self.assertEqual(self.reservation.members.count(),1)
        self.assertEqual(MemberDetail.all_objects.filter(reservation=self.reservation).count(),3)
        old=MemberDetail.all_objects.get(pk=removed.pk)
        self.assertFalse(old.is_active);self.assertIsNotNone(old.archived_at)
        self.assertEqual(old.waiver_signature,'QA舊簽名');self.assertEqual(old.waiver_document_snapshot,'QA舊文件')
        row=OrderAmendment.objects.get()
        self.assertEqual((row.balance_amount,row.status),(-4000,'refund_account_due'))
        self.assertEqual(set(row.participant_changes[str(self.reservation.pk)]['archived_ids']),{removed.pk,other.pk})

    def test_new_change_nets_unsettled_difference_without_collecting_twice(self):
        self.assertEqual(self.api.post(self.url_confirm,self.body(),format='json').status_code,201)
        original=OrderAmendment.objects.get()
        body=self.body(number_of_people=1,equipment=None,retained_member_ids=[self.member.pk])
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,201)
        original.refresh_from_db();latest=OrderAmendment.objects.exclude(pk=original.pk).get()
        self.assertEqual(original.status,'superseded')
        self.assertEqual((latest.difference_amount,latest.balance_amount,latest.status),(-2000,0,'no_difference'))
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'paid')

    def test_bank_snapshot_is_frozen_and_invalid_retained_member_does_not_partially_save(self):
        self.assertEqual(self.api.post(self.url_confirm,self.body(),format='json').status_code,201)
        row=OrderAmendment.objects.get()
        self.bank.account_number='CHANGED';self.bank.save()
        row.refresh_from_db();self.assertEqual(row.bank_snapshot['account_number'],'QA-12345')
        wrong=MemberDetail.objects.create(reservation=self.reservation.__class__.objects.create(group=self.group.__class__.objects.create(client=self.other_tenant)))
        body=self.body(number_of_people=1,retained_member_ids=[wrong.pk])
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,400)
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.number_of_people,2)
        self.assertEqual(OrderAmendment.objects.count(),1)

    def test_unpaid_changes_stay_in_original_payment_and_pending_payment_is_not_changed(self):
        self.payment.status='unpaid';self.payment.save()
        response=self.api.post(self.url_confirm,self.body(),format='json')
        self.assertEqual(response.status_code,201,getattr(response,'data',None))
        row=OrderAmendment.objects.get()
        self.assertEqual((row.status,row.balance_amount),('included_in_order',0))
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'unpaid')
        self.payment.status='pending';self.payment.save()
        body=self.body(number_of_people=3)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,409)
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.number_of_people,2)

    def test_bad_token_and_changed_draft_do_not_modify_original(self):
        body=self.body()
        self.assertEqual(self.api.post(self.url_confirm,{**body,'quote_token':'invalid'},format='json').status_code,409)
        body['changes'][0]['number_of_people']=3
        body['changes'][0]['ability_level_counts']={'no_exp':3}
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,409)
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.number_of_people,1)
        self.assertEqual(OrderAmendment.objects.count(),0)

    def test_existing_manual_coach_is_checked_against_new_student_level(self):
        coach=Coach.objects.create(client=self.tenant,name='QA原人工教練',languages=['zh'])
        coach.campuses.add(self.campus_a);CoachResort.objects.create(coach=coach,resort=self.resort_a)
        self.reservation.preferred_coach=coach;self.reservation.status='manually_assigned';self.reservation.save()
        body=self.body()
        body['changes'][0]['ability_level_counts']={'level3':2}
        preview=self.api.post(self.url,{'changes':body['changes']},format='json')
        self.assertEqual(preview.status_code,200,getattr(preview,'data',None))
        body['quote_token']=preview.data['data']['quote_token']
        with patch('booking.scheduler.get_feasible_coaches',return_value=[]) as feasible:
            response=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(response.status_code,409,getattr(response,'data',None))
        self.assertEqual(feasible.call_args.args[3],'level3')
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.number_of_people,1)

    def test_legacy_foreign_company_coach_cannot_be_kept_even_with_wrong_campus_link(self):
        coach=Coach.objects.create(client=self.other_tenant,name='QA外公司誤掛教練',languages=['zh'])
        coach.campuses.add(self.campus_a)
        self.reservation.preferred_coach=coach;self.reservation.status='manually_assigned';self.reservation.save()
        body=self.body()
        with patch('booking.scheduler.get_feasible_coaches',return_value=[coach]) as feasible:
            response=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(response.status_code,409,getattr(response,'data',None))
        feasible.assert_not_called()
        self.assertEqual(OrderAmendment.objects.count(),0)

    def test_time_only_change_revalidates_equipment_slot_before_any_write(self):
        from Resorts.models import EquipmentAssistanceTimeSlot
        slot=EquipmentAssistanceTimeSlot.objects.create(resort=self.resort_a,start_time='08:00',end_time='09:00',is_active=True)
        self.reservation.equipment='purchaseAssistanceTime';self.reservation.equipment_assistance_time_slot=slot;self.reservation.equipment_rental_fee=350;self.reservation.save()
        slot.is_active=False;slot.save()
        draft=fixtures.OrderAmendmentQuoteTests.draft(self,number_of_people=1,equipment='purchaseAssistanceTime')
        draft['changes'][0]['courses'][0].update(start_time='10:00',end_time='13:00')
        response=self.api.post(self.url,draft,format='json')
        self.assertEqual(response.status_code,400,getattr(response,'data',None))
        self.assertEqual(OrderAmendment.objects.count(),0)

    def test_cancelled_history_is_retained_but_not_counted_in_revision_difference(self):
        from booking.models import Reservation
        historical=Reservation.objects.create(group=self.group,status='cancelled',course_fee=9000)
        response=self.api.post(self.url_confirm,self.body(),format='json')
        self.assertEqual(response.status_code,201,getattr(response,'data',None))
        row=OrderAmendment.objects.get()
        self.assertEqual(row.revision.difference_amount,2000)
        self.assertIn(historical.pk,[item['id'] for item in row.revision.snapshot['reservations']])

    def test_overlapping_sessions_in_same_reservation_do_not_double_book_coach(self):
        from booking.models import Booking
        coach=Coach.objects.create(client=self.tenant,name='QA人工教練',languages=['zh'])
        coach.campuses.add(self.campus_a)
        self.reservation.preferred_coach=coach;self.reservation.status='manually_assigned';self.reservation.save()
        other=Booking.objects.create(reservation=self.reservation,date=self.day,start_time='13:00',end_time='16:00',course_template=self.template)
        draft=fixtures.OrderAmendmentQuoteTests.draft(self)
        draft['changes'][0]['ability_level_counts']={'no_exp':2}
        draft['changes'][0]['courses'].append({'booking_id':other.pk,'template_id':self.template.pk,'date':str(self.day),'start_time':'10:00','end_time':'13:00'})
        preview=self.api.post(self.url,draft,format='json');self.assertEqual(preview.status_code,200)
        body={**draft,'quote_token':preview.data['data']['quote_token'],'request_key':str(uuid.uuid4()),'reason':'QA重疊時段','confirmed':True}
        with patch('booking.scheduler.get_feasible_coaches',return_value=[coach]):
            response=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(response.status_code,409,getattr(response,'data',None))
        other.refresh_from_db();self.assertEqual(str(other.start_time),'13:00:00')
        self.assertEqual(OrderAmendment.objects.count(),0)

    def test_failed_rescheduling_rolls_back_new_members_prices_and_versions(self):
        body=self.body();body['reschedule']=True
        with patch('booking.scheduler.assign_coachs',return_value=(False,{})):
            response=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(response.status_code,409,getattr(response,'data',None))
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.payment_amount,9500)
        self.assertEqual(MemberDetail.all_objects.filter(reservation=self.reservation).count(),1)
        self.assertEqual(self.group.revisions.count(),0);self.assertEqual(OrderAmendment.objects.count(),0)

    def test_signed_course_date_change_archives_signature_and_requires_resign(self):
        from datetime import timedelta
        self.member.waiver_signature='QA原簽名';self.member.save()
        body=self.body();body['changes'][0]['courses'][0]['date']=str(self.day+timedelta(days=1))
        preview=self.api.post(self.url,{'changes':body['changes']},format='json');self.assertEqual(preview.status_code,200)
        body['quote_token']=preview.data['data']['quote_token']
        self.assertEqual(preview.data['data']['items'][0]['waiver_resign_count'],1)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,201)
        self.member.refresh_from_db();self.assertEqual(self.member.waiver_signature,'QA原簽名')
        self.assertTrue(self.member.waiver_resign_required)
        archive=self.member.course_document_revisions.get()
        self.assertEqual(archive.snapshot['waiver_signature'],'QA原簽名')
        from booking.amendment_notifications import _content
        self.assertIn('登入自己的會員區重新簽署',_content(archive.revision.amendment)[1])
        self.assertNotIn('QA原簽名',_content(archive.revision.amendment)[1])
        self.assertEqual(archive.snapshot['previous_courses'][0]['date'],str(self.day))
        self.booking.refresh_from_db();self.assertEqual(self.booking.date,self.day+timedelta(days=1))
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,200)
        self.assertEqual(self.member.course_document_revisions.count(),1)
        self.assertNotIn('document_history',str(self.api.get('/api/admin/snowland/insurance-records/?status=all').data))
        from booking.legal_documents import get_current_waiver
        self.member.user=self.manager;self.member.save(update_fields=['user'])
        member_api=APIClient();member_api.force_authenticate(self.manager)
        center='/booking/snowland/api/member-center/'
        form=next(row for row in member_api.get(center).data['pre_course_forms'] if row['id']==self.member.pk)
        self.assertNotIn('document_history',str(member_api.get(center).data))
        self.assertTrue(form['waiver_resign_required']);self.assertFalse(form['waiver_completed'])
        payload={'action':'update_pre_course_form','member_id':self.member.pk,'age_range':'25-35y',
            'insurance_data':{'full_name':'QA原學員','birth_date':'1995-01-01'},'waiver_agreed':False}
        self.assertEqual(member_api.post(center,payload,format='json').status_code,200)
        self.member.refresh_from_db();self.assertTrue(self.member.waiver_resign_required)
        payload.update(waiver_agreed=True,waiver_signature='QA重新簽名',media_consent='decline',
            waiver_document_version=get_current_waiver(self.tenant)['version'])
        self.assertEqual(member_api.post(center,payload,format='json').status_code,409)
        payload['waiver_course_revision']=archive.pk
        self.assertEqual(member_api.post(center,payload,format='json').status_code,200)
        self.member.refresh_from_db();self.assertFalse(self.member.waiver_resign_required)
        archive.refresh_from_db();self.assertEqual(archive.snapshot['waiver_signature'],'QA原簽名')

    def test_insured_amendment_requires_recheck_preserves_private_history_and_cannot_mark_resigned(self):
        from datetime import timedelta
        from django.utils import timezone
        self.member.waiver_completed_at=timezone.now()
        self.member.insurance_processing_status='insured';self.member.insurance_premium_amount=300
        self.member.insurance_premium_currency='TWD';self.member.save()
        body=self.body(number_of_people=1)
        body['changes'][0]['courses'][0]['date']=str(self.day+timedelta(days=1))
        preview=self.api.post(self.url,{'changes':body['changes']},format='json')
        self.assertEqual(preview.data['data']['items'][0]['insurance_recheck_count'],1)
        body['quote_token']=preview.data['data']['quote_token']
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,201)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_processing_status,'checking')
        self.assertIsNone(self.member.insurance_premium_amount)
        self.assertTrue(self.member.waiver_resign_required)
        history=self.member.course_document_revisions.get()
        self.assertEqual(history.snapshot['insurance_processing_status'],'insured')
        self.assertEqual(history.snapshot['insurance_premium_amount'],'300.00')
        detail_url=f'/api/admin/snowland/insurance-records/{self.member.pk}/'
        self.assertEqual(self.api.get(detail_url).data['document_history'][0]['snapshot']['insurance_processing_status'],'insured')
        self.assertEqual(self.api.post(detail_url+'complete/',{'field':'waiver'},format='json').status_code,409)
        self.assertNotIn('document_history',str(self.api.get(self.url.split('amendment-quote/')[0]).data))
        self.assertEqual(self.api.get(detail_url,HTTP_X_CAMPUS_ID=str(self.campus_b.pk)).status_code,404)

    def test_time_only_change_does_not_invalidate_documents_or_insurance(self):
        self.member.waiver_signature='QA保留';self.member.insurance_processing_status='insured';self.member.save()
        body=self.body(number_of_people=1)
        body['changes'][0]['courses'][0].update(start_time='10:00',end_time='13:00')
        preview=self.api.post(self.url,{'changes':body['changes']},format='json')
        body['quote_token']=preview.data['data']['quote_token']
        self.assertEqual(preview.data['data']['items'][0]['waiver_resign_count'],0)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,201)
        self.member.refresh_from_db()
        self.assertFalse(self.member.waiver_resign_required)
        self.assertEqual(self.member.insurance_processing_status,'insured')
        self.assertFalse(self.member.course_document_revisions.exists())

    def test_template_change_also_requires_resign_without_changing_date(self):
        from Coursekit.models import CourseTemplate
        replacement=CourseTemplate.objects.create(course_type=self.template.course_type,name='QA另一模板',duration_hours=3,max_capacity=4)
        replacement.resorts.add(self.resort_a);self.pricing.templates.add(replacement)
        self.member.waiver_signature='QA舊模板簽名';self.member.save()
        body=self.body(number_of_people=1)
        body['changes'][0]['courses'][0]['template_id']=replacement.pk
        preview=self.api.post(self.url,{'changes':body['changes']},format='json')
        self.assertEqual(preview.status_code,200,preview.data)
        body['quote_token']=preview.data['data']['quote_token']
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,201)
        self.member.refresh_from_db();self.booking.refresh_from_db()
        self.assertTrue(self.member.waiver_resign_required)
        self.assertEqual(self.booking.date,self.day)
        self.assertEqual(self.booking.course_template_id,replacement.pk)
        self.assertEqual(self.member.course_document_revisions.get().snapshot['previous_courses'][0]['template_id'],self.template.pk)

    def test_failed_reassignment_rolls_back_date_and_signed_document_state(self):
        from datetime import timedelta
        self.member.waiver_signature='QA不得被覆寫';self.member.insurance_processing_status='insured';self.member.save()
        body=self.body(number_of_people=1)
        body['changes'][0]['courses'][0]['date']=str(self.day+timedelta(days=1))
        body['quote_token']=self.api.post(self.url,{'changes':body['changes']},format='json').data['data']['quote_token']
        body['reschedule']=True
        with patch('booking.scheduler.assign_coachs',return_value=(False,{})):
            self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,409)
        self.member.refresh_from_db();self.booking.refresh_from_db()
        self.assertEqual(self.booking.date,self.day)
        self.assertEqual(self.member.waiver_signature,'QA不得被覆寫')
        self.assertEqual(self.member.insurance_processing_status,'insured')
        self.assertFalse(self.member.waiver_resign_required)
        self.assertFalse(self.member.course_document_revisions.exists())
