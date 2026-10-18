"""One CMS review catalogue feeds both homepage and coach detail placement."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from Coach.models import Coach
from .models import SiteContent
from .coach_profiles import coach_profile_record


def validate_review_metadata(metadata,tenant):
    if 'show_on_homepage' in metadata and type(metadata['show_on_homepage']) is not bool:
        raise ValueError('首頁展示必須是勾選或取消勾選')
    if 'coach_ids' not in metadata:
        return
    ids=metadata['coach_ids']
    if not isinstance(ids,list) or len(ids)>100 or any(type(value) is not int or not 0<value<=9223372036854775807 for value in ids):
        raise ValueError('請從教練清單選擇歸檔對象')
    if len(ids)!=len(set(ids)) or Coach.objects.filter(client=tenant,pk__in=ids).count()!=len(ids):
        raise ValueError('歸檔教練重複、不存在或不屬於此公司，請重新選擇')


def public_coach_reviews(coach):
    if not coach.website_enabled:
        return []
    now=timezone.now()
    rows=SiteContent.objects.filter(client_id=coach.client_id,content_type='review',status='active').filter(
        Q(start_at__isnull=True)|Q(start_at__lte=now)).filter(Q(end_at__isnull=True)|Q(end_at__gte=now)).order_by('-is_pinned','display_order','-created_at')
    result=[]
    for row in rows:
        metadata=row.metadata if isinstance(row.metadata,dict) else {}
        ids=metadata.get('coach_ids',[])
        if not isinstance(ids,list) or not any(type(value) is int and value==coach.pk for value in ids):
            continue
        photos=metadata.get('photos')
        photos=photos if isinstance(photos,list) else ([{'src':row.image_url,'alt':row.title}] if row.image_url else [])
        result.append({'name':row.title,'time':metadata.get('time') or row.subtitle,
            'date':metadata.get('date',''),'cid':metadata.get('cid',''),'pinned':row.is_pinned,
            'paragraphs':([row.summary] if row.summary else [])+[value for value in row.body.split('\n\n') if value],
            'photos':photos})
    return result


@transaction.atomic
def ensure_legacy_coach_reviews(coach):
    coach=Coach.objects.select_for_update().get(pk=coach.pk,client_id=coach.client_id)
    record=coach_profile_record(coach)
    if not record or not isinstance(record.metadata,dict) or record.metadata.get('reviews_catalog_version')==1:
        return 0
    profile=record.metadata.get('profile',{})
    reviews=profile.get('reviews',[]) if isinstance(profile,dict) else []
    created=0
    for index,review in enumerate(reviews if isinstance(reviews,list) else []):
        if not isinstance(review,dict):
            continue
        paragraphs=review.get('paragraphs',[])
        paragraphs=[value for value in paragraphs if isinstance(value,str)] if isinstance(paragraphs,list) else []
        lookup={'client_id':coach.client_id,'content_type':'review','location_key':'homepage.reviews','external_id':f'coach-{coach.pk}-legacy-review-{index+1}'}
        if SiteContent.objects.filter(**lookup).exists():
            continue
        photos=review.get('photos',[]) if isinstance(review.get('photos'),list) else []
        SiteContent.objects.create(**lookup,title=str(review.get('name',''))[:200],
            summary=paragraphs[0] if paragraphs else '',body='\n\n'.join(paragraphs[1:]),
            source='legacy-coach-review',status='active',display_order=index,is_pinned=bool(review.get('pinned')),
            metadata={'coach_ids':[coach.pk],'show_on_homepage':False,'photos':photos,
                      'time':review.get('time',''),'date':review.get('date',''),'cid':review.get('cid','')})
        created+=1
    record.metadata={**record.metadata,'reviews_catalog_version':1}
    record.save(update_fields=['metadata','updated_at'])
    return created
