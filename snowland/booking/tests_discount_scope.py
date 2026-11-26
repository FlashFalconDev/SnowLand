from copy import deepcopy
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from Client.models import Client, ModuleInfo, ModuleSetting
from Coursekit.models import CourseCategory, CoursePricing, CourseTemplate, CourseType, DiscountCode
from Resorts.models import EquipmentAssistanceTimeSlot, EquipmentPricingTier, PaymentAccount, PaymentCurrencySettings, ResortFee
from booking import tests_pricing_modes
from booking.models import ReservationGroup


class CheckoutDiscountScopeTests(TestCase):
    def setUp(self):
        tests_pricing_modes.PricingModeApiTests.setUp(self)
        self.coach, self.payload = tests_pricing_modes.PricingModeApiTests.selectable_coach_fixture(self)
        self.resort.auto_scheduling_enabled = False
        self.resort.save(update_fields=['auto_scheduling_enabled'])
        self.ski = self.payload['cart'][0]
        self.ski['courses'][0]['date'] = str(timezone.localdate() + timedelta(days=20))
        self.ski['language'] = 'en'
        self.coach.languages = ['zh', 'en']
        self.coach.save(update_fields=['languages'])
        ResortFee.objects.create(resort=self.resort, fee_type='coach_general', price=1000)
        ResortFee.objects.create(resort=self.resort, fee_type='language_en', price=500)
        EquipmentPricingTier.objects.create(resort=self.resort, min_people=1, max_people=3, price=1200)
        slot = EquipmentAssistanceTimeSlot.objects.create(resort=self.resort, label='測試裝備協助')
        self.ski.update(equipment=True, equipmentOption='extra_time_help', equipmentAssistanceTimeSlotId=slot.pk)

        photo_category = CourseCategory.objects.create(
            client=self.client_record, name='雪地攝影', service_type=CourseCategory.SERVICE_TYPE_PHOTO,
        )
        photo_type = CourseType.objects.create(category=photo_category, name='雪地旅拍')
        photo_template = CourseTemplate.objects.create(
            course_type=photo_type, name='攝影四小時', duration_hours=4, max_capacity=6,
        )
        photo_pricing = CoursePricing.objects.create(
            resort=self.resort, base_price_off_peak=4000, peak_season_surcharge=0,
            additional_person_fee=0, max_capacity=6,
        )
        photo_pricing.templates.add(photo_template)
        self.photo = {
            **self.ski, 'coach': 'any', 'language': 'zh', 'equipment': False,
            'equipmentOption': 'own_equipment', 'courseCategory': photo_category.name,
            'courses': [{
                **self.ski['courses'][0], 'courseTypeId': photo_type.pk,
                'courseTemplateId': photo_template.pk,
            }],
        }

    def configure(self, **settings):
        module, _ = ModuleInfo.objects.get_or_create(module_sid='booking', defaults={'module_name': '預約'})
        ModuleSetting.objects.update_or_create(
            client=self.client_record, module=module, defaults={'settings': settings},
        )

    def rule(self, code, **overrides):
        return DiscountCode.objects.create(**{
            'client': self.client_record, 'code': code, 'discount_value': 10,
            'discount_type': DiscountCode.DISCOUNT_TYPE_PERCENT,
            'apply_scope': DiscountCode.APPLY_SCOPE_SKI, 'can_combine': True,
            **overrides,
        })

    def bundle(self, **overrides):
        return self.rule('PHOTO-BUNDLE', **{
            'apply_scope': DiscountCode.APPLY_SCOPE_BUNDLE,
            'discount_type': DiscountCode.DISCOUNT_TYPE_AMOUNT,
            'discount_value': 200, 'amount_apply_mode': DiscountCode.AMOUNT_APPLY_MODE_HOUR,
            'is_auto_apply': True, **overrides,
        })

    def preview(self, *items, code=''):
        response = self.api.post('/booking/snowland/api/discount-preview/', {
            **self.payload, 'cart': items, 'discount_code': code,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def submit(self, endpoint, *items, code):
        response = self.api.post(f'/booking/snowland/api/{endpoint}/', {
            **self.payload, 'cart': items, 'discount_code': code,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return ReservationGroup.objects.get(pk=response.data['reservation_group_ids'][0])

    def test_ski_screenshot_amount_matches_preview_and_both_checkout_paths(self):
        self.rule('SL2627EB')
        preview = self.preview(self.ski, code='sl2627eb')
        self.assertEqual((preview['subtotal'], preview['discount_total'], preview['total']), (12200, 1000, 11200))
        group = self.submit('create-reservation', self.ski, code='SL2627EB')
        reservation = group.reservations.get()
        self.assertEqual(
            (reservation.course_fee, reservation.coach_fee, reservation.equipment_rental_fee, reservation.language_fee),
            (10000, 1000, 1200, 0),
        )
        self.assertEqual((reservation.discount_amount, reservation.payment_amount), (1000, 11200))

        # The advanced fallback removes the specified coach and its fee.
        without_coach = self.preview({**self.ski, 'coach': 'any'}, code='SL2627EB')
        advanced = self.submit('super-schedule', self.ski, code='SL2627EB').reservations.get()
        self.assertEqual((without_coach['discount_total'], without_coach['total']), (1000, 10200))
        self.assertEqual((advanced.coach_fee, advanced.discount_amount, advanced.payment_amount), (0, 1000, 10200))

    def test_jpy_checkout_converts_and_rounds_the_final_course_discount_total(self):
        self.rule('SL2627EB')
        PaymentCurrencySettings.objects.create(client=self.client_record, jpy_enabled=True, jpy_per_twd='4.50005')
        PaymentAccount.objects.create(
            client=self.client_record, name='測試日幣', currency='JPY', bank_name='測試銀行',
            bank_branch='測試分行', account_number='QA-JPY', account_holder='測試戶名',
        )
        self.payload.update(currency='JPY', currency_rate='4.50005000')
        group = self.submit('create-reservation', self.ski, code='SL2627EB')
        snapshot = group.currency_snapshot
        self.assertEqual((snapshot['base_amount'], snapshot['currency'], snapshot['amount']), (11200, 'JPY', 50401))

    def test_photo_bundle_requires_an_applied_allowlisted_course_discount(self):
        self.bundle()
        self.rule('SL2627EB')
        self.rule('COURSE-OFFER', is_active=False, is_auto_apply=True)
        self.configure(discount_photo_bundle_qualifying_course_codes=[' course-offer '])
        for items, code, expected in (
            ((self.photo,), '', [0]),
            ((self.ski, self.photo), '', [0, 0]),
            ((self.ski, self.photo), 'SL2627EB', [1000, 0]),
        ):
            with self.subTest(code=code, items=len(items)):
                self.assertEqual(self.preview(*items, code=code)['item_discount_amounts'], expected)

        DiscountCode.objects.filter(code='COURSE-OFFER').update(is_active=True)
        both = self.preview(self.ski, self.photo, code='SL2627EB')
        self.assertEqual(both['item_discount_amounts'], [1900, 800])
        self.assertEqual(
            [(rule['code'], rule['amount']) for rule in both['applied_discounts']],
            [('SL2627EB', 1000), ('COURSE-OFFER', 900), ('PHOTO-BUNDLE', 800)],
        )
        self.assertEqual(self.preview(self.ski, self.photo)['item_discount_amounts'], [1000, 800])

    def test_manual_bundle_supports_auto_course_offer_and_rejects_a_zero_hit(self):
        self.bundle(is_auto_apply=False)
        self.rule('COURSE-OFFER', is_auto_apply=True)
        self.configure(discount_photo_bundle_qualifying_course_codes=['COURSE-OFFER'])
        preview = self.preview(self.ski, self.photo, code='PHOTO-BUNDLE')
        self.assertEqual(preview['item_discount_amounts'], [1000, 800])
        self.assertFalse(preview['discount_code_error'])

        DiscountCode.objects.filter(code='COURSE-OFFER').update(discount_value=0)
        preview = self.preview(self.ski, self.photo, code='PHOTO-BUNDLE')
        self.assertEqual(preview['item_discount_amounts'], [0, 0])
        self.assertIn('合格課程折扣', preview['discount_code_error'])

    def test_whole_order_scope_still_discounts_addons_and_photography_without_unlocking_bundle(self):
        self.rule('ORDER10', apply_scope=DiscountCode.APPLY_SCOPE_ALL)
        self.bundle()
        self.configure(discount_photo_bundle_qualifying_course_codes=['ORDER10'])
        preview = self.preview(self.ski, self.photo, code='ORDER10')
        self.assertEqual(preview['item_discount_amounts'], [1220, 400])
        self.assertEqual([rule['code'] for rule in preview['applied_discounts']], ['ORDER10'])

    def test_qualified_bundle_keeps_its_priority_over_a_later_whole_order_rule(self):
        self.rule('COURSE-OFFER')
        self.bundle()
        self.rule('ORDER10', apply_scope=DiscountCode.APPLY_SCOPE_ALL, is_auto_apply=True)
        self.configure(discount_photo_bundle_qualifying_course_codes=['COURSE-OFFER'])
        preview = self.preview(self.ski, self.photo, code='COURSE-OFFER')
        self.assertEqual(preview['item_discount_amounts'], [2120, 1120])
        self.assertEqual(
            [rule['code'] for rule in preview['applied_discounts']], ['COURSE-OFFER', 'PHOTO-BUNDLE', 'ORDER10'],
        )

    def test_course_discount_uses_course_basis_but_cannot_exceed_whole_order_balance(self):
        self.rule('ORDER99', apply_scope=DiscountCode.APPLY_SCOPE_ALL, discount_value=99)
        self.rule('COURSE-OFFER', is_auto_apply=True)
        preview = self.preview(self.ski, code='ORDER99')
        self.assertEqual(
            [(rule['code'], rule['amount']) for rule in preview['applied_discounts']],
            [('ORDER99', 12078), ('COURSE-OFFER', 122)],
        )
        self.assertEqual(preview['total'], 0)

    def test_fixed_amount_caps_at_net_course_fee_and_cannot_unlock_bundle_from_zero_balance(self):
        self.bundle()
        self.rule('SL2627EB')
        self.rule(
            'FIXED', is_auto_apply=True, discount_type=DiscountCode.DISCOUNT_TYPE_AMOUNT,
            discount_value=3000, amount_apply_mode=DiscountCode.AMOUNT_APPLY_MODE_HOUR,
        )
        self.rule('COURSE-OFFER', is_auto_apply=True)
        self.configure(discount_photo_bundle_qualifying_course_codes=['COURSE-OFFER'])
        preview = self.preview(self.ski, self.photo, code='SL2627EB')
        self.assertEqual(preview['item_discount_amounts'], [10000, 0])
        self.assertEqual(preview['total'], 6200)
        self.assertEqual(
            [(rule['code'], rule['amount']) for rule in preview['applied_discounts']],
            [('SL2627EB', 1000), ('FIXED', 9000)],
        )

    def test_ski_scope_uses_catalog_service_and_rounds_percent_down(self):
        self.private_template.pricing_options.update(base_price_off_peak=10009)
        self.rule('SL2627EB')
        ski = {**self.ski, 'serviceType': 'photo', 'courseCategory': '攝影'}
        preview = self.preview(ski, self.photo, code='SL2627EB')
        self.assertEqual(preview['item_discount_amounts'], [1000, 0])
        self.assertEqual(preview['total'], 15209)

    def test_legacy_basis_is_tenant_specific_and_invalid_values_use_lily_defaults(self):
        self.rule('SL2627EB')
        other = Client.objects.create(name='其他學校', internal_code='other-school')
        module = ModuleInfo.objects.create(module_sid='booking', module_name='預約')
        legacy = {'discount_course_scope_basis': 'legacy_group_subtotal'}
        ModuleSetting.objects.create(client=other, module=module, settings=legacy)
        self.assertEqual(self.preview(self.ski, code='SL2627EB')['discount_total'], 1000)

        self.configure(**legacy)
        preview = self.preview(self.ski, code='SL2627EB')
        self.assertEqual((preview['discount_total'], preview['total']), (1220, 10980))
        self.configure(discount_course_scope_basis='typo')
        self.assertEqual(self.preview(self.ski, code='SL2627EB')['discount_total'], 1000)

    def test_advanced_split_preserves_discount_total_for_differently_priced_days(self):
        template = CourseTemplate.objects.create(
            course_type=self.private_template.course_type, name='較低價模板', duration_hours=4, max_capacity=6,
        )
        pricing = CoursePricing.objects.create(
            resort=self.resort, base_price_off_peak=1000, peak_season_surcharge=0,
            additional_person_fee=0, max_capacity=6,
        )
        pricing.templates.add(template)
        ski = deepcopy(self.ski)
        ski.update(coach='any', language='zh')
        second_day = str(timezone.localdate() + timedelta(days=21))
        ski['courses'] = [
            {**ski['courses'][0], 'courseTemplateId': template.pk},
            {**ski['courses'][0], 'date': second_day},
        ]
        self.rule('FIXED', discount_type=DiscountCode.DISCOUNT_TYPE_AMOUNT, discount_value=8000)
        preview = self.preview(ski, code='FIXED')
        self.assertEqual((preview['discount_total'], preview['total']), (8000, 4200))
        ordinary = self.submit('create-reservation', ski, code='FIXED').reservations.get()
        self.assertEqual((ordinary.discount_amount, ordinary.payment_amount), (8000, 4200))
        group = self.submit('super-schedule', ski, code='FIXED')
        first, second = group.reservations.order_by('pk')
        self.assertEqual((first.discount_amount, second.discount_amount), (727, 7273))
        self.assertEqual(first.payment_amount + second.payment_amount, 4200)
