import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from collections import defaultdict
from datetime import datetime, time, timedelta
from .models import Reservation, Booking, Payment
from Coach.models import (
    Coach, CoachResort, CoachCourseLevel,
    ABILITY_LEVEL_CHOICES, normalize_ability_level,
)
from Resorts.models import Resorts
from Coursekit.models import CourseSession, CourseTemplate

COACH_PRICE_LEVEL_RANK = {
    'Lv1': 1,
    'Lv2': 2,
    'Lv3': 3,
    'director': 4,
}

ASSIGNED_RESERVATION_STATUSES = [
    'auto_assigned',
    'manually_assigned',
    'pending_coach_confirmation',
    'completed',
]

MOVABLE_ASSIGNED_STATUSES = [
    'auto_assigned',
    'manually_assigned',
    'pending_coach_confirmation',
]

SCHEDULER_MUTABLE_STATUSES = ['created', *MOVABLE_ASSIGNED_STATUSES]


def _assignment_status_for_coach(coach, previous_status='created'):
    if coach.availability_status == 'passive':
        return 'pending_coach_confirmation'
    if previous_status == 'manually_assigned':
        return 'manually_assigned'
    return 'auto_assigned'


def _snapshot_reservation_state(reservation, snapshots):
    if reservation.id in snapshots:
        return
    snapshots[reservation.id] = {
        'preferred_coach_id': reservation.preferred_coach_id,
        'status': reservation.status,
        'bookings': [
            (booking.id, booking.is_scheduled)
            for booking in reservation.bookings.all()
        ],
    }


def _restore_reservation_snapshots(snapshots):
    for reservation_id, snapshot in snapshots.items():
        Reservation.objects.filter(id=reservation_id).update(
            preferred_coach_id=snapshot['preferred_coach_id'],
            status=snapshot['status'],
        )
        for booking_id, is_scheduled in snapshot['bookings']:
            Booking.objects.filter(id=booking_id).update(is_scheduled=is_scheduled)


def _remove_reservation_from_busy_map(reservation, coach_busy_map):
    coach_id = reservation.preferred_coach_id
    if not coach_id:
        return
    busy_slots = coach_busy_map.get(coach_id, [])
    for booking in reservation.bookings.all():
        if not booking.is_scheduled:
            continue
        slot = (booking.date, booking.start_time, booking.end_time)
        try:
            busy_slots.remove(slot)
        except ValueError:
            pass


def _find_movable_conflicts_for_preferred(reservation, exclude_ids):
    coach = reservation.preferred_coach
    if not coach:
        return []

    conflicts = Reservation.objects.none()
    for booking in reservation.bookings.all():
        conflicts = conflicts | Reservation.objects.filter(
            preferred_coach=coach,
            is_preferred_coach=False,
            status__in=MOVABLE_ASSIGNED_STATUSES,
            bookings__is_scheduled=True,
            bookings__date=booking.date,
            bookings__start_time__lt=booking.end_time,
            bookings__end_time__gt=booking.start_time,
        )

    return list(
        conflicts.exclude(id__in=exclude_ids)
        .select_related('preferred_coach', 'resort', 'course_type', 'course_template')
        .prefetch_related('bookings', 'rejected_coaches')
        .distinct()
    )


def _coach_assignment_status_rank(coach):
    return 0 if coach.availability_status == 'active' else 1


