from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_campus_scope as fixtures
from booking.models import Booking, MemberDetail, Reservation, ReservationGroup


class InsuranceProcessingTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)
        self.group = ReservationGroup.objects.create(client=self.tenant,campus=self.campus_a)
        self.member = MemberDetail.objects.create(reservation=Reservation.objects.create(group=self.group),
            insurance_data={'full_name':'QA 原學員'},insurance_completed_at=timezone.now(),
            waiver_signature='QA 原簽名',waiver_document_version='QA-v1',waiver_document_snapshot='QA 原文件')
        self.api = APIClient()
        self.api.force_authenticate(self.superuser)
        self.url = f'/api/admin/snowland/insurance-records/{self.member.pk}/'
        self.report_url = self.url+'processing/'

    def payload(self, **changes):
        return {'status':'checking','premium_amount':None,'currency':'','expected_updated_at':None,**changes}

    def test_filled_member_data_does_not_mean_insurance_has_been_purchased(self):
        response=self.api.get(self.url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data.get('insurance_processing_status'),'pending')
        self.assertIsNone(response.data['insurance_premium_amount'])

    def test_course_dates_are_unique_and_cancelled_courses_do_not_populate_calendar(self):
        for start,end in [('09:00','12:00'),('13:00','15:00')]:
            Booking.objects.create(reservation=self.member.reservation,date='2026-10-21',start_time=start,end_time=end)
        self.assertEqual(self.api.get(self.url).json()['course_dates'],['2026-10-21'])
        self.member.reservation.status='cancelled';self.member.reservation.save()
        response=self.api.get(self.url)
        self.assertEqual(response.data['course_dates'],[])
        self.assertFalse(response.data['can_remind'])

    def test_save_processing_and_amount_without_mutating_signed_or_member_data(self):
        response=self.api.post(self.report_url,self.payload(status='processing',premium_amount='350.50',currency='jpy'),format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_processing_status,'processing')
        self.assertEqual(str(self.member.insurance_premium_amount),'350.50')
        self.assertEqual(self.member.insurance_premium_currency,'JPY')
        self.assertEqual(self.member.insurance_processing_updated_by_id,self.superuser.pk)
        self.assertIsNotNone(self.member.insurance_processing_updated_at)
        self.assertEqual(self.member.insurance_data,{'full_name':'QA 原學員'})
        self.assertEqual(self.member.waiver_signature,'QA 原簽名')
        self.assertEqual(self.member.waiver_document_snapshot,'QA 原文件')

    def test_invalid_values_do_not_partially_save_or_allow_extra_member_fields(self):
        for changes in ({'premium_amount':'-1','currency':'TWD'}, {'premium_amount':'NaN','currency':'TWD'},
                        {'premium_amount':'12.345','currency':'TWD'}, {'premium_amount':'100','currency':''},
                        {'currency':'123'}, {'status':'bad'}, {'guardian':self.manager.pk},
                        {'insurance_data':{'full_name':'不該覆蓋'}}):
            with self.subTest(changes=changes):
                response=self.api.post(self.report_url,self.payload(**changes),format='json')
                self.assertEqual(response.status_code,400,response.data)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_data,{'full_name':'QA 原學員'})
        self.assertEqual(self.member.insurance_processing_status,'pending')

    def test_mark_insured_requires_explicit_confirmation_and_never_sets_form_or_signature(self):
        self.member.insurance_completed_at=None
        self.member.save(update_fields=['insurance_completed_at'])
        response=self.api.post(self.report_url,self.payload(status='insured'),format='json')
        self.assertEqual(response.status_code,400,response.data)
        response=self.api.post(self.report_url,self.payload(status='insured',confirm_insured=True),format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_processing_status,'insured')
        self.assertIsNone(self.member.insurance_completed_at)
        self.assertEqual(self.member.waiver_signature,'QA 原簽名')

    def test_stale_editor_cannot_overwrite_newer_report(self):
        first=self.api.post(self.report_url,self.payload(status='checking'),format='json')
        self.assertEqual(first.status_code,200,first.data)
        stale=self.api.post(self.report_url,self.payload(status='processing'),format='json')
        self.assertEqual(stale.status_code,409,stale.data)
        updated=self.api.post(self.report_url,self.payload(status='processing',expected_updated_at=first.data['data']['insurance_processing_updated_at']),format='json')
        self.assertEqual(updated.status_code,200,updated.data)

    def test_assistant_can_report_insurance_progress_but_member_forms_remain_readonly(self):
        # Customer slide59 separates operational insurance reporting from signed forms.
        self.profile.role='assistant'
        self.profile.admin_permissions=None
        self.profile.save()
        self.api.force_authenticate(User.objects.get(pk=self.manager.pk))
        detail=self.api.get(self.url)
        self.assertEqual(detail.status_code,200)
        self.assertFalse(detail.data['can_mark_complete'])
        self.assertTrue(detail.data['can_process_insurance'])
        result=self.api.post(self.report_url,self.payload(status='checking',premium_amount='350.50',currency='JPY'),format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(self.api.patch(self.url,{'age_range':'19-24y'},format='json').status_code,403)
        self.assertEqual(self.api.post(self.url+'complete/',{'field':'waiver'},format='json').status_code,403)
        self.assertEqual(self.api.get('/api/admin/snowland/campuses/').status_code,403)
        self.assertEqual(self.api.get('/api/admin/snowland/payroll-statements/').status_code,403)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_processing_status,'checking')
        self.assertEqual(self.member.insurance_processing_updated_by_id,self.manager.pk)
        self.assertEqual(self.member.insurance_data,{'full_name':'QA 原學員'})
        self.assertEqual(self.member.waiver_signature,'QA 原簽名')
        self.assertEqual(self.member.waiver_document_snapshot,'QA 原文件')

    def test_assistant_insured_report_still_needs_confirmation_and_cannot_forge_form_fields(self):
        self.profile.role='assistant';self.profile.admin_permissions=None;self.profile.save()
        self.api.force_authenticate(User.objects.get(pk=self.manager.pk))
        self.assertEqual(self.api.post(self.report_url,self.payload(status='insured'),format='json').status_code,400)
        self.assertEqual(self.api.post(self.report_url,self.payload(insurance_data={'full_name':'不應改動'}),format='json').status_code,400)
        result=self.api.post(self.report_url,self.payload(status='insured',confirm_insured=True),format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_processing_status,'insured')
        self.assertEqual(self.member.insurance_data,{'full_name':'QA 原學員'})
        self.assertEqual(self.member.waiver_document_version,'QA-v1')

    def test_assistant_processing_requires_current_permission_scope_and_csrf(self):
        self.profile.role='assistant';self.profile.admin_permissions=None;self.profile.save()
        api=APIClient(enforce_csrf_checks=True);api.force_login(User.objects.get(pk=self.manager.pk))
        self.assertEqual(api.post(self.report_url,self.payload(),format='json').status_code,403)
        self.assertEqual(api.get(self.url).status_code,200)
        token=api.cookies['csrftoken'].value
        self.assertEqual(api.post(self.report_url,self.payload(),format='json',HTTP_X_CSRFTOKEN=token,
            HTTP_X_CAMPUS_ID=str(self.campus_b.pk)).status_code,404)
        self.assertEqual(api.post(self.report_url,self.payload(),format='json',HTTP_X_CSRFTOKEN=token).status_code,200)
        self.profile.admin_permissions=['orders'];self.profile.save(update_fields=['admin_permissions'])
        self.assertEqual(api.get(self.url).status_code,403)
        self.assertEqual(api.post(self.report_url,self.payload(),format='json',HTTP_X_CSRFTOKEN=token).status_code,403)

    def test_generic_patch_cannot_rebind_guardian_or_rewrite_form_completion(self):
        response=self.api.patch(self.url,{'guardian':self.manager.pk,'insurance_completed_at':None},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.guardian_id)
        self.assertIsNotNone(self.member.insurance_completed_at)

    def test_processing_uses_campus_scope_and_requires_csrf(self):
        self.profile.admin_permissions=['insurance_records']
        self.profile.save()
        self.api.force_authenticate(User.objects.get(pk=self.manager.pk))
        self.group.campus=self.campus_b
        self.group.save(update_fields=['campus'])
        self.assertEqual(self.api.post(self.report_url,self.payload(),format='json').status_code,404)
        api=APIClient(enforce_csrf_checks=True)
        api.force_login(self.superuser)
        self.assertEqual(api.post(self.report_url,self.payload(),format='json').status_code,403)
        api.get(self.url)
        allowed=api.post(self.report_url,self.payload(),format='json',HTTP_X_CSRFTOKEN=api.cookies['csrftoken'].value)
        self.assertEqual(allowed.status_code,200,allowed.data)
