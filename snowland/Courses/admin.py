from django.contrib import admin
from .models import CourseType, CourseTemplate, Course, SeasonSetting, CoursePricingStrategy

@admin.register(CourseType)
class CourseTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order')
    search_fields = ('name',)
    ordering = ('display_order', 'name')

@admin.register(CourseTemplate)
class CourseTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_type', 'duration', 'is_active')
    list_filter = ('course_type', 'is_active')
    search_fields = ('name',)
    ordering = ('course_type', 'name')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    # 移除 period 與 total_time，避免在管理後台直接依賴欲淘汰欄位
    list_display = ('template', 'date_range', 'get_need_equipment')
    list_filter = ('template__course_type', 'template')
    search_fields = ('template__name',)
    raw_id_fields = ('template',)
    ordering = ('template__course_type', 'template')
    
    def get_need_equipment(self, obj):
        """從course_specific_info中獲取need_equipment狀態"""
        return obj.course_specific_info.get('need_equipment', False)
    get_need_equipment.boolean = True
    get_need_equipment.short_description = '需要裝備'

@admin.register(SeasonSetting)
class SeasonSettingAdmin(admin.ModelAdmin):
    list_display = ('name', 'season_type', 'start_date', 'end_date')
    list_filter = ('season_type',)
    search_fields = ('name',)
    ordering = ('start_date',)

@admin.register(CoursePricingStrategy)
class CoursePricingStrategyAdmin(admin.ModelAdmin):
    list_display = ('template', 'resort', 'base_price_off_peak', 'peak_season_surcharge', 'additional_person_fee', 'max_capacity', 'is_active')
    list_filter = ('template__course_type', 'resort', 'is_active')
    search_fields = ('template__course_type__name', 'resort__display_name')
    raw_id_fields = ('template', 'resort')
    ordering = ('template__course_type', 'resort', 'is_active')