def assign_coachs(reservations_to_assign=None):
    """
    主要排程與分配教練的函數
    核心邏輯：
    1) 建立一個包含所有已存在且不可移動的預約的忙碌表。
    2) 處理傳入的、需要排程的預約。
    可以傳入一個 reservation 列表來只處理這些預約，否則會處理所有未分配的預約。
    返回: (success, report)
    """
    
    if reservations_to_assign is not None:
        incoming_ids = {r.id for r in reservations_to_assign}
    else:
        incoming_ids = set()

    # 建立一個字典來儲存所有教練在特定日期的忙碌時段
    coach_busy_map = defaultdict(list)
    
    # --- 步驟 1: 建立基礎忙碌表，包含所有已確認且不可移動的預約 ---
    existing_confirmed_reservations = Reservation.objects.filter(
        status__in=ASSIGNED_RESERVATION_STATUSES
    ).exclude(id__in=incoming_ids).select_related('preferred_coach').prefetch_related('bookings')

    for resv in existing_confirmed_reservations:
        if resv.preferred_coach:
            coach_id = resv.preferred_coach_id
            for b in resv.bookings.all():
                if not b.is_scheduled:
                    continue
                coach_busy_map[coach_id].append((b.date, b.start_time, b.end_time))

    # --- 處理手動指定的預約，確保它們不會與現有預約衝突 ---
    # 這部分邏輯在新的架構下需要重新審視，因為 'manually_assigned' 已經在上面被處理
    # 我們可以假設傳入的 reservations_to_assign 不包含手動指定的
    
    # 排序忙碌時間表
    for inst_id in coach_busy_map:
        coach_busy_map[inst_id].sort(key=lambda x: (x[0], x[1]))

    # --- 步驟 2: 收集並處理需要自動排程的預約 ---
    state_snapshots = {}
    if reservations_to_assign is not None:
        # 只處理傳入的預約
        all_unspecified = [r for r in reservations_to_assign if not r.is_preferred_coach]
    else:
        # 處理所有需要自動排程的預約
        all_unspecified = list(
            Reservation.objects.filter(is_preferred_coach=False, status='created')
        )
    
    # 處理指定教練的預約 (在傳入的列表中)
    displaced_reservations = {}
    if reservations_to_assign is not None:
        preferred_in_request = [r for r in reservations_to_assign if r.is_preferred_coach]
        for resv in preferred_in_request:
            _snapshot_reservation_state(resv, state_snapshots)
            coach = resv.preferred_coach
            if not coach:
                # 這裡應該不會發生，因為 is_preferred_coach=True
                continue

            if not coach_matches_course_template(coach, resv.course_template):
                rule_label = course_template_restriction_label(resv.course_template) or '教練條件'
                error_msg = f"錯誤：指定教練 {coach.name} 不符合課程模板教練條件（{rule_label}）"
                resv.status = 'auto_assignment_failed'
                resv.save()
                _restore_reservation_snapshots(state_snapshots)
                return False, {
                    "error": error_msg,
                    "reservation_id": resv.id,
                    "conflict_details": {
                        "identifier": f"於「{resv.resort.display_name if resv.resort else '?'}」的「{resv.get_course_type_display()}」",
                        "reason": error_msg,
                    },
                }

            movable_conflicts = _find_movable_conflicts_for_preferred(resv, incoming_ids | {resv.id})
            for displaced in movable_conflicts:
                if displaced.id not in displaced_reservations:
                    displaced_reservations[displaced.id] = displaced
                    _snapshot_reservation_state(displaced, state_snapshots)
                    _remove_reservation_from_busy_map(displaced, coach_busy_map)
            
            is_resv_conflict = False
            for b in resv.bookings.all():
                if is_conflict(b.date, b.start_time, b.end_time, coach_busy_map[coach.id]):
                    error_msg = f"錯誤：指定教練的預約 {resv.id} 與教練 {coach.name} 現有行程衝突"
                    resv.status = 'auto_assignment_failed'
                    resv.save()
                    _restore_reservation_snapshots(state_snapshots)
                    return False, {"error": error_msg, "reservation_id": resv.id}
            
            # 如果沒有衝突，則將其加入忙碌表並更新狀態
            booking_ids = []
            for b in resv.bookings.all():
                coach_busy_map[coach.id].append((b.date, b.start_time, b.end_time))
                booking_ids.append(b.id)
            
            resv.status = _assignment_status_for_coach(coach, resv.status)
            resv.save()
            Booking.objects.filter(id__in=booking_ids).update(is_scheduled=True)
            # print(f"成功鎖定指定教練預約 {resv.id} 給 {coach.name}")

    if displaced_reservations:
        existing_unspecified_ids = {r.id for r in all_unspecified}
        all_unspecified.extend([
            r for r in displaced_reservations.values()
            if r.id not in existing_unspecified_ids
        ])

    resv_list = []
    for resv in all_unspecified:
        _snapshot_reservation_state(resv, state_snapshots)
        rejected_ids = list(resv.rejected_coaches.values_list('id', flat=True))
        # 修正：傳遞 course_type 的 ID，而不是物件本身，以確保與預檢查的邏輯一致
        fi = get_feasible_coaches(
            resv.language,
            resv.resort,
            resv.course_type_id,
            resv.max_ability_level,
            rejected_coach_ids=rejected_ids,
            course_template=resv.course_template,
        )
        if (
            resv.id in displaced_reservations and
            Payment.objects.filter(reservation_group=resv.group).exists()
        ):
            fi = [coach for coach in fi if coach.availability_status == 'active']
        if not fi:
            # 細化原因，讓前端 / 後台能看出卡在哪
            reason = _diagnose_no_feasible_coach(resv)
            error_msg = f"預約 {resv.id} 找不到可行教練：{reason}"
            resv.status = 'auto_assignment_failed'
            resv.save()
            _restore_reservation_snapshots(state_snapshots)
            return False, {
                "error": error_msg,
                "reservation_id": resv.id,
                "conflict_details": {
                    "identifier": f"於「{resv.resort.display_name if resv.resort else '?'}」的「{resv.get_course_type_display()}」",
                    "reason": reason,
                },
            }
        
        # 重置狀態以便重新分配
        resv.preferred_coach = None
        for b in resv.bookings.all():
            b.is_scheduled = False
            b.save()
        resv.save()
        resv_list.append((resv, fi))

    # 根據可行教練數量排序，最難安排的先排
    resv_list.sort(key=lambda x: len(x[1]))

    capacity_report = _precheck_batch_capacity(resv_list, coach_busy_map)
    if capacity_report:
        _restore_reservation_snapshots(state_snapshots)
        return False, capacity_report

    success, report = backtrack_assign(resv_list, 0, coach_busy_map)
    if success:
        affected_ids = set()
        affected_ids.update(resv.id for resv, _ in resv_list)
        if reservations_to_assign is not None:
            affected_ids.update(resv.id for resv in reservations_to_assign)
        pending_ids = list(
            Reservation.objects.filter(
                id__in=affected_ids,
                status='pending_coach_confirmation',
            ).values_list('id', flat=True)
        )
        report = {
            **report,
            'displaced_reservation_ids': list(displaced_reservations.keys()),
            'pending_coach_confirmation_reservation_ids': pending_ids,
        }
        return True, report
    else:
        _restore_reservation_snapshots(state_snapshots)
        return False, report

