"""Read-only order-change quotes. Applying/settling an amendment is a separate workflow."""
import hashlib
import json
import re
from datetime import date, datetime

from django.core import signing
from rest_framework import serializers

from Coach.models import Coach
from Coursekit.models import CoursePricing, CourseTemplate, SeasonSetting
from Resorts.models import EquipmentPricingTier, ResortFee
from booking.models import EQUIPMENT_CHOICES, MemberDetail
from booking.operations import order_snapshot
from .manual_notifications import NotificationConflict


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data,dict) or set(data)-set(self.fields):
            raise serializers.ValidationError({'non_field_errors':['修改資料包含不支援的欄位或格式']})
        return super().to_internal_value(data)


class WholeNumber(serializers.IntegerField):
    def to_internal_value(self,value):
        if type(value) is not int and not (isinstance(value,str) and re.fullmatch(r'\d+',value.strip())):
            self.fail('invalid')
        return super().to_internal_value(value)


class AmendmentCourseInput(StrictInput):
    booking_id=WholeNumber(min_value=1)
    template_id=WholeNumber(min_value=1)
    date=serializers.DateField()
    start_time=serializers.TimeField()
    end_time=serializers.TimeField()


class AmendmentItemInput(StrictInput):
    reservation_id=WholeNumber(min_value=1)
    number_of_people=WholeNumber(min_value=1,required=False)
    language=serializers.ChoiceField(choices=['zh','en','yue'],required=False)
    equipment=serializers.ChoiceField(choices=[key for key,_ in EQUIPMENT_CHOICES],allow_null=True,required=False)
    equipment_assistance_time_slot_id=WholeNumber(min_value=1,allow_null=True,required=False)
    is_preferred_coach=serializers.BooleanField(required=False)
    preferred_coach_id=WholeNumber(min_value=1,allow_null=True,required=False)
    discount_amount=WholeNumber(min_value=0,required=False)
    retained_member_ids=serializers.ListField(child=WholeNumber(min_value=1),required=False,allow_empty=True)
    ability_level_counts=serializers.DictField(child=WholeNumber(min_value=0),required=False)
    courses=AmendmentCourseInput(many=True,allow_empty=False,max_length=100)


class AmendmentQuoteInput(StrictInput):
    changes=AmendmentItemInput(many=True,allow_empty=False,max_length=50)


def _seconds(start,end):
    return (datetime.combine(date.min,end)-datetime.combine(date.min,start)).total_seconds()


def _fail(message):
    raise serializers.ValidationError({'changes':message})


def _configured_addons(resort,coach,template,people,equipment):
    from booking.api_views import _resolve_coach_price_level, _resolve_template_coach_price_level
    level=_resolve_coach_price_level(coach,template.course_type) if coach else _resolve_template_coach_price_level(template,template.course_type)
    if level:
        fee={'director':'coach_director','Lv2':'coach_lv2'}.get(level,'coach_general')
        if not ResortFee.objects.filter(resort=resort,fee_type=fee,is_active=True).exists():
            _fail('請先在雪場費用設定指定教練費，不能以未設定的預設金額修改訂單')
    if equipment=='purchaseAssistanceTime':
        tier=EquipmentPricingTier.objects.filter(resort=resort,is_active=True,min_people__lte=people,max_people__gte=people).exists()
        legacy='equipment_1to3' if people<=3 else 'equipment_4to6' if people<=6 else ''
        if not tier and not ResortFee.objects.filter(resort=resort,fee_type=legacy,is_active=True).exists():
            _fail('請先設定這個人數的裝備協助費用，不能套用寫死的預設金額')


