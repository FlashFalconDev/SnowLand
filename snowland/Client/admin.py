from django.contrib import admin
from .models import Client, ModuleInfo, ModuleSetting, PageInfo, PageColor, SiteContent


class ModuleSettingInline(admin.TabularInline):
    """在 Client 管理頁面內嵌顯示模組設定"""
    model = ModuleSetting
    extra = 0
    fields = ['module', 'is_active', 'settings']
    autocomplete_fields = ['module']
    verbose_name = '模組設定'
    verbose_name_plural = '功能模組管理'


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = [
        'internal_code',
        'name',
        'sales',
        'program',
        'service_end_date',
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
            'fields': ('service_start_date', 'service_end_date'),
            'description': '設定客戶的服務合約期間'
        }),
        ('時間記錄', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )



@admin.register(ModuleInfo)
class ModuleInfoAdmin(admin.ModelAdmin):
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
class ModuleSettingAdmin(admin.ModelAdmin):
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
            'description': '此客戶對該模組的特定配置（JSON 格式）'
        }),
        ('時間記錄', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PageInfo)
class PageInfoAdmin(admin.ModelAdmin):
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
class PageColorAdmin(admin.ModelAdmin):
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
class SiteContentAdmin(admin.ModelAdmin):
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
