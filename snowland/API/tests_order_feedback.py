import csv
import io
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client as BrowserClient, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Client.models import Client
from Coach.payroll import calculate_payroll_statement
from Coursekit.models import CourseCategory
from Resorts.models import PaymentAccount, Resorts
from booking.models import CancellationRequest, NotificationDelivery, Payment, ReservationGroup


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OrderFeedbackTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.admin = APIClient()
        self.admin.force_authenticate(User.objects.create_superuser('order-feedback', 'admin@example.test'))
        self.admin_base = '/api/admin/snowland'
        self.member = APIClient()
        self.member.force_authenticate(self.user)

    def set_management_email(self):
        url = self.admin_base + '/payment-settings/'
        self.assertEqual(self.admin.put(url, {'order_management_email': 'invalid'}, format='json').status_code, 400)
        response = self.admin.put(url, {'order_management_email': 'orders@example.test'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['order_management_email'], 'orders@example.test')

    def test_management_email_change_requires_csrf(self):
        browser = BrowserClient(enforce_csrf_checks=True)
        browser.force_login(User.objects.get(username='order-feedback'))
        url = self.admin_base + '/payment-settings/'
        payload = {'order_management_email': 'orders@example.test'}
        self.assertEqual(browser.put(url, payload, content_type='application/json').status_code, 403)
        self.assertEqual(browser.get(url).status_code, 200)
        self.assertEqual(browser.put(url, payload, content_type='application/json',
                                     HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value).status_code, 200)

    def test_browser_transfer_requires_csrf_and_only_one_staff_receipt_on_retry(self):
        self.set_management_email()
        PaymentAccount.objects.create(client=self.client_tenant, name='QA', bank_name='QA',
                                      bank_branch='QA', account_number='QA', account_holder='QA')
        browser = BrowserClient(enforce_csrf_checks=True)
        browser.force_login(self.user)
        base = '/booking/snowland/api'
        self.assertEqual(browser.get(f'{base}/payment-info/', {'reservation_group': self.group.pk}).status_code, 200)
        url = f'{base}/process-payment/'
        body = {'reservation_group_id': self.group.pk, 'payment_type': 'bank_transfer', 'sender_account': '00000'}
        self.assertEqual(browser.post(url, body, content_type='application/json').status_code, 403)
        self.assertFalse(self.group.payments.exists())
        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(2):
                result = browser.post(url, body, content_type='application/json', HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
                self.assertEqual(result.status_code, 200, result.content)
        payment = self.group.payments.get()
        self.assertEqual((payment.status, payment.bank_account), ('pending', '00000'))
        self.assertEqual([message.to for message in mail.outbox], [['orders@example.test']])
        self.assertEqual(mail.outbox[0].body, f'訂單：{self.group.order_number}\n請到後台訂單管理核對匯款。')
        self.assertEqual(NotificationDelivery.objects.get(group=self.group).status, 'sent')

    def test_cancellation_guards_past_lessons_and_notifies_once_for_valid_request(self):
        self.set_management_email()
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='credit_card')
        url = f'/booking/snowland/api/member-cancellations/{self.group.pk}/'
        first = self.booking_1.date
        self.booking_1.date = timezone.localdate() - timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
        self.assertFalse(self.member.get(url).data['can_request'])
        self.assertEqual(self.member.post(url, {'reason': 'schedule'}, format='json').status_code, 400)
        self.assertFalse(self.group.cancellation_requests.exists())
        self.assertFalse(NotificationDelivery.objects.filter(group=self.group).exists())
        self.booking_1.date = first
        self.booking_1.save(update_fields=['date'])
        preview = self.member.get(url).data
        self.assertEqual((preview['can_request'], preview['refund_percent'], preview['handling_fee_amount'], preview['refund_amount']),
                         (True, 100, 500, 9500))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.member.post(url, {'reason': 'schedule'}, format='json').status_code, 201)
            self.assertEqual(self.member.post(url, {'reason': 'schedule'}, format='json').status_code, 400)
        self.assertEqual([message.to for message in mail.outbox], [['orders@example.test']])
        order = self.admin.get(f'{self.admin_base}/orders/{self.group.pk}/').data['data']
        self.assertEqual(order['cancellation']['status'], 'requested')

    def test_payroll_uses_old_and_new_rates_in_one_period_and_locks_confirmed_snapshot(self):
        rules = self.admin_base + '/coach-pay-rules/'
        common = {'coach': self.coach.pk, 'discipline': 'snowboard', 'supervisor_allowance': 100}
        for body in [
            {**common, 'certification_level': '1', 'hourly_rate': 1000},
            {**common, 'certification_level': '2', 'hourly_rate': 1200, 'effective_from': self.booking_2.date.isoformat()},
        ]:
            result = self.admin.post(rules, body, format='json')
            self.assertEqual(result.status_code, 201, result.data)
        period = dict(coach=self.coach, campus=self.campus, period_start=self.booking_1.date, period_end=self.booking_2.date)
        statement = calculate_payroll_statement(**period)
        lines = statement.lines.filter(line_type='course').order_by('booking__date')
        self.assertEqual(list(lines.values_list('unit_amount', flat=True)), [1000, 1200])
        self.assertEqual(statement.lines.filter(line_type='allowance').count(), 1)
        statement.status = 'confirmed'
        statement.save(update_fields=['status'])
        with self.assertRaises(ValueError):
            calculate_payroll_statement(**period)
        self.assertEqual(list(lines.values_list('unit_amount', flat=True)), [1000, 1200])

    def test_admin_cannot_create_or_approve_past_cancellation_but_can_reject_it(self):
        self.booking_1.date = timezone.localdate() - timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
        orders_url = f'{self.admin_base}/orders/{self.group.pk}'
        preview = self.admin.get(f'{orders_url}/refund-preview/')
        self.assertLess(preview.data['data']['days_before'], 0)
        response = self.admin.post(f'{orders_url}/cancel/', {'reason': 'schedule'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(self.group.cancellation_requests.exists())

        cancellation = CancellationRequest.objects.create(group=self.group, reason='schedule', status='requested')
        process_url = f'{self.admin_base}/cancellations/{cancellation.pk}/process/'
        response = self.admin.post(process_url, {'status': 'approved'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        cancellation.refresh_from_db()
        self.assertEqual(cancellation.status, 'requested')
        response = self.admin.post(process_url, {'status': 'rejected'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_order_export_dates_sort_and_tenant_scope(self):
        url = self.admin_base + '/orders/export/'
        today = timezone.localdate().isoformat()
        other = Client.objects.create(name='Other tenant', internal_code='elsewhere')
        ReservationGroup.objects.create(client=other, order_number='FOREIGN-ONLY')
        self.group.order_number = '=SUM(1,2)'
        self.group.save(update_fields=['order_number'])
        created = self.admin.get(url, {'date_basis': 'created', 'start': today, 'end': today, 'sort': 'desc'})
        self.assertEqual(created.status_code, 200)
        self.assertNotIn('FOREIGN-ONLY', created.content.decode('utf-8-sig'))
        rows = list(csv.reader(io.StringIO(created.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][0], "'=SUM(1,2)")
        self.assertEqual(rows[1][3:6], [self.booking_2.date.isoformat(), '09:00', '11:00'])
        day = self.booking_1.date.isoformat()
        lesson = self.admin.get(url, {'date_basis': 'lesson', 'start': day, 'end': day})
        rows = list(csv.reader(io.StringIO(lesson.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][3], day)
        self.assertEqual(self.member.get(url, {'start': day, 'end': day}).status_code, 403)
        self.assertEqual(self.admin.get(url, {'start': day, 'end': today}).status_code, 400)

    def test_admin_can_order_booking_resorts_and_course_categories(self):
        second = Resorts.objects.create(client=self.client_tenant, name='second', display_name='Second')
        self.campus.resorts.add(second)
        result = self.admin.patch(f'{self.admin_base}/resorts/{self.resort.pk}/', {'display_order': 20}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual([row['name'] for row in self.member.get('/booking/snowland/api/resorts/').data],
                         [second.name, self.resort.name])
        first = CourseCategory.objects.create(client=self.client_tenant, name='Another category')
        result = self.admin.patch(f'{self.admin_base}/course-categories/{self.category.pk}/', {'display_order': 20}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual([row['id'] for row in self.member.get('/booking/snowland/api/course-categories/').data],
                         [first.pk, self.category.pk])