def _bookings_signature(bookings_list):
    return tuple(sorted((b.date, b.start_time, b.end_time) for b in bookings_list))


def _capacity_failure_report(resv, feasible_coaches, coach_busy_map, reason):
    resv.status = 'auto_assignment_failed'
    resv.save()
    bookings_list = list(resv.bookings.all())
    conflict_dates = list(set(b.date for b in bookings_list))
    suggestions = _generate_suggestion_report(conflict_dates, feasible_coaches, coach_busy_map)
    return {
        "error": reason,
        "reservation_id": resv.id,
        "conflict_details": {
            "identifier": f"於「{resv.resort.display_name}」的「{resv.get_course_type_display()}」（最高能力：{resv.get_max_ability_level_display()}）課程",
            "reason": reason,
            "suggestions": suggestions.get("suggestions", {}),
        },
    }


def _precheck_batch_capacity(resv_list, coach_busy_map):
    groups = {}
    for resv, feasible_coaches in resv_list:
        bookings_list = list(resv.bookings.all())
        candidate_coaches = [
            coach for coach in feasible_coaches
            if can_assign_all_bookings(bookings_list, coach.id, coach_busy_map)
        ]
        if not candidate_coaches:
            return _capacity_failure_report(
                resv,
                feasible_coaches,
                coach_busy_map,
                "此日期時段目前沒有可用教練，請改選其他日期或等待客服協助安排。",
            )

        key = (
            _bookings_signature(bookings_list),
            tuple(sorted(coach.id for coach in candidate_coaches)),
        )
        if key not in groups:
            groups[key] = {
                "count": 0,
                "resv": resv,
                "candidate_coaches": candidate_coaches,
            }
        groups[key]["count"] += 1

    for group in groups.values():
        if group["count"] > len(group["candidate_coaches"]):
            return _capacity_failure_report(
                group["resv"],
                group["candidate_coaches"],
                coach_busy_map,
                f"此日期時段最多可安排 {len(group['candidate_coaches'])} 組，目前訂單需要 {group['count']} 組，請改選其他日期或等待客服協助安排。",
            )

    return None

def _diagnose_no_feasible_coach(resv):
    """逐項檢查為何找不到教練，回傳人話原因"""
    total = Coach.objects.exclude(availability_status='unavailable').count()
    if total == 0:
        return "後台尚未建立任何可上班的教練"

    by_lang = Coach.objects.exclude(availability_status='unavailable') \
        .filter(languages__contains=resv.language).count() if resv.language else total
    if by_lang == 0:
        return f"沒有教練會「{resv.language}」此語言"

    at_resort_ids = CoachResort.objects.filter(resort=resv.resort).values_list('coach_id', flat=True)
    by_resort = Coach.objects.filter(id__in=at_resort_ids).count()
    if by_resort == 0:
        return f"沒有教練在「{resv.resort.display_name}」執教"

    has_course = CoachCourseLevel.objects.filter(course_type=resv.course_type).count()
    if has_course == 0:
        return f"沒有教練設定可教「{resv.get_course_type_display()}」課程類型（請去後台「教練管理」設定教學項目）"

    template_obj = resolve_course_template(resv.course_template)
    template_rule = course_template_restriction_label(template_obj)
    if template_obj and template_obj.minimum_coach_price_level and template_rule:
        return f"符合語言/雪場/課程的教練，不符合模板教練條件（{template_rule}）"

    return "符合條件的教練都被排除（語言/雪場/課程/能力等級任一項不符）"


