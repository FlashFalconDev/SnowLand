from django.db import models
from multiselectfield import MultiSelectField
from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from Resorts.models import Resorts
from Coursekit.models import CourseType

ABILITY_LEVEL_CHOICES = [
    ('no_exp', '等級 0'),
    ('level1', '等級 1'),
    ('level2', '等級 2'),
    ('level3', '等級 3'),
    ('level4', '等級 4'),
    ('level5', '等級 5'),
    ('level6', '等級 6'),
]

EQUIPMENT_CHOICES = [
        ('rentWithoutyourself', '自行租借不須協助'),
        ('ownWithoutAssistance', '自備裝備不須協助'),
        ('assistDuringCourse', '課程時間內協助'),
        ('purchaseAssistanceTime', '加購協助時間'),
    ]
class ReservationGroup(models.Model):
    client = models.ForeignKey(
        'Client.Client',
        on_delete=models.CASCADE,
        related_name='reservation_groups',
        verbose_name='所屬客戶',
        null=True,  # 暫時允許為 null 以便進行 migration
        blank=True
    )
    name = models.CharField(max_length=100, verbose_name='預約分組名稱', blank=True, null=True)
    campus = models.ForeignKey(
        'Resorts.Campus',
        on_delete=models.PROTECT,
        related_name='reservation_groups',
        null=True,
        blank=True,
        verbose_name='訂單校區',
    )
    order_number = models.CharField(max_length=40, blank=True, default='', db_index=True, verbose_name='訂單編號')
    marketing_source = models.CharField(max_length=60, blank=True, default='', verbose_name='行銷來源')
    marketing_source_detail = models.CharField(max_length=200, blank=True, default='', verbose_name='行銷來源說明')
    referral_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_reservation_groups', verbose_name='介紹人'
    )
    line_group_url = models.URLField(max_length=500, blank=True, default='', verbose_name='LINE 群組連結')
    source_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='下單 IP')
    source_country = models.CharField(max_length=2, blank=True, default='', verbose_name='下單國家')
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, verbose_name='使用者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')

    def __str__(self):
        return self.name or self.order_number or f"ReservationGroup #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.order_number:
            self.order_number = f"SL-{self.created_at:%Y%m%d}-{self.pk:06d}"
            type(self).objects.filter(pk=self.pk).update(order_number=self.order_number)

    class Meta:
        verbose_name = '預約分組'
        verbose_name_plural = '2-0.預約分組'

