"""Fields a staff booking link may share with the customer booking flow."""

CART_FIELDS = {
    'id', 'coach', 'coachName', 'peopleCount', 'abilityLevel', 'abilityLevelName',
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
