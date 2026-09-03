from django.db import models

class Resorts(models.Model):
    client = models.ForeignKey(
        'Client.Client',
        on_delete=models.CASCADE,
        related_name='resorts',
        verbose_name='所屬客戶',
        help_text='此雪場歸屬於哪個客戶',
        null=True,  # 暫時允許為 null 以便進行 migration
        blank=True
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="內部使用的英文或拼音名稱，例如 'Tomamu'"
    )
    display_name = models.CharField(
        max_length=100,
        verbose_name='顯示名稱',
        help_text="顯示給使用者看的名稱，例如 '星野 Tomamu'"
    )
    auto_scheduling_enabled = models.BooleanField(
        default=True,
        verbose_name='啟用自動排課',
        help_text='若勾選，此雪場的預約將會進入自動排課流程。'
    )

    def __str__(self):
        return self.display_name

    class Meta:
        verbose_name = '雪場'
        verbose_name_plural = '雪場'


class Campus(models.Model):
    """營運校區。校區與雪場是多對多，同一雪場可由多個校區使用。"""
    client = models.ForeignKey(
        'Client.Client',
        on_delete=models.CASCADE,
        related_name='campuses',
        verbose_name='所屬客戶',
    )
    name = models.CharField(max_length=100, verbose_name='校區名稱')
    code = models.SlugField(max_length=50, verbose_name='校區代碼')
    resorts = models.ManyToManyField(
        Resorts,
        blank=True,
        related_name='campuses',
        verbose_name='可使用雪場',
    )
    description = models.TextField(blank=True, default='', verbose_name='備註')
    is_active = models.BooleanField(default=True, verbose_name='是否啟用')
    display_order = models.IntegerField(default=0, verbose_name='顯示順序')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '校區'
        verbose_name_plural = '校區'
        ordering = ['display_order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['client', 'code'], name='unique_campus_code_per_client'),
        ]

    def __str__(self):
        return self.name


class PaymentAccount(models.Model):
    """校區／雪場可用的收款帳戶。"""
    client = models.ForeignKey(
        'Client.Client',
        on_delete=models.CASCADE,
        related_name='payment_accounts',
        verbose_name='所屬客戶',
    )
    name = models.CharField(max_length=100, verbose_name='帳戶名稱')
    bank_name = models.CharField(max_length=100, blank=True, default='', verbose_name='銀行名稱')
    bank_branch = models.CharField(max_length=100, blank=True, default='', verbose_name='分行')
    account_number = models.CharField(max_length=80, blank=True, default='', verbose_name='帳號')
    account_holder = models.CharField(max_length=100, blank=True, default='', verbose_name='戶名')
    overseas_details = models.TextField(blank=True, default='', verbose_name='海外匯款資料')
    campuses = models.ManyToManyField(Campus, blank=True, related_name='payment_accounts', verbose_name='適用校區')
    resorts = models.ManyToManyField(Resorts, blank=True, related_name='payment_accounts', verbose_name='適用雪場')
    is_default = models.BooleanField(default=False, verbose_name='預設帳戶')
    is_active = models.BooleanField(default=True, verbose_name='是否啟用')
    display_order = models.IntegerField(default=0, verbose_name='顯示順序')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '收款帳戶'
        verbose_name_plural = '收款帳戶'
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name


def default_cancellation_rules():
    return [
        {'days_before': 30, 'refund_percent': 100},
        {'days_before': 14, 'refund_percent': 80},
        {'days_before': 7, 'refund_percent': 50},
        {'days_before': 0, 'refund_percent': 0},
    ]


class OperatingPolicy(models.Model):
    """簡報未定義細節的營運規則，以可調整設定保留。"""
    client = models.ForeignKey(
        'Client.Client', on_delete=models.CASCADE, related_name='operating_policies', verbose_name='所屬客戶'
    )
    campus = models.OneToOneField(
        Campus, on_delete=models.CASCADE, related_name='operating_policy', null=True, blank=True, verbose_name='校區'
    )
    unpaid_hold_days = models.PositiveSmallIntegerField(default=3, verbose_name='未付款保留天數')
    provisional_extra_groups = models.PositiveSmallIntegerField(default=3, verbose_name='未付款容許加排組數')
    cancellation_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5, verbose_name='取消手續費百分比')
    cancellation_rules = models.JSONField(default=default_cancellation_rules, blank=True, verbose_name='退費階梯')
    leave_advance_days = models.PositiveSmallIntegerField(default=3, verbose_name='請假需提前天數')
    leave_daily_coach_limit = models.PositiveSmallIntegerField(default=2, verbose_name='每日請假人數上限')
    leave_max_consecutive_days = models.PositiveSmallIntegerField(default=2, verbose_name='連續請假天數上限')
    course_reminder_days = models.JSONField(default=list, blank=True, verbose_name='課前提醒天數')
    settings = models.JSONField(default=dict, blank=True, verbose_name='其他營運設定')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '營運規則'
        verbose_name_plural = '營運規則'

    def __str__(self):
        return f"{self.campus.name if self.campus else '全公司預設'}營運規則"