def _normalize_multiselect(value):
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    return list(value)


def _price_level_rank(value):
    return COACH_PRICE_LEVEL_RANK.get(value or '', 0)


def resolve_course_template(course_template):
    if not course_template:
        return None
    if isinstance(course_template, CourseTemplate):
        return course_template
    try:
        return CourseTemplate.objects.select_related('course_type').prefetch_related('allowed_coaches').get(id=course_template)
    except (TypeError, ValueError, CourseTemplate.DoesNotExist):
        return None


def course_template_restriction_label(course_template):
    course_template = resolve_course_template(course_template)
    if not course_template:
        return ''
    parts = []
    if course_template.minimum_coach_price_level:
        parts.append(course_template.get_minimum_coach_price_level_display())
    allowed_count = course_template.allowed_coaches.count()
    if allowed_count:
        parts.append(f'優先安排 {allowed_count} 位教練')
    return '、'.join(parts)


def coach_matches_course_template(coach, course_template, coach_course_level=None, allowed_coach_ids=None):
    course_template = resolve_course_template(course_template)
    if not course_template:
        return True

    minimum_level = course_template.minimum_coach_price_level
    if not minimum_level:
        return True

    if coach_course_level is None:
        coach_course_level = CoachCourseLevel.objects.filter(
            coach=coach,
            course_type=course_template.course_type,
        ).first()
    if not coach_course_level:
        return False

    return _price_level_rank(coach_course_level.price_level) >= _price_level_rank(minimum_level)


def get_coach_assignment_score_for_resort(coach, resort):
    if resort:
        resort_link = CoachResort.objects.filter(coach=coach, resort=resort).first()
        if resort_link:
            return resort_link.assignment_score
    return coach.assignment_score


def get_feasible_coaches(language, resort, course_type, max_ability_level, rejected_coach_ids=None, course_template=None):
    """
    找出符合指定條件的可行教練列表。
    新的排序邏輯：
    1. 課程模板優先名單
    2. 主動接課優先，需確認接課排在最後
    3. CoachCourseLevel 的 course_order (數字越小越優先)
    4. Coach 的 assignment_score (分數越低越優先)
    """
    if rejected_coach_ids is None:
        rejected_coach_ids = []

    course_template_obj = resolve_course_template(course_template)
    if course_template_obj and not course_type:
        course_type = course_template_obj.course_type_id
    allowed_coach_ids = set()
    if course_template_obj:
        allowed_coach_ids = set(course_template_obj.allowed_coaches.values_list('id', flat=True))

    # 0. 基礎查詢：只考慮可接課的教練
    available_coaches = Coach.objects.exclude(availability_status='unavailable')
    
    # 1. 語言能力
    available_coaches = available_coaches.filter(languages__contains=language)
    
    # 2. 雪場匹配
    coach_ids_at_resort = CoachResort.objects.filter(resort=resort).values_list('coach_id', flat=True)
    available_coaches = available_coaches.filter(id__in=coach_ids_at_resort)
    
    # 3. 課程與能力等級，並收集排序所需資訊
    
    def can_teach_level(ability_levels):
        # 只要教練有「等於或高於」需求等級的都算可接
        desired_idx = ability_level_index(max_ability_level)
        for lv in _normalize_multiselect(ability_levels):
            if ability_level_index(lv) >= desired_idx:
                return True
        return False

    final_coaches_with_priority = []
    for coach in available_coaches:
        # 檢查教練是否能教此課程類型
        can_teach = coach_can_teach_course(coach, course_type)
        if can_teach:
            # 獲取該教練在此課程類型下的能力等級與接客順序
            coach_levels = CoachCourseLevel.objects.filter(coach=coach, course_type=course_type).first()
            if (
                coach_levels and
                can_teach_level(coach_levels.ability_levels) and
                coach_matches_course_template(
                    coach,
                    course_template_obj,
                    coach_course_level=coach_levels,
                    allowed_coach_ids=allowed_coach_ids,
                )
            ):
                final_coaches_with_priority.append({
                    "coach": coach,
                    "course_order": coach_levels.course_order,
                    "template_priority": 0 if allowed_coach_ids and coach.id in allowed_coach_ids else 1,
                    "status_rank": _coach_assignment_status_rank(coach),
                    "score": get_coach_assignment_score_for_resort(coach, resort)
                })

    # 模板優先名單先嘗試，但不會排除其他合格教練；需確認教練留到主動教練都排不進去時才嘗試。
    final_coaches_with_priority.sort(
        key=lambda x: (
            x['status_rank'],
            x['template_priority'],
            x['course_order'],
            x['score'],
            x['coach'].id,
        )
    )
    
    # 從排序好的列表中僅取出 coach 物件
    final_coaches = [item['coach'] for item in final_coaches_with_priority]
    
    # 4. 排除被拒絕過的教練
    if rejected_coach_ids:
        final_coaches = [coach for coach in final_coaches if coach.id not in rejected_coach_ids]
    
    return final_coaches

