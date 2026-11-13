ADMIN_PERMISSION_DEFINITIONS = [
    {'key': 'analytics', 'label': '營運分析與報表', 'group': '營運總覽', 'description': '查看營運總覽與匯出統計報表'},
    {'key': 'vehicle_review', 'label': '車輛排班與用車審核', 'group': '營運總覽', 'description': '核准借車並審核授權校區的用車紀錄'},
    {'key': 'vehicle_finance', 'label': '車輛費率與費用核准', 'group': '營運總覽', 'description': '設定車輛、費率與匯率，核准用車費用'},
    {'key': 'order_view', 'label': '訂單列表與明細', 'group': '訂單', 'description': '查看授權校區的訂單'},
    {'key': 'order_edit', 'label': '修改與排課', 'group': '訂單', 'description': '修改課程、人數與教練，或完成課程'},
    {'key': 'order_payments', 'label': '對帳與差額', 'group': '訂單', 'description': '核對收款及補退差額'},
    {'key': 'order_refunds', 'label': '取消與退款', 'group': '訂單', 'description': '處理取消申請及記錄退款'},
    {'key': 'booking_links', 'label': '代客訂課連結', 'group': '訂單', 'description': '建立與管理代客訂課連結'},
    {'key': 'order_export', 'label': '匯出訂單', 'group': '訂單', 'description': '匯出訂單資料，限可管理全校的總部管理員'},
    {'key': 'contact_inbox', 'label': '官網聯絡收件', 'group': '客服與通知', 'description': '查看官網留言與處理狀態'},
    {'key': 'chat_support', 'label': 'LINE／AI 客服', 'group': '客服與通知', 'description': '查看對話及人工回覆'},
    {'key': 'notifications', 'label': '通知範本與發送紀錄', 'group': '客服與通知', 'description': '管理通知範本及發送紀錄'},
    {'key': 'member_directory', 'label': '會員名單與預約紀錄', 'group': '會員與課前資料', 'description': '查看會員資料與訂課紀錄'},
    {'key': 'insurance_records', 'label': '保險與聲明書紀錄', 'group': '會員與課前資料', 'description': '查看及處理學員課前資料'},
    {'key': 'member_loyalty', 'label': '會員制度與舊生審核', 'group': '會員與課前資料', 'description': '管理會員制度、舊生及點數'},
    {'key': 'course_documents', 'label': '課前聲明書與表單', 'group': '會員與課前資料', 'description': '設定聲明書與課前問題'},
    {'key': 'scheduling', 'label': '排課月曆與團體班', 'group': '教學與教練', 'description': '查看排課及團體班'},
    {'key': 'coach_directory', 'label': '教練名冊與排課設定', 'group': '教學與教練', 'description': '管理教練、證照與排課設定'},
    {'key': 'coach_leaves', 'label': '請假審核', 'group': '教學與教練', 'description': '查看與處理教練請假'},
    {'key': 'evaluations', 'label': '學習評量與課程附件', 'group': '教學與教練', 'description': '查看及處理學習評量和課程附件'},
    {'key': 'course_types', 'label': '課程架構', 'group': '課程與雪場', 'description': '管理課程大類、類型、模板與時段'},
    {'key': 'pricing', 'label': '課程定價', 'group': '課程與雪場', 'description': '管理旺淡季及結帳價格'},
    {'key': 'resorts', 'label': '雪場營運資料', 'group': '課程與雪場', 'description': '管理雪場、接送及租借'},
    {'key': 'payment_accounts', 'label': '收款帳戶與幣別', 'group': '財務', 'description': '管理匯款帳戶及幣別'},
    {'key': 'payroll_rules', 'label': '教練計薪規則', 'group': '財務', 'description': '管理時薪、費用及計薪時數'},
    {'key': 'payroll_statements', 'label': '薪資單與月結', 'group': '財務', 'description': '試算、核對及發布教練薪資單'},
    {'key': 'staff_incentives', 'label': '行政獎金', 'group': '財務', 'description': '管理行政獎金規則及月結'},
    {'key': 'payroll_documents', 'label': '薪資文件設定', 'group': '財務', 'description': '管理薪資文件設定'},
    {'key': 'discounts', 'label': '折扣碼與促銷規則', 'group': '行銷與優惠', 'description': '管理實際折扣與促銷'},
    {'key': 'site_campaigns', 'label': '官網優惠活動與社群內容', 'group': '行銷與優惠', 'description': '管理活動文案與貼文'},
    {'key': 'social_sync', 'label': '官方社群授權', 'group': '行銷與優惠', 'description': '管理官方社群授權'},
    {'key': 'site_home', 'label': '首頁與頁尾', 'group': '官網內容', 'description': '管理首頁及頁尾'},
    {'key': 'site_courses', 'label': '滑雪課程與雪場介紹', 'group': '官網內容', 'description': '管理網站課程、雪場介紹及展示價目'},
    {'key': 'site_photography', 'label': '海外攝影', 'group': '官網內容', 'description': '管理攝影服務頁面'},
    {'key': 'site_guides', 'label': '滑雪攻略與 FAQ', 'group': '官網內容', 'description': '管理攻略、問答及文章'},
    {'key': 'site_news', 'label': '最新消息', 'group': '官網內容', 'description': '管理公告文章'},
    {'key': 'site_about', 'label': '品牌介紹與聯絡頁', 'group': '官網內容', 'description': '管理品牌、招募及聯絡資訊'},
    {'key': 'recruitment', 'label': '教練招募', 'group': '官網內容', 'description': '設定應徵表單及查看應徵資料，須有全校資料範圍'},
    {'key': 'site_coaches', 'label': '官網教練資料', 'group': '官網內容', 'description': '管理公開教練介紹'},
    {'key': 'site_reviews', 'label': '網站評論', 'group': '官網內容', 'description': '管理 Google 評論與學員心得'},
    {'key': 'site_media', 'label': '圖庫', 'group': '官網內容', 'description': '管理官網圖庫'},
    {'key': 'site_tracking', 'label': '網站追蹤設定', 'group': '官網內容', 'description': '管理網站分析追蹤'},
    {'key': 'site_structure', 'label': '官網頁面與區塊架構', 'group': '官網內容', 'description': '管理共用的網站頁面配置'},
    {'key': 'campuses', 'label': '校區與營運規則', 'group': '設定', 'description': '管理校區、可用雪場及營運規則'},
    {'key': 'staff', 'label': '員工與權限', 'group': '設定', 'description': '管理租戶員工的分頁及校區，限總部管理員'},
    {'key': 'checkout_policies', 'label': '訂課條款與隱私政策', 'group': '設定', 'description': '管理訂課服務、退費及隱私條款'},
    {'key': 'booking_form_options', 'label': '訂單表單選項', 'group': '設定', 'description': '管理通訊軟體與行銷來源選項'},
]

