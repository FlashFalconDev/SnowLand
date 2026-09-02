from django.db import models

# Create your models here.

class CourseType(models.Model):
    """
    課程大類 (頂層)
    例如：單板 Snowboard, 雙板 Ski, 雪地攝影
    """
    name = models.CharField(max_length=100, help_text="例如：單板 Snowboard")
    display_order = models.IntegerField(default=0, verbose_name="顯示順序", help_text="數字越小，排序越前面")
    resorts = models.ManyToManyField(
        'Resorts.Resorts', 
        blank=True, 
        verbose_name="適用雪場", 
        help_text="適用於哪些雪場的列表"
    )

    class Meta:
        verbose_name = "1. 課程大類"
        verbose_name_plural = verbose_name
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name

class CourseTemplate(models.Model):
    """
    課程模板 (中層)
    例如：全天5小時教學課程, 半天3小時教學課程
    """
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='templates', verbose_name="所屬課程大類")
    name = models.CharField(max_length=100, help_text="例如：全天5小時教學課程")
    duration = models.CharField(max_length=50, help_text="例如：5小時")
    max_capacity = models.PositiveIntegerField(default=6, verbose_name="最大容量", help_text="此課程模板的最大人數限制")
    is_active = models.BooleanField(default=True, help_text="是否啟用此課程模板")
    
    class Meta:
        verbose_name = "2. 課程模板"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"[{self.course_type.name}] {self.name}"

class Course(models.Model):
    """
    課程時段 (底層) - 簡化版本，使用自動生成的pk
    """
    template = models.ForeignKey(CourseTemplate, on_delete=models.CASCADE, related_name='slots', verbose_name="所屬課程模板", null=True, blank=True)
    resort = models.ForeignKey(
        'Resorts.Resorts',
        on_delete=models.CASCADE,
        related_name='courses',
        verbose_name="開設雪場",
        null=True,
        blank=True
    )
    
    # 簡化的課程資訊
    date_range = models.CharField(max_length=50, help_text="適用日期範圍，例如 '(12/01~03/31)'")
    main_time = models.CharField(max_length=50, help_text="主要教學時間，例如 '09:00-11:30 / 12:30-15:00'")
    course_specific_info = models.JSONField(blank=True, default=dict, help_text="課程類型特定的額外資訊")

    class Meta:
        verbose_name = "3. 課程時段"
        verbose_name_plural = verbose_name

    def __str__(self):
        resort_name = self.resort.display_name if self.resort else "未指定雪場"
        # 盡量不依賴 period 欄位，優先使用 course_specific_info.period_label，其次由 main_time 推導
        period_label = None
        try:
            period_label = (self.course_specific_info or {}).get('period_label')
        except Exception:
            period_label = None

        if not period_label:
            # 從 main_time 取第一段開始時間作為簡易 period 顯示
            try:
                period_label = self.main_time.split('-')[0].strip() if self.main_time else ''
            except Exception:
                period_label = ''

        return f"{self.template.name} - {period_label or '-'} - {resort_name}"

    def to_dict(self):
        """將模型物件轉換為前端所需的字典格式，以兼容舊版"""
        # 衍生 period 與 total_time，避免硬依賴被淘汰的欄位
        try:
            period_label = (self.course_specific_info or {}).get('period_label')
        except Exception:
            period_label = None

        if not period_label:
            try:
                period_label = self.main_time.split('-')[0].strip() if self.main_time else ''
            except Exception:
                period_label = ''

        # 解析 main_time 例如: "09:00-11:30 / 12:30-15:00"
        def _derive_times(main_time_str):
            start_val, end_val = '', ''
            if not main_time_str:
                return start_val, end_val
            try:
                segments = [s.strip() for s in main_time_str.split('/')]
                first_seg = segments[0] if segments else ''
                last_seg = segments[-1] if segments else ''
                if first_seg:
                    start_val = first_seg.split('-')[0].strip()
                if last_seg:
                    end_val = last_seg.split('-')[-1].strip()
            except Exception:
                pass
            return start_val, end_val

        start_time_val, end_time_val = _derive_times(self.main_time)
        total_time_val = f"{start_time_val}-{end_time_val}".strip('-') if (start_time_val or end_time_val) else ''

        derived_course_type = f"{self.template.course_type.name.lower()}-{(period_label or '').lower()}" if self.template and self.template.course_type else (self.template.course_type.name.lower() if self.template and self.template.course_type else '')

        return {
            "course_type": derived_course_type,
            "course_name": self.template.name,
            "period": period_label or '',
            "date": self.date_range,
            "totalTime": total_time_val,
            "mainTime": self.main_time,
            "equipmentTime": (self.course_specific_info or {}).get('equipment_time', ''),
            "need_equipment": (self.course_specific_info or {}).get('need_equipment', False),
            "start_time": start_time_val,
            "end_time": end_time_val,
        }
    