def _quote_item(group,reservation,change):
    from booking.api_views import compute_addon_fees_authoritative, resolve_equipment_assistance_time_slot, select_cart_group_course_template
    from booking.scheduler import coach_matches_course_template
    if reservation.status in {'completed','cancelled','deleted'} or reservation.shared_course_class_id:
        raise NotificationConflict('完課／取消／刪除課程或跨訂單團體班不能在單一訂單直接改價')
    if not reservation.resort_id or reservation.resort.client_id!=group.client_id:
        _fail('這筆課程缺少可使用的雪場設定')
    people=change.get('number_of_people',reservation.number_of_people)
    language=change.get('language',reservation.language)
    equipment=change.get('equipment',reservation.equipment)
    specified=change.get('is_preferred_coach',reservation.is_preferred_coach)
    coach_id=change.get('preferred_coach_id',reservation.preferred_coach_id if specified else None)
    if bool(coach_id)!=specified:
        _fail('指定教練時須選擇教練；不指定時請清除指定教練編號')
    coach=None
    if specified:
        candidates=Coach.objects.filter(pk=coach_id,client=group.client).exclude(availability_status='unavailable')
        if not (reservation.is_preferred_coach and reservation.preferred_coach_id==coach_id):
            candidates=candidates.filter(customer_selectable=True)
        if group.campus_id:candidates=candidates.filter(campuses__id=group.campus_id)
        coach=candidates.filter(coachresort__resort_id=reservation.resort_id).distinct().first()
        if not coach or language not in coach.languages:
            _fail('這位教練不符合校區、雪場、語言或開放指定條件')
    existing={booking.pk:booking for booking in reservation.bookings.all()}
    ids=[course['booking_id'] for course in change['courses']]
    if len(set(ids))!=len(ids) or set(ids)!=set(existing):
        _fail('請完整列出這組原有課程，不可混入其他訂單、重複或漏掉課程')
    same_price_basis=(people==reservation.number_of_people and language==reservation.language and equipment==reservation.equipment
        and specified==reservation.is_preferred_coach and (not specified or coach_id==reservation.preferred_coach_id))
    courses=[];templates=[]
    for item in change['courses']:
        booking=existing[item['booking_id']]
        template=CourseTemplate.objects.select_related('course_type__category').prefetch_related('resorts','allowed_coaches','sessions').filter(
            pk=item['template_id'],course_type__category__client=group.client,course_type_id=reservation.course_type_id).first()
        if not template or (template.resorts.exists() and not template.resorts.filter(pk=reservation.resort_id).exists()):
            _fail('課程模板不屬於此公司、課程類型或雪場')
        if item['end_time']<=item['start_time']:_fail('課程結束時間必須晚於開始時間')
        duration=_seconds(item['start_time'],item['end_time'])
        old_duration=_seconds(booking.start_time,booking.end_time)
        unchanged_template=template.pk==(booking.course_template_id or reservation.course_template_id)
        allowed={template.duration_hours*3600,*(_seconds(session.start_time,session.end_time) for session in template.sessions.all() if session.is_active)}
        if duration not in allowed and not (unchanged_template and duration==old_duration):
            _fail('追加時數須選擇已設定時長與價格的課程模板，不會依時數猜測或免費加時')
        if people>template.max_capacity or (people<template.minimum_group_size and not template.shared_class_enabled):
            _fail('人數不符合課程模板的最低人數或最大容量')
        if template.shared_class_enabled:_fail('跨訂單團體班需使用整班調整流程')
        if template.course_start_date and item['date']<template.course_start_date or template.course_end_date and item['date']>template.course_end_date:
            _fail('修改日期不在課程模板開放的上課期間')
        if coach and (not coach_matches_course_template(coach,template) or template.allowed_coaches.exists() and not template.allowed_coaches.filter(pk=coach.pk).exists()):
            _fail('指定教練不符合這個課程模板的等級或名單')
        same_price_basis=same_price_basis and unchanged_template and item['date']==booking.date and duration==old_duration
        templates.append(template);courses.append({**item,'template_name':template.name})
    old_discount=int(reservation.discount_amount or 0)
    discount=change.get('discount_amount',old_discount)
    try:
        resolve_equipment_assistance_time_slot(reservation.resort,equipment,change.get('equipment_assistance_time_slot_id',reservation.equipment_assistance_time_slot_id),
            duration_hours=templates[0].duration_hours,session_start_time=courses[0]['start_time'],course_template_id=templates[0].pk)
    except ValueError:_fail('請選擇適用於新課程、雪場與時段的裝備協助時間')
    if same_price_basis:
        course_fee,coach_fee,language_fee,equipment_fee=reservation.course_fee,reservation.coach_fee,reservation.language_fee,reservation.equipment_rental_fee
    else:
        if any(not template.is_active for template in templates):_fail('課程模板已停用，請先確認可使用的課程與定價')
        course_fee=0
        for course,template in zip(courses,templates):
            pricing=CoursePricing.objects.filter(resort=reservation.resort,templates=template,is_active=True).first()
            if not pricing:_fail('找不到這個雪場與課程的有效定價，請先在課程定價設定')
            try:course_fee+=int(pricing.calculate_price(people,SeasonSetting.get_season_type_for_date(course['date'])=='peak',billing_mode=template.billing_mode))
            except ValueError as error:_fail(str(error))
        representative=select_cart_group_course_template([{'courseTemplateId':template.pk} for template in templates],reservation.course_type,reservation.resort)
        _configured_addons(reservation.resort,coach,representative,people,equipment)
        coach_fee,language_fee,equipment_fee=compute_addon_fees_authoritative(resort=reservation.resort,coach=coach,course_type=reservation.course_type,
            language=language,equipment_value=equipment,people_count=people,bookings_count=len(courses),course_template=representative)
    subtotal=course_fee+coach_fee+language_fee+equipment_fee
    if discount>subtotal:_fail('原折抵金額超過修改後總價，請先核對並調整折抵金額')
    return {'reservation_id':reservation.pk,'number_of_people':people,'language':language,'equipment':equipment,
        'is_preferred_coach':specified,'preferred_coach_id':coach_id,'courses':courses,'course_fee':course_fee,'coach_fee':coach_fee,
        'language_fee':language_fee,'equipment_fee':equipment_fee,'discount_amount':discount,'previous_amount':reservation.payment_amount,
        'new_amount':subtotal-discount,'price_basis_changed':not same_price_basis,
        'participant_review_required':people!=reservation.number_of_people,
        'discount_changed':discount!=old_discount,'ability_level_counts':change.get('ability_level_counts'),
        'retained_member_ids':change.get('retained_member_ids')}