class Reservation(models.Model):
    group = models.ForeignKey(
        'ReservationGroup',
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name='所屬分組'
    )

    # is_preferred_coach = True 代表使用者要「指定」教練
    is_preferred_coach = models.BooleanField(default=False)
    preferred_coach = models.ForeignKey(
        'Coach.Coach',  # <--- 改成字串
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # 記錄拒絕過的教練，避免重複分配
    rejected_coaches = models.ManyToManyField(
        'Coach.Coach',  # <--- 改成字串
        blank=True,
        related_name='rejected_reservations',
        verbose_name='拒絕過的教練'
    )

    # 在 Reservation 新增『是否租借裝備』
    need_equipment = models.BooleanField(default=False)

    equipment = models.CharField(
        max_length=100,
        choices=EQUIPMENT_CHOICES,
        blank=True,
        null=True,
        verbose_name='租借裝備'
    )
    
    # 新增『語言』只能選一個
    SINGLE_LANGUAGE_CHOICES = [
        ('zh', '中文'),
        ('en', '英文'),
        ('yue', '粵語'),
    ]
    equipment_assistance_time_slot = models.ForeignKey(
        'Resorts.EquipmentAssistanceTimeSlot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations',
        verbose_name='Equipment assistance time slot'
    )
    equipment_assistance_time_label = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Equipment assistance time label'
    )

    def get_equipment_assistance_time_display(self):
        if self.equipment_assistance_time_label:
            return self.equipment_assistance_time_label
        if self.equipment_assistance_time_slot:
            return self.equipment_assistance_time_slot.display_label()
        return ''

    language = models.CharField(
        max_length=10,
        choices=SINGLE_LANGUAGE_CHOICES,
        default='zh'
    )

    def get_language_display(self):
        # 使用 SINGLE_LANGUAGE_CHOICES 生成字典
        language_map = dict(self.SINGLE_LANGUAGE_CHOICES)
        return language_map.get(self.language, '未知语言')

    # 刪除舊的 resort_str 欄位
    # 將新的外鍵欄位命名為 'resort' 並設為不可為空
    resort = models.ForeignKey(
        Resorts,
        on_delete=models.SET_NULL,
        null=True, # 保持 null=True，因為 on_delete 是 SET_NULL
        blank=True,
        verbose_name='雪場'
    )

    def get_resort_display(self):
        # 現在只需要簡單地返回關聯名稱
        if self.resort:
            return self.resort.display_name
        return "未知雪場"
    
    course_type = models.ForeignKey(
        CourseType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='課程類型'
    )
    course_template = models.ForeignKey(
        'Coursekit.CourseTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations',
        verbose_name='課程模板'
    )
    def get_course_type_display(self):
        try:
            if self.course_type:
                return self.course_type.name
        except Exception:
            # 如果課程類型不存在或無法訪問，返回預設值
            pass
        return "未知課程"
    
    max_ability_level = models.CharField(
        max_length=20,
        choices=ABILITY_LEVEL_CHOICES,
        blank=True,
        null=True,
        verbose_name='最高滑雪能力'
    )

    # 新增預約狀態選擇
    STATUS_CHOICES = [
        ('created', '創建預約'),                 # Was 0
        ('cancelled', '已取消'),                 # Was 1
        ('deleted', '已刪除'),                   # Was 2
        ('auto_assignment_failed', '無法自動排定教練'),  # Was 9
        ('manual_assignment_needed', '需人工排定教練'),# Was 10
        ('auto_assigned', '已自動排定教練'),          # Was 20
        ('manually_assigned', '人工手動排定教練'),     # Was 21
        ('pending_coach_confirmation', '等待教練確認'),# Was 22
        ('form_filled', '已填表單'),                 # Was 30
        ('completed', '已完成'),                   # Was 99
    ]
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='created',
        verbose_name='預約狀態'
    )
    def get_status_display(self):
        # 使用 STATUS_CHOICES 生成字典
        status_map = dict(self.STATUS_CHOICES)
        return status_map.get(self.status, '未知狀態')


    mdt_add = models.DateTimeField(auto_now_add=True, null=True)

    # 新增人數
    number_of_people = models.IntegerField(default=0, verbose_name='人數')
    
    equipment_rental_fee = models.PositiveIntegerField(default=0, verbose_name='租借裝備費用')
    language_fee = models.PositiveIntegerField(default=0, verbose_name='語言指定費用')
    coach_fee = models.PositiveIntegerField(default=0, verbose_name='教練指定費用')
    course_fee = models.PositiveIntegerField(default=0, verbose_name='課程費用')
    discount_amount = models.PositiveIntegerField(default=0, verbose_name='折扣金額')
    discount_code = models.CharField(max_length=255, blank=True, default='', verbose_name='折扣碼')
    discount_name = models.CharField(max_length=255, blank=True, default='', verbose_name='折扣名稱')
    total_fee = models.PositiveIntegerField(default=0, verbose_name='總和費用')
    payment_amount = models.PositiveIntegerField(default=0, verbose_name='付款費用')

    def save(self, *args, **kwargs):
        # 自动计算总费用
        self.total_fee = (
            self.equipment_rental_fee +
            self.language_fee +
            self.coach_fee +
            self.course_fee
        )
        self.payment_amount = max(self.total_fee - int(self.discount_amount or 0), 0)
        super().save(*args, **kwargs)

    def __str__(self):
        user_name = f"{self.group.user}" if self.group.user else "未知使用者"
        coach_name = self.preferred_coach.name if self.preferred_coach else "無"
        if self.is_preferred_coach and self.preferred_coach:
            coach_info = f"指定教練: {coach_name}"
        else:
            coach_info = f"未指定教練: {coach_name}"
        return f"{self.pk} - 課程預約: {user_name} - {coach_info}"

    class Meta:
        verbose_name = '預約'
        verbose_name_plural = '2-1.預約列表'

class Booking(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="bookings"
    )
    # 課程名稱或類型
    course_type = models.CharField(max_length=50, default='')
    course_name = models.CharField(max_length=50, default='')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    # （原本在 Booking 的 need_equipment 已被移除，轉移到 Reservation）

    is_scheduled = models.BooleanField(default=False)

    def __str__(self):
        user_name = self.reservation.group.user if self.reservation.group.user else "未知使用者"
        coach_name = self.reservation.preferred_coach.name if self.reservation.preferred_coach else "無"
        coach_info = f"指定教練: {coach_name}" if self.reservation.is_preferred_coach else f"未指定教練: {coach_name}"
        return f"{self.date} {self.course_name} 預約者: {user_name} {coach_info}"

    class Meta:
        verbose_name = '預約課程'
        verbose_name_plural = '2-2.預約課程'

