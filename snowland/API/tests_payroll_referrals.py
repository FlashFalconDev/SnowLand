from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Coach.models import Coach, CoachPayRule, PayrollStatement
from Coach.payroll import calculate_payroll_statement


class CoachReferralPayrollTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.rule=CoachPayRule.objects.create(coach=self.coach,discipline='snowboard',hourly_rate=1000,
            referral_percent=Decimal('10'),specified_fee=100,supervisor_allowance=200)
        teacher_user=User.objects.create_user('other-teacher')
        self.teacher=Coach.objects.create(client=self.client_tenant,user=teacher_user,name='授課教練')
        self.teacher.campuses.add(self.campus)
        CoachPayRule.objects.create(coach=self.teacher,discipline='snowboard',hourly_rate=2000,referral_percent=20)
        self.reservation.preferred_coach=self.teacher
        self.reservation.save(update_fields=['preferred_coach'])

    def calculate(self,coach=None):
        return calculate_payroll_statement(coach=coach or self.coach,campus=self.campus,
            period_start=self.booking_1.date,period_end=self.booking_2.date)

    def test_referrer_is_paid_even_when_someone_else_teaches(self):
        statement=self.calculate()
        self.assertEqual(statement.referral_commission,900)
        self.assertEqual(statement.total_amount,900)
        self.assertEqual(statement.course_pay,0)
        self.assertEqual(statement.specified_fees,0)
        self.assertEqual(statement.supervisor_allowance,0)
        line=statement.lines.get(line_type='referral')
        self.assertEqual(line.quantity,Decimal('10'))
        self.assertEqual(line.unit_amount,9000)
        teacher=self.calculate(self.teacher)
        self.assertEqual(teacher.course_pay,8000)
        self.assertEqual(teacher.referral_commission,0)

    def test_teaching_own_referral_does_not_duplicate_commission(self):
        self.reservation.preferred_coach=self.coach;self.reservation.save()
        statement=self.calculate()
        self.assertEqual(statement.course_pay,4000)
        self.assertEqual(statement.referral_commission,900)
        self.assertEqual(statement.lines.filter(line_type='referral').count(),1)
        self.assertEqual(self.calculate().referral_commission,900)

    def test_unfinished_or_other_campus_referrals_are_not_paid(self):
        self.reservation.status='auto_assigned';self.reservation.save()
        self.assertEqual(self.calculate().referral_commission,0)
        self.reservation.status='completed';self.reservation.save()
        from Resorts.models import Campus
        other=Campus.objects.create(client=self.client_tenant,name='其他校區',code='other')
        self.group.campus=other;self.group.save()
        self.assertEqual(self.calculate().referral_commission,0)

    def test_no_linked_user_never_matches_unattributed_orders(self):
        self.coach.user=None;self.coach.save()
        self.group.referral_user=None;self.group.save()
        self.reservation.preferred_coach=self.coach;self.reservation.save()
        self.assertEqual(self.calculate().referral_commission,0)

    def test_referral_requires_own_pay_rule_and_rolls_back_new_statement(self):
        self.rule.delete()
        with self.assertRaisesMessage(ValueError,'介紹費'):
            self.calculate()
        self.assertFalse(PayrollStatement.objects.filter(coach=self.coach).exists())

    def test_zero_percent_is_valid_and_uses_referrers_setting(self):
        self.rule.referral_percent=0;self.rule.save()
        self.assertEqual(self.calculate().referral_commission,0)
        self.rule.referral_percent=Decimal('7.50');self.rule.save()
        self.assertEqual(self.calculate().referral_commission,675)

    def test_course_specific_referrer_rule_wins_over_own_default(self):
        CoachPayRule.objects.create(coach=self.coach,course_type=self.course_type,discipline='snowboard',
            hourly_rate=0,referral_percent=Decimal('12.50'))
        self.assertEqual(self.calculate().referral_commission,1125)

    def test_missing_rule_does_not_erase_existing_draft_lines(self):
        statement=self.calculate()
        previous=list(statement.lines.values_list('pk','total_amount'))
        self.rule.is_active=False;self.rule.save()
        with self.assertRaisesMessage(ValueError,'介紹費'):
            self.calculate()
        statement.refresh_from_db()
        self.assertEqual(statement.referral_commission,900)
        self.assertEqual(list(statement.lines.values_list('pk','total_amount')),previous)

    def test_other_tenant_referral_cannot_enter_statement(self):
        from Client.models import Client
        other=Client.objects.create(name='Other',internal_code='other')
        self.group.client=other;self.group.save()
        self.assertEqual(self.calculate().referral_commission,0)

    def test_headquarters_calculate_endpoint_includes_non_teaching_referral(self):
        admin=User.objects.create_superuser('referral-hq','qa-referral@example.test','test-password')
        api=APIClient();api.force_authenticate(admin)
        result=api.post('/api/admin/snowland/payroll-statements/calculate/',{
            'coach':self.coach.pk,'campus':self.campus.pk,
            'period_start':str(self.booking_1.date),'period_end':str(self.booking_2.date),
        },format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['data']['referral_commission'],900)
        self.assertEqual(result.data['data']['course_pay'],0)