def amendment_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def amendment_editor_options(group):
    from django.db.models import Q
    from Resorts.models import EquipmentAssistanceTimeSlot
    result=[]
    for reservation in group.reservations.select_related('resort','course_type').prefetch_related('bookings','members'):
        bookings=list(reservation.bookings.all())
        current_templates={booking.course_template_id or reservation.course_template_id for booking in bookings}
        templates=CourseTemplate.objects.filter(course_type__category__client=group.client,course_type_id=reservation.course_type_id).filter(
            Q(is_active=True)|Q(pk__in=current_templates)).filter(Q(resorts=reservation.resort)|Q(resorts__isnull=True)).distinct().prefetch_related('sessions')
        coaches=Coach.objects.filter(client=group.client,coachresort__resort=reservation.resort).exclude(availability_status='unavailable')
        if group.campus_id:coaches=coaches.filter(campuses=group.campus)
        coaches=coaches.filter(Q(customer_selectable=True)|Q(pk=reservation.preferred_coach_id)).distinct()
        blocked='此課程已結束或取消，不能直接修改' if reservation.status in {'completed','cancelled','deleted'} else '跨訂單團體班請使用整班調整' if reservation.shared_course_class_id else ''
        result.append({'reservation_id':reservation.pk,'resort':reservation.resort.display_name if reservation.resort else '',
            'course_type':reservation.course_type.name if reservation.course_type else '', 'blocked_reason':blocked,
            'number_of_people':reservation.number_of_people,'language':reservation.language,'equipment':reservation.equipment,
            'equipment_assistance_time_slot_id':reservation.equipment_assistance_time_slot_id,
            'is_preferred_coach':reservation.is_preferred_coach,'preferred_coach_id':reservation.preferred_coach_id if reservation.is_preferred_coach else None,
            'discount_amount':reservation.discount_amount,'ability_level_counts':reservation.ability_level_counts or {reservation.max_ability_level or 'no_exp':reservation.number_of_people},
            'members':[{'id':member.pk,'name':member.display_name} for member in reservation.members.all()],
            'courses':[{'booking_id':booking.pk,'template_id':booking.course_template_id or reservation.course_template_id,
                'date':str(booking.date),'start_time':str(booking.start_time)[:5],'end_time':str(booking.end_time)[:5]} for booking in bookings],
            'templates':[{'id':template.pk,'name':template.name,'is_active':template.is_active,'duration_hours':template.duration_hours,
                'minimum_group_size':template.minimum_group_size,'max_capacity':template.max_capacity,
                'sessions':[{'start_time':str(session.start_time)[:5],'end_time':str(session.end_time)[:5]} for session in template.sessions.all() if session.is_active]} for template in templates],
            'coaches':[{'id':coach.pk,'name':coach.name,'customer_selectable':coach.customer_selectable} for coach in coaches],
            'equipment_slots':[{'id':slot.pk,'name':slot.display_label()} for slot in EquipmentAssistanceTimeSlot.objects.filter(resort=reservation.resort,is_active=True,equipment_option='purchaseAssistanceTime')]})
    return {'items':result}


def amendment_state(group):
    return amendment_digest({'order':order_snapshot(group),
        'members':list(MemberDetail.objects.filter(reservation__group=group).order_by('pk').values()),
        'payments':list(group.payments.order_by('pk').values('pk','status','updated_at')),
        'amendments':list(group.amendments.order_by('pk').values('pk','status','balance_amount','updated_at'))})


def quote_order_amendment(group,data,actor):
    if group.cancellation_requests.filter(status__in=['requested','approved','refunded']).exists():
        raise NotificationConflict('訂單已有取消或退款流程，請先處理完成再修改')
    reservations={reservation.pk:reservation for reservation in group.reservations.all()}
    ids=[change['reservation_id'] for change in data['changes']]
    if len(set(ids))!=len(ids) or any(pk not in reservations for pk in ids):
        _fail('預約必須屬於這張訂單，且不可重複')
    items=[_quote_item(group,reservations[change['reservation_id']],change) for change in data['changes']]
    previous=sum(reservation.payment_amount for reservation in reservations.values() if reservation.status not in {'deleted','cancelled'})
    difference=sum(item['new_amount']-item['previous_amount'] for item in items)
    result={'previous_total':previous,'new_total':previous+difference,'difference_amount':difference,'items':items,
        'status':'preview_only','notice':'只預覽價格；尚未修改訂單、重排教練、寄信、收款或退款。原折抵金額保留，不會重新兌換優惠碼。'}
    result['quote_token']=signing.dumps({'actor':actor.pk,'group':group.pk,'state':amendment_state(group),
        'quote':amendment_digest(result),'draft':amendment_digest(data)},salt='snowland.order-amendment',compress=True)
    return result
