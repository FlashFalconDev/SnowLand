"""Atomic, versioned order changes and separate outstanding-balance records. No money transfer."""
from collections import defaultdict
from types import SimpleNamespace

from django.core import signing
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers

from Client.models import Client
from Coach.models import Coach, CoachLeaveRequest
from Coursekit.models import CourseTemplate
from booking.models import Booking, MemberDetail, OrderAmendment, Reservation, ReservationGroup
from booking.course_documents import capture_course_documents, save_course_documents
from booking.operations import order_snapshot, record_order_revision, resolve_payment_account
from .manual_notifications import NotificationConflict
from .order_amendments import AmendmentQuoteInput, amendment_digest, amendment_state, quote_order_amendment


class AmendmentConfirmInput(AmendmentQuoteInput):
    quote_token=serializers.CharField(max_length=4000)
    request_key=serializers.UUIDField()
    reason=serializers.CharField(max_length=1000)
    confirmed=serializers.BooleanField()
    reschedule=serializers.BooleanField(default=False)

    def validate_confirmed(self,value):
        if not value:raise serializers.ValidationError('請核對原價、新價、差額及學員後確認修改')
        return value


def amendment_summary(row,duplicate=False):
    from booking.amendment_notifications import notice_receipt
    document_notice=' 課程變更的舊文件已留底；已簽學員須重新簽署，已投保者請行政重新核對。' if row.revision.member_document_revisions.exists() else ''
    return {**({'settlement':row.currency_snapshot} if row.currency_snapshot else {}),'id':row.pk,'version':row.revision.version,'previous_total':row.previous_total,'new_total':row.new_total,
        'difference_amount':row.difference_amount,'balance_amount':row.balance_amount,'status':row.status,
        'participant_changes':row.participant_changes,'bank_snapshot':row.bank_snapshot,'duplicate':duplicate,
        'notification_status':notice_receipt(row)['email'],'notification':notice_receipt(row),
        'notice':'訂單修改已留底；通知狀態另列，系統沒有執行收款或退款。'+document_notice}


def _verify_quote(group,data,actor):
    try:original=signing.loads(data['quote_token'],salt='snowland.order-amendment',max_age=15*60)
    except signing.BadSignature:raise NotificationConflict('價格預覽已過期或無效，請重新預覽後確認')
    draft={'changes':data['changes']}
    quote=quote_order_amendment(group,draft,actor)
    quote.pop('quote_token')
    if (original.get('actor')!=actor.pk or original.get('group')!=group.pk
            or original.get('state')!=amendment_state(group) or original.get('draft')!=amendment_digest(draft)
            or original.get('quote')!=amendment_digest(quote)):
        raise NotificationConflict('訂單、學員、付款或價格已變更，請重新預覽後確認')
    return quote


def _participants(reservation,item):
    from booking.api_views import ABILITY_LEVEL_KEYS, normalize_student_level_counts
    active=list(MemberDetail.objects.select_for_update().filter(reservation=reservation).order_by('pk'))
    provided=item['retained_member_ids']
    if provided is None:
        if item['number_of_people']<len(active):
            raise serializers.ValidationError({'retained_member_ids':'減少人數時請明確選擇保留哪些學員，不會自動刪除任何人'})
        keep={member.pk for member in active}
    else:
        keep=set(provided)
        if len(keep)!=len(provided) or not keep.issubset({member.pk for member in active}) or len(keep)>item['number_of_people']:
            raise serializers.ValidationError({'retained_member_ids':'保留學員必須屬於這組目前學員，且不能重複或超過新的人數'})
        if item['number_of_people']<len(active) and len(keep)!=item['number_of_people']:
            raise serializers.ValidationError({'retained_member_ids':'請選足修改後要保留的學員人數'})
    if item['number_of_people']!=reservation.number_of_people and item['ability_level_counts'] is None:
        raise serializers.ValidationError({'ability_level_counts':'變更人數時請核對新組別的程度人數，不能猜測新學員程度'})
    levels=None
    if item['ability_level_counts'] is not None:
        if not item['ability_level_counts']:
            raise serializers.ValidationError({'ability_level_counts':'請明確填寫學員程度人數，不可留空'})
        try:levels=normalize_student_level_counts({'abilityLevelCounts':item['ability_level_counts']},item['number_of_people'])
        except ValueError as error:raise serializers.ValidationError({'ability_level_counts':str(error)})
    effective_levels=levels or reservation.ability_level_counts or {reservation.max_ability_level or 'no_exp':item['number_of_people']}
    for course in item['courses']:
        minimum=CourseTemplate.objects.get(pk=course['template_id']).minimum_student_level
        if minimum and any(ABILITY_LEVEL_KEYS.index(level)<ABILITY_LEVEL_KEYS.index(minimum) for level in effective_levels):
            raise serializers.ValidationError({'ability_level_counts':'學員程度不符合新課程模板限制'})
    return active,keep,levels


