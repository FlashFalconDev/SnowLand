from django.db import models
from django.contrib.auth.models import User
from multiselectfield import MultiSelectField
# 1. 匯入新的 Resorts model 和 CourseType model
from Resorts.models import Resorts
from Coursekit.models import CourseType
from django.db.utils import ProgrammingError



ABILITY_LEVEL_CHOICES = [
    ('no_exp', '等級 0'),
    ('level1', '等級 1'),
    ('level2', '等級 2'),
    ('level3', '等級 3'),
    ('level4', '等級 4'),
    ('level5', '等級 5'),
    ('level6', '等級 6'),
]

ABILITY_LEVEL_LEGACY_MAP = {
    'entry': 'level1',
    'basic': 'level2',
    'intermediate': 'level3',
    'advanced': 'level4',
    'expert': 'level6',
}


def normalize_ability_level(level):
    value = str(level or '').strip()
    return ABILITY_LEVEL_LEGACY_MAP.get(value, value)


def normalize_ability_levels(levels):
    if not levels:
        return []
    if isinstance(levels, str):
        raw_levels = [item.strip() for item in levels.split(',') if item.strip()]
    else:
        raw_levels = [str(item or '').strip() for item in levels if str(item or '').strip()]

    normalized = []
    for level in raw_levels:
        next_level = normalize_ability_level(level)
        if next_level and next_level not in normalized:
            normalized.append(next_level)
    return normalized
class Coach(models.Model):
    client = models.ForeignKey(
        'Client.Client',
        on_delete=models.CASCADE,
        related_name='coaches',
        verbose_name='所屬客戶',
        null=True,  # 暫時允許為 null 以便進行 migration
        blank=True
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='使用者')
    name = models.CharField(max_length=100, null=True, blank=True, default='')
    # 語言選單
    LANGUAGE_CHOICES = [
        ('en', 'EN'),
        ('zh', '中文'),
        ('yue', '廣東'),
    ]
    languages = MultiSelectField(
        choices=LANGUAGE_CHOICES,
        default='zh'  # 若只允許單選可改成 CharField + choices
    )
    
    # 修改為三種狀態的可用性設定
    AVAILABILITY_CHOICES = [
        ('active', '主動接課'),      # 接課且在用戶界面顯示
        ('passive', '需確認接課'),     # 接課但不在用戶界面主動顯示
        ('unavailable', '不可接課'), # 完全不參與排課
    ]
    availability_status = models.CharField(
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default='active',
        verbose_name='接課狀態'
    )

    assignment_score = models.IntegerField(
        default=0,
        verbose_name='教練分派權重分數',
        help_text='分數越低，越優先被系統指派。成功指派後會自動增加。'
    )

    # 新增圖片URL字段
    img = models.URLField(max_length=200, blank=True, null=True, verbose_name='教練圖片URL')

    website_enabled = models.BooleanField(default=False, db_index=True, verbose_name='官網顯示')
    website_slug = models.SlugField(max_length=80, blank=True, default='', db_index=True, verbose_name='官網代號')
    website_sort_order = models.IntegerField(default=0, verbose_name='官網排序')
    website_card_bio = models.CharField(max_length=160, blank=True, default='', verbose_name='官網卡片簡介')
    certifications = models.JSONField(default=list, blank=True, verbose_name='教練證照')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')

    def __str__(self):
        return f"教練: {self.name}"

    class Meta:
        verbose_name = '教練'
        verbose_name_plural = '教練基礎設定'

class CoachResort(models.Model):
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, verbose_name='教練')
    
    # 使用 db_column 明確告訴 Django，
    # 這個 'resort' 欄位在資料庫中對應的欄位叫做 'resort_fk_id'
    resort = models.ForeignKey(
        Resorts, 
        on_delete=models.CASCADE, 
        verbose_name='雪場',
        db_column='resort_fk_id'  # <--- 核心修正！
    )

    resort_priority = models.IntegerField(default=0, verbose_name='雪場優先順序')
    assignment_score = models.IntegerField(
        default=0,
        verbose_name='雪場分派權重分數',
        help_text='同一位教練在不同雪場的分派優先順序，分數越低越優先。'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')

    def __str__(self):
        return f"{self.coach.name} - {self.resort.display_name} (優先順序: {self.resort_priority})"

    class Meta:
        verbose_name = '教練雪場'
        verbose_name_plural = '教練雪場設定'

class CoachCourseLevel(models.Model):
    PRICE_LEVEL_CHOICES = [
        ('Lv1', 'Lv1'),
        ('Lv2', 'Lv2'),
        ('Lv3', 'Lv3'),
        ('director', '校長&總監'),
    ]
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name='course_levels')
    
    # --- START OF CHANGES ---
    course_type = models.ForeignKey(
        CourseType,
        on_delete=models.CASCADE,
        verbose_name='課程類型',
        null=True # 暫時允許為空，以便順利進行 migration
    )
    # --- END OF CHANGES ---

    ability_levels = MultiSelectField(
        choices=ABILITY_LEVEL_CHOICES,
        verbose_name='可接課等級',
        blank=True,
        null=True
    )
    price_level = models.CharField(max_length=20, choices=PRICE_LEVEL_CHOICES, verbose_name='價格等級')
    course_order = models.IntegerField(default=0, verbose_name='接課順序')

    class Meta:
        verbose_name = '教練課程等級'
        verbose_name_plural = '教練課程等級'

    def __str__(self):
        # ability_levels_display 用中文顯示
        ability_map = dict(ABILITY_LEVEL_CHOICES)
        ability_levels_display = ', '.join([
            ability_map.get(normalize_ability_level(al), al)
            for al in self.ability_levels
        ])
        
        # 修正：直接存取ForeignKey的屬性，並處理可能為空的情況
        course_type_name = self.course_type.name if self.course_type else "未指定類型"
        
        return f"{self.coach.name} - {course_type_name} - {ability_levels_display} - {self.get_price_level_display()} - 順序:{self.course_order}"

class CoachLeaveRequest(models.Model):
    """教練請假申請"""
    coach = models.ForeignKey(
        Coach, 
        on_delete=models.CASCADE, 
        verbose_name='教練'
    )
    start_date = models.DateField(verbose_name='請假開始日期')
    end_date = models.DateField(verbose_name='請假結束日期')
    reason = models.TextField(verbose_name='請假原因')
    
    STATUS_CHOICES = [
        ('pending', '待審核'),
        ('approved', '已批准'),
        ('rejected', '已拒絕'),
        ('cancelled', '已取消'),
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        verbose_name='狀態'
    )
    
    # 受影響的預約 - 需要import booking模型
    affected_reservations = models.ManyToManyField(
        'booking.Reservation', 
        blank=True,
        verbose_name='受影響的預約'
    )
    
    # 處理結果
    processing_result = models.TextField(
        blank=True,
        verbose_name='處理結果'
    )
    
    # 審核人
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_leave_requests',
        verbose_name='審核人'
    )
    
    reviewed_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='審核時間'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='申請時間')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新時間')
    
    def __str__(self):
        return f"{self.coach.name} - {self.start_date} 到 {self.end_date} ({self.get_status_display()})"
    
    @property
    def leave_days(self):
        """計算請假天數"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
    
    class Meta:
        verbose_name = '教練請假申請'
        verbose_name_plural = '教練請假申請'