LEGACY_PERMISSIONS = {
    'orders': ('order_view', 'order_edit', 'order_payments', 'order_refunds', 'booking_links', 'order_export'),
    'coaches': ('coach_directory', 'coach_leaves'),
    'customers': ('member_directory', 'member_loyalty'),
    'payment_settings': ('payment_accounts', 'booking_form_options'),
    'payroll': ('payroll_rules', 'payroll_statements', 'staff_incentives', 'payroll_documents'),
    'cms': ('site_home', 'site_courses', 'site_photography', 'site_guides', 'site_news', 'site_about', 'site_coaches', 'site_campaigns', 'site_tracking', 'site_structure', 'social_sync', 'course_documents', 'checkout_policies', 'site_reviews', 'site_media'),
    'reviews': ('site_reviews', 'site_media'),
}

ADMIN_PERMISSION_KEYS = [item['key'] for item in ADMIN_PERMISSION_DEFINITIONS]

ROLE_DEFAULT_PERMISSIONS = {
    'marketing': ['analytics', 'discounts'],
    'web_editor': ['cms', 'reviews'],
    'insurance': ['insurance_records'],
    'assistant': ['orders', 'scheduling', 'insurance_records', 'evaluations', 'coaches', 'cms', 'reviews', 'contact_inbox', 'vehicle_finance'],
    'campus_principal': ['analytics', 'orders', 'scheduling', 'coaches', 'evaluations', 'payroll', 'vehicle_review'],
    'campus_manager': ['orders', 'scheduling', 'coaches', 'evaluations', 'vehicle_review'],
    'photographer': ['evaluations', 'reviews'],
}


def normalize_admin_permissions(value):
    if not isinstance(value, list):
        return []
    allowed = {child for key in value if isinstance(key, str)
               for child in LEGACY_PERMISSIONS.get(key, (key,))}
    return [key for key in ADMIN_PERMISSION_KEYS if key in allowed]


def get_user_admin_permissions(user, tenant=None):
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    if getattr(user, 'is_superuser', False):
        return list(ADMIN_PERMISSION_KEYS)
    from Control.tenant_memberships import staff_profile
    profile = staff_profile(user, tenant)
    if not profile or not profile.is_manager:
        return []
    stored = profile.admin_permissions
    if stored is None:
        permissions = list(ADMIN_PERMISSION_KEYS) if profile.role in ('', 'hq_admin') else normalize_admin_permissions(ROLE_DEFAULT_PERMISSIONS.get(profile.role, []))
    else:
        permissions = normalize_admin_permissions(stored)
    if tenant is not None:
        from Client.models import ModuleSetting, ModuleInfo
        from django.db.models import Q
        disabled = set(ModuleSetting.objects.filter(client=tenant).filter(
            Q(is_active=False)|Q(module__is_active=False)).values_list('module__module_sid',flat=True))
        disabled.update(ModuleInfo.objects.filter(is_active=False).values_list('module_sid',flat=True))
        disabled = set(normalize_admin_permissions(list(disabled)))
        permissions = [key for key in permissions if key not in disabled]
    return permissions


def user_has_admin_permission(user, permission_key, tenant=None):
    permissions = set(get_user_admin_permissions(user, tenant))
    if not permission_key:
        return bool(permissions)
    if tenant is not None and not getattr(user, 'is_superuser', False):
        from Client.tenant_settings import module_enabled
        if not module_enabled(tenant, permission_key):
            return False
    return set(LEGACY_PERMISSIONS.get(permission_key, (permission_key,))).issubset(permissions)


def console_permissions_for_user(user, tenant):
    permissions = get_user_admin_permissions(user, tenant)
    grants = set(permissions)
    # An older frontend may remain cached during a backend-first release.
    return [*permissions, *(key for key, children in LEGACY_PERMISSIONS.items() if set(children) <= grants)]
