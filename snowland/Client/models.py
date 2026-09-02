from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password
from django.utils import timezone
from datetime import timedelta
import hashlib


def one_month_later():
    """預設服務期限：一個月後"""
    return timezone.now() + timedelta(days=30)


class Client(models.Model):
    """
    客戶/平台模型
    代表使用本系統的不同客戶（例如：雪域創遊、其他滑雪學校等）
    整合了 FFSystem 的完整客戶管理功能
    """

    # ========== 基本資訊 ==========
    name = models.CharField(
        max_length=200,
        verbose_name='客戶名稱',
        help_text='客戶的顯示名稱'
    )
    internal_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='內部代碼',
        help_text='用於系統內部識別的唯一代碼（client_sid）'
    )

    # ========== 密碼管理 ==========
    password = models.CharField(
        max_length=128,
        blank=True,
        verbose_name='密碼',
        help_text='客戶登入密碼（加密儲存）'
    )

    # ========== 業務資訊 ==========
    sales = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='業務負責人'
    )
    program = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='方案名稱'
    )

    # ========== 品牌資訊 ==========
    logo_url = models.URLField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Logo URL'
    )


    # ========== 公司資訊（整合 CompanyInfo）==========
    company_tax_id = models.CharField(
        max_length=10,
        blank=True,
        default='',
        verbose_name='公司統編'
    )
    company_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='公司全名'
    )
    company_address = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='公司地址'
    )
    company_phone = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='公司電話'
    )
    company_email = models.EmailField(
        blank=True,
        null=True,
        verbose_name='公司 Email'
    )

    # ========== 收款銀行資訊 ==========
    bank_name = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='銀行名稱', help_text='收款用銀行名稱，例如：台灣銀行'
    )
    bank_branch = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='分行名稱', help_text='例如：信義分行'
    )
    bank_account_number = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='銀行帳號', help_text='收款帳號'
    )
    bank_account_holder = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='帳戶戶名', help_text='收款戶名'
    )

    # ========== 服務期限 ==========
    service_start_date = models.DateTimeField(
        auto_now=False,
        default=timezone.now,
        verbose_name='服務開始日期'
    )
    service_end_date = models.DateTimeField(
        auto_now=False,
        default=one_month_later,
        verbose_name='服務結束日期'
    )

    # ========== 狀態 ==========
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否啟用'
    )

    # ========== 時間戳記 ==========
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='建立時間'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新時間'
    )

    class Meta:
        verbose_name = '客戶'
        verbose_name_plural = '1. 客戶管理'
        ordering = ['name']

    def __str__(self):
        return f"{self.internal_code} | {self.name}"

    # ========== 密碼管理方法 ==========
    def save(self, *args, **kwargs):
        """保存時自動處理密碼"""
        # 如果沒有密碼，自動生成（使用 internal_code 的 hash）
        if not self.password:
            raw_password = hashlib.sha256(
                self.internal_code.encode()
            ).hexdigest()[:16]
            self.password = make_password(raw_password)
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        """設定密碼（加密）"""
        self.password = make_password(raw_password)
        return self.password

    def check_password(self, raw_password):
        """驗證密碼"""
        return django_check_password(raw_password, self.password)


class ModuleInfo(models.Model):
    """
    模組資訊
    定義系統中可用的功能模組
    """
    module_sid = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='模組 ID'
    )
    module_name = models.CharField(
        max_length=50,
        verbose_name='模組名稱'
    )
    description = models.TextField(
        blank=True,
        verbose_name='模組描述'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否啟用'
    )

    class Meta:
        verbose_name = '模組資訊'
        verbose_name_plural = '2-1. 模組資訊'
        ordering = ['module_sid']

    def __str__(self):
        return f"{self.module_sid} - {self.module_name}"


class ModuleSetting(models.Model):
    """
    模組設定
    管理每個客戶啟用了哪些模組
    """
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='module_settings',
        verbose_name='客戶'
    )
    module = models.ForeignKey(
        ModuleInfo,
        on_delete=models.CASCADE,
        related_name='client_settings',
        verbose_name='模組'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否啟用'
    )
    settings = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='模組特定設定',
        help_text='此客戶對該模組的特定配置'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='建立時間'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新時間'
    )

    class Meta:
        verbose_name = '模組設定'
        verbose_name_plural = '2-2. 模組設定'
        unique_together = (('client', 'module'),)  # ✅ 修正：放在 Meta 裡面
        ordering = ['client', 'module']

    def __str__(self):
        return f"{self.client.name} - {self.module.module_name} ({'啟用' if self.is_active else '停用'})"


