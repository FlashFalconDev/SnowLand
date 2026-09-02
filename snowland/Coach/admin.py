from django.contrib import admin
from .models import Coach, CoachResort, CoachCourseLevel, CoachLeaveRequest, ABILITY_LEVEL_CHOICES

@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'availability_status', 'created_at']

@admin.register(CoachResort)
class CoachResortAdmin(admin.ModelAdmin):
    list_display = ['id', 'coach_name', 'resort_zh', 'resort_priority', 'assignment_score', 'created_at']

    def coach_name(self, obj):
        # 只顯示教練名稱
        return obj.coach.name
    coach_name.short_description = '教練'

    def resort_zh(self, obj):
        # 修正：直接從關聯的 Resorts 物件獲取顯示名稱
        if obj.resort:
            return obj.resort.display_name
        return "N/A" # 或者其他你認為合適的預設值
    resort_zh.short_description = '雪場'

@admin.register(CoachCourseLevel)
class CoachCourseLevelAdmin(admin.ModelAdmin):
    list_display = ['id', 'coach', 'ability_levels', 'price_level']

@admin.register(CoachLeaveRequest)
class CoachLeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'coach_name', 'date_range', 'status', 'created_at', 'reviewed_by_name', 'reviewed_at']
    list_filter = ['status', 'created_at', 'reviewed_at']
    search_fields = ['coach__name', 'reason']
    readonly_fields = ['created_at', 'updated_at']
    
    def coach_name(self, obj):
        return obj.coach.name
    coach_name.short_description = '教練'
    
    def date_range(self, obj):
        return f"{obj.start_date} ~ {obj.end_date}"
    date_range.short_description = '請假日期'
    
    def reviewed_by_name(self, obj):
        return obj.reviewed_by.get_full_name() if obj.reviewed_by else '未審核'
    reviewed_by_name.short_description = '審核人'