class ResortFee(models.Model):
    """雪場費用設定模型"""
    FEE_TYPE_CHOICES = [
        ('coach_director', '校長/總監指定費用'),
        ('coach_lv2', '二級教練指定費用'),
        ('coach_general', '一般教練指定費用'),
        ('language_zh', '中文授課費用'),
        ('language_en', '英文授課費用'),
        ('language_yue', '粵語授課費用'),
        ('equipment_1to3', '1-3人裝備租借費用'),
        ('equipment_4to6', '4-6人裝備租借費用'),
    ]
    
    resort = models.ForeignKey(
        Resorts, 
        on_delete=models.CASCADE, 
        related_name='fees',
        verbose_name='所屬雪場'
    )
    fee_type = models.CharField(
        max_length=20,
        choices=FEE_TYPE_CHOICES,
        verbose_name='費用類型'
    )
    price = models.PositiveIntegerField(
        verbose_name='價格',
        help_text='費用金額（新台幣）'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否啟用'
    )
    description = models.TextField(
        blank=True,
        verbose_name='費用說明',
        help_text='可選的費用說明文字'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='創建時間'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新時間'
    )

    class Meta:
        verbose_name = '雪場費用設定'
        verbose_name_plural = '雪場費用設定'
        unique_together = ('resort', 'fee_type')  # 每個雪場的每種費用類型只能有一個設定
        ordering = ['resort', 'fee_type']

    def __str__(self):
        return f"{self.resort.display_name} - {self.get_fee_type_display()}"

    @classmethod
    def get_fee_for_resort(cls, resort, fee_type, default_price=0):
        """獲取指定雪場的指定費用類型價格"""
        try:
            fee_obj = cls.objects.get(resort=resort, fee_type=fee_type, is_active=True)
            return fee_obj.price
        except cls.DoesNotExist:
            return default_price

    @classmethod
    def get_coach_fee(cls, resort, price_level):
        """根據教練等級獲取指定費用"""
        fee_map = {
            'director': 'coach_director',
            'Lv2': 'coach_lv2',
            'general': 'coach_general'
        }
        fee_type = fee_map.get(price_level, 'coach_general')
        return cls.get_fee_for_resort(resort, fee_type, 1000)  # 預設1000元
    
    @classmethod
    def get_language_fee(cls, resort, language_code):
        """根據語言獲取指定費用"""
        fee_map = {
            'zh': 'language_zh',
            'en': 'language_en',
            'yue': 'language_yue'
        }
        fee_type = fee_map.get(language_code, 'language_zh')
        return cls.get_fee_for_resort(resort, fee_type, 0)  # 預設0元
    
    @classmethod
    def get_equipment_fee(cls, resort, people_count):
        """根據人數獲取裝備租借費用"""
        people_count = int(people_count or 1)
        tier = EquipmentPricingTier.objects.filter(
            resort=resort,
            is_active=True,
            min_people__lte=people_count,
            max_people__gte=people_count,
        ).order_by('min_people', 'max_people', 'id').first()
        if tier:
            return tier.price

        if 1 <= people_count <= 3:
            return cls.get_fee_for_resort(resort, 'equipment_1to3', 1000)  # 預設1000元
        elif 4 <= people_count <= 6:
            return cls.get_fee_for_resort(resort, 'equipment_4to6', 2000)  # 預設2000元
        return 0


class EquipmentPricingTier(models.Model):
    """People-count pricing tier for resort equipment rental assistance."""
    resort = models.ForeignKey(
        Resorts,
        on_delete=models.CASCADE,
        related_name='equipment_pricing_tiers',
        verbose_name='Resort',
    )
    min_people = models.PositiveIntegerField(verbose_name='Minimum people')
    max_people = models.PositiveIntegerField(verbose_name='Maximum people')
    price = models.PositiveIntegerField(verbose_name='Price')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    display_order = models.IntegerField(default=0, verbose_name='Display order')
    description = models.TextField(blank=True, verbose_name='Description')

    class Meta:
        verbose_name = 'Equipment pricing tier'
        verbose_name_plural = 'Equipment pricing tiers'
        ordering = ['resort', 'display_order', 'min_people', 'max_people', 'id']
        unique_together = ('resort', 'min_people', 'max_people')

    def __str__(self):
        return f"{self.resort.display_name}: {self.min_people}-{self.max_people} people ${self.price}"


