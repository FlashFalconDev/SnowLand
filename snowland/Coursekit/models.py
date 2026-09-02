from django.db import models

# Create your models here.

class CourseCategory(models.Model):
    SERVICE_TYPE_SKI = 'ski'
    SERVICE_TYPE_PHOTO = 'photo'
    SERVICE_TYPE_CHOICES = [
        (SERVICE_TYPE_SKI, '滑雪課程'),
        (SERVICE_TYPE_PHOTO, '攝影服務'),
    ]

    """
    課程大類 (最頂層)
    例如：單板 Snowboard, 雙板 Ski, 雪地攝影
    """
    client = models.ForeignKey(
        'Client.Client',
        on_delete=models.CASCADE,
        related_name='course_categories',
        verbose_name='所屬客戶'
    )
    name = models.CharField(max_length=100, verbose_name="課程大類名稱", help_text="例如：單板 Snowboard")
    display_order = models.IntegerField(default=0, verbose_name="顯示順序", help_text="數字越小，排序越前面")

    # 多對多關係：這個課程大類可以在哪些雪場開設
    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_TYPE_CHOICES,
        default=SERVICE_TYPE_SKI,
        db_index=True,
        verbose_name="服務類型",
        help_text="控制此分類出現在哪一種前台預約流程",
    )

    available_resorts = models.ManyToManyField(
        'Resorts.Resorts',
        blank=True,
        related_name='available_categories',
        verbose_name="可開設雪場"
    )
    
    class Meta:
        verbose_name = "1. 課程大類"
        verbose_name_plural = verbose_name
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name

class CourseType(models.Model):
    """
    課程類型 (第二層)
    例如：初學者課程、進階課程、私人教學
    """
    category = models.ForeignKey(CourseCategory, on_delete=models.CASCADE, related_name='types', verbose_name="所屬課程大類")
    name = models.CharField(max_length=100, verbose_name="課程類型名稱", help_text="例如：初學者課程")
    display_order = models.IntegerField(default=0, verbose_name="顯示順序", help_text="數字越小，排序越前面")
    
    # 多對多關係：這個課程類型可以在哪些雪場開設（只能選 category 下的雪場）
    available_resorts = models.ManyToManyField(
        'Resorts.Resorts', 
        blank=True,
        related_name='available_course_types',
        verbose_name="可開設雪場"
    )
    
    class Meta:
        verbose_name = "2. 課程類型"
        verbose_name_plural = verbose_name
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"{self.category.name} - {self.name}"

class CourseTemplate(models.Model):
    """
    課程模板 (第三層 - 整合類型+時長+容量)
    例如：4小時初學者課程
    """
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='templates', verbose_name="所屬課程類型")
    name = models.CharField(max_length=100, verbose_name="課程模板名稱", help_text="例如：4小時初學者課程")
    duration_hours = models.PositiveIntegerField(verbose_name="課程時長(小時)", help_text="例如：4")
    max_capacity = models.PositiveIntegerField(default=6, verbose_name="預設最大容量", help_text="此課程模板的預設人數限制")
    display_order = models.IntegerField(default=0, verbose_name="顯示順序", help_text="數字越小，前台排序越前面")
    is_active = models.BooleanField(default=True, verbose_name="是否啟用此課程模板")
    
    # 綁定雪場（多對多關係）
    resorts = models.ManyToManyField(
        'Resorts.Resorts',
        blank=True,
        related_name='bound_courses',
        verbose_name="綁定雪場"
    )
    
    # 預約時間設定
    booking_open_date = models.DateField(verbose_name="開放預約日期", help_text="例如：2024-12-01", null=True, blank=True)
    booking_close_date = models.DateField(verbose_name="關閉預約日期", help_text="例如：2024-03-31", null=True, blank=True)

    # 課程開放期間
    course_start_date = models.DateField(verbose_name="課程開始日期", help_text="例如：2024-12-01", null=True, blank=True)
    course_end_date = models.DateField(verbose_name="課程結束日期", help_text="例如：2024-03-31", null=True, blank=True)

    COACH_PRICE_LEVEL_ANY = ''
    COACH_PRICE_LEVEL_CHOICES = [
        (COACH_PRICE_LEVEL_ANY, '不限制'),
        ('Lv1', 'Lv1 以上'),
        ('Lv2', 'Lv2 以上'),
        ('Lv3', 'Lv3 以上'),
        ('director', '校長 / 總監'),
    ]

    minimum_coach_price_level = models.CharField(
        max_length=20,
        choices=COACH_PRICE_LEVEL_CHOICES,
        blank=True,
        default=COACH_PRICE_LEVEL_ANY,
        verbose_name="最低教練等級",
        help_text="例如進階課程可設定 Lv2 以上。",
    )
    allowed_coaches = models.ManyToManyField(
        'Coach.Coach',
        blank=True,
        related_name='allowed_course_templates',
        verbose_name="指定可上課教練",
        help_text="留空代表只看最低等級；選擇教練後，只有名單內教練可上。",
    )
    
    class Meta:
        verbose_name = "3. 課程模板"
        verbose_name_plural = verbose_name
        ordering = ['course_type__category__display_order', 'course_type__display_order', 'display_order', 'duration_hours', 'id']

    def __str__(self):
        resort_names = ", ".join([r.display_name for r in self.resorts.all()[:2]])
        if self.resorts.count() > 2:
            resort_names += f" 等{self.resorts.count()}個雪場"
        return f"{self.course_type.category.name} - {self.course_type.name} - {self.name} - {resort_names}"