def coach_can_teach_course(coach, desired_course_type):
    """
    用 CoachCourseLevel 判斷教練是否會這個課程類型
    """
    if not desired_course_type:
        return True
    return CoachCourseLevel.objects.filter(coach=coach, course_type=desired_course_type).exists()

def ability_level_index(level):
    try:
        level = normalize_ability_level(level)
        # 修正：從 (key, value) 的 tuple 列表中，只取出 key 來尋找索引
        level_keys = [item[0] for item in ABILITY_LEVEL_CHOICES]
        return level_keys.index(level)
    except ValueError:
        # 如果找不到，回傳一個不可能的索引，避免錯誤
        return -1

def backtrack_assign(resv_list, idx, coach_busy_map):
    if idx == len(resv_list):
        return True, {}
        
    (resv, feasible_coaches) = resv_list[idx]
    bookings_list = list(resv.bookings.all())
    
    original_coach_id = resv.preferred_coach_id
    original_scheduled_status = [(b.id, b.is_scheduled) for b in bookings_list]
    original_status = resv.status

    # feasible_coaches 列表已經根據 assignment_score 排序，直接遍歷即可
    for inst in feasible_coaches:
        if can_assign_all_bookings(bookings_list, inst.id, coach_busy_map):
            original_busy = []
            for b in bookings_list:
                coach_busy_map[inst.id].append((b.date, b.start_time, b.end_time))
                original_busy.append((b.date, b.start_time, b.end_time))
            coach_busy_map[inst.id].sort(key=lambda x: (x[0], x[1]))
            
            # 成功指派，增加教練的權重分數
            
            resv.preferred_coach_id = inst.id
            if original_status in SCHEDULER_MUTABLE_STATUSES:
                resv.status = _assignment_status_for_coach(inst, original_status)
            resv.save()
            for b in bookings_list:
                b.is_scheduled = True
                b.save()
                
            success, report = backtrack_assign(resv_list, idx + 1, coach_busy_map)
            if success:
                return True, {}
                
            # 回溯：如果後續失敗，需要將分數減回來

            for busy_slot in original_busy:
                coach_busy_map[inst.id].remove(busy_slot)
            coach_busy_map[inst.id].sort(key=lambda x: (x[0], x[1]))
            resv.preferred_coach_id = original_coach_id
            resv.status = original_status
            resv.save()
            for (b_id, old_sch) in original_scheduled_status:
                b = Booking.objects.get(id=b_id)
                b.is_scheduled = old_sch
                b.save()
            
    error_msg = f"預約 {resv.id} 在所有可行教練中都找不到無衝突的時段"

    # 設置預約狀態為排課失敗
    resv.status = 'auto_assignment_failed'
    resv.save()

    # Generate detailed suggestion report
    conflict_dates = list(set(b.date for b in bookings_list))
    suggestions = _generate_suggestion_report(conflict_dates, feasible_coaches, coach_busy_map)

    # 建立更詳細的報告，以便前端可以識別是哪個預約失敗了
    report = {
        "error": error_msg,
        "conflict_details": {
            "identifier": f"於「{resv.resort.display_name}」的「{resv.get_course_type_display()}」（最高能力：{resv.get_max_ability_level_display()}）課程",
            "suggestions": suggestions.get("suggestions", {})
        }
    }
    return False, report

def can_assign_all_bookings(bookings_list, coach_id, coach_busy_map):
    busy_list = coach_busy_map[coach_id]
    for b in bookings_list:
        if is_conflict(b.date, b.start_time, b.end_time, busy_list):
            return False
    return True

def is_conflict(date, start, end, busy_list):
    for (d, s, e) in busy_list:
        if d == date:
            # time overlap => [start, end) 與 [s, e) 相交
            if not (end <= s or start >= e):
                return True
    return False