# 課程預約系統的新模型 - 暫時註釋掉，待討論確認後啟用
# class CourseSchedule(models.Model):
#     """
#     課程排程表 - 用於課程預約系統
#     基於原有的 Course 模型，但專注於預約功能
#     """
#     # 綁定課程模板
#     template = models.ForeignKey(CourseTemplate, on_delete=models.CASCADE, related_name='schedules', verbose_name="所屬課程模板")
#     
#     # 綁定多個雪場（一個課程可以在多個雪場開設）
#     resorts = models.ManyToManyField('Resorts.Resorts', related_name='course_schedules', verbose_name="開設雪場")
#     
#     # 上課日期和時間
#     start_date = models.DateField(verbose_name="課程開始日期")
#     end_date = models.DateField(verbose_name="課程結束日期")
#     class_start_time = models.TimeField(verbose_name="上課開始時間")
#     class_end_time = models.TimeField(verbose_name="上課結束時間")
#     
#     # 預約相關時間設定
#     booking_open_date = models.DateTimeField(verbose_name="開放預約時間")
#     booking_close_date = models.DateTimeField(verbose_name="關閉預約時間")
#     
#     # 開關控制
#     is_active = models.BooleanField(default=True, verbose_name="是否啟用")
#     is_booking_open = models.BooleanField(default=False, verbose_name="是否開放預約")
#     
#     # 技能等級要求
#     skill_level_required = models.CharField(
#         max_length=50, 
#         blank=True, 
#         verbose_name="技能等級要求",
#         help_text="例如：初學者、中級、高級"
#     )
#     
#     # 額外設定
#     notes = models.TextField(blank=True, verbose_name="備註說明")
#     special_requirements = models.JSONField(blank=True, default=dict, verbose_name="特殊要求")
#     
#     class Meta:
#         verbose_name = "課程排程"
#         verbose_name_plural = verbose_name
#         ordering = ['start_date', 'class_start_time']
#     
#     def __str__(self):
#         return f"{self.template.name} - {self.start_date} - {self.class_start_time}"
#     
#     # 可以考慮添加的欄位（暫時註釋掉）：
#     # coaches = models.ManyToManyField('Coach.Coach', related_name='course_schedules', verbose_name="指派教練")
#     # coach_notes = models.TextField(blank=True, verbose_name="教練備註")
#     # cancellation_policy = models.TextField(blank=True, verbose_name="取消政策")
#     # refund_policy = models.TextField(blank=True, verbose_name="退款政策")
#     # waitlist_enabled = models.BooleanField(default=False, verbose_name="是否啟用候補名單")
#     # flexible_timing = models.BooleanField(default=False, verbose_name="是否允許彈性時間")
#     # alternative_dates = models.JSONField(blank=True, default=list, verbose_name="備選日期")
#     # age_restrictions = models.CharField(max_length=100, blank=True, verbose_name="年齡限制")
#     # equipment_included = models.BooleanField(default=False, verbose_name="是否包含裝備")
#     # weather_dependent = models.BooleanField(default=False, verbose_name="是否依賴天氣條件")



class SeasonSetting(models.Model):
    """
    用來定義不同的季節定價期間，例如 '2024聖誕旺季', '2025春季淡季'
    """
    name = models.CharField(max_length=100, verbose_name="季節期間名稱")
    season_type = models.CharField(max_length=10, choices=[('peak', '旺季'), ('off', '淡季')], verbose_name="季節類型")
    start_date = models.DateField(verbose_name="開始日期")
    end_date = models.DateField(verbose_name="結束日期")

    class Meta:
        verbose_name = "5. 季節定價設定"
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

class CoursePricingStrategy(models.Model):
    """
    課程定價策略，替代原有的PriceTier模型
    處理基礎價格 + 旺季加價 + 每增加一人費用的定價邏輯
    """
    template = models.ForeignKey(CourseTemplate, on_delete=models.CASCADE, related_name='pricing_strategies', verbose_name="所屬課程模板")
    resort = models.ForeignKey(
        'Resorts.Resorts',
        on_delete=models.CASCADE,
        related_name='pricing_strategies',
        verbose_name="適用雪場"
    )
    base_price_off_peak = models.PositiveIntegerField(verbose_name="淡季基礎價格", help_text="淡季時1人的基礎價格")
    peak_season_surcharge = models.PositiveIntegerField(verbose_name="旺季加價", help_text="旺季時額外加價的金額")
    additional_person_fee = models.PositiveIntegerField(verbose_name="每增加一人費用", help_text="每增加1人需額外支付的費用")
    max_capacity = models.PositiveIntegerField(verbose_name="最大容量", help_text="此定價策略的最大人數限制")
    is_active = models.BooleanField(default=True, verbose_name="是否啟用")
    
    class Meta:
        verbose_name = "6. 課程定價策略"
        verbose_name_plural = verbose_name
        unique_together = ('template', 'resort')
        ordering = ['template', 'resort']
    
    def __str__(self):
        return f"{self.template} - {self.resort.display_name} - 淡季${self.base_price_off_peak} + 旺季${self.peak_season_surcharge} + 每人${self.additional_person_fee}"
    
    def calculate_price(self, people_count, is_peak_season=False):
        """
        計算指定人數和季節的價格
        
        Args:
            people_count: 人數
            is_peak_season: 是否為旺季
        
        Returns:
            總價格
        """
        if people_count > self.max_capacity:
            raise ValueError(f"人數超過最大容量限制: {people_count} > {self.max_capacity}")
        
        # 基礎價格（淡季或旺季）
        base_price = self.base_price_off_peak
        if is_peak_season:
            base_price += self.peak_season_surcharge
        
        # 總價格 = 基礎價格 + (人數-1) × 每增加一人費用
        total_price = base_price + (people_count - 1) * self.additional_person_fee
        
        return total_price