class CourseSession(models.Model):
    """
    上課時段 (第四層 - 每天可選擇的時段)
    例如：09:00-13:00
    """
    template = models.ForeignKey(CourseTemplate, on_delete=models.CASCADE, related_name='sessions', verbose_name="所屬課程模板")
    
    # 時段設定
    start_time = models.TimeField(verbose_name="開始時間", help_text="例如：09:00")
    end_time = models.TimeField(verbose_name="結束時間", help_text="例如：13:00")
    is_active = models.BooleanField(default=True, verbose_name="是否啟用此時段")
    
    class Meta:
        verbose_name = "4. 上課時段"
        verbose_name_plural = verbose_name
        ordering = ['start_time']

    def __str__(self):
        return f"{self.template} - {self.start_time}-{self.end_time}"

class CoursePricing(models.Model):
    """
    課程定價 - 每個雪場+多個課程模板的價格設定
    處理基礎價格 + 旺季加價 + 每增加一人費用的定價邏輯
    """
    # 改為多對多關係，一個定價策略可以適用多個課程模板
    templates = models.ManyToManyField(
        CourseTemplate, 
        related_name='pricing_options', 
        verbose_name="適用課程模板",
        help_text="此定價策略適用的課程模板"
    )
    resort = models.ForeignKey('Resorts.Resorts', on_delete=models.CASCADE, related_name='course_pricing', verbose_name="適用雪場")
    
    base_price_off_peak = models.PositiveIntegerField(verbose_name="淡季基礎價格", help_text="淡季時1人的基礎價格")
    peak_season_surcharge = models.PositiveIntegerField(verbose_name="旺季加價", help_text="旺季時額外加價的金額")
    additional_person_fee = models.PositiveIntegerField(verbose_name="每增加一人費用", help_text="每增加1人需額外支付的費用")
    max_capacity = models.PositiveIntegerField(verbose_name="最大容量", help_text="此定價策略的最大人數限制")
    is_active = models.BooleanField(default=True, verbose_name="是否啟用")
    
    class Meta:
        verbose_name = "5. 課程定價"
        verbose_name_plural = verbose_name
        # 移除 unique_together，因為現在是多對多關係
        ordering = ['resort', 'id']
    
    def __str__(self):
        template_names = ", ".join([t.name for t in self.templates.all()[:2]])
        if self.templates.count() > 2:
            template_names += f" 等{self.templates.count()}個模板"
        return f"{template_names} - {self.resort.display_name} - 淡季${self.base_price_off_peak} + 旺季${self.peak_season_surcharge} + 每人${self.additional_person_fee}"
    
    def calculate_price(self, people_count, is_peak_season=False):
        """
        計算指定人數和季節的價格
        
        Args:
            people_count: 人數
            is_peak_season: 是否為旺季
        
        Returns:
            總價格
        """
        people_count = int(people_count)
        if people_count < 1:
            raise ValueError(f"people_count must be greater than 0: {people_count}")
        if people_count > self.max_capacity:
            raise ValueError(f"人數超過最大容量限制: {people_count} > {self.max_capacity}")
        
        # 基礎價格（淡季或旺季）
        base_price = self.base_price_off_peak
        tier = self.people_tiers.filter(
            is_active=True,
            min_people__lte=people_count,
            max_people__gte=people_count,
        ).order_by('min_people', 'max_people', 'id').first()

        if tier:
            base_price = tier.price
        else:
            base_price = self.base_price_off_peak + (people_count - 1) * self.additional_person_fee

        if is_peak_season:
            base_price += self.peak_season_surcharge

        return base_price


class CoursePricingTier(models.Model):
    """
    People-count pricing tier for a CoursePricing rule.

    price is the total off-peak course price for the matching people range.
    CoursePricing.peak_season_surcharge is still added on peak-season dates.
    """
    pricing = models.ForeignKey(
        CoursePricing,
        on_delete=models.CASCADE,
        related_name='people_tiers',
        verbose_name='Course pricing',
    )
    min_people = models.PositiveIntegerField(verbose_name='Minimum people')
    max_people = models.PositiveIntegerField(verbose_name='Maximum people')
    price = models.PositiveIntegerField(verbose_name='Off-peak total price')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    display_order = models.IntegerField(default=0, verbose_name='Display order')

    class Meta:
        verbose_name = 'Course pricing people tier'
        verbose_name_plural = 'Course pricing people tiers'
        ordering = ['pricing', 'display_order', 'min_people', 'max_people', 'id']
        unique_together = ('pricing', 'min_people', 'max_people')

    def __str__(self):
        return f"{self.pricing_id}: {self.min_people}-{self.max_people} people ${self.price}"