def get_coach_load(inst_id, coach_busy_map):
    total_hours = 0
    for (d, s, e) in coach_busy_map[inst_id]:
        total_hours += get_duration_in_hours(s, e)
    return total_hours

def get_duration_in_hours(start_time, end_time):
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    diff = end_minutes - start_minutes
    return diff / 60.0

def _generate_suggestion_report(conflict_dates, all_potential_coaches, coach_busy_map, nearby_days=3):
    """
    為衝突日期及前後 nearby_days 天，生成可用時段建議報告。
    報告每個日期包含上午/下午/全天的可用教練數量。
    """
    report = {}
    potential_coaches_set = set(all_potential_coaches)

    # 將衝突日期擴展為「衝突日 ± nearby_days」的集合
    dates_to_check = set()
    for cd in conflict_dates:
        for delta in range(-nearby_days, nearby_days + 1):
            dates_to_check.add(cd + timedelta(days=delta))

    all_day_slots = [
        {'name': '上午', 'segments': [('09:00', '12:00')]},
        {'name': '下午', 'segments': [('13:00', '16:00')]},
        {'name': '全天', 'segments': [('09:00', '12:00'), ('13:00', '16:00')]},
    ]

    for check_date in sorted(dates_to_check):
        date_suggestions = {}
        for slot in all_day_slots:
            available = set()
            for coach in potential_coaches_set:
                ok = True
                for start_s, end_s in slot['segments']:
                    start_t, end_t = _str_to_time(start_s), _str_to_time(end_s)
                    if is_conflict(check_date, start_t, end_t, coach_busy_map.get(coach.id, [])):
                        ok = False
                        break
                if ok:
                    available.add(coach.id)

            if available:
                date_suggestions[slot['name']] = {"available_sessions": len(available)}

        if date_suggestions:
            report[check_date.strftime('%Y-%m-%d')] = date_suggestions

    return {"suggestions": report}

def _parse_time_segments_from_db(slot_id):
    """
    透過 slot_id 從資料庫查詢 Course 物件，並解析其 main_time。
    取代舊的 _parse_time_ranges 函式。
    """
    try:
        # 首先嘗試從CourseTemplate模型查找
        course_template = CourseTemplate.objects.get(id=slot_id)
        # CourseTemplate沒有main_time，需要從CourseSession獲取時間段
        sessions = CourseSession.objects.filter(template=course_template, is_active=True)
        if sessions.exists():
            result = []
            for session in sessions:
                start_time_str = session.start_time.strftime('%H:%M')
                end_time_str = session.end_time.strftime('%H:%M')
                result.append((start_time_str, end_time_str))
            return result
        else:
            return []
    except CourseTemplate.DoesNotExist:
        try:
            # 如果CourseTemplate模型找不到，嘗試從CourseSession模型查找
            course_session = CourseSession.objects.get(id=slot_id)
            # 從CourseSession創建時間段
            start_time_str = course_session.start_time.strftime('%H:%M')
            end_time_str = course_session.end_time.strftime('%H:%M')
            return [(start_time_str, end_time_str)]
        except CourseSession.DoesNotExist:
            return []

def _str_to_time(time_s):
    return time(*map(int, time_s.split(':')))