class PageInfo(models.Model):
    """
    頁面資訊
    定義系統中可以自訂的頁面
    """
    page_sid = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='頁面 ID'
    )
    page_name = models.CharField(
        max_length=50,
        verbose_name='頁面名稱'
    )
    description = models.TextField(
        blank=True,
        verbose_name='頁面描述'
    )

    class Meta:
        verbose_name = '頁面資訊'
        verbose_name_plural = '3-1. 頁面資訊'
        ordering = ['page_sid']

    def __str__(self):
        return f"{self.page_sid} - {self.page_name}"


class PageColor(models.Model):
    """
    頁面顏色設定
    管理每個客戶的頁面色彩配置
    """
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='page_colors',
        verbose_name='客戶'
    )
    page = models.ForeignKey(
        PageInfo,
        on_delete=models.CASCADE,
        related_name='client_colors',
        verbose_name='頁面'
    )
    color_primary = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name='主色',
        help_text='例如：#1E40AF'
    )
    color_secondary = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name='副色'
    )
    color_tertiary = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name='強調色'
    )
    color_background = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name='背景色'
    )
    color_text = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name='文字色'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='建立時間'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新時間'
    )

    class Meta:
        verbose_name = '頁面顏色設定'
        verbose_name_plural = '3-2. 頁面顏色設定'
        unique_together = (('client', 'page'),)  # ✅ 修正：放在 Meta 裡面
        ordering = ['client', 'page']

    def __str__(self):
        return f"{self.client.name} - {self.page.page_name}"


class SiteContent(models.Model):
    """
    官網可編輯內容。

    用一張通用表先支援首頁、優惠、文章、FAQ、作品集與社群貼文等簡單 CMS 需求。
    """
    CONTENT_TYPE_CHOICES = [
        ('page', '頁面內容'),
        ('offer', '限定優惠'),
        ('article', '攻略/文章'),
        ('faq', '常見問題'),
        ('review', '學生評價'),
        ('media', '攝影作品'),
        ('social', '社群動態'),
        ('setting', '區塊設定'),
    ]
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('active', '進行中'),
        ('ended', '已結束'),
        ('hidden', '隱藏'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='site_contents',
        verbose_name='客戶',
    )
    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        db_index=True,
        verbose_name='內容類型',
    )
    location_key = models.CharField(
        max_length=80,
        db_index=True,
        verbose_name='顯示位置',
        help_text='例如 homepage.reviews、news.offers、guides.preparation',
    )
    title = models.CharField(max_length=200, blank=True, default='', verbose_name='標題')
    subtitle = models.CharField(max_length=300, blank=True, default='', verbose_name='副標題')
    summary = models.TextField(blank=True, default='', verbose_name='摘要')
    body = models.TextField(blank=True, default='', verbose_name='內容')
    image_url = models.CharField(max_length=500, blank=True, default='', verbose_name='圖片網址')
    link_url = models.CharField(max_length=500, blank=True, default='', verbose_name='連結網址')
    source = models.CharField(max_length=50, blank=True, default='', verbose_name='來源')
    external_id = models.CharField(max_length=120, blank=True, default='', verbose_name='外部 ID')
    tags = models.JSONField(default=list, blank=True, verbose_name='標籤')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='其他設定')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
        verbose_name='狀態',
    )
    start_at = models.DateTimeField(null=True, blank=True, verbose_name='開始時間')
    end_at = models.DateTimeField(null=True, blank=True, verbose_name='結束時間')
    display_order = models.IntegerField(default=0, verbose_name='排序')
    is_pinned = models.BooleanField(default=False, verbose_name='置頂')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新時間')

    class Meta:
        verbose_name = '官網內容'
        verbose_name_plural = '4-1. 官網內容'
        ordering = ['content_type', 'location_key', '-is_pinned', 'display_order', '-created_at']
        indexes = [
            models.Index(fields=['client', 'content_type', 'location_key', 'status']),
            models.Index(fields=['client', 'end_at']),
        ]

    def __str__(self):
        return f"{self.client.name} - {self.location_key} - {self.title or self.get_content_type_display()}"

    @property
    def computed_status(self):
        now = timezone.now()
        if self.status != 'active':
            return self.status
        if self.start_at and self.start_at > now:
            return 'draft'
        if self.end_at and self.end_at < now:
            return 'ended'
        return 'active'

    @property
    def is_public_visible(self):
        return self.computed_status == 'active'
