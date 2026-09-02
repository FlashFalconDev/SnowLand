from django.core.management.base import BaseCommand, CommandError

from Client.models import Client, SiteContent


def find_client(code):
    if code:
        client = Client.objects.filter(internal_code=code, is_active=True).first()
        if client:
            return client, False

    active_clients = list(Client.objects.filter(is_active=True))
    if len(active_clients) == 1:
        return active_clients[0], True

    if code:
        raise CommandError(f'找不到啟用中的客戶代碼: {code}')
    raise CommandError('找不到唯一的啟用客戶，請用 --client 指定 internal_code')


def item(
    *,
    content_type,
    location_key,
    external_id,
    title='',
    subtitle='',
    summary='',
    body='',
    image_url='',
    link_url='',
    source='manual',
    tags=None,
    metadata=None,
    status='draft',
    display_order=0,
    is_pinned=False,
):
    return {
        'content_type': content_type,
        'location_key': location_key,
        'external_id': external_id,
        'title': title,
        'subtitle': subtitle,
        'summary': summary,
        'body': body,
        'image_url': image_url,
        'link_url': link_url,
        'source': source,
        'tags': tags or [],
        'metadata': metadata or {},
        'status': status,
        'display_order': display_order,
        'is_pinned': is_pinned,
    }


SITE_CONTENT_ITEMS = [
    item(
        content_type='review',
        location_key='homepage.reviews',
        external_id='seed-home-review-01',
        title='Chingyee Lee',
        subtitle='CL',
        summary='5歲初次接觸滑雪的小男生給cash教練帶，因為性格內向又黏人所以媽媽本身很擔心他會很抵觸。',
        body='但cash教練帶小朋友很耐心、又很會教，結果滑了一天超愛滑雪，從山上滑到山下，完全不找爸媽，又指定下一定要讓cash叔叔帶滑！只有唯一的缺點是現在鋼琴課也不想上了，說只想學滑雪！期待明年再見面！',
        source='google',
        tags=['學生評價', 'Google評論'],
        metadata={'initials': 'CL'},
        status='active',
        display_order=1,
    ),
    item(
        content_type='review',
        location_key='homepage.reviews',
        external_id='seed-home-review-02',
        title='Eunice Liu',
        subtitle='EL',
        summary='超感謝教練耐心指導即時糾正我滑雪時的盲點！不僅幽默還很會聊天，期待明年再來找教練滑雪。',
        source='google',
        tags=['學生評價', 'Google評論'],
        metadata={'initials': 'EL'},
        status='active',
        display_order=2,
    ),
    item(
        content_type='review',
        location_key='homepage.reviews',
        external_id='seed-home-review-03',
        title='Wat Hans',
        subtitle='WH',
        summary='初次滑雪找到七針教練，參加了一天雙板課程，講解十分容易明白。',
        body='感謝教練，令我們日本旅遊留下歡笑回憶。',
        source='google',
        tags=['學生評價', 'Google評論'],
        metadata={'initials': 'WH'},
        status='active',
        display_order=3,
    ),
    item(
        content_type='review',
        location_key='homepage.reviews',
        external_id='seed-home-review-04',
        title='BESS LIN',
        subtitle='BL',
        summary='對於一年只滑一次，每次只能滑個四五天的我們來說，只恨自己沒有早點找中文教練教學。',
        body='非常謝謝Cash及七針教練細心的教學，不躁進讓我們挑戰更進階，而是一步一步紮實反覆確認我們的基本功並點出我們的問題！真的非常感謝，非常棒。',
        source='google',
        tags=['學生評價', 'Google評論'],
        metadata={'initials': 'BL'},
        status='active',
        display_order=4,
    ),
    item(
        content_type='review',
        location_key='homepage.reviews',
        external_id='seed-home-review-05',
        title='OS',
        subtitle='OS',
        summary='謝謝Lily教練的教學，原本一直卡在落葉飄，這次終於學會S Turn了，真的很神奇。',
        source='google',
        tags=['學生評價', 'Google評論'],
        metadata={'initials': 'OS'},
        status='active',
        display_order=5,
    ),
    item(
        content_type='offer',
        location_key='homepage.offers',
        external_id='seed-home-offer-earlybird',
        title='25-26雪季早鳥優惠',
        subtitle='7.01 - 9.30日止',
        summary='早鳥優惠內容可在後台更新。期限結束後會顯示為已結束。',
        image_url='/homepage/Special offers-early bird.jpg',
        link_url='/specialoffers/earlybird',
        tags=['早鳥優惠', '首頁限定優惠'],
        metadata={'badge': '已結束'},
        status='ended',
        display_order=1,
    ),
    item(
        content_type='offer',
        location_key='homepage.offers',
        external_id='seed-home-offer-referral',
        title='舊生帶新生優惠',
        subtitle='優惠內容整理中。',
        summary='舊生帶新生優惠可由後台更新標題、副標題、圖片與連結。',
        image_url='/homepage/Special offers-referal.jpg',
        link_url='/specialoffers/referral',
        tags=['舊生優惠', '首頁限定優惠'],
        metadata={'badge': '進行中'},
        status='active',
        display_order=2,
    ),
    item(
        content_type='offer',
        location_key='offers.earlybird',
        external_id='seed-offer-earlybird-page',
        title='早早鳥 / 早鳥優惠',
        subtitle='每年可自行調整優惠期間與內容',
        summary='此項目先放在草稿，不會覆蓋目前前台頁面；確認內容後可切為進行中。',
        tags=['早鳥優惠'],
        status='draft',
        display_order=1,
    ),
    item(
        content_type='offer',
        location_key='offers.referral',
        external_id='seed-offer-referral-page',
        title='舊生推薦優惠',
        subtitle='推薦活動內容可由後台維護',
        summary='可填寫推薦條件、折扣方式、使用期限與注意事項。',
        tags=['舊生優惠', '推薦優惠'],
        status='draft',
        display_order=2,
    ),
    item(
        content_type='offer',
        location_key='offers.promo',
        external_id='seed-offer-promo-page',
        title='限時活動',
        subtitle='可設定活動標籤、期間與狀態',
        summary='限時活動若切為進行中，前台可依標籤顯示。',
        tags=['限時活動'],
        status='draft',
        display_order=3,
    ),
    item(
        content_type='article',
        location_key='news.social',
        external_id='seed-instagram-01',
        title='雪地攝影體驗',
        summary='SnowLand滑雪學校攜手攝影團隊，帶來滑雪課程側拍與雪地寫真服務。',
        image_url='/instagram/instagram-01.jpg',
        link_url='https://www.instagram.com/p/DDqlF6iioOO/',
        source='instagram',
        tags=['IG動態', '雪地攝影'],
        status='active',
        display_order=1,
    ),
    item(
        content_type='article',
        location_key='news.social',
        external_id='seed-instagram-02',
        title='一個人的北海道雪國旅行',
        summary='北海道雪國寫真，記錄獨旅女孩與雪地風景的旅行回憶。',
        image_url='/instagram/instagram-02.jpg',
        link_url='https://www.instagram.com/p/DE6XHixPYpy/',
        source='instagram',
        tags=['IG動態', '旅拍'],
        status='active',
        display_order=2,
    ),
    item(
        content_type='article',
        location_key='news.social',
        external_id='seed-instagram-03',
        title='SnowLand 雪地攝影',
        summary='滑雪課程側拍、雪地家庭寫真、情侶寫真與旅遊攝影服務。',
        image_url='/instagram/instagram-03.jpg',
        link_url='https://www.instagram.com/p/DE1NRZlIe7r/',
        source='instagram',
        tags=['IG動態', '作品集'],
        status='active',
        display_order=3,
    ),
    item(
        content_type='article',
        location_key='news.articles',
        external_id='seed-news-article-01',
        title='北海道滑雪攻略',
        subtitle='滑雪月份、雪場推薦與行前準備',
        summary='此文章先作為後台草稿範例，確認內容後可切為進行中。',
        tags=['滑雪攻略'],
        metadata={'date': '2026.06.26'},
        status='draft',
        display_order=1,
    ),
    item(
        content_type='page',
        location_key='course.info',
        external_id='seed-course-info',
        title='滑雪課程說明資訊',
        subtitle='價目表、課程說明與注意事項',
        summary='每年微調整的課程說明可放在這裡維護。',
        tags=['滑雪課程'],
        status='draft',
        display_order=1,
    ),
    item(
        content_type='page',
        location_key='course.open-dates',
        external_id='seed-course-open-dates',
        title='雪場開放日期',
        subtitle='每年雪季開放日期可在此更新',
        summary='可填寫不同雪場的預計開放與結束日期。',
        tags=['雪場資訊'],
        status='draft',
        display_order=2,
    ),
    item(
        content_type='page',
        location_key='course.lift-ticket',
        external_id='seed-course-lift-ticket',
        title='雪票價格',
        subtitle='各雪場雪票價格資訊',
        summary='可由後台更新每年雪票價格與購買說明。',
        tags=['雪票'],
        status='draft',
        display_order=3,
    ),
    item(
        content_type='page',
        location_key='guides.preparation',
        external_id='seed-guide-preparation',
        title='行前須知',
        subtitle='出發前需要知道的事',
        summary='可新增或修改行前提醒、集合方式、注意事項。',
        tags=['滑雪攻略', '行前須知'],
        status='draft',
        display_order=1,
    ),
    item(
        content_type='page',
        location_key='guides.packing',
        external_id='seed-guide-packing',
        title='滑雪裝備',
        subtitle='裝備清單與租借說明',
        summary='可維護滑雪裝備、穿著建議與租借提醒。',
        tags=['滑雪攻略', '滑雪裝備'],
        status='draft',
        display_order=2,
    ),
    item(
        content_type='faq',
        location_key='guides.faq',
        external_id='seed-guide-faq',
        title='常見問題',
        subtitle='客人常見訂課與滑雪問題',
        summary='可新增 FAQ 問答內容。',
        tags=['滑雪攻略', 'FAQ'],
        status='draft',
        display_order=3,
    ),
    item(
        content_type='article',
        location_key='guides.articles',
        external_id='seed-guide-article',
        title='滑雪精選文章',
        subtitle='攻略文章列表',
        summary='可新增文章並依狀態控制是否顯示。',
        tags=['滑雪攻略', '文章'],
        status='draft',
        display_order=4,
    ),
    item(
        content_type='media',
        location_key='photography.gallery',
        external_id='seed-photography-gallery',
        title='攝影作品集',
        subtitle='上傳新作品',
        summary='雪地攝影作品可在此新增圖片、標題與連結。',
        tags=['攝影作品集'],
        status='draft',
        display_order=1,
    ),
    item(
        content_type='page',
        location_key='about.snowland',
        external_id='seed-about-snowland',
        title='關於 SnowLand',
        subtitle='品牌介紹頁面',
        summary='關於 SnowLand 的頁面內容可在此維護。',
        tags=['關於Snowland'],
        status='draft',
        display_order=1,
    ),
    item(
        content_type='page',
        location_key='about.join-us',
        external_id='seed-about-join-us',
        title='成為教練',
        subtitle='招募內容每年可微調',
        summary='教練招募條件、流程與聯絡方式可在此更新。',
        tags=['成為教練'],
        status='draft',
        display_order=2,
    ),
]


