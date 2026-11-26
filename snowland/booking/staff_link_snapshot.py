"""Fields a staff booking link may share with the customer booking flow."""

CART_FIELDS = {
    'id', 'serviceType', 'coach', 'coachName', 'peopleCount', 'abilityLevel', 'abilityLevelName',
    'abilityLevelCounts', 'equipment', 'equipmentOption',
    'equipmentAssistanceTimeSlotId', 'equipmentAssistanceTimeLabel',
    'language', 'resort', 'resortName', 'campusId', 'campusName',
    'courseCategory', 'courseFee', 'coachFee', 'languageFee',
    'equipmentRentalFee', 'totalPrice',
}
COURSE_FIELDS = {
    'segmentId', 'date', 'courseTypeId', 'courseTypeName',
    'courseTemplateId', 'courseTemplateName', 'sharedClassEnabled',
    'durationHours', 'timeSlotId', 'timeSlotStart', 'timeSlotEnd', 'price',
}


def public_staff_cart_snapshot(snapshot):
    result = []
    for item in snapshot if isinstance(snapshot, list) else []:
        if not isinstance(item, dict):
            continue
        courses = item.get('courses')
        result.append({
            **{key: value for key, value in item.items() if key in CART_FIELDS},
            'courses': [
                {key: value for key, value in course.items() if key in COURSE_FIELDS}
                for course in courses if isinstance(course, dict)
            ] if isinstance(courses, list) else [],
        })
    return result


def staff_cart_price_preview(link, snapshot):
    from .api_views import calculate_cart_discount_summary

    # An unnamed recipient may be a returning member. Count only automatic
    # discounts available without a member, code, or new-customer status.
    summary = calculate_cart_discount_summary(snapshot, link.client, assume_returning_customer=True)
    priced_snapshot = [
        {
            **item,
            'serviceType': pricing['service_type'],
            'courses': [
                {**course, 'price': price}
                for course, price in zip(item['courses'], pricing['course_fees'])
            ],
            'courseFee': pricing['course_fee'],
            'coachFee': pricing['coach_fee'],
            'languageFee': pricing['language_fee'],
            'equipmentRentalFee': pricing['equipment_fee'],
            'totalPrice': pricing['subtotal'],
        }
        for item, pricing in zip(snapshot, summary['item_pricing'])
    ]
    old_snapshot = public_staff_cart_snapshot(link.cart_snapshot)
    old_prices = [item.get('totalPrice') for item in old_snapshot]
    previous_subtotal = sum(old_prices) if old_prices and all(type(price) is int for price in old_prices) else None
    subtotal = summary['subtotal']
    return priced_snapshot, {
        'previous_subtotal': previous_subtotal,
        'subtotal': subtotal,
        'subtotal_difference': subtotal - previous_subtotal if previous_subtotal is not None else None,
        'discount_total': summary['discount_total'],
        'total': summary['total'],
        'previous_total': link.quoted_total,
        'total_difference': summary['total'] - link.quoted_total if link.quoted_total is not None else None,
    }


def staff_cart_is_current(link):
    """Recheck current assignments; do not offer a withdrawn preselected course."""
    from Coursekit.models import CourseTemplate
    from Resorts.models import Resorts
    snapshot=link.cart_snapshot
    if link.campus.client_id!=link.client_id:return False
    # Older generic links carry only a campus, rather than a preselected cart.
    if snapshot==[]:
        return True
    if not isinstance(snapshot,list):
        return False
    required=set();resorts=set()
    for item in snapshot:
        if not isinstance(item,dict) or not isinstance(item.get('resort'),str):return False
        if item.get('campusId') not in (None,link.campus_id):return False
        courses=item.get('courses')
        if not isinstance(courses,list) or not courses:return False
        resorts.add(item['resort'])
        for course in courses:
            if not isinstance(course,dict) or type(course.get('courseTemplateId')) is not int:return False
            required.add((course['courseTemplateId'],item['resort']))
    assigned=set(Resorts.objects.filter(client_id=link.client_id,campuses=link.campus_id,name__in=resorts).values_list('name',flat=True))
    if assigned!=resorts:return False
    available=set(CourseTemplate.objects.filter(
        id__in={template for template,_ in required},is_active=True,
        course_type__category__client_id=link.client_id,resorts__client_id=link.client_id,
        resorts__name__in=resorts,
    ).values_list('id','resorts__name'))
    # Legacy templates without explicit resort bindings use their active price association.
    available.update(CourseTemplate.objects.filter(
        id__in={template for template,_ in required},is_active=True,resorts__isnull=True,
        course_type__category__client_id=link.client_id,pricing_options__is_active=True,
        pricing_options__resort__client_id=link.client_id,pricing_options__resort__name__in=resorts,
    ).values_list('id','pricing_options__resort__name'))
    return required.issubset(available)
