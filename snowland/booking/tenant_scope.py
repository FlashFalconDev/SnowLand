"""Resolve names only within an explicitly known school/course owner."""
from Coursekit.models import CourseTemplate, CourseType
from Resorts.models import Resorts


def resort_for_course(name, *, client=None, template_id=None, course_type_id=None):
    client_id=getattr(client,'pk',None)
    if template_id:
        template=CourseTemplate.objects.select_related('course_type__category').filter(pk=template_id).first()
        if not template or (client is not None and template.course_type.category.client_id != client.pk):
            raise Resorts.DoesNotExist('Course does not belong to this school')
        client_id=template.course_type.category.client_id
    elif course_type_id:
        kind=CourseType.objects.select_related('category').filter(pk=course_type_id).first()
        if not kind or (client is not None and kind.category.client_id != client.pk):
            raise Resorts.DoesNotExist('Course type does not belong to this school')
        client_id=kind.category.client_id
    query=Resorts.objects.filter(name=name)
    if client is not None or template_id or course_type_id:
        query=query.filter(client_id=client_id)
    rows=list(query[:2])
    if len(rows)!=1:
        raise Resorts.DoesNotExist('Resort is missing or its school is ambiguous')
    return rows[0]


def selected_coach_for_school(coach_id, client_id):
    """A requested coach must belong to the same school; never fall back silently."""
    if coach_id in (None, '', 'any'):
        return None
    from Coach.models import Coach
    try:
        if client_id is None:
            raise Coach.DoesNotExist
        coach = Coach.objects.get(pk=coach_id, client_id=client_id)
    except (Coach.DoesNotExist, TypeError, ValueError):
        raise ValueError('找不到此學校可指定的教練，請重新選擇')
    if not coach.customer_selectable:
        raise ValueError('這位教練目前不開放指定，請改選其他教練或「不指定教練」')
    return coach
