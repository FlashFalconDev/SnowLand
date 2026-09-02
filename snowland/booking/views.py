from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.http import JsonResponse
from .models import *
from booking.scheduler import assign_coachs, check_availability_and_get_suggestions
from datetime import datetime, timedelta
from .funcNewebpay import neweb_pay_request
from snowland.settings import RUN_HOST, PAYMENT_HOST
import json
from django.db import transaction
from booking.tasks import auto_cancel_unpaid_reservations
import requests
from Coach.models import CoachCourseLevel, CoachResort, Coach, CoachLeaveRequest
from Resorts.models import Resorts # 1. 匯入 Resorts model
from Control.views import login_required_control
from Coursekit.models import CourseCategory, CourseType, CourseTemplate, CourseSession, SeasonSetting
from .utils import build_course_data_optimized  # 新增：匯入優化的資料建構函數
from django.core.cache import cache  # 新增：快取支援
from .decorators import require_tenant  # 🔥 新增：匯入裝飾器


def get_client_ip(request):
    """取得用戶端 IP 位址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_ip(view_func):
    def wrapper(request, *args, **kwargs):
        user_ip = get_client_ip(request)
        print("用戶IP:", user_ip)
        return view_func(request, *args, **kwargs)
    return wrapper

@require_tenant  # 🔥 使用裝飾器，自動檢查和注入 tenant
def home(request, client_code):
    """
    優化版：使用快取和單次查詢建立所有課程資料（支持多租戶）

    改進點：
    1. 移除頁面載入時的 auto_cancel（改為背景任務）
    2. 使用快取減少資料庫查詢
    3. 單次遍歷建立所有資料結構
    4. 保持前端完全向後相容
    5. 🔥 多租戶隔離：只查詢當前租戶的資料
    6. 🔥 使用裝飾器自動處理 tenant，不用每個函數都寫

    參數：
    - client_code: 由 URL 傳入，例如 /booking/snowland/ -> client_code='snowland'
    """
    # TODO: 將 auto_cancel_unpaid_reservations() 移到 Celery 定時任務
    # 暫時保留以確保向後相容，但應該盡快移除
    auto_cancel_unpaid_reservations()

    # 🔥 租戶資訊由 middleware 和裝飾器自動注入
    tenant = request.tenant  # 由 middleware 注入，裝飾器已確保存在

    next_url = RUN_HOST + f'/booking/{client_code}/'

    # 🔥 教練列表（過濾租戶）
    coach_query = Coach.objects
    if tenant:
        coach_query = coach_query.filter(client=tenant)
    coachs_list = list(coach_query.values('pk', 'name'))

    # 🔥 雪場選項（過濾租戶）
    resort_query = Resorts.objects
    if tenant:
        resort_query = resort_query.filter(client=tenant)
    resorts = resort_query.all()
    resort_choices = {
        resort.name: {
            'display_name': resort.display_name,
            'auto_scheduling_enabled': resort.auto_scheduling_enabled
        } for resort in resorts
    }

    # 🔥 課程類型選項（過濾租戶）
    course_type_query = CourseType.objects
    if tenant:
        course_type_query = course_type_query.filter(category__client=tenant)
    course_types = course_type_query.all().order_by('display_order')
    course_type_choices = {ct.id: ct.name for ct in course_types}

    # ========== 使用快取獲取課程資料（按租戶分開快取）==========
    cache_key = f'course_data_optimized_v2_{client_code}'  # 🔥 加入 client_code
    course_data = cache.get(cache_key)

    if not course_data:
        # 快取未命中，重新建立資料
        print(f"快取未命中 [{client_code}]，重新查詢資料庫")
        course_data = build_course_data_optimized(tenant=tenant)  # 🔥 傳入 tenant
        # 快取 15 分鐘（課程資料不常變動）
        cache.set(cache_key, course_data, 60 * 15)
    else:
        print(f"使用快取資料 [{client_code}]")

    # ========== 返回模板 ==========
    return render(request, 'booking/booking_complete.html', {
        'next_url': next_url,
        'resort_choices': json.dumps(resort_choices),
        'ability_level_choices': dict(ABILITY_LEVEL_CHOICES),
        'course_type_choices': course_type_choices,
        'equipment_choices': dict(EQUIPMENT_CHOICES),
        'coachs_list': coachs_list,
        # 以下所有變數名稱保持不變，確保前端向後相容
        'time_slot_config': json.dumps(course_data['time_slot_config']),
        'template_slots_config': json.dumps(course_data['template_slots_config']),
        'all_courses_data': json.dumps(course_data['all_courses_data']),
        'course_categories': json.dumps(course_data['course_categories']),
        'course_types': json.dumps(course_data['course_types']),
        'course_templates': json.dumps(course_data['course_templates']),
        'course_sessions': json.dumps(course_data['course_sessions']),
    })

@log_ip
@require_tenant  # 🔥 使用裝飾器
def payment(request, client_code):
    """
    付款頁面

    參數：
    - client_code: 由 URL 傳入，例如 /booking/snowland/payment/ -> client_code='snowland'
    """
    print("payment")
    # auto_cancel_unpaid_reservations()
    order_details = []
    total_amount = 0
    reservation_group_pk = request.GET.get('reservation_group', '')
    tenant = request.tenant  # 🔥 由裝飾器確保存在

    next_url = PAYMENT_HOST.replace('/booking/', f'/booking/{client_code}/') + '?reservation_group=' + reservation_group_pk
    bank_info = {
        'account_name': '雪域有限公司',
        'account_number': '123-456-789012',
        'branch_name': '信義分行',
        'bank_name': '台灣銀行',
    }
    context = {'next_url': next_url, 'reservation_group_pk': reservation_group_pk}

    # 🔥 多租戶過濾（裝飾器已確保 tenant 存在）
    group = ReservationGroup.objects.filter(
        pk=reservation_group_pk,
        client=tenant
    ).first()
    
    if group:
        # 獲取所有未被軟刪除的預約
        active_reservations = group.reservations.exclude(status='deleted')
        
        # 檢查是否有任何有效的預約
        if not active_reservations.exists():
            context['payment_status'] = 'no_active_reservations'
            context['message'] = '此預約群組沒有有效的預約項目。'
            return render(request, 'booking/payment.html', context)
        
        # --- 新增的嚴格狀態檢查 ---
        # 檢查是否所有有效的預約都已準備好付款
        for resv in active_reservations:
            if resv.status not in ['auto_assigned', 'manually_assigned', 'cancelled']:
                # 如果有任何一個預約尚未準備好，則根據其狀態阻擋付款
                if resv.status == 'pending_coach_confirmation':
                    context['payment_status'] = 'pending_coach_approval'
                    context['message'] = '您的部分預約正在等待教練確認，在所有課程都被教練接受前無法付款，請稍後再試。'
                elif resv.status == 'auto_assignment_failed':
                    context['payment_status'] = 'assignment_failed'
                    context['message'] = '系統自動排課失敗，請聯繫客服人員協助處理您的預約。'
                else: # 包含 'created' 等其他中間狀態
                    context['payment_status'] = 'processing'
                    context['message'] = '您的預約正在處理中，請稍後再回來查看狀態。'
                
                return render(request, 'booking/payment.html', context)
            
        payment_status = Payment.objects.get(reservation_group__pk=reservation_group_pk).status
        context['payment_status'] = payment_status
        if payment_status == 'paid':
            context['orderer_user'] = group.user.email
            return render(request, 'booking/payment.html', context)
        elif payment_status == 'pending':
            return render(request, 'booking/payment.html', context)
        elif payment_status == 'expired':
            return render(request, 'booking/payment.html', context)
        
        # 過濾掉已取消的預約，以正確計算總金額
        reservations_to_pay = active_reservations.exclude(status='cancelled')

        # 如果過濾掉取消後沒有剩餘課程，也顯示特殊頁面
        if not reservations_to_pay.exists():
            context['payment_status'] = 'all_cancelled'
            context['message'] = '您預約的所有課程均已取消，無需付款。'
            return render(request, 'booking/payment.html', context)

        for resv in reservations_to_pay:
            resv = Reservation.objects.get(pk=resv.pk)

            detail = {}
            detail['pk'] = resv.pk
            if resv.equipment_rental_fee != 0:
                detail['equipment_rental_fee'] = resv.equipment_rental_fee
            if resv.language_fee != 0:
                detail['language_fee'] = resv.language_fee
            if resv.coach_fee != 0:
                detail['coach_fee'] = resv.coach_fee
            if resv.course_fee != 0:
                detail['course_fee'] = resv.course_fee
            if resv.payment_amount != 0:
                detail['payment_amount'] = resv.payment_amount
            order_details.append(detail)
            total_amount += resv.payment_amount

        # 檢查總金額是否為0
        if total_amount <= 0:
            context['payment_status'] = 'zero_amount'
            context['message'] = '此預約群組的總費用為0，無需付款'
            return render(request, 'booking/payment.html', context)

        user_ip = get_client_ip(request)
        # # 模擬國外IP（開發測試用）
        # from django.conf import settings
        # if settings.DEBUG:
        #     user_ip = "8.8.8.8"  # 美國IP

        # paymentType = 'newebpay'
        try:
            resp = requests.get(f"https://ipinfo.io/{user_ip}/json", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                country = data.get('country', '')
                if country == 'TW':
                    paymentType = 'TT'
                else:
                    paymentType = 'newebpay'
        except Exception as e:
            print("IP 位置查詢失敗:", e)
        context['payment_type'] = paymentType
        context['bank_info'] = bank_info
        context['total_amount'] = total_amount
        context['order_details'] = order_details
        return render(request, 'booking/payment.html', context)
    else:
        context['payment_status'] = 'not_found'
        return render(request, 'booking/payment.html', context)

@api_view(['GET'])
@login_required_control
def calculate_price_api(request, Client_Info=None):
    """計算課程價格的 API"""
    try:
        template_id = request.GET.get('template_id')
        people_count = int(request.GET.get('people_count', 1))
        date_str = request.GET.get('date')
        resort_name = request.GET.get('resort')
        
        if not all([template_id, date_str, resort_name]):
            return JsonResponse({'error': '缺少必要參數'}, status=400)
        
        # 獲取課程模板
        template = CourseTemplate.objects.get(id=template_id)
        
        # 獲取雪場
        resort = Resorts.objects.get(name=resort_name)
        
        # 獲取價格策略
        from Coursekit.models import CoursePricing
        pricing_strategy = CoursePricing.objects.filter(
            templates=template,
            resort=resort,
            is_active=True
        ).first()
        
        if not pricing_strategy:
            return JsonResponse({'error': '找不到對應的價格設定'}, status=404)
        
        # 判斷季節類型
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        season_type = SeasonSetting.get_season_type_for_date(booking_date)
        is_peak_season = (season_type == 'peak')
        
        # 計算價格
        price = pricing_strategy.calculate_price(people_count, is_peak_season)
        
        return JsonResponse({'price': price})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET', 'POST'])
@login_required_control
def API(request, tunnel, Client_Info=None):
    print('API', tunnel)
    if tunnel == 'courses':
        if request.method == 'GET':
            resort_name = request.GET.get('resort', '') # 變數名改為 resort_name 更清晰
            course_type = request.GET.get('courseType', '')
            ability_level = request.GET.get('abilityLevel', '')

            # 1. 攝影課程不可指定教練
            if course_type == 'Photography':
                return JsonResponse({
                    'coach_list': [],
                    'courses': []
                }, status=200)

            # 2. 根據新的 'auto_scheduling_enabled' 欄位來判斷
            try:
                # 先用傳入的名稱找到對應的 Resort 物件
                resort_obj = Resorts.objects.get(name=resort_name)
                print('resort_obj', resort_obj)
                # 如果該雪場不啟用自動排課（即不提供教練），則直接返回空列表
                if not resort_obj.auto_scheduling_enabled:
                    print('不啟用自動排課')
                    return JsonResponse({
                        'coach_list': [],
                        'courses': []
                    }, status=200)
            except Resorts.DoesNotExist:
                # 如果找不到對應的雪場，也返回空列表
                return JsonResponse({
                    'coach_list': [],
                    'courses': []
                }, status=404)

            # 3. 使用查詢到的 resort_obj 來正確地過濾 CoachResort
            #    使用 'resort__id' 來明確指定我們要用 Resort 物件的 id 進行過濾
            coach_ids_resort = CoachResort.objects.filter(resort__id=resort_obj.id).values_list('coach_id', flat=True)
            coach_ids_course = CoachCourseLevel.objects.filter(course_type=course_type).values_list('coach_id', flat=True)
            if ability_level:
                coach_ids_ability = [
                    ccl.coach_id
                    for ccl in CoachCourseLevel.objects.filter(course_type=course_type)
                    if ability_level in ccl.ability_levels
                ]
                # coach_ids_ability = CoachCourseLevel.objects.filter(
                #     course_type=course_type,
                #     ability_levels__contains=[ability_level]
                # ).values_list('coach_id', flat=True)
                coach_ids = set(coach_ids_resort) & set(coach_ids_course) & set(coach_ids_ability)
            else:
                coach_ids = set(coach_ids_resort) & set(coach_ids_course)

            # 判斷登入用戶權限
            is_manager = False
            if Client_Info and Client_Info.get('user_profile'):
                is_manager = Client_Info['user_profile'].is_manager

            # 根據權限查詢教練
            if is_manager:
                # 如果是管理員，顯示所有教練
                coachs = Coach.objects.filter(id__in=coach_ids)
            else:
                # 一般用戶只顯示主動接課的教練（不顯示被動接課和不可接課的教練）
                coachs = Coach.objects.filter(id__in=coach_ids, availability_status='active')
            coach_list = []
            for coach in coachs:
                # 處理 languages - 如果是字符串則分割為列表  
                languages = coach.languages or ""
                if isinstance(languages, str):
                    languages = [l.strip() for l in languages.split(',') if l.strip()]
                elif not isinstance(languages, list):
                    languages = ['中文']  # 預設值

                # 新增：語言代碼轉中文
                lang_map = {
                    "zh": "中文",
                    "en": "英文",
                    "yue": "粵語",
                }
                languages = [lang_map.get(l, l) for l in languages]
                
                # 處理圖片路徑
                image_url = coach.img if coach.img else 'https://host.flashfalcon.info/static/manager/img/logo.png'
                
                coach_data = {
                    'pk': coach.pk,
                    'name': f"{coach.name} (僅管理員可見)" if is_manager and coach.availability_status != 'active' else coach.name,
                    # 'description': coach.description or '專業滑雪教練',
                    'description': "",
                    'specialties': [],  # Coach模型沒有specialties字段，設為空列表
                    'languages': languages,
                    'image': image_url
                }
                coach_list.append(coach_data)

            return JsonResponse({
                'coach_list': coach_list,
                'courses': []  # 課程資料由前端從預載入的資料中獲取
            }, status=200)
    elif tunnel == 'coach_bookings':
        if request.method == 'GET':
            coach_id = request.GET.get('coach_id', '')
            booked_slots = []
            unavailable_dates = []
            
            if coach_id and coach_id != "any":
                coach_instance = get_object_or_404(Coach, pk=coach_id)
                booked_slots = get_booked_slots(coach_instance)
                
                # 獲取已批准的請假日期
                approved_leaves = CoachLeaveRequest.objects.filter(
                    coach=coach_instance,
                    status='approved'
                )
                
                for leave in approved_leaves:
                    current_date = leave.start_date
                    while current_date <= leave.end_date:
                        unavailable_dates.append(current_date.strftime('%Y-%m-%d'))
                        current_date += timedelta(days=1)

            booking_data = {
                "coach_id": coach_id,
                "booked_slots": booked_slots,
                "unavailable_dates": unavailable_dates
            }
            return JsonResponse(booking_data, status=200)
        
    elif tunnel == 'create_reservation':
        if request.method == 'POST':
            body = request.data
            courses = body.get("courses", [])
            user = Client_Info.get('user')
            if not user:
                return JsonResponse({"message": "User not found or not authenticated."}, status=401)
            
            # 整合點：檢查是否為超級排課模式
            is_super_schedule = body.get("tunnel") == "super_schedule"
            
            courses_to_process = []
            if is_super_schedule:
                # 如果是超級排課，先將課程拆分為單日單元
                for course_data in courses:
                    for booking_slot in course_data.get("booking", []):
                        new_course_unit = course_data.copy()
                        new_course_unit['booking'] = [booking_slot]
                        courses_to_process.append(new_course_unit)
            else:
                # 普通排課，直接使用原課程
                courses_to_process = courses
            
            # 對於普通排課，執行預檢
            if not is_super_schedule:
                is_successful, report = check_availability_and_get_suggestions(courses_to_process)
                if not is_successful:
                    return JsonResponse({
                        "success": False,
                        "message": "部分時段無法預約，請參考建議調整。",
                        **report
                    }, status=400)

            # --- 統一的預約創建流程 ---
            try:
                with transaction.atomic():
                    group = ReservationGroup.objects.create(user=user)
                    payment = Payment.objects.create(
                        reservation_group=group,
                        status='unpaid',
                    )

                    new_reservations = []
                    for course_data in courses_to_process:
                        # --- 這段邏輯對兩種模式都通用 ---
                        equipment = course_data.get("equipment")
                        language = course_data.get("language")
                        lang_map_reverse = {"中文": "zh", "英文": "en", "粵語": "yue"}
                        language = lang_map_reverse.get(language, language)
                        
                        resort_name = course_data.get("resort")
                        resort_instance = get_object_or_404(Resorts, name=resort_name)

                        course_type_str = course_data.get("courseType")
                        course_type = get_object_or_404(CourseType, id=course_type_str)
                        
                        number_of_people = course_data.get("peopleCount")
                        ability_level = course_data.get("abilityLevel")
                        booking_list = course_data.get("booking", [])
                        # season = "off"  <- This is now dynamically determined

                        # 在超級排課模式下，強制不指定教練
                        # 普通模式下，則尊重前端的選擇
                        is_preferred = (not is_super_schedule) and (course_data.get("coach") != "any")
                        coach_instance = None
                        if is_preferred:
                            coach_instance = get_object_or_404(Coach, pk=course_data.get("coach"))

                        reservation = Reservation.objects.create(
                            is_preferred_coach=is_preferred,
                            preferred_coach=coach_instance,
                            language=language,
                            resort=resort_instance,
                            course_type=course_type,
                            status='created',
                            number_of_people=number_of_people,
                            equipment=equipment,
                            group=group,
                            max_ability_level=ability_level,
                        )
                        
                        for slot_info in booking_list:
                            ctype = slot_info.get("course")
                            slot_id = slot_info.get("timeSlot")
                            date = slot_info.get("date")

                            try:
                                # 首先嘗試從CourseTemplate模型查找
                                course_template = CourseTemplate.objects.get(id=slot_id)
                                # 創建一個臨時的Course對象來兼容後續邏輯
                                class TempCourse:
                                    def __init__(self, template):
                                        self.template = template
                                        # 從CourseSession獲取時間段
                                        sessions = CourseSession.objects.filter(template=template, is_active=True)
                                        if sessions.exists():
                                            session = sessions.first()  # 取第一個時段
                                            self.main_time = f"{session.start_time.strftime('%H:%M')}-{session.end_time.strftime('%H:%M')}"
                                        else:
                                            self.main_time = "09:00-17:00"  # 預設時間
                                course_slot = TempCourse(course_template)
                            except CourseTemplate.DoesNotExist:
                                try:
                                    # 如果CourseTemplate模型找不到，嘗試從CourseSession模型查找
                                    course_session = CourseSession.objects.select_related('template').get(id=slot_id)
                                    # 創建一個臨時的Course對象來兼容後續邏輯
                                    class TempCourse:
                                        def __init__(self, session):
                                            self.template = session.template
                                            self.main_time = f"{session.start_time.strftime('%H:%M')}-{session.end_time.strftime('%H:%M')}"
                                    course_slot = TempCourse(course_session)
                                except CourseSession.DoesNotExist:
                                    raise Exception(f"無效的時段ID: {slot_id}")

                            main_time_str = course_slot.main_time
                            main_segments = parse_time_ranges(main_time_str)
                            
                            for (start_s, end_s) in main_segments:
                                Booking.objects.create(
                                    reservation=reservation,
                                    course_type=ctype,
                                    course_name=course_slot.template.name,
                                    date=date,
                                    start_time=str_to_time(start_s),
                                    end_time=str_to_time(end_s),
                                )
                            
                            # --- 動態價格計算邏輯 ---
                            booking_date = datetime.strptime(date, '%Y-%m-%d').date()
                            season_type = SeasonSetting.get_season_type_for_date(booking_date)
                            
                            try:
                                # 使用CoursePricing模型
                                from Coursekit.models import CoursePricing
                                pricing_strategy = CoursePricing.objects.filter(
                                    templates=course_slot.template,
                                    resort=resort_instance,
                                    is_active=True
                                ).first()
                                if pricing_strategy:
                                    is_peak_season = (season_type == 'peak')
                                    course_fee = pricing_strategy.calculate_price(number_of_people, is_peak_season)
                                else:
                                    raise Exception(f"找不到對應的價格設定: 課程='{course_slot.template.name}', 雪場='{resort_instance.name}'")
                            except Exception as e:
                                raise Exception(f"價格計算失敗: {str(e)}")
                            
                            reservation.course_fee += course_fee

                        if is_preferred and coach_instance:
                            # 注意: coach_course_level 的 course_type 應該是 CourseType instance
                            coach_course_level = CoachCourseLevel.objects.filter(coach=coach_instance, course_type=course_type).first()
                            if coach_course_level:
                                # 使用雪場綁定的教練指定費用
                                from Resorts.models import ResortFee
                                price_level = coach_course_level.price_level
                                if price_level == 'director':
                                    reservation.coach_fee = ResortFee.get_coach_fee(resort_instance, 'director') * len(booking_list)
                                elif price_level == 'Lv2':
                                    reservation.coach_fee = ResortFee.get_coach_fee(resort_instance, 'Lv2') * len(booking_list)
                                else:
                                    reservation.coach_fee = ResortFee.get_coach_fee(resort_instance, 'general') * len(booking_list)
                        
                        # 語言只作為教練篩選條件,不另外收費;指定教練時才依教練等級收指定費
                        reservation.language_fee = 0
                        
                        # 新增：計算裝備租借費用
                        if equipment == 'purchaseAssistanceTime':
                            from Resorts.models import ResortFee
                            reservation.equipment_rental_fee = ResortFee.get_equipment_fee(resort_instance, number_of_people) * len(booking_list)
                        
                        reservation.save()
                        new_reservations.append(reservation)

                    # 執行標準排程
                    schedule_success, schedule_report = assign_coachs(reservations_to_assign=new_reservations)
                    
                    if not schedule_success:
                        error_message = "進階排課失敗，即使將您的預約拆開，目前時段依然非常搶手，請調整日期後再試一次。" if is_super_schedule else "自動排課失敗，所有預約已取消。"
                        raise Exception(error_message)

                    # --- 優化的資料回傳邏輯 ---
                    # 初始化狀態標記
                    has_status_10 = False
                    has_status_22 = False
                    
                    # 檢查所有預約的狀態
                    for reservation in new_reservations:
                        if reservation.status == 10:
                            # 狀態10表示需要人工排定教練,保持不變
                            has_status_10 = True
                        elif reservation.status == 0:
                            # 只將狀態0(創建預約)改為20(已自動排定教練)
                            # 其他狀態(如22等待教練確認) 由scheduler.py處理,不在此處覆蓋
                            reservation.status = 20
                            reservation.save()
                        elif reservation.status == 22:
                            # 狀態22表示等待教練確認
                            has_status_22 = True
                            # 其他狀態保持不變
                    
                    # 根據不同情況提供相應的用戶提示
                    if has_status_10 and has_status_22:
                        response_data = {"message": "預約成功,部分課程等待教練確認,部分需要人工安排"}
                    elif has_status_10:
                        response_data = {"message": "預約成功,請等待相關人員協助確認"}
                    elif has_status_22:
                        response_data = {"message": "預約成功,正在等待教練確認接課"}
                    else:
                        # 所有預約都成功自動分配
                        payment_url = PAYMENT_HOST + '?reservation_group=' + str(group.pk)
                        response_data = {
                            "message": "預約成功,已排定教練",
                            "payment_url": payment_url,
                            "status": "success", 
                            "payment_id": payment.id, 
                            "group_id": group.id
                        }
                    
                    return JsonResponse(response_data, status=200)
                    
            except Exception as e:
                # 統一的錯誤處理
                if "排課失敗" in str(e):
                    report = locals().get('schedule_report', {})
                    return JsonResponse({
                        "success": False,
                        "message": str(e),
                        "details": report.get("conflict_details", {})
                    }, status=409)
                return JsonResponse({"message": "預約失敗，系統錯誤請聯繫客服人員", "error": str(e)}, status=500)

    elif tunnel == 'member_detail': #!!!待確認是否還需要
        if request.method == 'POST':
            body = request.data
            user_id = body.get("user_id")
            reservation_pk = body.get("reservation_pk")
            members_data = body.get("members_data", [])
            user = get_object_or_404(User, pk=user_id)
            resv = get_object_or_404(Reservation, pk=reservation_pk)

            # 先刪除與 resv 關聯的所有 MemberDetail 對象
            MemberDetail.objects.filter(reservation=resv).delete()

            created_list = []
            for md in members_data:
                age_range = md.get("age_range", "19-24y")
                snowboard_skills = md.get("snowboard_skills", [])
                ski_skills = md.get("ski_skills", [])

                # 創建 MemberDetail 對象
                member_obj = MemberDetail.objects.create(
                    user=user,
                    reservation=resv,
                    filled_by='user',
                    age_range=age_range,
                    snowboard_skills=snowboard_skills,  # MultiSelectField可以接受list
                    ski_skills=ski_skills
                )
                created_list.append(member_obj.id)

            # # 更新 resv 的 member_count
            # resv.number_of_people = len(created_list)

            # 计算总课程费用
            season = "off"  # 或 "peak"，根据实际情况设置
            total_course_fee = 0
            bookings = Booking.objects.filter(reservation=resv)
            # 使用集合来跟踪已经计算过的日期和课程类型组合
            calculated_courses = set()
            for booking in bookings:
                # 创建一个唯一的标识符用于日期和课程类型组合
                course_key = (booking.date, booking.course_type)
                if course_key not in calculated_courses:
                    # 使用新的價格計算邏輯
                    booking_date = datetime.strptime(booking.date, '%Y-%m-%d').date()
                    season_type = SeasonSetting.get_season_type_for_date(booking_date)
                    try:
                        # 使用新的CoursePricing模型
                        from Coursekit.models import CoursePricing
                        pricing_strategy = CoursePricing.objects.filter(
                            templates=booking.course_type,
                            resort=resv.resort,
                            is_active=True
                        ).first()
                        if pricing_strategy:
                            is_peak_season = (season_type == 'peak')
                            course_fee = pricing_strategy.calculate_price(resv.number_of_people, is_peak_season)
                        else:
                            raise Exception("找不到定價策略")
                    except Exception as e:
                        # 如果找不到定價策略，嘗試使用CoursePricing模型
                        try:
                            from Coursekit.models import CoursePricing
                            pricing = CoursePricing.objects.filter(
                                templates=booking.course_type,
                                resort=resv.resort,
                                is_active=True
                            ).first()
                            if pricing:
                                is_peak_season = (season_type == 'peak')
                                course_fee = pricing.calculate_price(resv.number_of_people, is_peak_season)
                            else:
                                raise Exception(f"找不到對應的價格設定: 課程='{booking.course_type.name}', 雪場='{resv.resort.name}'")
                        except Exception as e:
                            raise Exception(f"找不到對應的價格設定: 課程='{booking.course_type.name}', 人數={resv.number_of_people}, 季節='{season_type}': {str(e)}")
                    total_course_fee += course_fee
                    # 将此组合添加到集合中，避免重复计算
                    calculated_courses.add(course_key)

            resv.course_fee = total_course_fee  # 假设 Reservation 模型有 course_fee 字段

            # 计算设备租赁费
            number_of_courses = 0
            calculated_courses = set()  # 用于跟踪已计算的课程组合
            for booking in bookings:
                # 创建一个唯一的标识符用于日期和课程类型组合
                course_key = (booking.date, booking.course_type)
                if course_key not in calculated_courses:
                    number_of_courses += 1
                    # 将此组合添加到集合中，避免重复计算
                    calculated_courses.add(course_key)

            # 使用雪場綁定的裝備費用
            if resv.resort:
                from Resorts.models import ResortFee
                resv.equipment_rental_fee = ResortFee.get_equipment_fee(resv.resort, resv.number_of_people) * number_of_courses
            else:
                # 如果沒有雪場信息，使用預設費用（保持向後兼容）
                if 1 <= resv.number_of_people <= 3:
                    resv.equipment_rental_fee = 1000 * number_of_courses
                elif 4 <= resv.number_of_people <= 6:
                    resv.equipment_rental_fee = 2000 * number_of_courses
                else:
                    resv.equipment_rental_fee = 0

            resv.status = 'form_filled'
            resv.save()

            price_list = {
                "equipment_rental_fee": resv.equipment_rental_fee,
                "language_fee": resv.language_fee,
                "coach_fee": resv.coach_fee,
                "course_fee": resv.course_fee,
                "total_fee": resv.total_fee
            }
            # 返回成功信息
            return JsonResponse({
                "message": "Members created",
                "price_list": price_list
            }, status=200)
    elif tunnel == 'process_payment':
        if request.method == 'POST':
            body = request.data
            img = body.get('img', False)
            reservation_group_pk = body.get("reservation_group_pk")
            paymentType = body.get("paymentType")
            resv = get_object_or_404(ReservationGroup, pk=reservation_group_pk)
            user_data = body.get("user")
            user_id = user_data.get("id")
            if paymentType == "newebpay":
                # 使用 Newebpay 付款
                bookings = Booking.objects.filter(reservation__in=resv.reservations.all())
                # 使用集合来跟踪已经写过的日期和课程名称组合
                written_courses = set()
                product_name_parts = ["滑雪預約"]

                for booking in bookings:
                    # 假设 booking.date 是一个 datetime 对象
                    # 使用 strftime 格式化日期
                    formatted_date = booking.date.strftime("%Y-%m-%d")
                    course_key = (formatted_date, booking.course_name)
                    if course_key not in written_courses:
                        product_name_parts.append(f"{formatted_date} {booking.course_name}")
                        written_courses.add(course_key)

                product_name = " / ".join(product_name_parts)

                data = {
                    "store": {
                        # "MerchantID": 'FFI1120725001',
                        # "HashKey": 'X4L7m0jAEnbi9AVr92iYfin4ZcHJgdz0',  # 确保此处的 HashKey 长度为 32 字节
                        # "HashIV": 'P1R2FuzKPpSkS48C',  # 确保此处的 HashIV 长度为 16 字节

                        "MerchantID": 'MS3680822811',
                        "HashKey": 'tXnG2aLtEnVzACrJY3CW0SLCLyFYZDEf',
                        "HashIV": 'PKmJnNJCcJyXpqcC',
                        
                        # "MerchantID": 'MS127874575',
                        # "HashKey": 'Fs5cX1TGqYM2PpdbE14a9H83YQSQF5jn',
                        # "HashIV": 'C6AcmfqJILwgnhIP',
                    },
                    "body": {
                        "img": img,  # 商品照片
                        "OrderNo": reservation_group_pk,  # 訂單編號
                        # "price": resv.total_fee,  # 訂單金額
                        "price": '1',  # 訂單金額
                        "product": product_name,  # 商品名
                        "NotifyURL": f"{RUN_HOST}/call_back/NewebPay/?user_id={user_id}",  # 返回網址
                    },
                }
                print('data', data)
                response = neweb_pay_request(data)
                print('response', response)
                return JsonResponse({"message": "Payment confirmed", 'html': response}, status=200)
            elif paymentType == "TT":
                senderAccount = body.get("senderAccount")
                user = User.objects.get(id=user_id)
                # 使用匯款付款
                payment = Payment.objects.get(reservation_group=resv)
                payment.status = 'pending'
                payment.bank_account = senderAccount
                payment.user = user
                payment.save()
                return JsonResponse({"message": "Payment confirmed"}, status=200)
    elif tunnel == 'history_reservations':
        if request.method == 'GET':
            reservations = Reservation.objects.filter(user=request.user)
            reservations_list = []
            for resv in reservations:
                # 获取与预订相关的学生信息
                students = MemberDetail.objects.filter(reservation=resv, filled_by='user').values(
                    'age_range', 'snowboard_skills', 'ski_skills'
                )
                students_coach = MemberDetail.objects.filter(reservation=resv, filled_by='coach').values(
                    'age_range', 'snowboard_skills', 'ski_skills'
                )
                bookings = Booking.objects.filter(reservation=resv)
                sessions = []
                # 格式化学生信息
                formatted_students = [
                    {
                        'age': student['age_range'],
                        'snowboardLevel': student['snowboard_skills'] if student['snowboard_skills'] else ["無"],
                        'skiLevel': student['ski_skills'] if student['ski_skills'] else ["無"]
                    }
                    for student in students
                ]
                formatted_students_coach = [
                    {
                        'age': student_coach['age_range'],
                        'snowboardLevel': student_coach['snowboard_skills'] if student_coach['snowboard_skills'] else ["無"],
                        'skiLevel': student_coach['ski_skills'] if student_coach['ski_skills'] else ["無"]
                    }
                    for student_coach in students_coach
                ]
                for booking in bookings:
                    if booking.course_type == "full-day-5h":
                        # 合并全天课程
                        existing = next((b for b in sessions if b['course_name'] == booking.course_name and b['date'] == booking.date), None)
                        if existing:
                            # 更新结束时间为最新的结束时间
                            existing['endTime'] = max(existing['endTime'], booking.end_time.strftime('%H:%M'))
                        else:
                            sessions.append({
                                'course_name': booking.course_name,
                                'date': booking.date,
                                'startTime': booking.start_time.strftime('%H:%M'),
                                'endTime': booking.end_time.strftime('%H:%M')
                            })
                    else:
                        sessions.append({
                            'course_name': booking.course_name,
                            'date': booking.date,
                            'startTime': booking.start_time.strftime('%H:%M'),
                            'endTime': booking.end_time.strftime('%H:%M')
                        })
                
                # 添加格式化后的预订信息
                reservations_list.append({
                    # 'id': resv.id,
                    'sessions': sessions,
                    'courseType': resv.get_course_type_display(),
                    'language': resv.get_language_display(),
                    'resort': resv.get_resort_display(),
                    'status': resv.get_status_display(),
                    'students': formatted_students,
                    'coach_info': formatted_students_coach,
                })
            return JsonResponse(reservations_list, safe=False, status=200)
        
    elif tunnel == 'payment_gmail':
        if request.method == 'POST':
            from .scheduler import send_gmail
            body = request.data
            gmail = body.get('gmail')
            payment_url = body.get('payment_url')
            subject = "滑雪課程預約付款連結"
            body = f"""
            親愛的用戶您好，

            您的滑雪課程預約已完成，請點擊下方連結進行付款以完成訂單：

            付款連結：{payment_url}

            若有任何問題，歡迎隨時與我們聯繫。
            感謝您的預約，祝您有美好的一天！

            雪域創遊SNOWLAND 敬上
            """
            to_email = gmail

            result = send_gmail(subject, body, to_email)
            return JsonResponse({"message": "成功傳送", 'result': result}, status=200)


# # 後端自己的時段配置表 (舊版，已由 Coursekit.models.Course 取代)
# TIME_SLOT_CONFIG = {
#     "full-day-equipment": {
#         "course_type": "full-day-5h",
#         "course_name": "全天5小時教學課程",
#         "start_time": "09:00",
#         "end_time": "15:00",
#         "date": "(12/01~03/31)",
#         "period": "全天",
#         "totalTime": "09:00-15:00",
#         "mainTime": "09:00-11:30 / 12:30-15:00",
#         "equipmentTime": "08:30-09:00 or 前一日16:00",
#         "need_equipment": True
#     },
#     "full-day": {
#         "course_type": "full-day-5h",
#         "course_name": "全天5小時教學課程",
#         "start_time": "09:00",
#         "end_time": "15:00",
#         "date": "(12/01~03/31)",
#         "period": "全天",
#         "totalTime": "09:00-15:00",
#         "mainTime": "09:00-11:30 / 12:30-15:00",
#         "equipmentTime": None,
#         "need_equipment": False
#     },#5hr
#     "morning-equipment": {
#         "course_type": "half-day-3h",
#         "course_name": "上午3小時教學課程",
#         "start_time": "09:00",
#         "end_time": "12:00",
#         "date": "(12/01~03/31)",
#         "period": "上午",
#         "totalTime": "09:00-12:00",
#         "mainTime": "09:00-12:00",
#         "equipmentTime": "08:30-09:00 or 前一日16:00",
#         "need_equipment": True
#     },
#     "morning": {
#         "course_type": "half-day-3h",
#         "course_name": "上午3小時教學課程",
#         "start_time": "09:00",
#         "end_time": "12:00",
#         "date": "(12/01~03/31)",
#         "period": "上午",
#         "totalTime": "09:00-12:00",
#         "mainTime": "09:00-12:00",
#         "equipmentTime": None,
#         "need_equipment": False
#     },
#     "afternoon-equipment-limited": {
#         "course_type": "half-day-3h",
#         "course_name": "下午3小時教學課程",
#         "start_time": "12:30",
#         "end_time": "15:30",
#         "date": "(12/01~12/25)",
#         "period": "下午",
#         "totalTime": "12:30-15:30",
#         "mainTime": "12:30-15:30",
#         "equipmentTime": "12:30-16:00 or 前一日16:00",
#         "need_equipment": True
#     },
#     "afternoon-limited": {
#         "course_type": "half-day-3h",
#         "course_name": "下午3小時教學課程",
#         "start_time": "12:30",
#         "end_time": "15:30",
#         "date": "(12/01~12/25)",
#         "period": "下午",
#         "totalTime": "12:30-15:30",
#         "mainTime": "12:30-15:30",
#         "equipmentTime": None,
#         "need_equipment": False
#     },
#     "afternoon-equipment": {
#         "course_type": "half-day-3h",
#         "course_name": "下午3小時教學課程",
#         "start_time": "13:00",
#         "end_time": "16:00",
#         "date": "(12/26~03/31)",
#         "period": "下午",
#         "totalTime": "13:00-16:00",
#         "mainTime": "13:30-16:00",
#         "equipmentTime": "12:30-13:00 or 前一日16:00",
#         "need_equipment": True
#     },
#     "afternoon": {
#         "course_type": "half-day-3h",
#         "course_name": "下午3小時教學課程",
#         "start_time": "13:00",
#         "end_time": "16:00",
#         "date": "(12/26~03/31)",
#         "period": "下午",
#         "totalTime": "13:00-16:00",
#         "mainTime": "13:00-16:00",
#         "equipmentTime": None,
#         "need_equipment": False
#     },#3hr
#     "morning-equipment-2h": {
#         "course_type": "half-day-2h",
#         "course_name": "上午2小時教學課程",
#         "start_time": "08:30",
#         "end_time": "11:00",
#         "date": "當日",
#         "period": "上午",
#         "totalTime": "08:30-11:00",
#         "mainTime": "09:00-11:00",
#         "equipmentTime": "08:30-09:00",
#         "need_equipment": True
#     },  
#     "morning-2h": {
#         "course_type": "half-day-2h",
#         "course_name": "上午2小時教學課程",
#         "start_time": "09:00",
#         "end_time": "11:00",
#         "date": "當日",
#         "period": "上午",
#         "totalTime": "09:00-11:00",
#         "mainTime": "09:10-11:00",
#         "equipmentTime": None,
#         "need_equipment": False
#     },
#     "noon-2h": {
#         "course_type": "half-day-2h",
#         "course_name": "中午2小時教學課程",
#         "start_time": "11:30",
#         "end_time": "13:30",
#         "date": "當日",
#         "period": "中午",
#         "totalTime": "11:30-13:30",
#         "mainTime": "11:40-13:30",
#         "equipmentTime": None,
#         "need_equipment": False
#     },
#     "afternoon-2h": {
#         "course_type": "half-day-2h",
#         "course_name": "下午2小時教學課程",
#         "start_time": "13:30",
#         "end_time": "15:30",
#         "date": "當日",
#         "period": "下午",
#         "totalTime": "13:30-15:30",
#         "mainTime": "13:40-15:30",
#         "equipmentTime": None,
#         "need_equipment": False
#     },#2hr
# }

def parse_time_ranges(time_str):
    """
    將類似 '09:10-11:30 / 13:30-15:30' 的字串
    拆成 [(start1, end1), (start2, end2)] (皆為 string)
    """
    segments = [seg.strip() for seg in time_str.split('/') if seg.strip()]
    result = []
    for seg in segments:
        start_end = seg.split('-')
        if len(start_end) == 2:
            start_str = start_end[0].strip()
            end_str   = start_end[1].strip()
            result.append((start_str, end_str))
    return result

def str_to_time(time_s):
    """
    將 '09:10' 轉成 datetime.time(9, 10)
    """
    # 假設格式一定是 HH:MM
    hh, mm = time_s.split(':')
    return datetime.strptime(f"{hh}:{mm}", "%H:%M").time()
