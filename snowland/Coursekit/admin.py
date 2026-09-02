from django.contrib import admin
from .models import CourseCategory, CourseType, CourseTemplate, CourseSession, CoursePricing, SeasonSetting

@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'service_type', 'display_order', 'get_resort_count']
    list_editable = ['service_type', 'display_order']
    list_filter = ['client', 'service_type']
    search_fields = ['name', 'client__name', 'client__internal_code']
    filter_horizontal = ['available_resorts']
    ordering = ['client', 'display_order', 'id']
    autocomplete_fields = ['client']  # 支援 client 搜尋

    fieldsets = (
        ('基本資訊', {
            'fields': ('client', 'name', 'service_type', 'display_order')
        }),
        ('雪場設定', {
            'fields': ('available_resorts',),
            'description': '選擇此課程大類可以在哪些雪場開設'
        }),
    )

    def get_resort_count(self, obj):
        return obj.available_resorts.count()
    get_resort_count.short_description = '適用雪場數量'

@admin.register(CourseType)
class CourseTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'get_client', 'display_order', 'get_resort_count']
    list_editable = ['display_order']
    list_filter = ['category', 'category__client']
    search_fields = ['name', 'category__name', 'category__client__name']
    filter_horizontal = ['available_resorts']
    autocomplete_fields = ['category']
    ordering = ['category__client', 'category__display_order', 'display_order', 'id']

    fieldsets = (
        ('基本資訊', {
            'fields': ('category', 'name', 'display_order')
        }),
        ('雪場設定', {
            'fields': ('available_resorts',),
            'description': '選擇此課程類型可以在哪些雪場開設'
        }),
    )

    def get_client(self, obj):
        return obj.category.client.name if obj.category and obj.category.client else '-'
    get_client.short_description = '所屬客戶'
    get_client.admin_order_field = 'category__client__name'

    def get_resort_count(self, obj):
        return obj.available_resorts.count()
    get_resort_count.short_description = '適用雪場數量'

@admin.register(CourseTemplate)
class CourseTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'course_type', 'get_client', 'display_order', 'duration_hours', 'max_capacity', 'is_active', 'get_session_count']
    list_editable = ['display_order', 'is_active', 'max_capacity']
    list_filter = ['course_type__category__client', 'course_type__category', 'course_type', 'is_active', 'duration_hours']
    search_fields = ['name', 'course_type__name', 'course_type__category__client__name']
    autocomplete_fields = ['course_type']
    ordering = ['course_type__category__client', 'course_type__category__display_order', 'course_type__display_order', 'display_order', 'duration_hours', 'id']
    filter_horizontal = ['resorts']

    fieldsets = (
        ('基本資訊', {
            'fields': ('course_type', 'name', 'display_order', 'duration_hours', 'max_capacity', 'is_active')
        }),
        ('雪場綁定', {
            'fields': ('resorts',),
            'description': '選擇此課程模板可以在哪些雪場使用'
        }),
        ('預約時間設定', {
            'fields': ('booking_open_date', 'booking_close_date', 'course_start_date', 'course_end_date'),
            'classes': ('collapse',)
        }),
    )

    def get_client(self, obj):
        if obj.course_type and obj.course_type.category and obj.course_type.category.client:
            return obj.course_type.category.client.name
        return '-'
    get_client.short_description = '所屬客戶'
    get_client.admin_order_field = 'course_type__category__client__name'

    def get_resort_count(self, obj):
        return obj.resorts.count()
    get_resort_count.short_description = '綁定雪場'

    def get_session_count(self, obj):
        return obj.sessions.count()
    get_session_count.short_description = '時段數'

@admin.register(CourseSession)
class CourseSessionAdmin(admin.ModelAdmin):
    list_display = ['template', 'get_client', 'start_time', 'end_time', 'is_active', 'get_duration']
    list_editable = ['is_active']
    list_filter = ['template__course_type__category__client', 'template__course_type__category', 'template__course_type', 'is_active']
    search_fields = ['template__name', 'template__course_type__category__client__name']
    autocomplete_fields = ['template']
    ordering = ['template__course_type__category__client', 'template__course_type__category__display_order', 'template__course_type__display_order', 'start_time']

    fieldsets = (
        ('基本資訊', {
            'fields': ('template', 'start_time', 'end_time', 'is_active')
        }),
    )

    def get_client(self, obj):
        if obj.template and obj.template.course_type and obj.template.course_type.category:
            return obj.template.course_type.category.client.name
        return '-'
    get_client.short_description = '所屬客戶'

    def get_duration(self, obj):
        if obj.start_time and obj.end_time:
            # 計算時長
            start_minutes = obj.start_time.hour * 60 + obj.start_time.minute
            end_minutes = obj.end_time.hour * 60 + obj.end_time.minute
            duration_minutes = end_minutes - start_minutes
            hours = duration_minutes // 60
            minutes = duration_minutes % 60
            if minutes > 0:
                return f"{hours}小時{minutes}分鐘"
            else:
                return f"{hours}小時"
        return "未設定"
    get_duration.short_description = '時長'

@admin.register(CoursePricing)
class CoursePricingAdmin(admin.ModelAdmin):
    list_display = ['get_templates_display', 'get_client', 'resort', 'base_price_off_peak', 'peak_season_surcharge', 'additional_person_fee', 'max_capacity', 'is_active']
    list_editable = ['is_active']
    list_filter = ['templates__course_type__category__client', 'templates__course_type__category', 'templates__course_type', 'resort', 'is_active']
    search_fields = ['templates__name', 'resort__display_name', 'templates__course_type__category__client__name']
    ordering = ['resort__display_name', 'id']
    filter_horizontal = ['templates']

    fieldsets = (
        ('基本資訊', {
            'fields': ('templates', 'resort', 'is_active')
        }),
        ('價格設定', {
            'fields': ('base_price_off_peak', 'peak_season_surcharge', 'additional_person_fee'),
            'description': '淡季基礎價格 + 旺季加價 + 每增加一人費用'
        }),
        ('容量設定', {
            'fields': ('max_capacity',)
        }),
    )

    def get_client(self, obj):
        """顯示所屬客戶（從 templates 取得）"""
        templates = obj.templates.all()
        if templates.exists():
            first_template = templates.first()
            if first_template.course_type and first_template.course_type.category:
                return first_template.course_type.category.client.name
        return '-'
    get_client.short_description = '所屬客戶'

    def get_templates_display(self, obj):
        """顯示適用的課程模板"""
        templates = obj.templates.all()
        if templates.count() == 0:
            return "無模板"
        elif templates.count() <= 2:
            return ", ".join([t.name for t in templates])
        else:
            return f"{templates[0].name}, {templates[1].name} 等{templates.count()}個"
    get_templates_display.short_description = '適用模板'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            'templates__course_type__category__client',
            'templates__course_type__category',
            'templates__course_type'
        ).select_related('resort')

@admin.register(SeasonSetting)
class SeasonSettingAdmin(admin.ModelAdmin):
    list_display = ['name', 'season_type', 'start_date', 'end_date', 'get_duration_days']
    list_editable = ['season_type']
    list_filter = ['season_type']
    search_fields = ['name']
    ordering = ['start_date']
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('name', 'season_type')
        }),
        ('時間設定', {
            'fields': ('start_date', 'end_date')
        }),
    )
    
    def get_duration_days(self, obj):
        if obj.start_date and obj.end_date:
            delta = obj.end_date - obj.start_date
            return f"{delta.days + 1}天"
        return "未設定"
    get_duration_days.short_description = '持續天數'