class DiscountCode(models.Model):
    DISCOUNT_TYPE_PERCENT = 'percent'
    DISCOUNT_TYPE_AMOUNT = 'amount'
    DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_TYPE_PERCENT, '百分比折扣'),
        (DISCOUNT_TYPE_AMOUNT, '固定金額折扣'),
    ]

    AMOUNT_APPLY_MODE_ORDER = 'order'
    AMOUNT_APPLY_MODE_ITEM = 'item'
    AMOUNT_APPLY_MODE_COURSE = 'course'
    AMOUNT_APPLY_MODE_HOUR = 'hour'
    AMOUNT_APPLY_MODE_CHOICES = [
        (AMOUNT_APPLY_MODE_ORDER, '整筆一次'),
        (AMOUNT_APPLY_MODE_ITEM, '每個項目'),
        (AMOUNT_APPLY_MODE_COURSE, '每堂課'),
        (AMOUNT_APPLY_MODE_HOUR, '每小時'),
    ]

    APPLY_SCOPE_ALL = 'all'
    APPLY_SCOPE_SKI = 'ski'
    APPLY_SCOPE_PHOTO = 'photo'
    APPLY_SCOPE_BUNDLE = 'bundle'
    APPLY_SCOPE_CHOICES = [
        (APPLY_SCOPE_ALL, '全部訂單'),
        (APPLY_SCOPE_SKI, '滑雪課程'),
        (APPLY_SCOPE_PHOTO, '攝影服務'),
        (APPLY_SCOPE_BUNDLE, '課程搭配/組合'),
    ]

    client = models.ForeignKey(
        'Client.Client',
        on_delete=models.CASCADE,
        related_name='discount_codes',
        verbose_name='所屬客戶',
    )
    code = models.CharField(max_length=50, verbose_name='折扣碼')
    name = models.CharField(max_length=100, blank=True, verbose_name='活動名稱')
    description = models.TextField(blank=True, verbose_name='備註')
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default=DISCOUNT_TYPE_AMOUNT,
        verbose_name='折扣類型',
    )
    discount_value = models.PositiveIntegerField(default=0, verbose_name='折扣數值')
    amount_apply_mode = models.CharField(
        max_length=20,
        choices=AMOUNT_APPLY_MODE_CHOICES,
        default=AMOUNT_APPLY_MODE_ORDER,
        verbose_name='固定金額折扣單位',
    )
    max_discount_amount = models.PositiveIntegerField(null=True, blank=True, verbose_name='最高折抵金額')
    min_order_amount = models.PositiveIntegerField(default=0, verbose_name='最低訂單金額')
    apply_scope = models.CharField(
        max_length=20,
        choices=APPLY_SCOPE_CHOICES,
        default=APPLY_SCOPE_ALL,
        verbose_name='適用範圍',
    )
    require_multiple_items = models.BooleanField(default=False, verbose_name='需搭配多項課程或服務')
    can_combine = models.BooleanField(default=False, verbose_name='可與其他優惠並用')
    is_auto_apply = models.BooleanField(default=False, verbose_name='自動套用')
    new_customer_only = models.BooleanField(default=False, verbose_name='限新客')
    usage_limit = models.PositiveIntegerField(null=True, blank=True, verbose_name='使用上限')
    used_count = models.PositiveIntegerField(default=0, verbose_name='已使用次數')
    start_at = models.DateTimeField(null=True, blank=True, verbose_name='開始時間')
    end_at = models.DateTimeField(null=True, blank=True, verbose_name='結束時間')
    is_active = models.BooleanField(default=True, verbose_name='是否啟用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新時間')

    class Meta:
        verbose_name = '7. 優惠折扣碼'
        verbose_name_plural = verbose_name
        ordering = ['-is_active', '-created_at', 'code']
        unique_together = ('client', 'code')

    def __str__(self):
        return f"{self.code} - {self.name or self.get_discount_type_display()}"


class SeasonSetting(models.Model):
    """
    用來定義不同的季節定價期間，例如 '2024聖誕旺季', '2025春季淡季'
    """
    name = models.CharField(max_length=100, verbose_name="季節期間名稱")
    season_type = models.CharField(max_length=10, choices=[('peak', '旺季'), ('off', '淡季')], verbose_name="季節類型")
    start_date = models.DateField(verbose_name="開始日期")
    end_date = models.DateField(verbose_name="結束日期")

    class Meta:
        verbose_name = "6. 季節定價設定"
        verbose_name_plural = verbose_name
        ordering = ['start_date']

    def __str__(self):
        return f"{self.name} ({self.get_season_type_display()}: {self.start_date} ~ {self.end_date})"

    @staticmethod
    def get_season_type_for_date(date_to_check):
        """
        根據資料庫中的設定，判斷指定日期屬於哪個季節類型 (peak/off)
        如果日期不落在任何已定義的季節中，預設為淡季
        """
        active_season = SeasonSetting.objects.filter(
            start_date__lte=date_to_check,
            end_date__gte=date_to_check
        ).first()

        return active_season.season_type if active_season else 'off'
