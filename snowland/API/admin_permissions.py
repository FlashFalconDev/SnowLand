ADMIN_PERMISSION_DEFINITIONS = [
    {
        'key': 'analytics',
        'label': '營運分析',
        'group': '營運管理',
        'description': '查看儀表板、營收與訂單統計',
    },
    {
        'key': 'orders',
        'label': '訂單管理',
        'group': '營運管理',
        'description': '查看與處理訂單、寄送訂單信件',
    },
    {
        'key': 'scheduling',
        'label': '排課管理',
        'group': '營運管理',
        'description': '查看排課月曆與課程安排',
    },
    {
        'key': 'customers',
        'label': '會員管理',
        'group': '營運管理',
        'description': '查看會員資料與預約紀錄',
    },
    {
        'key': 'chat_support',
        'label': 'AI 客服',
        'group': '營運管理',
        'description': '查看 LINE 對話、接手案件並人工回覆',
    },
    {
        'key': 'campuses',
        'label': '校區與營運規則',
        'group': '基本設定',
        'description': '管理校區、可用雪場、收款帳戶與營運規則',
    },
    {
        'key': 'insurance_records',
        'label': '保險資料',
        'group': '營運管理',
        'description': '查看課前保險與聲明書完成狀態',
    },
    {
        'key': 'evaluations',
        'label': '評量與課程紀錄',
        'group': '營運管理',
        'description': '填寫評量、學習進度與上傳課程媒體',
    },
    {
        'key': 'payroll',
        'label': '薪資結算',
        'group': '營運管理',
        'description': '管理教練時薪、指定費、介紹費與月結',
    },
    {
        'key': 'notifications',
        'label': '自動通知',
        'group': '營運管理',
        'description': '設定郵件、LINE 通知內容與發送時間',
    },
    {
        'key': 'resorts',
        'label': '雪場管理',
        'group': '基本設定',
        'description': '管理雪場、接送與租借設定',
    },
    {
        'key': 'course_types',
        'label': '課程架構',
        'group': '基本設定',
        'description': '管理課程大類、類型、模板與時段',
    },
    {
        'key': 'pricing',
        'label': '課程定價',
        'group': '基本設定',
        'description': '管理旺淡季與課程價格',
    },
    {
        'key': 'discounts',
        'label': '優惠折扣',
        'group': '基本設定',
        'description': '管理折扣碼、早鳥與促銷規則',
    },
    {
        'key': 'coaches',
        'label': '教練管理',
        'group': '基本設定',
        'description': '管理教練資料、證照與請假審核',
    },
    {
        'key': 'staff',
        'label': '員工權限',
        'group': '基本設定',
        'description': '設定管理員、教練與模組權限',
    },
    {
        'key': 'payment_settings',
        'label': '付款設定',
        'group': '基本設定',
        'description': '管理匯款帳戶與付款資訊',
    },
    {
        'key': 'cms',
        'label': '官網內容',
        'group': '官網內容',
        'description': '管理首頁、教練、雪場、FAQ 與文章內容',
    },
    {
        'key': 'reviews',
        'label': '評論與媒體',
        'group': '評論與媒體',
        'description': '管理 Google 評論、手動評論與媒體素材',
    },
]

ADMIN_PERMISSION_KEYS = [item['key'] for item in ADMIN_PERMISSION_DEFINITIONS]

ROLE_DEFAULT_PERMISSIONS = {
    'marketing': ['analytics', 'discounts'],
    'web_editor': ['cms', 'reviews'],
    'insurance': ['insurance_records'],
    'assistant': ['orders', 'scheduling', 'insurance_records', 'evaluations', 'coaches', 'cms', 'reviews'],
    'campus_principal': ['analytics', 'orders', 'scheduling', 'coaches', 'evaluations', 'payroll'],
    'campus_manager': ['orders', 'scheduling', 'coaches', 'evaluations'],
    'photographer': ['evaluations', 'reviews'],
}


def normalize_admin_permissions(value):
    if not isinstance(value, list):
        return []
    return [key for key in value if key in ADMIN_PERMISSION_KEYS]


def get_user_admin_permissions(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    if getattr(user, 'is_superuser', False):
        return list(ADMIN_PERMISSION_KEYS)

    try:
        profile = user.userprofile
    except Exception:
        return []

    if not getattr(profile, 'is_manager', False):
        return []

    stored = getattr(profile, 'admin_permissions', None)
    if getattr(profile, 'is_manager', False) and stored is None:
        if profile.role in ('', 'hq_admin'):
            return list(ADMIN_PERMISSION_KEYS)
        return ROLE_DEFAULT_PERMISSIONS.get(profile.role, [])
    return normalize_admin_permissions(stored)


def user_has_admin_permission(user, permission_key):
    if not permission_key:
        return bool(get_user_admin_permissions(user))
    return permission_key in get_user_admin_permissions(user)