class MemberDetail(models.Model):
    """
    用來儲存單一位學員的資訊，如年齡、單板程度、雙板程度。
    透過 ForeignKey 連到 Reservation (或 User)，看你需求。
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    # 與哪個 Reservation 關聯？（若整筆預約有多個學員，就一對多）
    reservation = models.ForeignKey(
        "Reservation",  # 你的 Reservation 模型所在app的命名空間
        on_delete=models.CASCADE,
        related_name="members"
    )
    
    # 新增填寫人選擇
    FILLED_BY_CHOICES = [
        ('coach', '教練'),
        ('user', '使用者'),
    ]
    filled_by = models.CharField(
        max_length=10,
        choices=FILLED_BY_CHOICES,
        default='user',
        verbose_name='填寫人'
    )
    # 年齡 - 單選 (radio)
    # 可以事先定義一組 CHOICES
    AGE_CHOICES = [
        ("4-6y", "幼兒4-6y"),
        ("7-12y", "兒童7-12y"),
        ("13-18y", "青少年13-18y"),
        ("19-24y", "成人19-24y"),
        ("25-35y", "成人25-35y"),
        ("36-45y", "成人36-45y"),
        ("46-55y", "成人46-55y"),
        ("56y以上", "56y以上"),
    ]
    age_range = models.CharField(
        max_length=10,
        choices=AGE_CHOICES,
        default="19-24y",
        verbose_name="年齡區間"
    )

    # 單板 (Snowboard) 程度 - 多選 (checkbox)
    # 你可把「無經驗、室內滑雪機橫滑...」等統整成 CHOICES
    SNOWBOARD_CHOICES = [
        ("無經驗", "無經驗"),
        ("室內滑雪機橫滑", "室內滑雪機橫滑"),
        ("室內滑雪機Healside落葉飄", "室內滑雪機Healside落葉飄"),
        ("室內滑雪機C turn", "室內滑雪機C turn"),
        ("室內滑雪機S turn", "室內滑雪機S turn"),
        ("室內滑雪機Toeside落葉飄", "室內滑雪機Toeside落葉飄"),
        ("小叮噹橫滑", "小叮噹橫滑"),
        ("小叮噹Healside落葉飄", "小叮噹Healside落葉飄"),
        ("小叮噹Toeside落葉飄", "小叮噹Toeside落葉飄"),
        ("小叮噹 C turn", "小叮噹 C turn"),
        ("小叮噹S turn", "小叮噹S turn"),
        ("雪場橫滑", "雪場橫滑"),
        ("雪場Healside落葉飄", "雪場Healside落葉飄"),
        ("雪場Toeside落葉飄", "雪場Toeside落葉飄"),
        ("雪場C turn", "雪場C turn"),
        ("雪場S turn", "雪場S turn"),
        ("雪場綠線順滑", "雪場綠線順滑"),
        ("雪場藍(紅)線順滑", "雪場藍(紅)線順滑"),
        ("雪場黑線順滑", "雪場黑線順滑"),
        ("雪場樹林", "雪場樹林"),
        ("雪場界外", "雪場界外"),
    ]

    snowboard_skills = MultiSelectField(
        choices=SNOWBOARD_CHOICES,
        blank=True,
        null=True,
        verbose_name="單板程度"
    )

    # 雙板 (Ski) 程度 - 多選 (checkbox)
    SKI_CHOICES = [
        ("無經驗", "無經驗"),
        ("室內滑雪機全制動煞車", "室內滑雪機全制動煞車"),
        ("室內滑雪機全制動轉彎", "室內滑雪機全制動轉彎"),
        ("室內滑雪機半制動轉彎", "室內滑雪機半制動轉彎"),
        ("室內滑雪機並腿轉彎", "室內滑雪機並腿轉彎"),
        ("小叮噹全制動煞車", "小叮噹全制動煞車"),
        ("小叮噹全制動轉彎", "小叮噹全制動轉彎"),
        ("小叮噹半制動轉彎", "小叮噹半制動轉彎"),
        ("小叮噹並腿轉彎", "小叮噹並腿轉彎"),
        ("雪場全制動煞車", "雪場全制動煞車"),
        ("雪場全制動轉彎", "雪場全制動轉彎"),
        ("雪場半制動轉彎", "雪場半制動轉彎"),
        ("雪場並腿轉彎", "雪場並腿轉彎"),
        ("雪場綠線順滑", "雪場綠線順滑"),
        ("雪場藍(紅)線順滑", "雪場藍(紅)線順滑"),
        ("雪場黑線順滑", "雪場黑線順滑"),
        ("雪場樹林", "雪場樹林"),
        ("雪場界外", "雪場界外"),
    ]

    ski_skills = MultiSelectField(
        choices=SKI_CHOICES,
        blank=True,
        null=True,
        verbose_name="雙板程度"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    guardian = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='guarded_member_details', verbose_name='家長帳號'
    )
    insurance_completed_at = models.DateTimeField(null=True, blank=True, verbose_name='保險資料完成時間')
    waiver_completed_at = models.DateTimeField(null=True, blank=True, verbose_name='聲明書完成時間')

    def __str__(self):
        coach_name = self.reservation.preferred_coach.name if self.reservation.preferred_coach else "無"
        coach_info = f"指定教練: {coach_name}" if self.reservation.is_preferred_coach else f"未指定教練: {coach_name}"
        user_name = f"{self.user.last_name}{self.user.first_name}" if self.user else "未知使用者"
        return f"課程預約者: {user_name}, {coach_info},[學員]年齡: {self.age_range}, 單板程度: {self.snowboard_skills}, 雙板程度: {self.ski_skills}"

    class Meta:
        verbose_name = '學員程度表單'
        verbose_name_plural = '2-3.學員程度表單'

class Payment(models.Model):
    STATUS_CHOICES = [
        ('unpaid', '未付款'),
        ('pending', '待確認付款'),
        ('paid', '已付款'),
        ('expired', '付款時間已過期'),
        ('refunded', '已退款'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('newebpay', '藍新支付'),
        ('TT', '匯款'),
        ('credit_card', '信用卡'),
        ('apple_pay', 'Apple Pay'),
        ('google_pay', 'Google Pay'),
    ]
    reservation_group = models.ForeignKey(
        ReservationGroup,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='關聯預約分組'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payments',
        verbose_name='付款用戶'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='unpaid',
        verbose_name='付款狀態'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='TT',
        verbose_name='付款方式'
    )
    bank_account = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='匯款帳號'
    )
    payment_account = models.ForeignKey(
        'Resorts.PaymentAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments', verbose_name='收款帳戶'
    )
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name='付款保留到期時間')
    DataJSON = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新時間')

    def __str__(self):
        return f"付款單#{self.pk} - 預約{self.reservation_group} - 狀態: {self.get_status_display()}"

    class Meta:
        verbose_name = '付款紀錄'
        verbose_name_plural = '2-4.付款紀錄'


def referral_code_default():
    return uuid.uuid4().hex[:10].upper()


class MemberProfile(models.Model):
    LEVEL_CHOICES = [('new', '新會員'), ('alumni', '舊生'), ('silver', '銀級'), ('gold', '金級')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='snowland_member_profile')
    referral_code = models.CharField(max_length=20, unique=True, default=referral_code_default, verbose_name='專屬推薦碼')
    points = models.PositiveIntegerField(default=0, verbose_name='點數')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='new', verbose_name='會員等級')
    alumni_verified = models.BooleanField(default=False, verbose_name='舊生已審核')
    previous_points = models.PositiveIntegerField(default=0, verbose_name='手動補登點數')
    line_user_id = models.CharField(max_length=100, blank=True, default='', verbose_name='LINE 帳號')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user} - {self.referral_code}'


class OrderRevision(models.Model):
    CHANGE_CHOICES = [('create', '建立'), ('modify', '修改'), ('add', '追加'), ('reduce', '追減'), ('cancel', '取消')]
    group = models.ForeignKey(ReservationGroup, on_delete=models.CASCADE, related_name='revisions', verbose_name='訂單')
    version = models.PositiveIntegerField(verbose_name='版本')
    change_type = models.CharField(max_length=20, choices=CHANGE_CHOICES, default='modify')
    snapshot = models.JSONField(default=dict, verbose_name='當時訂單內容')
    difference_amount = models.IntegerField(default=0, verbose_name='與上一版差額')
    reason = models.TextField(blank=True, default='', verbose_name='修改原因')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_revisions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['group', '-version']
        unique_together = ('group', 'version')


class CancellationRequest(models.Model):
    STATUS_CHOICES = [('requested', '待處理'), ('approved', '已核准'), ('rejected', '已拒絕'), ('refunded', '已退款')]
    REASON_CHOICES = [('schedule', '行程變更'), ('health', '健康因素'), ('weather', '天候因素'), ('duplicate', '重複訂單'), ('other', '其他')]
    group = models.ForeignKey(ReservationGroup, on_delete=models.PROTECT, related_name='cancellation_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    reason_note = models.TextField(blank=True, default='')
    original_amount = models.PositiveIntegerField(default=0)
    days_before = models.IntegerField(default=0)
    refund_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    handling_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    refund_amount = models.PositiveIntegerField(default=0)
    refund_bank_name = models.CharField(max_length=100, blank=True, default='')
    refund_account_number = models.CharField(max_length=100, blank=True, default='')
    refund_account_holder = models.CharField(max_length=100, blank=True, default='')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_cancellations')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationTemplate(models.Model):
    CHANNEL_CHOICES = [('email', 'Email'), ('line', 'LINE'), ('in_app', '站內通知')]
    EVENT_CHOICES = [
        ('order_created', '訂單成立'), ('payment_confirmed', '付款完成'),
        ('pre_course', '課前提醒'), ('missing_documents', '資料未完成'),
        ('line_group', 'LINE 群組邀請'), ('evaluation_due', '評量未完成'),
    ]
    client = models.ForeignKey('Client.Client', on_delete=models.CASCADE, related_name='notification_templates')
    campus = models.ForeignKey('Resorts.Campus', on_delete=models.CASCADE, null=True, blank=True, related_name='notification_templates')
    name = models.CharField(max_length=100)
    event = models.CharField(max_length=30, choices=EVENT_CHOICES)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    subject = models.CharField(max_length=200, blank=True, default='')
    body = models.TextField()
    days_before = models.IntegerField(default=0, help_text='課前幾天；事件立即發送請填 0')
    course_templates = models.ManyToManyField('Coursekit.CourseTemplate', blank=True, related_name='notification_templates')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationDelivery(models.Model):
    STATUS_CHOICES = [('scheduled', '已排程'), ('sent', '已發送'), ('failed', '發送失敗'), ('cancelled', '已取消')]
    template = models.ForeignKey(NotificationTemplate, on_delete=models.PROTECT, related_name='deliveries')
    group = models.ForeignKey(ReservationGroup, on_delete=models.CASCADE, related_name='notification_deliveries')
    recipient = models.CharField(max_length=200)
    scheduled_at = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    error_message = models.TextField(blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CourseEvaluation(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='evaluations')
    member = models.ForeignKey(MemberDetail, on_delete=models.CASCADE, related_name='evaluations')
    coach = models.ForeignKey('Coach.Coach', on_delete=models.SET_NULL, null=True, blank=True, related_name='course_evaluations')
    self_assessment = models.JSONField(default=dict, blank=True)
    coach_assessment = models.JSONField(default=dict, blank=True)
    learning_progress = models.JSONField(default=dict, blank=True)
    trail_names = models.JSONField(default=list, blank=True)
    coach_notes = models.TextField(blank=True, default='')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('booking', 'member')


class CourseMedia(models.Model):
    evaluation = models.ForeignKey(CourseEvaluation, on_delete=models.CASCADE, related_name='media')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    media_type = models.CharField(max_length=10, choices=[('photo', '照片'), ('video', '影片')])
    url = models.URLField(max_length=800)
    caption = models.CharField(max_length=200, blank=True, default='')
    is_public = models.BooleanField(default=False, verbose_name='可於官網顯示')
    created_at = models.DateTimeField(auto_now_add=True)


class StaffBookingLink(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client = models.ForeignKey('Client.Client', on_delete=models.CASCADE, related_name='staff_booking_links')
    campus = models.ForeignKey('Resorts.Campus', on_delete=models.PROTECT, related_name='staff_booking_links')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='staff_booking_links')
    title = models.CharField(max_length=120, blank=True, default='')
    cart_snapshot = models.JSONField(default=list)
    expires_at = models.DateTimeField()
    used_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='used_staff_booking_links')
    used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_available(self):
        return self.is_active and not self.used_at and self.expires_at > timezone.now()

@receiver(user_signed_up)
def user_signed_up_callback(request, user, **kwargs):
    # 在这里可以自定义用户创建后的操作
    # 例如，自动将用户添加到某个组或设置某些默认值
    pass

def get_booked_slots(self):
    """
    获取教练的预订信息，返回格式化的字典。
    过滤掉没有指定教练的预订。
    """
    bookings = Booking.objects.filter(reservation__preferred_coach=self)
    booked_slots = {}
    for booking in bookings:
        date_str = booking.date.strftime("%Y-%m-%d")
        if date_str not in booked_slots:
            booked_slots[date_str] = []
        booked_slots[date_str].append({
            "start_time": booking.start_time.strftime("%H:%M"),
            "end_time": booking.end_time.strftime("%H:%M"),
            "course_type": booking.course_type
        })
    return booked_slots
