from rest_framework import serializers
from Coursekit.models import CourseCategory, CourseType, CourseTemplate, CourseSession, CoursePricing, CoursePricingTier
from Resorts.models import Resorts, ResortFee
from Coach.models import Coach, CoachResort, CoachCourseLevel


class ResortSerializer(serializers.ModelSerializer):
    """雪場序列化器"""
    class Meta:
        model = Resorts
        fields = ['id', 'name', 'display_name', 'auto_scheduling_enabled']


class CourseCategorySerializer(serializers.ModelSerializer):
    """課程大類序列化器"""
    available_resorts = serializers.SerializerMethodField()

    class Meta:
        model = CourseCategory
        fields = ['id', 'name', 'service_type', 'display_order', 'available_resorts']

    def get_available_resorts(self, obj):
        """返回可用雪場的顯示名稱列表"""
        return [resort.display_name for resort in obj.available_resorts.all()]


class CourseTypeSerializer(serializers.ModelSerializer):
    """課程類型序列化器"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    available_resorts = serializers.SerializerMethodField()

    class Meta:
        model = CourseType
        fields = ['id', 'name', 'category', 'category_name', 'display_order', 'available_resorts']

    def get_available_resorts(self, obj):
        """返回可用雪場的顯示名稱列表"""
        return [resort.display_name for resort in obj.available_resorts.all()]


class CourseSessionSerializer(serializers.ModelSerializer):
    """課程時段序列化器"""
    class Meta:
        model = CourseSession
        fields = ['id', 'start_time', 'end_time', 'is_active']


class CourseTemplateSerializer(serializers.ModelSerializer):
    """課程模板序列化器"""
    course_type_name = serializers.CharField(source='course_type.name', read_only=True)
    category_name = serializers.CharField(source='course_type.category.name', read_only=True)
    resorts = ResortSerializer(many=True, read_only=True)
    sessions = CourseSessionSerializer(many=True, read_only=True)

    class Meta:
        model = CourseTemplate
        fields = [
            'id', 'name', 'course_type', 'course_type_name', 'category_name',
            'display_order', 'duration_hours', 'max_capacity', 'is_active',
            'booking_open_date', 'booking_close_date',
            'course_start_date', 'course_end_date',
            'resorts', 'sessions'
        ]


class CoursePricingSerializer(serializers.ModelSerializer):
    """課程定價序列化器"""
    resort_name = serializers.CharField(source='resort.display_name', read_only=True)
    templates = CourseTemplateSerializer(many=True, read_only=True)
    people_tiers = serializers.SerializerMethodField()

    class Meta:
        model = CoursePricing
        fields = [
            'id', 'resort', 'resort_name', 'templates',
            'base_price_off_peak', 'peak_season_surcharge',
            'additional_person_fee', 'max_capacity', 'people_tiers', 'is_active'
        ]

    def get_people_tiers(self, obj):
        return [
            {
                'id': tier.id,
                'min_people': tier.min_people,
                'max_people': tier.max_people,
                'price': tier.price,
                'is_active': tier.is_active,
                'display_order': tier.display_order,
            }
            for tier in obj.people_tiers.all()
        ]


class CoachSerializer(serializers.ModelSerializer):
    """教練序列化器"""
    languages = serializers.ListField(child=serializers.CharField(), source='languages')

    class Meta:
        model = Coach
        fields = ['id', 'name', 'languages', 'img', 'availability_status']

    def to_representation(self, instance):
        """自訂輸出格式"""
        data = super().to_representation(instance)
        # 將 languages 從資料庫格式轉換為列表
        if isinstance(data['languages'], str):
            data['languages'] = data['languages'].split(',') if data['languages'] else []
        return data
