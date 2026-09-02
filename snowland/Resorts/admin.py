from django.contrib import admin
from .models import *

class ResortFeeInline(admin.TabularInline):
    """在雪場管理頁面中內嵌顯示費用設定"""
    model = ResortFee
    extra = 0  # 不顯示額外的空行
    fields = ('fee_type', 'price', 'is_active', 'description')
    
    def get_queryset(self, request):
        """只顯示啟用的費用設定"""
        return super().get_queryset(request).filter(is_active=True)

class EquipmentAssistanceTimeSlotInline(admin.TabularInline):
    model = EquipmentAssistanceTimeSlot
    extra = 0
    fields = (
        'equipment_option', 'lesson_duration', 'session_period', 'day_type',
        'label', 'start_time', 'end_time', 'is_active', 'display_order', 'description',
    )


class EquipmentRentalItemInline(admin.TabularInline):
    model = EquipmentRentalItem
    extra = 0
    fields = ('code', 'name', 'daily_price', 'additional_day_price', 'is_active', 'display_order', 'description')


@admin.register(Resorts)
class ResortsAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'auto_scheduling_enabled', 'get_fee_count']
    list_filter = ['auto_scheduling_enabled']
    search_fields = ['name', 'display_name']
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('name', 'display_name', 'auto_scheduling_enabled')
        }),
    )
    
    inlines = [ResortFeeInline, EquipmentRentalItemInline, EquipmentAssistanceTimeSlotInline]
    
    def get_fee_count(self, obj):
        """顯示該雪場的費用設定數量"""
        count = obj.fees.filter(is_active=True).count()
        return f"{count} 個費用設定"
    get_fee_count.short_description = '費用設定數量'

@admin.register(ResortFee)
class ResortFeeAdmin(admin.ModelAdmin):
    list_display = ['resort', 'fee_type', 'price', 'is_active', 'created_at']
    list_filter = ['resort', 'fee_type', 'is_active', 'created_at']
    search_fields = ['resort__name', 'resort__display_name', 'fee_type']
    list_editable = ['price', 'is_active']
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('resort', 'fee_type', 'price', 'is_active')
        }),
        ('詳細說明', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('時間資訊', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """優化查詢，預先載入雪場資訊"""
        return super().get_queryset(request).select_related('resort')


@admin.register(EquipmentAssistanceTimeSlot)
class EquipmentAssistanceTimeSlotAdmin(admin.ModelAdmin):
    list_display = [
        'resort', 'equipment_option', 'lesson_duration', 'session_period',
        'day_type', 'label', 'start_time', 'end_time', 'is_active', 'display_order',
    ]
    list_filter = ['resort', 'equipment_option', 'lesson_duration', 'session_period', 'day_type', 'is_active']
    search_fields = ['resort__name', 'resort__display_name', 'label']
    list_editable = ['is_active', 'display_order']
    filter_horizontal = ['course_templates']


@admin.register(EquipmentRentalItem)
class EquipmentRentalItemAdmin(admin.ModelAdmin):
    list_display = ['resort', 'code', 'name', 'daily_price', 'additional_day_price', 'is_active', 'display_order']
    list_filter = ['resort', 'is_active']
    search_fields = ['resort__name', 'resort__display_name', 'code', 'name']
    list_editable = ['daily_price', 'additional_day_price', 'is_active', 'display_order']
