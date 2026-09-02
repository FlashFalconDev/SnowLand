from django.urls import path
from . import views,views_item,views_set
app_name = 'control'

urlpatterns = [
    # 基礎
     path('', views.login, name='login'),
     path('logout/', views.logout, name='logout'),
     path('tmp/<str:page>/<str:page_name>', views.tmp_page, name='tmp_page'),
     path('api/google-login/', views.api_google_login, name='api_google_login'),
     path('api/logout/', views.api_logout, name='api_logout'),
     path('api/manager/nav/',
          views.nav, name='nav'),


     path('api/manager/member_list/',
          views.member_list, name='member_list'),
     path('api/manager/member_permission/',
          views.member_permission, name='member_permission'),

     # 課程管理
     path('api/manager/all_course_info/',
          views.all_course_info, name='all_course_info'),
     path('api/manager/all_course_permission/',
          views.all_course_permission, name='all_course_permission'),
     path('api/manager/course_delete/',
          views.course_delete, name='course_delete'),
     path('api/manager/coach_courses/',
          views.coach_courses, name='coach_courses'),
     path('api/manager/reservation_detail/',
          views.reservation_detail, name='reservation_detail'),
     path('api/manager/calendar_courses/',
          views.calendar_courses, name='calendar_courses'),
     path('api/manager/coach_calendar/',
          views.coach_calendar, name='coach_calendar'),
     path('api/manager/send_email_form/',
          views.send_email_form, name='send_email_form'),

     # 教練管理
     path('api/manager/coach_list/',
          views.coach_list, name='coach_list'),
     path('api/manager/coach_form/',
          views.coach_form, name='coach_form'),
     path('api/manager/coach_delete/',
          views.coach_delete, name='coach_delete'),
     path('api/manager/coach_confirm_course/',
          views.coach_confirm_course, name='coach_confirm_course'),
     path('api/manager/pending_confirmations/',
          views.pending_confirmations, name='pending_confirmations'),

     # 教練請假功能
     path('api/manager/coach/submit_leave/', views.submit_leave, name='submit_leave'),
     path('coach/leave_list/', views.leave_list, name='leave_list'),
     path('coach/leave_management/', views.leave_management, name='leave_management'),
     path('coach/leave_review/', views.leave_review, name='leave_review'),

     # 產品分類
     path('api/manager/item_category/<str:item_type>/',
          views_item.item_category),
     path('api/manager/item_category_form/<str:item_type>/',
          views_item.item_category_form),

     # 產品資訊
     path('api/manager/item_info/<str:item_type>/',
          views_item.item_info, name='item_info'),
     path('api/manager/item_info_form/<str:item_type>/',
          views_item.item_info_form, name='item_info_form'),
     path('api/manager/item_info_image/<str:item_type>/',
          views_item.item_info_image, name='item_info_image'),
     
     # 訂單
     path('api/manager/item_order/<str:item_type>/',
          views_item.item_order, name='item_order'),
     
     #設定
     path('api/manager/set/finance/<str:finance_type>/',
          views_set.finance, name='finance'),
     path('api/manager/set/print/',
          views_set.print_settings, name='print_settings'),
     path('api/manager/set/invoice/',
          views_set.invoice, name='invoice'),
     path('api/manager/set/table/',
          views_set.table, name='table'),

     # ===== 新版課程設定管理系統 =====
     # 新的課程設定管理API
     path('api/manager/settings/course_settings_new/',
          views.course_settings_new, name='course_settings_new'),
     
     # 課程大類 CRUD API
     path('api/manager/settings/course_categories/action/',
          views.course_categories_action, name='course_categories_action'),
     path('api/manager/settings/course_categories/action/<int:category_id>/',
          views.course_categories_action, name='course_categories_action_id'),
     
     # 課程類型 CRUD API
     path('api/manager/settings/course_types_new/action/',
          views.course_types_action_new, name='course_types_action_new'),
     path('api/manager/settings/course_types_new/action/<int:type_id>/',
          views.course_types_action_new, name='course_types_action_new_id'),
     
     # 課程模板 CRUD API
     path('api/manager/settings/templates_new/action/',
          views.templates_action_new, name='templates_action_new'),
     path('api/manager/settings/templates_new/action/<int:template_id>/',
          views.templates_action_new, name='templates_action_new_id'),
     
     # 上課時段 CRUD API
     path('api/manager/settings/sessions/action/',
          views.sessions_action, name='sessions_action'),
     path('api/manager/settings/sessions/action/<int:session_id>/',
          views.sessions_action, name='sessions_action_id'),
     
     # 課程定價 CRUD API
     path('api/manager/settings/pricing/action/',
          views.pricing_action, name='pricing_action'),
     path('api/manager/settings/pricing/action/<int:pricing_id>/',
          views.pricing_action, name='pricing_action_id'),
     

     # ===== 雪場設定管理系統 =====
     # 雪場設定管理API
     path('api/manager/settings/resort_settings_new/',
          views.resort_settings_new, name='resort_settings_new'),
     
     # 雪場 CRUD API
     path('api/manager/settings/resorts/action/',
          views.resort_action, name='resort_action'),
     path('api/manager/settings/resorts/action/<int:resort_id>/',
          views.resort_action, name='resort_action_id'),
     
     # 雪場費用 CRUD API
     path('api/manager/settings/resort_fees/action/',
          views.resort_fee_action, name='resort_fee_create_action'),
     path('api/manager/settings/resort_fees/action/<int:fee_id>/',
          views.resort_fee_action, name='resort_fee_action_id'),

     path('api/manager/settings/resorts/<int:resort_id>/bulk_update_fees/',
          views.bulk_update_resort_fees, name='bulk_update_resort_fees'),
    # 支援
    path('api/manager/upload-image/<str:type>/',
          views.upload_image, name='upload-image'),
     path('api/manager/item_order_status/',
          views_item.item_order_status, name='item_order_status'),
     
]