def check_availability_and_get_suggestions(courses):
    """
    對一個包含多個課程請求的完整訂單進行可用性檢查。
    這是一個"全有或全無"的檢查。如果任何一個時段無法滿足，則整個訂單失敗，
    並返回詳細的衝突和建議報告。
    返回: (is_successful, report)
    """
    lang_map_reverse = {"中文": "zh", "英文": "en", "粵語": "yue"}
    
    # 步驟 1: 建立所有請求日期和可行教練的"世界狀態"
    all_requested_dates = set()
    all_potential_coaches = set()
    
    for course in courses:
        resort_name = course.get("resort")
        resort = Resorts.objects.get(name=resort_name)
        
        # 收集所有請求的日期
        for slot in course.get("booking", []):
            all_requested_dates.add(datetime.strptime(slot['date'], '%Y-%m-%d').date())
        
        # 收集所有潛在的教練
        # 注意：這裡的 get_feasible_coachs 是一個簡化表示，我們需要根據課程要求來篩選
        # 直接傳遞參數，而不是創建臨時物件
        language_name = course.get("language", "中文")
        language_code = lang_map_reverse.get(language_name, language_name)
        feasible_coaches_for_course = get_feasible_coaches(
            language=language_code,
            resort=resort,
            course_type=course.get("courseType"),
            max_ability_level=course.get("abilityLevel"),
            course_template=course.get("courseTemplateId"),
        )
        all_potential_coaches.update(feasible_coaches_for_course)

    # 建立所有潛在教練在所有請求日期的忙碌時間表
    coach_busy_map = defaultdict(list)
    existing_bookings = Booking.objects.filter(
        reservation__preferred_coach__in=list(all_potential_coaches),
        date__in=list(all_requested_dates),
        is_scheduled=True,
        reservation__status__in=['auto_assigned', 'manually_assigned', 'pending_coach_confirmation', 'completed']
    )
    for b in existing_bookings:
        coach_busy_map[b.reservation.preferred_coach_id].append((b.date, b.start_time, b.end_time))

    # 步驟 2: 模擬預約並檢查衝突
    conflicts = {}
    is_order_successful = True
    
    for course in courses:
        resort_name = course.get("resort")
        resort = Resorts.objects.get(name=resort_name)
        
        # 再次直接傳遞參數
        language_name = course.get("language", "中文")
        language_code = lang_map_reverse.get(language_name, language_name)
        feasible_coaches = get_feasible_coaches(
            language=language_code,
            resort=resort,
            course_type=course.get("courseType"),
            max_ability_level=course.get("abilityLevel"),
            course_template=course.get("courseTemplateId"),
        )
        
        for slot in course.get("booking", []):
            requested_date = datetime.strptime(slot['date'], '%Y-%m-%d').date()
            
            # 使用新的函式從資料庫獲取時間段
            time_segments = _parse_time_segments_from_db(slot.get("timeSlot"))
            
            if not time_segments:
                # 如果找不到時段，這是一個無效的請求，直接標記為失敗
                is_order_successful = False
                if requested_date not in conflicts:
                    conflicts[requested_date] = {"requested": slot.get("timeSlot"), "suggestions": {}}
                continue

            for start_s, end_s in time_segments:
                start_t, end_t = _str_to_time(start_s), _str_to_time(end_s)
                
                # 檢查是否有任何一個可行教練在該時段是空閒的
                is_slot_bookable = False
                for coach in feasible_coaches:
                    coach_busy = coach_busy_map[coach.id]
                    has_conflict = is_conflict(requested_date, start_t, end_t, coach_busy)
                    if not has_conflict:
                        is_slot_bookable = True
                        break # 找到一個就行
                
                if not is_slot_bookable:
                    is_order_successful = False
                    if requested_date not in conflicts:
                        conflicts[requested_date] = {"requested": slot.get("timeSlot"), "suggestions": {}}
    
    if is_order_successful:
        return True, {}

    # 步驟 3: 如果訂單失敗，生成詳細的建議報告
    conflict_date_objects = list(conflicts.keys())
    suggestions_report = _generate_suggestion_report(conflict_date_objects, list(all_potential_coaches), coach_busy_map)

    # 將請求的時段資訊加入報告中，以提供更完整的上下文
    final_report_conflicts = {}
    for date_obj, details in conflicts.items():
        date_str = date_obj.strftime('%Y-%m-%d')
        final_report_conflicts[date_str] = {
            "requested": details["requested"],
            "suggestions": suggestions_report.get("suggestions", {}).get(date_str, {})
        }

    return False, {"conflicts": final_report_conflicts}


def send_gmail(subject, body, to_email):
    from_email = "land110602@gmail.com"
    password = "weyw fsym lkps plql"

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_email, password)
    server.sendmail(from_email, to_email, msg.as_string())
    server.quit()
    return 'ok'