def _assignment(reservation,item,busy,levels):
    from booking.api_views import ABILITY_LEVEL_KEYS
    from booking.scheduler import can_assign_all_bookings, get_feasible_coaches
    removes_specification=reservation.is_preferred_coach and not item['is_preferred_coach']
    coach_id=item['preferred_coach_id'] if item['is_preferred_coach'] else None if removes_specification else reservation.preferred_coach_id
    if not coach_id:return None,'created',False
    coach=Coach.objects.get(pk=coach_id)
    if coach.client_id!=reservation.group.client_id or coach.availability_status=='unavailable' or not coach.campuses.filter(pk=reservation.group.campus_id).exists():
        raise NotificationConflict('原教練目前不能接此校區，請先選擇可接課的教練或重新排課')
    required_level=max(levels,key=ABILITY_LEVEL_KEYS.index) if levels else reservation.max_ability_level or 'no_exp'
    for template_id in {course['template_id'] for course in item['courses']}:
        feasible=get_feasible_coaches(item['language'],reservation.resort,reservation.course_type_id,
            required_level,course_template=CourseTemplate.objects.get(pk=template_id))
        if coach_id not in {candidate.pk for candidate in feasible}:
            raise NotificationConflict('原教練不符合新語言、程度或模板條件，請重新選擇教練')
    course_slots=[SimpleNamespace(reservation=reservation,date=course['date'],start_time=course['start_time'],end_time=course['end_time']) for course in item['courses']]
    for course in course_slots:
        if CoachLeaveRequest.objects.filter(coach_id=coach_id,status='approved',start_date__lte=course.date,end_date__gte=course.date).exists():
            raise NotificationConflict('教練在新日期已請假，原訂單未變更')
        if not can_assign_all_bookings([course],coach_id,busy):raise NotificationConflict('新時段與教練其他課程或同組課程衝突，原訂單未變更')
        busy[coach_id].append((course.date,course.start_time,course.end_time))
    status=reservation.status
    if removes_specification or reservation.preferred_coach_id!=coach_id or item['is_preferred_coach']:
        status='pending_coach_confirmation' if coach.availability_status=='passive' else 'manually_assigned'
    return coach,status,True


