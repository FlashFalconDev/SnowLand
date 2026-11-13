from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LoginView, CustomTokenRefreshView, client_ip
from .viewsManagerSet import ViewsManagerSet
from .admin_views import (
    SiteContentAdminViewSet,
    CoachAdminViewSet,
    CoachLeaveAdminViewSet,
    ResortAdminViewSet,
    CampusAdminViewSet,
    PaymentAccountAdminViewSet,
    OperatingPolicyAdminViewSet,
    CourseCategoryAdminViewSet,
    CourseTypeAdminViewSet,
    CourseTemplateAdminViewSet,
    CourseSessionAdminViewSet,
    CoursePricingAdminViewSet,
    DiscountCodeAdminViewSet,
    SeasonSettingAdminViewSet,
    OrderAdminViewSet,
    CancellationAdminViewSet,
    NotificationTemplateAdminViewSet,
    NotificationDeliveryAdminViewSet,
    CourseEvaluationAdminViewSet,
    CoachCourseEvaluationViewSet,
    CoachPayRuleAdminViewSet,
    StaffIncentiveRuleAdminViewSet,
    PayrollStatementAdminViewSet,
    CoachPayrollViewSet,
    StaffBookingLinkAdminViewSet,
    InsuranceRecordAdminViewSet,
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
from .staff_incentives import StaffIncentiveStatementAdminViewSet
from .member_loyalty import customer_loyalty, loyalty_policy
from .website_coach_editor import WebsiteCoachEditorViewSet
from .contact_inbox import ContactInboxViewSet
from .recruitment import RecruitmentViewSet
from .instagram_sync import InstagramSyncViewSet
from .frontend_releases import FrontendReleaseViewSet
from .staff_positions import staff_positions, staff_position_detail
from .learning_views import CoachCourseAlbumAPI, CoachLearnerHistoryAPI, EvaluationLearnerLinkViewSet
from .vehicle_views import VehicleDesk, VehicleFile


# 後台 ViewSet router
admin_router = DefaultRouter()
admin_router.register(r'frontend-releases', FrontendReleaseViewSet, basename='admin-frontend-releases')
admin_router.register(r'instagram-sync', InstagramSyncViewSet, basename='admin-instagram-sync')
admin_router.register(r'contact-inbox', ContactInboxViewSet, basename='admin-contact-inbox')
admin_router.register(r'recruitment', RecruitmentViewSet, basename='admin-recruitment')
admin_router.register(r'site-content', SiteContentAdminViewSet, basename='admin-site-content')
admin_router.register(r'coaches', CoachAdminViewSet, basename='admin-coaches')
admin_router.register(r'website-coach-editor', WebsiteCoachEditorViewSet, basename='admin-website-coach-editor')
admin_router.register(r'coach-leaves', CoachLeaveAdminViewSet, basename='admin-coach-leaves')
admin_router.register(r'resorts', ResortAdminViewSet, basename='admin-resorts')
admin_router.register(r'campuses', CampusAdminViewSet, basename='admin-campuses')
admin_router.register(r'payment-accounts', PaymentAccountAdminViewSet, basename='admin-payment-accounts')
admin_router.register(r'operating-policies', OperatingPolicyAdminViewSet, basename='admin-operating-policies')
admin_router.register(r'course-categories', CourseCategoryAdminViewSet, basename='admin-course-categories')
admin_router.register(r'course-types', CourseTypeAdminViewSet, basename='admin-course-types')
admin_router.register(r'course-templates', CourseTemplateAdminViewSet, basename='admin-course-templates')
admin_router.register(r'course-sessions', CourseSessionAdminViewSet, basename='admin-course-sessions')
admin_router.register(r'course-pricing', CoursePricingAdminViewSet, basename='admin-course-pricing')
admin_router.register(r'discount-codes', DiscountCodeAdminViewSet, basename='admin-discount-codes')
admin_router.register(r'seasons', SeasonSettingAdminViewSet, basename='admin-seasons')
admin_router.register(r'orders', OrderAdminViewSet, basename='admin-orders')
admin_router.register(r'cancellations', CancellationAdminViewSet, basename='admin-cancellations')
admin_router.register(r'notification-templates', NotificationTemplateAdminViewSet, basename='admin-notification-templates')
admin_router.register(r'notification-deliveries', NotificationDeliveryAdminViewSet, basename='admin-notification-deliveries')
admin_router.register(r'evaluations', CourseEvaluationAdminViewSet, basename='admin-evaluations')
admin_router.register(r'coach/evaluations', CoachCourseEvaluationViewSet, basename='coach-evaluations')
admin_router.register(r'coach-pay-rules', CoachPayRuleAdminViewSet, basename='admin-coach-pay-rules')
admin_router.register(r'staff-incentive-rules', StaffIncentiveRuleAdminViewSet, basename='admin-staff-incentive-rules')
admin_router.register(r'staff-incentive-statements', StaffIncentiveStatementAdminViewSet, basename='admin-staff-incentive-statements')
admin_router.register(r'payroll-statements', PayrollStatementAdminViewSet, basename='admin-payroll-statements')
admin_router.register(r'coach/payroll', CoachPayrollViewSet, basename='coach-payroll')
admin_router.register(r'staff-booking-links', StaffBookingLinkAdminViewSet, basename='admin-staff-booking-links')
admin_router.register(r'insurance-records', InsuranceRecordAdminViewSet, basename='admin-insurance-records')
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
    path('admin/<str:client_code>/customers/loyalty-policy/', loyalty_policy, name='admin-loyalty-policy'),
    path('admin/<str:client_code>/customers/<int:user_id>/loyalty/', customer_loyalty, name='admin-customer-loyalty'),
    path('admin/<str:client_code>/customers/<int:user_id>/permission/', update_customer_permission, name='admin-customer-permission'),
    path('admin/<str:client_code>/staff/', staff_list, name='admin-staff-list'),
    path('admin/<str:client_code>/staff-positions/', staff_positions, name='admin-staff-positions'),
    path('admin/<str:client_code>/staff-positions/<int:position_id>/', staff_position_detail, name='admin-staff-position-detail'),
    path('admin/<str:client_code>/dashboard/', dashboard_stats, name='admin-dashboard'),
    path('admin/<str:client_code>/vehicles/', VehicleDesk.as_view(), name='admin-vehicles'),
    path('admin/<str:client_code>/vehicles/<int:trip_id>/files/<str:file_key>/', VehicleFile.as_view(), name='admin-vehicle-file'),
    path('admin/<str:client_code>/coach/vehicles/', VehicleDesk.as_view(), {'personal': True}, name='coach-vehicles'),
    path('admin/<str:client_code>/coach/vehicles/<int:trip_id>/files/<str:file_key>/', VehicleFile.as_view(), {'personal': True}, name='coach-vehicle-file'),
    path('admin/<str:client_code>/orders/<int:order_id>/send-email/', send_order_email, name='admin-order-send-email'),
    path('admin/<str:client_code>/resorts/<int:resort_id>/bulk-fees/', bulk_update_resort_fees, name='admin-resort-bulk-fees'),
    path('admin/<str:client_code>/coach/pending/', coach_pending_confirmations, name='admin-coach-pending'),
    path('admin/<str:client_code>/coach/confirm/<int:reservation_id>/', coach_confirm_course, name='admin-coach-confirm'),
    path('admin/<str:client_code>/coach/my-courses/', coach_my_courses, name='admin-coach-my-courses'),
    path('admin/<str:client_code>/coach/learner-history/<int:reservation_id>/', CoachLearnerHistoryAPI.as_view(), name='coach-learner-history'),
    path('admin/<str:client_code>/coach/course-albums/<int:booking_id>/', CoachCourseAlbumAPI.as_view(), name='coach-course-album'),
    path('admin/<str:client_code>/evaluations/<int:pk>/learner-profile/',
         EvaluationLearnerLinkViewSet.as_view({'get': 'profile_choices', 'patch': 'profile_choices'}), name='evaluation-learner-link'),
    path('admin/<str:client_code>/coach/my-calendar/', coach_my_calendar, name='admin-coach-my-calendar'),
    path('admin/<str:client_code>/coach/my-leaves/', coach_my_leaves, name='admin-coach-my-leaves'),
    path('admin/<str:client_code>/coach/apply-leave/', coach_apply_leave, name='admin-coach-apply-leave'),
    path('admin/<str:client_code>/payment-settings/', payment_settings_view, name='admin-payment-settings'),
    path('admin/<str:client_code>/', include(admin_router.urls)),
]
