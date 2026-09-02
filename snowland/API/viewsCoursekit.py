from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.db.models import Q

from Coursekit.models import (
    CourseCategory, CourseType, CourseTemplate,
    CourseSession, CoursePricing
)
from Resorts.models import Resorts
from Coach.models import Coach, CoachResort, CoachCourseLevel
from .serializers import (
    CourseCategorySerializer, CourseTypeSerializer,
    CourseTemplateSerializer, CourseSessionSerializer,
    CoursePricingSerializer, ResortSerializer, CoachSerializer
)


class CourseCategoryListView(generics.ListAPIView):
    """課程大類列表 API"""
    queryset = CourseCategory.objects.all().prefetch_related('available_resorts')
    serializer_class = CourseCategorySerializer


class ResortListView(generics.ListAPIView):
    """雪場列表 API"""
    queryset = Resorts.objects.all()
    serializer_class = ResortSerializer


class CourseTypeListView(generics.ListAPIView):
    """課程類型列表 API"""
    serializer_class = CourseTypeSerializer

    def get_queryset(self):
        queryset = CourseType.objects.all().select_related('category').prefetch_related('available_resorts')

        # 支援依課程大類篩選
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # 支援依雪場篩選（只返回該雪場有的課程類型）
        resort = self.request.query_params.get('resort')
        if resort:
            # 根據雪場的 name 過濾（前端傳的是 name，不是 id）
            queryset = queryset.filter(available_resorts__name=resort)

        return queryset


class CourseTemplateListView(generics.ListAPIView):
    """課程模板列表 API"""
    serializer_class = CourseTemplateSerializer

    def get_queryset(self):
        queryset = CourseTemplate.objects.filter(
            is_active=True
        ).select_related(
            'course_type', 'course_type__category'
        ).prefetch_related(
            'resorts', 'sessions'
        )

        # 支援依課程類型篩選
        course_type_id = self.request.query_params.get('course_type_id')
        if course_type_id:
            queryset = queryset.filter(course_type_id=course_type_id)

        # 支援依雪場篩選
        resort = self.request.query_params.get('resort')
        if resort:
            queryset = queryset.filter(resorts__name=resort)

        return queryset


class CourseSessionListView(generics.ListAPIView):
    """課程時段列表 API"""
    serializer_class = CourseSessionSerializer

    def get_queryset(self):
        queryset = CourseSession.objects.filter(is_active=True)

        # 支援依課程模板篩選
        template_id = self.request.query_params.get('template_id')
        if template_id:
            queryset = queryset.filter(template_id=template_id)

        return queryset


@api_view(['GET'])
def calculate_price(request):
    """
    計算課程價格 API

    參數：
    - template_id: 課程模板 ID
    - resort: 雪場名稱
    - people_count: 人數
    - course_date: 日期 (YYYY-MM-DD)，用於判斷淡旺季
    """
    from Coursekit.models import SeasonSetting
    from datetime import datetime

    try:
        template_id = request.GET.get('template_id')
        resort_name = request.GET.get('resort')
        people_count = int(request.GET.get('people_count', 1))
        date_str = request.GET.get('course_date')

        if not all([template_id, resort_name]):
            return Response(
                {'error': '缺少必要參數: template_id, resort'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 獲取課程模板和雪場（用名稱查詢）
        template = CourseTemplate.objects.get(id=template_id)
        resort = Resorts.objects.get(name=resort_name)

        # 獲取定價策略
        pricing = CoursePricing.objects.filter(
            templates=template,
            resort=resort,
            is_active=True
        ).first()

        if not pricing:
            return Response(
                {'error': '找不到對應的定價策略'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 判斷淡旺季
        is_peak_season = False
        if date_str:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            season_type = SeasonSetting.get_season_type_for_date(date_obj)
            is_peak_season = (season_type == 'peak')

        # 計算價格
        price = pricing.calculate_price(people_count, is_peak_season)

        # 回傳前端期望的格式
        return Response({
            'price': price,
            'course_type_name': template.course_type.name,
            'course_template_name': template.name,
            'duration_hours': template.duration_hours,
            # 額外資訊
            'resort_name': resort.display_name,
            'people_count': people_count,
            'is_peak_season': is_peak_season,
            'base_price': pricing.base_price_off_peak,
            'peak_surcharge': pricing.peak_season_surcharge if is_peak_season else 0,
            'additional_person_fee': pricing.additional_person_fee,
            'total_price': price
        })

    except CourseTemplate.DoesNotExist:
        return Response(
            {'error': '找不到指定的課程模板'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Resorts.DoesNotExist:
        return Response(
            {'error': '找不到指定的雪場'},
            status=status.HTTP_404_NOT_FOUND
        )
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'計算價格時發生錯誤: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CoachListView(generics.ListAPIView):
    """教練列表 API"""
    serializer_class = CoachSerializer

    def get_queryset(self):
        queryset = Coach.objects.filter(availability_status='active')

        # 支援依雪場篩選
        resort = self.request.query_params.get('resort')
        if resort:
            # 根據雪場名稱篩選教練
            queryset = queryset.filter(
                coachresort__resort__name=resort
            ).distinct()

        # 支援依課程類型篩選
        course_type = self.request.query_params.get('courseType')
        if course_type:
            queryset = queryset.filter(
                course_levels__course_type_id=course_type
            ).distinct()

        # 支援依能力等級篩選
        ability_level = self.request.query_params.get('abilityLevel')
        if ability_level:
            queryset = queryset.filter(
                course_levels__ability_levels__contains=ability_level
            ).distinct()

        return queryset

    def list(self, request, *args, **kwargs):
        """自訂列表輸出，加入 price_level 資訊"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # 為每個教練加入 price_level 資訊
        data = serializer.data
        for coach_data in data:
            coach_id = coach_data['id']
            # 獲取教練的價格等級（取第一個）
            course_level = CoachCourseLevel.objects.filter(
                coach_id=coach_id
            ).first()
            coach_data['price_level'] = course_level.price_level if course_level else 'Lv1'

        return Response(data)