def reassign_single_reservation(reservation_id):
    """
    重新排課單個預約，不影響其他預約
    專門用於教練拒絕後的重新分配
    """
    from django.db import models
    from .models import Reservation, Booking, Coach
    from Coach.models import CoachResort
    
    print(f"\n=== 開始單個預約重新排課：Reservation ID {reservation_id} ===")
    
    try:
        reservation = Reservation.objects.get(id=reservation_id)
    except Reservation.DoesNotExist:
        print(f"錯誤：預約 {reservation_id} 不存在")
        return False
    
    print(f"預約詳情：用戶={reservation.group.user}, 課程={reservation.course_type}, 狀態={reservation.status}")
    
    # 1. 建立教練忙碌表 - 只考慮其他已確認的預約
    coach_busy_map = {inst.id: [] for inst in Coach.objects.all()}
    
    # 排除當前預約，查詢其他已確認的預約來建立忙碌表
    other_confirmed_reservations = Reservation.objects.exclude(id=reservation_id).filter(
        models.Q(is_preferred_coach=True) | models.Q(status__in=['auto_assigned', 'manually_assigned', 'pending_coach_confirmation'])
    )
    
    print(f"其他已確認預約數量：{other_confirmed_reservations.count()}")
    
    for other_resv in other_confirmed_reservations:
        if not other_resv.preferred_coach:
            continue
        inst_id = other_resv.preferred_coach_id
        
        for booking in other_resv.bookings.all():
            if booking.is_scheduled:
                coach_busy_map[inst_id].append((booking.date, booking.start_time, booking.end_time))
    
    # 排序忙碌時間表
    for inst_id in coach_busy_map:
        coach_busy_map[inst_id].sort(key=lambda x: (x[0], x[1]))
    
    # 2. 檢查當前預約是否有可行的教練
    rejected_ids = list(reservation.rejected_coaches.values_list('id', flat=True))
    feasible_coaches = get_feasible_coaches(
        reservation.language,
        reservation.resort,
        reservation.course_type,
        reservation.max_ability_level,
        rejected_coach_ids=rejected_ids,
        course_template=reservation.course_template,
    )
    if not feasible_coaches:
        print(f"預約 {reservation_id} 沒有可行的教練，設為需要人工處理")
        reservation.status = 'auto_assignment_failed'  # 需人工排定教練
        reservation.preferred_coach = None
        reservation.save()
        
        # 清除 booking 的排程狀態
        for booking in reservation.bookings.all():
            booking.is_scheduled = False
            booking.save()
        
        return False
    
    print(f"可行教練：{[c.name for c in feasible_coaches]}")
    
    # 3. 備份當前狀態
    original_coach_id = reservation.preferred_coach_id
    original_status = reservation.status
    original_bookings_scheduled = [(b.id, b.is_scheduled) for b in reservation.bookings.all()]
    
    # 4. 清除當前預約的教練和排程狀態
    reservation.preferred_coach = None
    reservation.save()
    for booking in reservation.bookings.all():
        booking.is_scheduled = False
        booking.save()
    
    # 5. 嘗試為這個預約分配教練
    bookings_list = list(reservation.bookings.all())
    
    # 根據接課狀態、雪場優先級和教練負載排序
    def coach_sort_key(coach):
        status_rank = _coach_assignment_status_rank(coach)
        resort_priority = 0
        resort_qs = CoachResort.objects.filter(coach=coach, resort=reservation.resort)
        if resort_qs.exists():
            resort_priority = resort_qs.first().resort_priority
        coach_load = get_coach_load(coach.id, coach_busy_map)
        assignment_score = get_coach_assignment_score_for_resort(coach, reservation.resort)
        return (status_rank, resort_priority, assignment_score, coach_load, coach.id)
    
    feasible_coaches.sort(key=coach_sort_key)
    
    # 6. 嘗試分配每個可行的教練
    for coach in feasible_coaches:
        print(f"嘗試分配教練：{coach.name} (ID: {coach.id})")
        
        # 檢查是否可以分配所有時段
        if can_assign_all_bookings(bookings_list, coach.id, coach_busy_map):
            print(f"教練 {coach.name} 無時間衝突，進行分配")
            
            # 分配成功
            reservation.preferred_coach = coach
            
            # 根據教練狀態設置預約狀態
            if coach.availability_status == 'passive':
                reservation.status = 'pending_coach_confirmation' # 等待教練確認
                print(f"教練 {coach.name} 為 passive 狀態，設置為等待確認")
            else:
                reservation.status = 'auto_assigned' # 已自動排定教練
                print(f"教練 {coach.name} 為 active 狀態，直接確認")
            
            reservation.save()
            
            # 設置 booking 為已排程
            for booking in bookings_list:
                booking.is_scheduled = True
                booking.save()
            
            print(f"✅ 成功將預約 {reservation_id} 分配給教練 {coach.name}")
            return True
        else:
            print(f"教練 {coach.name} 有時間衝突，跳過")
    
    # 7. 如果所有教練都無法分配，恢復原狀態並設為需人工處理
    print(f"❌ 無法為預約 {reservation_id} 找到合適的教練")
    
    reservation.preferred_coach_id = original_coach_id
    reservation.status = 'manual_assignment_needed' # 需人工排定教練
    reservation.save()
    
    # 恢復 booking 狀態
    for booking_id, was_scheduled in original_bookings_scheduled:
        booking = Booking.objects.get(id=booking_id)
        booking.is_scheduled = was_scheduled
        booking.save()
    
    print(f"已將預約 {reservation_id} 設為需要人工處理")
    return False