class Command(BaseCommand):
    help = '將目前前台預設內容寫入 SiteContent，讓官網內容後台一開始就有資料。'

    def add_arguments(self, parser):
        parser.add_argument('--client', default='snowland', help='Client.internal_code，預設 snowland')
        parser.add_argument('--force', action='store_true', help='覆蓋已存在的 seed 資料')

    def handle(self, *args, **options):
        client, used_fallback = find_client(options['client'])
        force = options['force']

        created = 0
        updated = 0
        skipped = 0

        for seed in SITE_CONTENT_ITEMS:
            lookup = {
                'client': client,
                'content_type': seed['content_type'],
                'location_key': seed['location_key'],
                'external_id': seed['external_id'],
            }
            defaults = {
                key: value
                for key, value in seed.items()
                if key not in {'content_type', 'location_key', 'external_id'}
            }

            existing = SiteContent.objects.filter(**lookup).first()
            if existing and not force:
                skipped += 1
                continue

            _, was_created = SiteContent.objects.update_or_create(**lookup, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1

        if used_fallback:
            self.stdout.write(self.style.WARNING(f'找不到指定 client，已改用唯一啟用客戶：{client.internal_code}'))

        self.stdout.write(self.style.SUCCESS(f'官網內容 seed 完成：新增 {created}、更新 {updated}、略過 {skipped}'))
        self.stdout.write(self.style.SUCCESS(f'目前客戶 {client.internal_code} 的官網內容總數：{client.site_contents.count()}'))
