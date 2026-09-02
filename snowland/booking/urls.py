from django.urls import path
from . import views
from .api_views import (
    SiteContentListAPI,
    CoachListAPI,
    WebsiteCoachListAPI,
    CoachBookingsAPI,
    CalculatePriceAPI,
    CourseCategoryListAPI,
    ResortListAPI,
    CourseTypeListAPI,
    CourseTemplateListAPI,
    CourseSessionListAPI,
    CourseAvailableDatesAPI,
    DiscountPreviewAPI,
    CreateReservationAPI,
    SuperScheduleAPI,
    PaymentInfoAPI,
    ProcessPaymentAPI,
    ReservationHistoryAPI,
    GoogleLoginAPI,
    CancelFailedReservationsAPI,
)

app_name = 'booking'


urlpatterns = [
    # ========== 指定 client_code 的路由 ==========
    path('<str:client_code>/', views.home, name='home'),
    path('<str:client_code>/payment/', views.payment, name='payment'),

    # ========== 新的 RESTful API 端點（支援 client_code） ==========
    # 資料查詢 API
    path('<str:client_code>/api/course-categories/', CourseCategoryListAPI.as_view(), name='api_course_categories_client'),
    path('<str:client_code>/api/site-content/', SiteContentListAPI.as_view(), name='api_site_content_client'),
    path('<str:client_code>/api/resorts/', ResortListAPI.as_view(), name='api_resorts_client'),
    path('<str:client_code>/api/course-types/', CourseTypeListAPI.as_view(), name='api_course_types_client'),
    path('<str:client_code>/api/course-templates/', CourseTemplateListAPI.as_view(), name='api_course_templates_client'),
    path('<str:client_code>/api/course-sessions/', CourseSessionListAPI.as_view(), name='api_course_sessions_client'),
    path('<str:client_code>/api/course-templates/<int:template_id>/available-dates/', CourseAvailableDatesAPI.as_view(), name='api_course_available_dates_client'),

    # 教練和預約 API
    path('<str:client_code>/api/coaches/', CoachListAPI.as_view(), name='api_coaches_client'),
    path('<str:client_code>/api/website-coaches/', WebsiteCoachListAPI.as_view(), name='api_website_coaches_client'),
    path('<str:client_code>/api/coach-bookings/', CoachBookingsAPI.as_view(), name='api_coach_bookings_client'),
    path('<str:client_code>/api/calculate-price/', CalculatePriceAPI.as_view(), name='api_calculate_price_client'),
    path('<str:client_code>/api/discount-preview/', DiscountPreviewAPI.as_view(), name='api_discount_preview_client'),
    path('<str:client_code>/api/create-reservation/', CreateReservationAPI.as_view(), name='api_create_reservation_client'),
    path('<str:client_code>/api/super-schedule/', SuperScheduleAPI.as_view(), name='api_super_schedule_client'),
    path('<str:client_code>/api/cancel-failed-reservations/', CancelFailedReservationsAPI.as_view(), name='api_cancel_failed_client'),

    # 付款 API
    path('<str:client_code>/api/payment-info/', PaymentInfoAPI.as_view(), name='api_payment_info_client'),
    path('<str:client_code>/api/process-payment/', ProcessPaymentAPI.as_view(), name='api_process_payment_client'),

    # 歷史紀錄 API
    path('<str:client_code>/api/reservation-history/', ReservationHistoryAPI.as_view(), name='api_reservation_history_client'),

    # Google 登入 API（預約系統專用，不檢查管理員權限）
    path('<str:client_code>/api/google-login/', GoogleLoginAPI.as_view(), name='api_google_login_client'),

    # ========== 向後相容的 API 端點（無 client_code） ==========
    path('api/course-categories/', CourseCategoryListAPI.as_view(), name='api_course_categories'),
    path('api/site-content/', SiteContentListAPI.as_view(), name='api_site_content'),
    path('api/resorts/', ResortListAPI.as_view(), name='api_resorts'),
    path('api/course-types/', CourseTypeListAPI.as_view(), name='api_course_types'),
    path('api/course-templates/', CourseTemplateListAPI.as_view(), name='api_course_templates'),
    path('api/course-sessions/', CourseSessionListAPI.as_view(), name='api_course_sessions'),
    path('api/coaches/', CoachListAPI.as_view(), name='api_coaches'),
    path('api/website-coaches/', WebsiteCoachListAPI.as_view(), name='api_website_coaches'),
    path('api/coach-bookings/', CoachBookingsAPI.as_view(), name='api_coach_bookings'),
    path('api/calculate-price/', CalculatePriceAPI.as_view(), name='api_calculate_price'),
    path('api/discount-preview/', DiscountPreviewAPI.as_view(), name='api_discount_preview'),
    path('api/create-reservation/', CreateReservationAPI.as_view(), name='api_create_reservation'),
    path('api/super-schedule/', SuperScheduleAPI.as_view(), name='api_super_schedule'),
    path('api/cancel-failed-reservations/', CancelFailedReservationsAPI.as_view(), name='api_cancel_failed'),
    path('api/payment-info/', PaymentInfoAPI.as_view(), name='api_payment_info'),
    path('api/process-payment/', ProcessPaymentAPI.as_view(), name='api_process_payment'),
    path('api/reservation-history/', ReservationHistoryAPI.as_view(), name='api_reservation_history'),
    path('api/google-login/', GoogleLoginAPI.as_view(), name='api_google_login'),

    # ========== 舊的 API 端點（逐步棄用） ==========
    path('api/calculate_price/', views.calculate_price_api, name='calculate_price_legacy'),
    path('api/<str:tunnel>/', views.API, name='API'),  # 保留舊的萬用路由
]