class EquipmentRentalItem(models.Model):
    """Optional equipment rental add-on item for backcountry/off-piste courses."""
    resort = models.ForeignKey(
        Resorts,
        on_delete=models.CASCADE,
        related_name='equipment_rental_items',
        verbose_name='Resort',
    )
    code = models.CharField(max_length=50, verbose_name='Item code')
    name = models.CharField(max_length=120, verbose_name='Item name')
    daily_price = models.PositiveIntegerField(default=0, verbose_name='Daily price')
    additional_day_price = models.PositiveIntegerField(default=0, verbose_name='Additional day price')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    display_order = models.IntegerField(default=0, verbose_name='Display order')
    description = models.TextField(blank=True, verbose_name='Description')

    class Meta:
        verbose_name = 'Equipment rental add-on item'
        verbose_name_plural = 'Equipment rental add-on items'
        ordering = ['resort', 'display_order', 'id']
        unique_together = ('resort', 'code')

    def __str__(self):
        return f"{self.resort.display_name}: {self.name} ${self.daily_price}/${self.additional_day_price}"


class EquipmentAssistanceTimeSlot(models.Model):
    """Selectable time slot for paid equipment assistance."""
    EQUIPMENT_OPTION_CHOICES = [
        ('purchaseAssistanceTime', '加購協助時間'),
        ('assistDuringCourse', '課程時間內協助'),
        ('rentWithoutyourself', '自行租借不須協助'),
        ('ownWithoutAssistance', '自備裝備不須協助'),
    ]
    LESSON_DURATION_CHOICES = [
        ('any', '不限'),
        ('full_day', '全天'),
        ('half_day', '半天'),
    ]
    SESSION_PERIOD_CHOICES = [
        ('any', '不限'),
        ('all_day', '全天課'),
        ('morning', '上午課'),
        ('afternoon', '下午課'),
    ]
    DAY_TYPE_CHOICES = [
        ('same_day', '當天'),
        ('previous_day', '前一日'),
    ]

    resort = models.ForeignKey(
        Resorts,
        on_delete=models.CASCADE,
        related_name='equipment_assistance_time_slots',
        verbose_name='Resort',
    )
    course_templates = models.ManyToManyField(
        'Coursekit.CourseTemplate',
        blank=True,
        related_name='equipment_assistance_time_slots',
        verbose_name='Applicable course templates',
    )
    equipment_option = models.CharField(
        max_length=40,
        choices=EQUIPMENT_OPTION_CHOICES,
        default='purchaseAssistanceTime',
        verbose_name='Equipment option',
    )
    lesson_duration = models.CharField(
        max_length=20,
        choices=LESSON_DURATION_CHOICES,
        default='any',
        verbose_name='Lesson duration',
    )
    session_period = models.CharField(
        max_length=20,
        choices=SESSION_PERIOD_CHOICES,
        default='any',
        verbose_name='Session period',
    )
    day_type = models.CharField(
        max_length=20,
        choices=DAY_TYPE_CHOICES,
        default='same_day',
        verbose_name='Day type',
    )
    label = models.CharField(max_length=120, verbose_name='Label')
    start_time = models.TimeField(null=True, blank=True, verbose_name='Start time')
    end_time = models.TimeField(null=True, blank=True, verbose_name='End time')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    display_order = models.IntegerField(default=0, verbose_name='Display order')
    description = models.TextField(blank=True, verbose_name='Description')

    class Meta:
        verbose_name = 'Equipment assistance time slot'
        verbose_name_plural = 'Equipment assistance time slots'
        ordering = ['resort', 'equipment_option', 'lesson_duration', 'session_period', 'display_order', 'start_time', 'id']
        unique_together = ('resort', 'equipment_option', 'lesson_duration', 'session_period', 'day_type', 'label')

    def display_label(self):
        if self.label:
            return self.label
        if self.start_time and self.end_time:
            return f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        if self.start_time:
            return self.start_time.strftime('%H:%M')
        return ''

    @staticmethod
    def duration_key(duration_hours):
        if not duration_hours:
            return 'any'
        return 'full_day' if int(duration_hours) >= 5 else 'half_day'

    @staticmethod
    def session_period_key(duration_hours=None, start_time=None):
        if duration_hours and EquipmentAssistanceTimeSlot.duration_key(duration_hours) == 'full_day':
            return 'all_day'
        if not start_time:
            return 'any'
        return 'morning' if start_time.hour < 12 else 'afternoon'

    def matches_course(self, duration_hours=None, session_start_time=None, course_template_id=None):
        if course_template_id and self.course_templates.exists():
            if not self.course_templates.filter(id=course_template_id).exists():
                return False
        duration_key = self.duration_key(duration_hours)
        period_key = self.session_period_key(duration_hours, session_start_time)
        if self.lesson_duration != 'any' and self.lesson_duration != duration_key:
            return False
        if self.session_period != 'any' and self.session_period != period_key:
            return False
        return True

    def __str__(self):
        return f"{self.resort.display_name}: {self.display_label()}"
