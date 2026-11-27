from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_campus_scope as fixtures
from API.staff_positions import apply_position_access
from Client.models import ModuleInfo, ModuleSetting
from Coach.models import Coach
from Control.models import TenantStaffMembership, TenantStaffPosition
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

    def configure_eligibility(self, **flags):
        module, _ = ModuleInfo.objects.get_or_create(module_sid='booking', defaults={'module_name': '訂課'})
        row, _ = ModuleSetting.objects.get_or_create(client=self.tenant, module=module)
        row.settings = {**row.settings, **flags}
        row.save(update_fields=['settings'])
        return row

    def report(self, status, **changes):
        return self.api.post(self.report_url, self.payload(status=status, **changes), format='json')

    def sign_in_with_role(self, role, permissions=None):
        self.profile.role = role
        self.profile.admin_permissions = permissions
        self.profile.save(update_fields=['role', 'admin_permissions'])
        self.api.force_authenticate(User.objects.get(pk=self.manager.pk))

    def test_eligibility_requires_an_explicit_boolean_on_an_active_tenant_row(self):
        listing = '/api/admin/snowland/insurance-records/'
        self.assertEqual(self.report('ineligible').status_code, 400)
        self.assertIs(self.api.get(listing).data['data']['insurance_eligibility_enabled'], False)
        row = self.configure_eligibility(another_setting='keep')
        ModuleSetting.objects.create(client=self.other_tenant, module=row.module,
                                     settings={'insurance_eligibility_enabled': True})
        self.assertEqual(self.report('ineligible').status_code, 400)
        for value in (False, 'true', 1, None):
            with self.subTest(value=value):
                self.configure_eligibility(insurance_eligibility_enabled=value)
                self.assertEqual(self.report('ineligible').status_code, 400)
        row = self.configure_eligibility(insurance_eligibility_enabled=True)
        row.is_active = False
        row.save(update_fields=['is_active'])
        self.assertEqual(self.report('ineligible').status_code, 400)
        row.is_active = True
        row.save(update_fields=['is_active'])
        row.module.is_active = False
        row.module.save(update_fields=['is_active'])
        self.assertEqual(self.report('ineligible').status_code, 400)
        row.module.is_active = True
        row.module.save(update_fields=['is_active'])
        self.assertIs(self.api.get(listing).data['data']['insurance_eligibility_enabled'], True)
        self.assertEqual(self.report('ineligible').status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.settings['another_setting'], 'keep')

    def test_insurance_staff_can_mark_each_open_status_and_restore_only_to_checking(self):
        self.configure_eligibility(insurance_eligibility_enabled=True)
        self.sign_in_with_role('insurance')
        for previous in ('pending', 'checking', 'processing'):
            with self.subTest(previous=previous):
                MemberDetail.objects.filter(pk=self.member.pk).update(
                    insurance_processing_status=previous, insurance_processing_updated_at=None,
                )
                self.assertEqual(self.api.get(self.url).data['insurance_eligibility'], {'can_mark': True, 'can_restore': False})
                marked = self.report('ineligible')
                self.assertEqual(marked.status_code, 200, marked.data)
                self.member.refresh_from_db()
                self.assertEqual(self.member.insurance_processing_status, 'ineligible')
                self.assertEqual(self.member.insurance_processing_updated_by_id, self.manager.pk)
                version = marked.data['data']['insurance_processing_updated_at']
                self.assertIsNotNone(version)
                for forbidden in ('pending', 'processing', 'insured'):
                    result = self.report(forbidden, confirm_insured=True, expected_updated_at=version)
                    self.assertEqual(result.status_code, 400, result.data)
                    self.assertIn('僅能復原為對資料中', result.data['msg'])
                self.assertEqual(self.report('insured', expected_updated_at=version).status_code, 400)
                self.assertEqual(self.report('checking').status_code, 409)
                self.assertEqual(self.report('checking', expected_updated_at=version).status_code, 200)
                self.member.refresh_from_db()
                self.assertEqual(self.member.insurance_processing_status, 'checking')

    def test_hq_can_mark_with_effective_permission_but_insured_cannot_be_marked(self):
        self.configure_eligibility(insurance_eligibility_enabled=True)
        self.sign_in_with_role('hq_admin', ['order_view'])
        self.assertEqual(self.report('ineligible').status_code, 403)
        self.sign_in_with_role('hq_admin')
        self.member.insurance_processing_status = 'insured'
        self.member.save(update_fields=['insurance_processing_status'])
        self.assertIs(self.api.get(self.url).data['insurance_eligibility']['can_mark'], False)
        rejected = self.report('ineligible')
        self.assertEqual(rejected.status_code, 400, rejected.data)
        self.assertIn('已投保完成的紀錄不能直接標記', rejected.data['msg'])
        self.member.insurance_processing_status = 'pending'
        self.member.save(update_fields=['insurance_processing_status'])
        self.assertEqual(self.report('ineligible').status_code, 200)

    def test_assistant_requires_explicit_opt_in_to_mark_or_restore(self):
        self.configure_eligibility(insurance_eligibility_enabled=True)
        self.sign_in_with_role('assistant')
        for admin_flag in (False, 'true', 1):
            self.configure_eligibility(insurance_eligibility_allow_admin=admin_flag)
            self.assertIs(self.api.get(self.url).data['insurance_eligibility']['can_mark'], False)
            self.assertEqual(self.report('ineligible').status_code, 403)
        self.configure_eligibility(insurance_eligibility_allow_admin=True)
        marked = self.report('ineligible')
        self.assertEqual(marked.status_code, 200, marked.data)
        version = marked.data['data']['insurance_processing_updated_at']
        self.configure_eligibility(insurance_eligibility_allow_admin=False)
        self.assertIs(self.api.get(self.url).data['insurance_eligibility']['can_restore'], False)
        self.assertEqual(self.report('checking', expected_updated_at=version).status_code, 403)
        self.configure_eligibility(insurance_eligibility_enabled=False, insurance_eligibility_allow_admin=True)
        self.assertEqual(self.report('checking', expected_updated_at=version).status_code, 200)

    def test_combined_insurance_position_honors_permission_tenant_campus_and_csrf(self):
        self.configure_eligibility(insurance_eligibility_enabled=True)
        self.sign_in_with_role('assistant')
        membership = TenantStaffMembership.objects.create(client=self.tenant, user=self.manager)
        assistant = TenantStaffPosition.objects.create(client=self.tenant, name='QA 行政', role='assistant',
                                                       permissions=['order_view'], all_campuses=True)
        insurance = TenantStaffPosition.objects.create(client=self.tenant, name='QA 保險', role='insurance',
                                                       permissions=['insurance_records'])
        insurance.campuses.add(self.campus_a)
        apply_position_access(membership, [assistant, insurance], False)
        membership.positions.set([assistant, insurance])
        self.assertEqual(membership.role, 'assistant')
        self.assertEqual(self.api.post(self.report_url.replace('/snowland/', '/other/'),
                                       self.payload(status='ineligible'), format='json').status_code, 403)
        self.group.campus = self.campus_b
        self.group.save(update_fields=['campus'])
        self.assertEqual(self.report('ineligible').status_code, 404)
        self.group.campus = self.campus_a
        self.group.save(update_fields=['campus'])
        session = APIClient(enforce_csrf_checks=True)
        session.force_login(self.manager)
        self.assertEqual(session.post(self.report_url, self.payload(status='ineligible'), format='json').status_code, 403)
        self.assertEqual(self.report('ineligible').status_code, 200)
        coach = User.objects.create_user('qa-insurance-coach')
        coach_profile = coach.userprofile
        coach_profile.is_coach = True
        coach_profile.save(update_fields=['is_coach'])
        Coach.objects.create(client=self.tenant, user=coach, name='QA 教練').campuses.add(self.campus_a)
        self.api.force_authenticate(coach)
        self.assertEqual(self.report('ineligible').status_code, 403)

    def test_ineligible_rejects_new_positive_premiums_and_leaves_existing_amount_untouched(self):
        self.configure_eligibility(insurance_eligibility_enabled=True)
        self.member.insurance_premium_amount = '350.50'
        self.member.insurance_premium_currency = 'JPY'
        self.member.save(update_fields=['insurance_premium_amount', 'insurance_premium_currency'])
        self.assertEqual(self.report('ineligible', premium_amount='1').status_code, 400)
        version = None
        for amount in ('0', '', None):
            response = self.report('ineligible', premium_amount=amount, expected_updated_at=version)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['data']['insurance_premium_amount'], '350.50')
            self.assertEqual(response.data['data']['insurance_premium_currency'], 'JPY')
            version = response.data['data']['insurance_processing_updated_at']
        self.assertEqual(self.report('ineligible', premium_amount='1', currency='TWD', expected_updated_at=version).status_code, 400)

    def test_disabled_tenant_still_lists_filters_and_restores_previously_marked_records(self):
        self.sign_in_with_role('insurance')
        self.member.insurance_processing_status = 'ineligible'
        self.member.save(update_fields=['insurance_processing_status'])
        other = MemberDetail.objects.create(reservation=self.member.reservation)
        url = '/api/admin/snowland/insurance-records/'
        all_rows = self.api.get(url, {'status': 'all', 'processing_status': 'all'}).data['data']
        self.assertIs(all_rows['insurance_eligibility_enabled'], False)
        self.assertEqual({row['id']: row['insurance_processing_status'] for row in all_rows['list']},
                         {self.member.pk: 'ineligible', other.pk: 'pending'})
        filtered = self.api.get(url, {'processing_status': 'ineligible'}).data['data']
        self.assertEqual([row['id'] for row in filtered['list']], [self.member.pk])
        self.assertEqual(self.api.get(self.url).data['insurance_eligibility'], {'can_mark': False, 'can_restore': True})
        self.assertEqual(self.report('checking').status_code, 200)
        self.assertEqual(self.api.get(url, {'processing_status': 'ineligible'}).data['data']['list'], [])

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
