import re
from urllib.parse import urlsplit, parse_qs
from .article_pages import safe_article_url


def normalize_youtube_id(value):
    if not isinstance(value,str) or len(value)>2000:return ''
    value=value.strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{11}',value):return value
    try:
        url=urlsplit(value)
        if url.scheme!='https':return ''
        if url.netloc=='youtu.be':candidate=url.path.lstrip('/')
        elif url.netloc in ('www.youtube.com','youtube.com','m.youtube.com'):
            if url.path=='/watch':
                videos=parse_qs(url.query).get('v',[])
                candidate=videos[0] if len(videos)==1 else ''
            elif re.fullmatch(r'/(embed|shorts)/[A-Za-z0-9_-]{11}',url.path):candidate=url.path.rsplit('/',1)[-1]
            else:return ''
        else:return ''
        return candidate if re.fullmatch(r'[A-Za-z0-9_-]{11}',candidate) else ''
    except ValueError:return ''


def validate_homepage_presentation(attrs, instance, tenant):
    def value(key, default=''):
        return attrs.get(key,getattr(instance,key,default))
    location=value('location_key')
    legacy_page=bool(instance and instance.content_type=='page' and value('content_type')=='page')
    if value('content_type')!='setting' and not legacy_page:
        raise ValueError('首頁展示區塊請使用區塊設定類型')
    from .models import SiteContent
    duplicates=SiteContent.objects.filter(client=tenant,location_key=location)
    if instance:duplicates=duplicates.exclude(pk=instance.pk)
    if duplicates.exists():raise ValueError('這個首頁區塊已有設定，請編輯既有資料')
    for field in ['image_url','link_url']:
        if not safe_article_url(value(field)):
            raise ValueError('圖片與按鈕連結請用完整http/https網址或站內路徑')
    metadata=value('metadata',{})
    for key in ['button_text','opening_text','resort_names','opening_suffix','language_prefix','languages','language_suffix']:
        if not isinstance(metadata.get(key,''),str) or len(metadata.get(key,''))>10000:
            raise ValueError('首頁文字欄位格式或長度不正確')
    extra=metadata.get('extra_paragraphs',[])
    if not isinstance(extra,list) or len(extra)>20 or any(not isinstance(text,str) or len(text)>20000 for text in extra):
        raise ValueError('展開段落請使用文字清單，最多20段')
    if metadata.get('image_asset','') not in ('','original-school-photo'):
        raise ValueError('請選用原學校照片或填寫圖片網址')
    if location=='homepage.hero':
        mode=metadata.get('media_type','none')
        if mode not in ('youtube','image','none'):raise ValueError('請選擇影片、圖片或純色背景')
        if mode=='youtube' and metadata.get('youtube_id',''):
            video_id=normalize_youtube_id(metadata['youtube_id'])
            if not video_id:raise ValueError('請貼上有效YouTube影片網址或11碼影片代號')
            metadata={**metadata,'youtube_id':video_id}
        if value('status')=='active':
            if mode=='youtube' and not metadata.get('youtube_id'):raise ValueError('影片背景請填寫YouTube影片代號')
            if mode=='image' and not value('image_url'):raise ValueError('圖片背景請填寫圖片網址')
    if value('status')=='active':
        if not value('title').strip():raise ValueError('公開前請填寫標題')
        if location!='homepage.coaches' and value('link_url') and not metadata.get('button_text','').strip():raise ValueError('有按鈕連結時，請填寫按鈕文字')
    return metadata
