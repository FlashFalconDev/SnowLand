"""
優化的資料處理工具函數
目的：減少資料庫查詢次數，提升性能
"""
from collections import defaultdict
from Coursekit.models import CourseSession, CourseTemplate, CourseType, CourseCategory
from Resorts.models import Resorts


def build_course_data_optimized(tenant=None):
    """
    優化版：一次查詢建立所有課程相關資料（支持多租戶）

    參數：
    - tenant: Client 物件，用於過濾租戶資料

    返回字典包含：
    - time_slot_config: 時段配置（舊格式，向後相容）
    - template_slots_config: 按模板分組的時段配置
    - all_courses_data: 按課程類型分組的課程資料
    - course_categories: 課程大類資料
    - course_types: 課程類型資料
    - course_templates: 課程模板資料
    - course_sessions: 課程時段資料
    """

    # ========== 一次性查詢所有需要的資料 ==========
    # 使用 select_related 和 prefetch_related 減少查詢次數
    sessions_query = CourseSession.objects.select_related(
        'template',
        'template__course_type',
        'template__course_type__category'
    ).prefetch_related(
        'template__resorts',
        'template__course_type__available_resorts',
        'template__course_type__category__available_resorts'
    ).filter(
        template__is_active=True
    )

    # 🔥 多租戶過濾：只查詢屬於當前租戶的課程
    if tenant:
        sessions_query = sessions_query.filter(template__course_type__category__client=tenant)

    all_sessions = sessions_query.order_by(
        'template__course_type__category__display_order',
        'template__course_type__display_order',
        'template__display_order',
        'template__duration_hours',
        'template__id',
        'start_time',
    )

    # 預先獲取所有雪場（避免重複查詢）- 🔥 也需要過濾租戶
    resorts_query = Resorts.objects.all()
    if tenant:
        resorts_query = resorts_query.filter(client=tenant)
    all_resorts = list(resorts_query)
    resorts_list = [r.name for r in all_resorts]

    # ========== 初始化資料結構 ==========
    time_slot_config = {}
    template_slots_config = defaultdict(list)
    all_courses_data = defaultdict(list)

    # 使用字典去重，避免重複處理
    categories_dict = {}
    types_dict = {}
    templates_dict = {}
    sessions_list = []

    # ========== 單次遍歷處理所有資料 ==========
    for session in all_sessions:
        template = session.template
        course_type = template.course_type
        category = course_type.category

        # --- 1. 處理課程大類（去重） ---
        if category.id not in categories_dict:
            # 獲取該課程大類的可用雪場
            available_resorts = [r.name for r in category.available_resorts.all()]
            if not available_resorts:
                available_resorts = resorts_list  # 備用：使用所有雪場

            categories_dict[category.id] = {
                'id': category.id,
                'name': category.name,
                'display_order': category.display_order,
                'available_resorts': available_resorts
            }

        # --- 2. 處理課程類型（去重） ---
        if course_type.id not in types_dict:
            # 獲取該課程類型的可用雪場
            available_resorts = [r.name for r in course_type.available_resorts.all()]
            if not available_resorts:
                available_resorts = resorts_list  # 備用：使用所有雪場

            types_dict[course_type.id] = {
                'id': course_type.id,
                'name': course_type.name,
                'category_id': category.id,
                'display_order': course_type.display_order,
                'available_resorts': available_resorts
            }

        # --- 3. 處理課程模板（去重） ---
        if template.id not in templates_dict:
            templates_dict[template.id] = {
                'id': template.id,
                'name': template.name,
                'course_type_id': course_type.id,
                'display_order': template.display_order,
                'duration_hours': template.duration_hours,
                'max_capacity': template.max_capacity,
                'is_active': template.is_active,
                'resorts': [r.name for r in template.resorts.all()],
                'booking_open_date': template.booking_open_date.isoformat() if template.booking_open_date else None,
                'booking_close_date': template.booking_close_date.isoformat() if template.booking_close_date else None,
                'course_start_date': template.course_start_date.isoformat() if template.course_start_date else None,
                'course_end_date': template.course_end_date.isoformat() if template.course_end_date else None
            }

            # 同時加入 all_courses_data（按課程類型分組）
            if template.id not in [t['id'] for t in all_courses_data[course_type.id]]:
                all_courses_data[course_type.id].append({
                    'id': template.id,
                    'name': template.name,
                    'duration': template.duration_hours,
                    'display_order': template.display_order,
                    'is_active': template.is_active,
                    'course_type_id': course_type.id,
                    'resorts': [r.name for r in template.resorts.all()]
                })

        # --- 4. 處理課程時段 ---
        # 計算日期範圍字串
        date_range = ''
        if template.course_start_date and template.course_end_date:
            start_month = template.course_start_date.month
            start_day = template.course_start_date.day
            end_month = template.course_end_date.month
            end_day = template.course_end_date.day
            date_range = f"{start_month:02d}/{start_day:02d}~{end_month:02d}/{end_day:02d}"

        # 建立時段字典
        slot_dict = {
            'id': session.id,
            'course_type': f"{category.name.lower()}-{session.start_time.strftime('%H%M')}",
            'course_name': template.name,
            'period': session.start_time.strftime('%H:%M'),
            'date': date_range,
            'totalTime': f"{session.start_time.strftime('%H:%M')}-{session.end_time.strftime('%H:%M')}",
            'mainTime': f"{session.start_time.strftime('%H:%M')}-{session.end_time.strftime('%H:%M')}",
            'equipmentTime': '',
            'need_equipment': False,
            'start_time': session.start_time.strftime('%H:%M'),
            'end_time': session.end_time.strftime('%H:%M'),
        }

        # 加入 time_slot_config（舊格式）
        time_slot_config[session.id] = slot_dict

        # 加入 template_slots_config（按模板分組）
        template_slots_config[template.id].append(slot_dict)

        # 加入 sessions_list
        sessions_list.append({
            'id': session.id,
            'template_id': template.id,
            'start_time': session.start_time.strftime('%H:%M'),
            'end_time': session.end_time.strftime('%H:%M'),
            'is_active': template.is_active
        })

    # ========== 返回所有資料 ==========
    return {
        'time_slot_config': time_slot_config,
        'template_slots_config': dict(template_slots_config),
        'all_courses_data': dict(all_courses_data),
        'course_categories': list(categories_dict.values()),
        'course_types': list(types_dict.values()),
        'course_templates': list(templates_dict.values()),
        'course_sessions': sessions_list,
    }
