from django.contrib import admin
from .models import Client, ModuleInfo, ModuleSetting, PageInfo, PageColor, SiteContent


class PlatformOnlyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    has_add_permission = has_view_permission
    has_change_permission = has_view_permission
    has_delete_permission = has_view_permission


class ModuleSettingInline(admin.TabularInline):
    """在 Client 管理頁面內嵌顯示模組設定"""
    model = ModuleSetting
    extra = 0
    fields = ['module', 'is_active', 'settings']
    autocomplete_fields = ['module']
    verbose_name = '模組設定'
    verbose_name_plural = '功能模組管理'


@admin.register(Client)
class ClientAdmin(PlatformOnlyAdmin):
    def get_readonly_fields(self, request, obj=None):
        return list(self.readonly_fields) + (['internal_code'] if obj else [])

    list_display = [
        'internal_code',
        'name',
        'sales',
        'program',
        'service_end_date',
        'service_status',
        'is_active',
        'created_at'
    ]
    list_filter = [
        'is_active',
        'program',
        'sales',
        'created_at',
        'service_start_date',
        'service_end_date',
    ]
    search_fields = [
        'name',
        'internal_code',
        'sales',
        'company_name',
        'company_tax_id'
    ]
    readonly_fields = ['created_at', 'updated_at']

    # 加入 inline 模組設定
    inlines = [ModuleSettingInline]

    # 列表頁面優化
    list_per_page = 25
    date_hierarchy = 'created_at'

    fieldsets = (
        ('基本資訊', {
            'fields': ('name', 'internal_code', 'is_active', 'password')
        }),
        ('業務與方案', {
            'fields': ('sales', 'program', 'logo_url')
        }),
        ('公司資訊', {
            'fields': ('company_name', 'company_tax_id', 'company_address', 'company_phone', 'company_email'),
            'classes': ('collapse',),
        }),
        ('服務期限', {
            'fields': ('service_start_date', 'service_end_date', 'expiry_reminder_days'),
            'description': '到期僅提示，不會自動停用或中斷既有課程。需由平台管理者人工處理。'
        }),
        ('登入與金流設定', {'fields': ('google_oauth_client_id', 'payment_env_prefix'), 'description': 'Google 可沿用平台登入。金流只填此校的環境變數前綴；密鑰不存於此表單。'}),
        ('時間記錄', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )



@admin.register(ModuleInfo)
class ModuleInfoAdmin(PlatformOnlyAdmin):
    list_display = ['module_sid', 'module_name', 'description', 'is_active']
    list_filter = ['is_active']
    search_fields = ['module_sid', 'module_name', 'description']  # 支援 autocomplete
    list_editable = ['is_active']  # 可直接在列表編輯
    ordering = ['module_sid']
    list_per_page = 50

    fieldsets = (
        ('基本資訊', {
            'fields': ('module_sid', 'module_name', 'is_active')
        }),
        ('詳細說明', {
            'fields': ('description',)
        }),
    )


@admin.register(ModuleSetting)
class ModuleSettingAdmin(PlatformOnlyAdmin):
    list_display = ['client', 'module', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'module', 'created_at']
    search_fields = ['client__name', 'client__internal_code', 'module__module_name']
    autocomplete_fields = ['client', 'module']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active']  # 可直接在列表編輯
    date_hierarchy = 'created_at'
    list_per_page = 50

    fieldsets = (
        ('基本設定', {
            'fields': ('client', 'module', 'is_active')
        }),
        ('模組特定設定', {
            'fields': ('settings',),
            'classes': ('collapse',),
            'description': (
                '此客戶對該模組的特定配置（JSON 格式）。在 booking 模組的設定加入 '
                'learner_rename_policy，可填 disabled（停用）、unlinked_only（僅限未連結有效名額）'
                '或 owner_all（所有本人學員檔案）。預設為 disabled。'
                '入帳日期請編輯該租戶的 booking 設定列，在 JSON 中加入 '
                '"manual_payment_posting_date_mode"，值可填 "optional"（選填，預設）、'
                '"required"（必填）或 "disabled"（停用輸入，保留已存日期）。'
                '客人來源補登預設開啟。可加入 "order_source_override_enabled": false 關閉編輯，'
                '已補登的來源仍供訂單明細與統計使用。'
                '共用相簿可在 booking 設定加入 "course_album_coach_delete_enabled": false，'
                '關閉現任授課教練刪除本人上傳附件的權限。預設開啟。'
                '在 booking 設定加入 "test_order_marking_enabled": false 可停用測試訂單標記操作。預設開啟。'
                '後台學習評量的 booking 設定可用 "evaluation_date_filters_enabled": false 還原原清單。'
                '"evaluation_default_date_field" 可填 "ordered"（下單日期，預設）或 "lesson"（上課日期）。'
                '"evaluation_default_date_range_days" 可填 1 至 366 的整數，預設 30 天（含今天）。'
                '在 vehicle_review 模組的設定加入 vehicle_conflict_mode，可填 manual_review（預設）、'
                'block（同手動審核）或 auto_revoke（尚未實作，視同 manual_review）。'
                '同一模組可加入 "vehicle_calendar_visible_to_coaches": false，關閉教練的車輛行事曆。'
                '使用 JSON 布林值 true／false，缺少、空白或無效值皆預設開啟。'
                '數字 0 與文字 false、off、no、0 也視為關閉。'
            ),
        }),
        ('時間記錄', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PageInfo)
class PageInfoAdmin(PlatformOnlyAdmin):
    list_display = ['page_sid', 'page_name', 'description']
    search_fields = ['page_sid', 'page_name', 'description']  # 支援 autocomplete
    ordering = ['page_sid']
    list_per_page = 50

    fieldsets = (
        ('基本資訊', {
            'fields': ('page_sid', 'page_name')
        }),
        ('詳細說明', {
            'fields': ('description',)
        }),
    )


@admin.register(PageColor)
class PageColorAdmin(PlatformOnlyAdmin):
    list_display = [
        'client',
        'page',
        'color_primary',
        'color_secondary',
        'color_tertiary',
        'updated_at'
    ]
    list_filter = ['page', 'updated_at']
    search_fields = ['client__name', 'client__internal_code', 'page__page_name']
    autocomplete_fields = ['client', 'page']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'updated_at'
    list_per_page = 50

    fieldsets = (
        ('基本設定', {
            'fields': ('client', 'page')
        }),
        ('顏色配置', {
            'fields': (
                'color_primary',
                'color_secondary',
                'color_tertiary',
                'color_background',
                'color_text',
            ),
            'description': '設定頁面的色彩方案（格式：#RRGGBB）'
        }),
        ('時間記錄', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SiteContent)
class SiteContentAdmin(PlatformOnlyAdmin):
    list_display = [
        'client',
        'content_type',
        'location_key',
        'title',
        'status',
        'computed_status',
        'start_at',
        'end_at',
        'display_order',
        'updated_at',
    ]
    list_filter = ['content_type', 'status', 'location_key', 'updated_at']
    search_fields = ['client__name', 'client__internal_code', 'location_key', 'title', 'subtitle', 'body', 'tags']
    autocomplete_fields = ['client']
    readonly_fields = ['created_at', 'updated_at', 'computed_status']
    list_editable = ['status', 'display_order']
    date_hierarchy = 'updated_at'
    list_per_page = 50

    fieldsets = (
        ('顯示位置', {
            'fields': ('client', 'content_type', 'location_key', 'status', 'computed_status')
        }),
        ('內容', {
            'fields': ('title', 'subtitle', 'summary', 'body', 'image_url', 'link_url')
        }),
        ('分類與期間', {
            'fields': ('source', 'external_id', 'tags', 'metadata', 'start_at', 'end_at', 'display_order', 'is_pinned')
        }),
        ('時間記錄', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
