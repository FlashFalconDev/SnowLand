"""Private evidence and invalidation shared by individual and whole-class changes."""
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from .models import MemberCourseDocumentRevision


def capture_course_documents(members, previous_courses, new_courses):
    entries=[]
    for member in members:
        signed=bool(member.waiver_signature or member.waiver_completed_at)
        insured=member.insurance_processing_status=='insured'
        if not (signed or insured):
            continue
        snapshot={key:getattr(member,key) for key in [
            'insurance_data','insurance_processing_status','insurance_premium_amount','insurance_premium_currency',
            'insurance_processing_updated_at','insurance_processing_updated_by_id','insurance_completed_at',
            'waiver_signature','waiver_document_version','waiver_document_snapshot','waiver_completed_at','media_consent',
            'user_id','guardian_id','waiver_resign_required']}
        snapshot.update(previous_courses=previous_courses,new_courses=new_courses)
        entries.append((member,json.loads(json.dumps(snapshot,cls=DjangoJSONEncoder)),signed,insured))
    return entries


def save_course_documents(entries, revision, actor):
    for member,snapshot,signed,insured in entries:
        MemberCourseDocumentRevision.objects.create(member=member,revision=revision,snapshot=snapshot)
        fields=[]
        if signed:
            member.waiver_resign_required=True;fields.append('waiver_resign_required')
        if insured:
            member.insurance_processing_status='checking'
            member.insurance_processing_updated_at=timezone.now()
            member.insurance_processing_updated_by=actor
            member.insurance_premium_amount=None;member.insurance_premium_currency=''
            fields.extend(['insurance_processing_status','insurance_processing_updated_at','insurance_processing_updated_by',
                'insurance_premium_amount','insurance_premium_currency'])
        member.save(update_fields=fields)