@transaction.atomic
def confirm_order_amendment(request,group_id,data,scope):
    Client.objects.select_for_update().get(pk=request.tenant.pk)
    group=get_object_or_404(ReservationGroup.objects.select_for_update().select_related('client','user','campus'),
        pk=group_id,client=request.tenant,pk__in=scope.values('pk'))
    fingerprint=amendment_digest({'actor':request.user.pk,'changes':data['changes'],'reason':data['reason'],'reschedule':data['reschedule']})
    existing=OrderAmendment.objects.filter(request_key=data['request_key']).first()
    if existing:
        if existing.group_id!=group.pk or existing.created_by_id!=request.user.pk or existing.request_fingerprint!=fingerprint:
            raise NotificationConflict('此修改識別碼已使用，請重新開啟修改視窗')
        return existing,True
    reservations={row.pk:row for row in Reservation.objects.select_for_update().filter(group=group).select_related('group','resort','course_type','course_template').order_by('pk')}
    list(Booking.objects.select_for_update().filter(reservation__group=group).order_by('pk'))
    list(MemberDetail.objects.select_for_update().filter(reservation__group=group).order_by('pk'))
    quote=_verify_quote(group,data,request.user)
    previous=group.payments.order_by('-created_at','-pk').first()
    if previous and previous.status in {'pending','expired','refunded'}:
        raise NotificationConflict('請先核對待確認、逾期或已退款的付款狀態，再修改訂單')
    pending=list(group.amendments.select_for_update().filter(status__in=['topup_due','topup_reported','refund_account_due','refund_due']))
    if any(row.status=='topup_reported' for row in pending):raise NotificationConflict('已有回報補款待核對，請先確認實際收款再修改')
    balance=quote['difference_amount']+sum(row.balance_amount for row in pending) if previous and previous.status=='paid' else 0
    status=('topup_due' if balance>0 else 'refund_account_due' if balance<0 else 'no_difference') if previous and previous.status=='paid' else 'included_in_order'
    from booking.currency import amendment_settlement
    try:settlement=amendment_settlement(group,quote['previous_total'],quote['new_total'],pending=pending)
    except ValueError as error:raise serializers.ValidationError({'settlement':str(error)})
    if settlement:
        if previous and previous.status=='paid':
            native_balance=settlement['balance_amount']
            status='topup_due' if native_balance>0 else 'refund_account_due' if native_balance<0 else 'no_difference'
        else:settlement['balance_amount']=0
    bank=resolve_payment_account(group) if balance>0 and not settlement else None
    bank_snapshot={key:getattr(bank,key) for key in ['name','bank_name','bank_branch','account_number','account_holder','overseas_details']} if bank else {}
    if settlement and settlement['balance_amount']>0:
        original=group.currency_snapshot.get('bank_info',{})
        bank_snapshot={'currency':'JPY','bank_name':original.get('bank_name',''),'bank_branch':original.get('bank_branch',''),
            'account_number':original.get('bank_account_number',''),'account_holder':original.get('bank_account_holder',''),'overseas_details':original.get('overseas_details','')}
    if status=='topup_due' and not all(bank_snapshot.get(key) for key in ['bank_name','account_number','account_holder']):
        raise serializers.ValidationError({'bank_snapshot':'補款前請先在後台設定此校區可用的銀行、帳號及戶名'})
    changed_ids={item['reservation_id'] for item in quote['items']}
    coach_ids={row.preferred_coach_id for row in reservations.values() if row.pk in changed_ids and row.preferred_coach_id}
    coach_ids.update(item['preferred_coach_id'] for item in quote['items'] if item['preferred_coach_id'])
    list(Coach.objects.select_for_update().filter(pk__in=coach_ids).order_by('pk'))
    busy=defaultdict(list)
    for booking in Booking.objects.filter(is_scheduled=True,reservation__preferred_coach_id__in=coach_ids).exclude(
            reservation__status__in=['deleted','cancelled']).exclude(reservation_id__in=changed_ids).select_related('reservation'):
        busy[booking.reservation.preferred_coach_id].append((booking.date,booking.start_time,booking.end_time))
    before=order_snapshot(group);plans=[];document_archives=[]
    for item in quote['items']:
        reservation=reservations[item['reservation_id']]
        bookings=list(reservation.bookings.order_by('pk'))
        old={booking.pk:booking for booking in bookings}
        changes_course=any(course['date']!=old[course['booking_id']].date or course['template_id']!=(old[course['booking_id']].course_template_id or reservation.course_template_id) for course in item['courses'])
        active,keep,levels=_participants(reservation,item)
        if changes_course:
            document_archives.extend(capture_course_documents([member for member in active if member.pk in keep],
                [{'id':row.pk,'date':row.date,'start_time':row.start_time,'end_time':row.end_time,
                  'template_id':row.course_template_id or reservation.course_template_id} for row in bookings],item['courses']))
        assignment=_assignment(reservation,item,busy,levels)
        plans.append((reservation,item,old,active,keep,levels,assignment))
    if not group.revisions.exists():record_order_revision(group,user=request.user,change_type='create',reason='首次修改前原單留底')
    participants={};to_schedule=[]
    for reservation,item,old,active,keep,levels,(coach,next_status,scheduled) in plans:
        archived=[member.pk for member in active if member.pk not in keep]
        MemberDetail.objects.filter(pk__in=archived).update(is_active=False,archived_at=timezone.now())
        created=[MemberDetail.objects.create(reservation=reservation,user=None,filled_by='user',age_range='').pk
            for _ in range(item['number_of_people']-len(keep))]
        participants[str(reservation.pk)]={'retained_ids':sorted(keep),'archived_ids':archived,'created_ids':created}
        reservation.number_of_people=item['number_of_people'];reservation.language=item['language'];reservation.equipment=item['equipment']
        reservation.need_equipment=item['equipment'] in {'assistDuringCourse','purchaseAssistanceTime'}
        reservation.is_preferred_coach=item['is_preferred_coach'];reservation.preferred_coach=coach;reservation.status=next_status
        if levels is not None:
            from booking.api_views import ABILITY_LEVEL_KEYS
            reservation.ability_level_counts=levels;reservation.max_ability_level=max(levels,key=ABILITY_LEVEL_KEYS.index)
        from booking.api_views import select_cart_group_course_template, resolve_equipment_assistance_time_slot
        reservation.course_template=select_cart_group_course_template([{'courseTemplateId':course['template_id']} for course in item['courses']],reservation.course_type,reservation.resort)
        original=next(change for change in data['changes'] if change['reservation_id']==reservation.pk)
        try:
            slot,label=resolve_equipment_assistance_time_slot(reservation.resort,item['equipment'],original.get('equipment_assistance_time_slot_id',reservation.equipment_assistance_time_slot_id),
                duration_hours=CourseTemplate.objects.get(pk=item['courses'][0]['template_id']).duration_hours,session_start_time=item['courses'][0]['start_time'],course_template_id=item['courses'][0]['template_id'])
        except ValueError:
            raise NotificationConflict('裝備協助時段已變更，請重新預覽；原訂單未變更')
        reservation.equipment_assistance_time_slot=slot;reservation.equipment_assistance_time_label=label
        reservation.course_fee=item['course_fee'];reservation.coach_fee=item['coach_fee'];reservation.language_fee=item['language_fee']
        reservation.equipment_rental_fee=item['equipment_fee'];reservation.discount_amount=item['discount_amount'];reservation.save()
        for course in item['courses']:
            booking=old[course['booking_id']]
            booking.date=course['date'];booking.start_time=course['start_time'];booking.end_time=course['end_time']
            booking.course_template_id=course['template_id'];booking.course_name=course['template_name'];booking.is_scheduled=scheduled
            booking.save(update_fields=['date','start_time','end_time','course_template','course_name','is_scheduled'])
        if data['reschedule'] and reservation.status=='created':to_schedule.append(reservation)
    if to_schedule:
        from booking.scheduler import assign_coachs
        ok,_=assign_coachs(reservations_to_assign=to_schedule)
        if not ok:raise NotificationConflict('新條件無法排入教練，已恢復原訂單；請調整後重新預覽')
    group=ReservationGroup.objects.get(pk=group.pk)
    revision=record_order_revision(group,user=request.user,change_type='modify',reason=data['reason'],previous_total=quote['previous_total'])
    group.amendments.filter(pk__in=[row.pk for row in pending]).update(status='superseded',updated_at=timezone.now())
    try:
        with transaction.atomic():
            amendment=OrderAmendment.objects.create(group=group,revision=revision,request_key=data['request_key'],request_fingerprint=fingerprint,
                reason=data['reason'],previous_total=quote['previous_total'],new_total=quote['new_total'],difference_amount=quote['difference_amount'],
                balance_amount=balance,status=status,before_snapshot=before,participant_changes=participants,created_by=request.user,
                bank_snapshot=bank_snapshot,currency_snapshot=settlement)
    except IntegrityError:raise NotificationConflict('修改識別碼已使用，原訂單未重複修改，請重新載入確認')
    save_course_documents(document_archives,revision,request.user)
    from booking.amendment_notifications import prepare_amendment_notice
    prepare_amendment_notice(amendment,request.user)
    return amendment,False
