from django.conf import settings
RUN_HOST = settings.RUN_HOST
def get_nav_list(user_profile):
    print('nav')
    print(user_profile)
    nav_list = []

    customer_nav = [
    {
        'id': 1,
        'pid': 0,
        'name': '客戶',
        'href': 'javascript:;',
        'icon': 'ri-user-line',
        'children': [
            {
                'name': '客戶列表',
                'href': '/Member/member_list'
            }
        ]
    }]

    coach_nav = [
    {
        'id': 1,
        'pid': 0,
        'name': '教練',
        'href': 'javascript:;',
        'icon': 'ri-user-star-line',
        'children': [
            {
                'name': '教練列表',
                'href': '/coach/coach_list'
            },
            {
                'name': '請假申請管理',
                'href': '/coach/leave_management'
            }
        ]
    }]

    all_course_nav = [
    {
        'id': 1,
        'pid': 0,
        'name': '全部課程',
        'href': 'javascript:;',
        'icon': 'ri-database-2-line',
        'children': [
            {
                'name': '課程資訊',
                'href': '/course/all_course_info'
            },
            {
                'name': '預約課表',
                'href': '/course/all_calendar',
            },
        ]
    }]
    
    course_nav = [
    {
        'id': 1,
        'pid': 0,
        'name': '課程',
        'href': 'javascript:;',
        'icon': 'ri-calendar-line',
        'children': [
            {
                'name': '課程資訊',
                'href': '/course/coach_courses'
            },
            {
                'name': '預約課表',
                'href': '/course/coach_calendar',
            },
            {
                'name': '請假管理',
                'href': '/coach/apply_leave'
            }
        ]
    }]

    settings_nav = [
    {
        'id': 1,
        'pid': 0,
        'name': '設定',
        'href': 'javascript:;',
        'icon': 'ri-settings-3-line',
        'children': [
            {
                'name': '課程設定',
                'href': '/settings/course_settings'
            },
            {
                'name': '雪場設定',
                'href': '/settings/resort_settings'
            },
            {
                'name': '價格管理',
                'href': '/settings/price_management'
            }
        ]
    }]

    if user_profile.is_manager:
        nav_list = customer_nav + coach_nav + all_course_nav + course_nav + settings_nav
    elif user_profile.is_coach:
        nav_list = course_nav
    return nav_list