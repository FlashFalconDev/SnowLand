from django.conf import settings
"""One real-cookie journey across member, school, coach and participant APIs.

No forced authentication, scheduler/payment mocks or external delivery. Only the
clock advances after booking, so completion is exercised without backdating rows.
"""
from booking.tests_policy_support import checkout_policy_acknowledgement
from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from Coach.models import CoachPayRule
from Resorts.models import PaymentAccount
from booking.models import CourseEvaluation, Reservation, ReservationGroup
from booking import tests_participants as fixtures


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CustomerJourneyTests(TestCase):
    center = '/booking/snowland/api/member-center/'
    password = 'QA-journey-password!'

    def setUp(self):
        fixtures.MemberEnrollmentTests.setUp(self)
        self.owner.set_password(self.password)
        self.owner.save(update_fields=['password'])
        self.hq_user = User.objects.create_superuser('journey-hq', 'journey-hq@example.test', self.password)
        self.coach_user = User.objects.create_user('journey-coach', 'journey-coach@example.test', self.password)
        self.coach_user.userprofile.is_coach = True
        self.coach_user.userprofile.save(update_fields=['is_coach'])
        self.coach.user = self.coach_user
        self.coach.availability_status = 'passive'
        self.coach.save(update_fields=['user', 'availability_status'])
        self.participant = User.objects.create_user('journey-participant', 'journey-participant@example.test', self.password)
        bank = PaymentAccount.objects.create(client=self.tenant, name='QA only', bank_name='QA bank',
            bank_branch='QA branch', account_number='QA-NO-REAL-ACCOUNT', account_holder='QA only')
        bank.campuses.add(self.campus)
        self.day = timezone.localdate() + timedelta(days=2)
        self.api = self.login(self.owner)
        self.hq = self.login(self.hq_user)
        self.coach_api = self.login(self.coach_user)

    def login(self, user):
        api = APIClient(enforce_csrf_checks=True)
        response = api.post('/booking/snowland/api/member-auth/',
            {'action': 'login', 'email': user.email, 'password': self.password}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(settings.SESSION_COOKIE_NAME, api.cookies)
        self.assertIn('csrftoken', api.cookies)
        api.credentials(HTTP_X_CSRFTOKEN=api.cookies['csrftoken'].value)
        return api

    def create_order(self, overrides=None, endpoint='create-reservation', expected_status=200):
        response = self.api.post(f'/booking/snowland/api/{endpoint}/', {
            **checkout_policy_acknowledgement(),
            'contact': {'name': 'QA訂課人', 'email': self.owner.email, 'phone': '0900000000',
                'messengerType': 'line', 'messengerId': 'qa-only', 'referralSource': '其他'},
            'cart': [{'coach': 'any', 'peopleCount': 2, 'abilityLevel': 'no_exp',
                'abilityLevelCounts': {'no_exp': 2}, 'equipment': False, 'equipmentOption': 'own_equipment',
                'language': 'zh', 'resort': self.resort.name, 'campusId': self.campus.pk, 'courseCategory': '單板',
                'courses': [{'date': self.day.isoformat(), 'courseTypeId': self.template.course_type_id,
                    'courseTemplateId': self.template.pk, 'courseTemplateName': self.template.name,
                    'timeSlotStart': '09:00', 'timeSlotEnd': '13:00'}]}],
            **(overrides or {}),
        }, format='json')
        self.assertEqual(response.status_code, expected_status, response.data)
        if expected_status != 200:
            return response
        return Reservation.objects.get(group_id=response.data['reservation_group_ids'][0])

    def test_both_booking_paths_reject_missing_partial_and_stale_policy_without_writes(self):
        proof = checkout_policy_acknowledgement()['policy_acceptance']
        for endpoint in ('create-reservation', 'super-schedule'):
            for invalid in (None, {**proof, 'privacy': False}, {**proof, 'terms_version': 'old'}):
                self.create_order({'policy_acceptance': invalid, 'checkout_consent_channel': 'legacy_chat'}, endpoint=endpoint, expected_status=400)
                self.assertFalse(ReservationGroup.objects.exists())
                self.assertFalse(Reservation.objects.exists())

    def test_publishing_new_policy_does_not_rewrite_existing_order_receipt(self):
        from Client.models import SiteContent
        reservation = self.create_order()
        group = reservation.group
        receipt = group.booking_contact['policy_acceptance']
        SiteContent.objects.create(client=group.client,content_type='page',location_key='policy.privacy-policy',
            title='QA新版隱私政策',body='QA新的無法律效力正文',status='active')
        group.refresh_from_db()
        self.assertEqual(group.booking_contact['policy_acceptance'], receipt)
        self.assertEqual(ReservationGroup.objects.count(), 1)
        self.assertNotEqual(checkout_policy_acknowledgement()['policy_acceptance']['privacy_version'], receipt['privacy']['version'])

    def test_jpy_checkout_locks_rate_and_bank_before_coach_acceptance(self):
        from Resorts.models import PaymentCurrencySettings
        config = PaymentCurrencySettings.objects.create(client=self.tenant, jpy_enabled=True, jpy_per_twd='4.5')
        bank = PaymentAccount.objects.create(client=self.tenant, name='QA日幣', currency='JPY',
            bank_name='QA日幣銀行', bank_branch='QA分行', account_number='QA-JPY-NOT-REAL', account_holder='QA戶名')
        reservation = self.create_order({'currency': 'JPY', 'currency_rate':'4.50000000',
            'currency_snapshot':{'currency':'JPY','rate':'0.00001','amount':1}})
        relabel = self.hq.patch(f'/api/admin/snowland/payment-accounts/{bank.pk}/',{'currency':'TWD'},format='json')
        self.assertEqual(relabel.status_code,400,relabel.data)
        member_order=next(row for row in self.api.get(self.center).data['orders'] if row['id']==reservation.group_id)
        self.assertEqual(member_order['settlement']['currency'],'JPY')
        self.assertEqual(member_order['settlement']['amount'],45000)
        self.assertNotIn('bank_info',member_order['settlement'])
        admin_order=self.hq.get(f'/api/admin/snowland/orders/{reservation.group_id}/').data['data']
        self.assertEqual(admin_order['settlement']['amount'],45000)
        self.assertNotIn('bank_info',admin_order['settlement'])
        config.jpy_per_twd='9';config.jpy_enabled=False;config.save()
        bank.account_number='QA-CHANGED';bank.save()
        accepted = self.coach_api.post(f'/api/admin/snowland/coach/confirm/{reservation.pk}/', {'action': 'accept'}, format='json')
        self.assertEqual(accepted.status_code, 200, accepted.data)
        info = self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': reservation.group_id})
        self.assertEqual(info.status_code, 200, info.data)
        self.assertEqual(info.data['total_amount'], 10000)
        self.assertEqual(info.data['settlement']['currency'], 'JPY')
        self.assertEqual(info.data['settlement']['amount'], 45000)
        self.assertEqual(info.data['settlement']['rate'], '4.50000000')
        self.assertEqual(info.data['bank_info']['bank_account_number'], 'QA-JPY-NOT-REAL')
        self.assertEqual(APIClient().get('/booking/snowland/api/payment-info/',{'reservation_group':reservation.group_id}).status_code,404)
        wrong = self.api.post('/booking/snowland/api/process-payment/', {'reservation_group_id':reservation.group_id,
            'payment_type':'bank_transfer','sender_account':'12345','currency':'TWD','expected_amount':10000}, format='json')
        self.assertEqual(wrong.status_code,409,wrong.data)
        reported = self.api.post('/booking/snowland/api/process-payment/', {'reservation_group_id':reservation.group_id,
            'payment_type':'bank_transfer','sender_account':'12345','currency':'JPY','expected_amount':45000}, format='json')
        self.assertEqual(reported.status_code,200,reported.data)
        self.assertEqual(self.api.get('/booking/snowland/api/payment-info/', {'reservation_group':reservation.group_id}).data['payment_status'],'pending')
        unsafe=self.hq.patch(f'/api/admin/snowland/orders/{reservation.group_id}/',{'action':'save','payment_status':'paid'},format='json')
        self.assertEqual(unsafe.status_code,400,unsafe.data)
        mismatch=self.hq.patch(f'/api/admin/snowland/orders/{reservation.group_id}/',{'action':'save','payment_status':'paid',
            'payment_currency':'TWD','payment_received_amount':10000},format='json')
        self.assertEqual(mismatch.status_code,400,mismatch.data)
        confirmed=self.hq.patch(f'/api/admin/snowland/orders/{reservation.group_id}/',{'action':'save','payment_status':'paid',
            'payment_currency':'JPY','payment_received_amount':45000},format='json')
        self.assertEqual(confirmed.status_code,200,confirmed.data)
        receipt=self.hq.get(f'/api/admin/snowland/orders/{reservation.group_id}/').data['data']['received_settlement']
        self.assertEqual(receipt['currency'],'JPY')
        self.assertEqual(receipt['amount'],45000)
        member_receipt=next(row for row in self.api.get(self.center).data['orders'] if row['id']==reservation.group_id)['received_settlement']
        self.assertEqual(member_receipt,receipt)
        self.assertNotIn('bank_info',member_receipt)

    def test_jpy_disabled_missing_account_and_unknown_currency_roll_back_checkout(self):
        from Resorts.models import PaymentCurrencySettings
        for endpoint in ('create-reservation','super-schedule'):
            self.create_order({'currency':'JPY'},endpoint=endpoint,expected_status=400)
            self.create_order({'currency':'USD'},endpoint=endpoint,expected_status=400)
        self.assertFalse(ReservationGroup.objects.exists())
        PaymentCurrencySettings.objects.create(client=self.tenant,jpy_enabled=True,jpy_per_twd='4.5')
        self.create_order({'currency':'JPY'},expected_status=400)
        self.assertFalse(ReservationGroup.objects.exists())

    def test_jpy_checkout_rounds_half_yen_up_once_on_order_total(self):
        from Resorts.models import PaymentCurrencySettings
        PaymentCurrencySettings.objects.create(client=self.tenant,jpy_enabled=True,jpy_per_twd='4.50005')
        PaymentAccount.objects.create(client=self.tenant,name='QA日幣',currency='JPY',bank_name='QA銀行',bank_branch='QA分行',account_number='QA-ONLY',account_holder='QA戶名')
        reservation=self.create_order({'currency':'JPY','currency_rate':'4.50005000'})
        accepted=self.coach_api.post(f'/api/admin/snowland/coach/confirm/{reservation.pk}/',{'action':'accept'},format='json')
        self.assertEqual(accepted.status_code,200,accepted.data)
        info=self.api.get('/booking/snowland/api/payment-info/',{'reservation_group':reservation.group_id})
        self.assertEqual(info.status_code,200,info.data)
        self.assertEqual(info.data['settlement']['amount'],45001)

    def test_jpy_checkout_rejects_a_stale_displayed_rate_before_creating_any_order(self):
        from Resorts.models import PaymentCurrencySettings
        PaymentCurrencySettings.objects.create(client=self.tenant,jpy_enabled=True,jpy_per_twd='4.5')
        PaymentAccount.objects.create(client=self.tenant,name='QA日幣',currency='JPY',bank_name='QA銀行',bank_branch='QA分行',account_number='QA-ONLY',account_holder='QA戶名')
        self.create_order({'currency':'JPY','currency_rate':'4.6'},expected_status=400)
        self.assertFalse(ReservationGroup.objects.exists())

    def test_completed_course_days_do_not_wait_for_coach_to_finish_evaluation(self):
        from booking.models import Booking
        reservation=self.create_order()
        reservation.status='completed';reservation.save(update_fields=['status'])
        member=reservation.members.first();member.user=self.owner;member.save(update_fields=['user'])
        first=reservation.bookings.get();first.date=timezone.localdate()-timedelta(days=2);first.save(update_fields=['date'])
        second=Booking.objects.create(reservation=reservation,date=timezone.localdate()-timedelta(days=1),start_time=time(9),end_time=time(13))
        future=Booking.objects.create(reservation=reservation,date=self.day,start_time=time(9),end_time=time(13))
        for booking in [first,second,future]:
            CourseEvaluation.objects.create(booking=booking,member=member,coach=self.coach,
                completed_at=timezone.now() if booking==first else None)
        response=self.api.get(self.center)
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['journey']['completed_course_days'],2)
        self.assertEqual(len(response.data['learning_records']),2)

    def test_same_order_real_sessions_payment_binding_completion_feedback_and_payroll(self):
        reservation = self.create_order()
        group = reservation.group
        self.assertTrue(group.booking_contact['policy_acceptance']['terms']['body'])
        self.assertTrue(group.booking_contact['policy_acceptance']['privacy']['version'])
        self.assertEqual(reservation.status, 'pending_coach_confirmation')
        self.assertEqual(reservation.preferred_coach_id, self.coach.pk)
        self.assertEqual(reservation.course_fee, 10000)
        pay_url = '/booking/snowland/api/process-payment/'
        pay_body = {'reservation_group_id': group.pk, 'payment_type': 'bank_transfer', 'sender_account': '12345'}
        self.assertEqual(self.api.post(pay_url, pay_body, format='json').status_code, 400)
        accepted = self.coach_api.post(f'/api/admin/snowland/coach/confirm/{reservation.pk}/', {'action': 'accept'}, format='json')
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(self.api.post(pay_url, {**pay_body, 'sender_account': '１２３４５'}, format='json').status_code, 400)
        self.assertEqual(self.api.post(pay_url, pay_body, format='json').status_code, 200)
        self.assertEqual(group.payments.get().status, 'pending')
        paid = self.hq.patch(f'/api/admin/snowland/orders/{group.pk}/', {'action': 'save', 'payment_status': 'paid'}, format='json')
        self.assertEqual(paid.status_code, 200, paid.data)
        self.assertEqual(self.api.get(self.center).data['orders'][0]['payment_status'], 'paid')
        self.assertEqual(self.api.post(pay_url, pay_body, format='json').status_code, 400)

        learner = reservation.members.order_by('pk').last()
        invited = self.api.post(self.center, {'action': 'invite_participant', 'member_id': learner.pk}, format='json')
        self.assertEqual(invited.status_code, 201, invited.data)
        participant_api = self.login(self.participant)
        invitation_url = f"/booking/snowland/api/participant-invitations/{invited.data['token']}/"
        bound = participant_api.post(invitation_url, {'confirmed': True, 'role': 'self'}, format='json')
        self.assertEqual(bound.status_code, 200, bound.data)
        saved = participant_api.post(self.center, {'action': 'update_pre_course_form', 'member_id': learner.pk,
            'age_range': '25-35y', 'insurance_data': {'full_name': 'QA同行學員', 'birth_date': '1995-01-01',
                'id_number': 'QA-NOT-A-REAL-ID', 'phone': '0900000001', 'waiver_signer_role': 'self'}}, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertNotIn(learner.pk, [row['id'] for row in self.api.get(self.center).data['pre_course_forms']])
        own_view = participant_api.get(self.center).data
        self.assertEqual(own_view['orders'], [])
        self.assertEqual([row['id'] for row in own_view['pre_course_forms']], [learner.pk])
        self.assertEqual(self.api.post(self.center, {'action': 'update_pre_course_form', 'member_id': learner.pk,
            'insurance_data': {'full_name': 'cannot override'}}, format='json').status_code, 404)

        finish = timezone.make_aware(datetime.combine(self.day + timedelta(days=1), time(14)))
        with patch('django.utils.timezone.localtime', return_value=finish), patch('django.utils.timezone.localdate', return_value=finish.date()):
            completed = self.hq.post(f'/api/admin/snowland/orders/{group.pk}/complete-course/', {'reservation_id': reservation.pk}, format='json')
            self.assertEqual(completed.status_code, 200, completed.data)
            self.assertEqual(CourseEvaluation.objects.filter(booking__reservation=reservation).count(), 2)
            evaluation = CourseEvaluation.objects.get(member=learner)
            marked = self.coach_api.patch(f'/api/admin/snowland/coach/evaluations/{evaluation.pk}/',
                {'coach_notes': 'QA可安全煞車', 'learning_progress': {'next': 'QA連續轉彎'}, 'completed_at': finish.isoformat()}, format='json')
            self.assertEqual(marked.status_code, 200, marked.data)
            records = participant_api.get(self.center).data['learning_records']
            self.assertEqual([row['id'] for row in records], [evaluation.pk])
            self.assertEqual(records[0]['coach_notes'], 'QA可安全煞車')
            for invalid_rating in [True, False, 2.5, 5.0, '５', '2.0', '6', {}, []]:
                invalid = participant_api.post(self.center, {'action': 'submit_satisfaction',
                    'evaluation_id': evaluation.pk, 'rating': invalid_rating}, format='json')
                self.assertEqual(invalid.status_code, 400, (invalid_rating, invalid.data))
                evaluation.refresh_from_db()
                self.assertNotIn('satisfaction_rating', evaluation.self_assessment)
            feedback = participant_api.post(self.center, {'action': 'submit_satisfaction', 'evaluation_id': evaluation.pk,
                'rating': 5, 'feedback': 'QA清楚好理解'}, format='json')
            self.assertEqual(feedback.status_code, 200, feedback.data)
            self.assertEqual(self.api.post(self.center, {'action': 'submit_satisfaction', 'evaluation_id': evaluation.pk,
                'rating': 1}, format='json').status_code, 404)
            self.assertEqual(self.coach_api.get(f'/api/admin/snowland/coach/evaluations/{evaluation.pk}/').data['self_assessment']['satisfaction_rating'], 5)
            CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
            payroll = self.hq.post('/api/admin/snowland/payroll-statements/calculate/', {'coach': self.coach.pk,
                'campus': self.campus.pk, 'period_start': self.day.isoformat(), 'period_end': self.day.isoformat()}, format='json')
            self.assertEqual(payroll.status_code, 200, payroll.data)
            self.assertEqual(payroll.data['data']['course_pay'], 4000)
            self.assertEqual(group.payments.get().status, 'paid')
            self.assertEqual(ReservationGroup.objects.count(), 1)
