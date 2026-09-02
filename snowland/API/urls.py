from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LoginView, CustomTokenRefreshView, client_ip
from .viewsManagerSet import ViewsManagerSet
from .admin_views import (
    SiteContentAdminViewSet,
    CoachAdminViewSet,
    CoachLeaveAdminViewSet,
    ResortAdminViewSet,
    CourseCategoryAdminViewSet,
    CourseTypeAdminViewSet,
    CourseTemplateAdminViewSet,
    CourseSessionAdminViewSet,
    CoursePricingAdminViewSet,
    DiscountCodeAdminViewSet,
    SeasonSettingAdminViewSet,
    OrderAdminViewSet,
    BookingScheduleAdminViewSet,
    customers_list,
    dashboard_stats,
    admin_login,
    admin_logout,
    admin_me,
    send_order_email,
    update_customer_permission,
    bulk_update_resort_fees,
    coach_pending_confirmations,
    coach_confirm_course,
    coach_my_courses,
    coach_my_calendar,
    coach_my_leaves,
    coach_apply_leave,
    staff_list,
    payment_settings_view,
)
from chatbooking.admin_views import ChatSupportViewSet


# 後台 ViewSet router
admin_router = DefaultRouter()
admin_router.register(r'site-content', SiteContentAdminViewSet, basename='admin-site-content')
admin_router.register(r'coaches', CoachAdminViewSet, basename='admin-coaches')
admin_router.register(r'coach-leaves', CoachLeaveAdminViewSet, basename='admin-coach-leaves')
admin_router.register(r'resorts', ResortAdminViewSet, basename='admin-resorts')
admin_router.register(r'course-categories', CourseCategoryAdminViewSet, basename='admin-course-categories')
admin_router.register(r'course-types', CourseTypeAdminViewSet, basename='admin-course-types')
admin_router.register(r'course-templates', CourseTemplateAdminViewSet, basename='admin-course-templates')
admin_router.register(r'course-sessions', CourseSessionAdminViewSet, basename='admin-course-sessions')
admin_router.register(r'course-pricing', CoursePricingAdminViewSet, basename='admin-course-pricing')
admin_router.register(r'discount-codes', DiscountCodeAdminViewSet, basename='admin-discount-codes')
admin_router.register(r'seasons', SeasonSettingAdminViewSet, basename='admin-seasons')
admin_router.register(r'orders', OrderAdminViewSet, basename='admin-orders')
admin_router.register(r'bookings', BookingScheduleAdminViewSet, basename='admin-bookings')
admin_router.register(r'chat-support', ChatSupportViewSet, basename='admin-chat-support')


urlpatterns = [
    path('login/', LoginView.as_view()),
    path('token/refresh/', CustomTokenRefreshView.as_view()),
    path('client_ip/', client_ip),
    path('manager/set/<str:category>/<str:subcategory>/',
         ViewsManagerSet.as_view()),

    # 後台 API：/api/admin/<client_code>/...
    # 後台跟預約系統共用同一套 OAuth session，所以不另開 login endpoint
    path('admin/<str:client_code>/me/', admin_me, name='admin-me'),
    path('admin/<str:client_code>/customers/', customers_list, name='admin-customers'),
    path('admin/<str:client_code>/customers/<int:user_id>/permission/', update_customer_permission, name='admin-customer-permission'),
    path('admin/<str:client_code>/staff/', staff_list, name='admin-staff-list'),
    path('admin/<str:client_code>/dashboard/', dashboard_stats, name='admin-dashboard'),
    path('admin/<str:client_code>/orders/<int:order_id>/send-email/', send_order_email, name='admin-order-send-email'),
    path('admin/<str:client_code>/resorts/<int:resort_id>/bulk-fees/', bulk_update_resort_fees, name='admin-resort-bulk-fees'),
    path('admin/<str:client_code>/coach/pending/', coach_pending_confirmations, name='admin-coach-pending'),
    path('admin/<str:client_code>/coach/confirm/<int:reservation_id>/', coach_confirm_course, name='admin-coach-confirm'),
    path('admin/<str:client_code>/coach/my-courses/', coach_my_courses, name='admin-coach-my-courses'),
    path('admin/<str:client_code>/coach/my-calendar/', coach_my_calendar, name='admin-coach-my-calendar'),
    path('admin/<str:client_code>/coach/my-leaves/', coach_my_leaves, name='admin-coach-my-leaves'),
    path('admin/<str:client_code>/coach/apply-leave/', coach_apply_leave, name='admin-coach-apply-leave'),
    path('admin/<str:client_code>/payment-settings/', payment_settings_view, name='admin-payment-settings'),
    path('admin/<str:client_code>/', include(admin_router.urls)),
]
