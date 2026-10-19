export type SiteLocale = 'zh-Hant' | 'en' | 'ja'
export type SiteLanguagePreference = SiteLocale | 'auto'
export const siteLanguageStorageKey = 'snowland.site-language.v1'
export const siteLanguages: { value: SiteLanguagePreference; label: string }[] = [
  { value: 'auto', label: '自動 / Auto / 自動' },
  { value: 'zh-Hant', label: '繁體中文' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
]

export function readSiteLanguagePreference(storage?: Pick<Storage, 'getItem'>): SiteLanguagePreference {
  try {
    const saved = storage?.getItem(siteLanguageStorageKey)
    return siteLanguages.some(item => item.value === saved) ? saved as SiteLanguagePreference : 'auto'
  } catch { return 'auto' }
}

export function resolveSiteLocale(preference: unknown, languages: readonly unknown[] = []): SiteLocale {
  if (preference === 'en' || preference === 'ja' || preference === 'zh-Hant') return preference
  for (const language of languages) {
    if (typeof language !== 'string') continue
    const code = language.toLowerCase().split('-')[0]
    if (code === 'ja' || code === 'en') return code
    if (code === 'zh') return 'zh-Hant'
  }
  return 'zh-Hant'
}

// Only product-owned UI copy belongs here. Do not translate personal information,
// course/CMS names or signed/legal documents through a text replacement service.
const messages: Record<string, { en: string; ja: string }> = {
  '滑雪課程': { en: 'Ski & snowboard lessons', ja: 'スキー・スノーボード' },
  '海外攝影': { en: 'Photography', ja: '写真撮影' },
  '滑雪攻略': { en: 'Snow guides', ja: 'スノーガイド' },
  '最新消息': { en: 'News', ja: 'お知らせ' },
  '關於Snowland': { en: 'About SnowLand', ja: 'SnowLandについて' },
  '會員專區': { en: 'Member area', ja: 'マイページ' },
  '預約課程': { en: 'Book a lesson', ja: 'レッスンを予約' },
  '北海道所有雪場': { en: 'All Hokkaido resorts', ja: '北海道の全スキー場' },
  '野雪嚮導': { en: 'Backcountry guiding', ja: 'バックカントリーガイド' },
  '預約流程': { en: 'How to book', ja: '予約の流れ' },
  '冬季雪地攝影': { en: 'Winter photography', ja: '冬の写真撮影' },
  '夏季旅拍攝影': { en: 'Summer photography', ja: '夏の写真撮影' },
  '攝影作品': { en: 'Photo gallery', ja: 'フォトギャラリー' },
  '預約攝影流程': { en: 'Book a photo session', ja: '撮影予約の流れ' },
  '雪場攻略': { en: 'Resort guides', ja: 'スキー場ガイド' },
  '行前須知': { en: 'Before your trip', ja: 'ご出発前のご案内' },
  '滑雪裝備': { en: 'Equipment', ja: '装備について' },
  '常見問題': { en: 'FAQ', ja: 'よくあるご質問' },
  '滑雪精選文章': { en: 'Featured articles', ja: 'おすすめ記事' },
  '限定優惠': { en: 'Special offers', ja: '特別キャンペーン' },
  '滑雪學校介紹': { en: 'Our school', ja: 'スクール紹介' },
  '教練團隊': { en: 'Our instructors', ja: 'インストラクター' },
  '成為教練': { en: 'Join our team', ja: '採用情報' },
  '聯絡我們': { en: 'Contact us', ja: 'お問い合わせ' },
  '購物車': { en: 'Booking cart', ja: '予約カート' },
  '會員頭像': { en: 'My account', ja: 'アカウント' },
  '校區載入中…': { en: 'Loading areas…', ja: 'エリアを読み込み中…' },
  '校區載入失敗，點此重試': { en: 'Could not load areas. Retry', ja: 'エリアを読み込めません。再試行' },
  '語言': { en: 'Language', ja: '言語' },
  '首頁': { en: 'Home', ja: 'ホーム' },
  '會員總覽': { en: 'Overview', ja: '会員ページ' },
  '通知中心': { en: 'Notifications', ja: '通知' },
  '我的訂單': { en: 'My bookings', ja: '予約一覧' },
  '專屬優惠': { en: 'Member offers', ja: '会員特典' },
  '課前資料': { en: 'Pre-lesson forms', ja: '受講前の登録情報' },
  '課程評量': { en: 'Learning records', ja: 'レッスン記録' },
  '會員功能': { en: 'Member navigation', ja: '会員メニュー' },
  '關閉訊息': { en: 'Dismiss message', ja: 'メッセージを閉じる' },
  '會員登入': { en: 'Sign in', ja: 'ログイン' },
  '註冊會員': { en: 'Register', ja: '新規会員登録' },
  '電子郵件': { en: 'Email', ja: 'メールアドレス' },
  '密碼': { en: 'Password', ja: 'パスワード' },
  '會員姓名': { en: 'Full name', ja: '氏名' },
  '請填寫實際姓名': { en: 'Enter your full name', ja: '本名をご入力ください' },
  '記住帳號': { en: 'Remember my email', ja: 'メールアドレスを保存' },
  '忘記密碼': { en: 'Forgot password', ja: 'パスワードを忘れた方' },
  '設定新密碼': { en: 'Set a new password', ja: '新しいパスワードの設定' },
  '建立 SnowLand 帳號': { en: 'Create a SnowLand account', ja: 'SnowLandアカウントを作成' },
  '歡迎回來': { en: 'Welcome back', ja: 'ようこそ' },
  '輸入註冊信箱，我們會寄送重設連結。': { en: 'Enter your registered email to request a password reset link.', ja: '登録済みメールアドレスに再設定用リンクをお送りします。' },
  '新密碼至少需要 8 個字元。': { en: 'Your new password must contain at least 8 characters.', ja: '新しいパスワードは8文字以上でご入力ください。' },
  '登入後即可查看只屬於您的課程資料。': { en: 'Sign in to view your bookings and lesson information.', ja: 'ログインすると、ご自身の予約・レッスン情報を確認できます。' },
  '查看訂單、課前資料與每一次滑雪學習紀錄': { en: 'Your bookings, pre-lesson forms and learning records in one place.', ja: '予約、受講前の登録情報、スキー・スノーボードの学習記録を確認できます。' },
  '請重新登入後送出訂單。購物車已保留，登入後會回到資料確認頁。': { en: 'Please sign in again before placing your booking. Your cart is saved; you will return to the review page.', ja: '予約を送信する前に、再度ログインしてください。カートは保持され、ログイン後に確認画面へ戻ります。' },
  '您收到同行學員邀請。請登入您自己的帳號；登入後仍需確認綁定，不會自動認領。': { en: 'You have a participant invitation. Sign in to your own account, then confirm the link; it is not accepted automatically.', ja: '同行者の招待が届いています。ご自身のアカウントでログインし、連携を確認してください。自動では連携されません。' },
  '處理中…': { en: 'Processing…', ja: '処理中…' },
  '寄送重設信': { en: 'Send reset link', ja: '再設定メールを送信' },
  '更新密碼': { en: 'Update password', ja: 'パスワードを更新' },
  '建立帳號': { en: 'Create account', ja: 'アカウントを作成' },
  '返回登入': { en: 'Back to sign in', ja: 'ログインへ戻る' },
  '或使用': { en: 'Or continue with', ja: 'または以下の方法でログイン' },
  '登入中,請稍候...': { en: 'Signing in, please wait…', ja: 'ログイン中です。しばらくお待ちください…' },
  'Google 登入尚未完成設定': { en: 'Google sign-in has not been configured', ja: 'Googleログインの設定が完了していません' },
  'LINE 登入尚未啟用': { en: 'LINE sign-in is not enabled', ja: 'LINEログインは現在ご利用いただけません' },
  '登出': { en: 'Sign out', ja: 'ログアウト' },
  '登出中…': { en: 'Signing out…', ja: 'ログアウト中…' },
  '載入會員資料': { en: 'Loading your account', ja: '会員情報を読み込み中' },
  '會員資料暫時無法載入': { en: 'Your account could not be loaded', ja: '会員情報を読み込めません' },
  '重新載入': { en: 'Reload', ja: '再読み込み' },
  '準備好下一趟滑雪旅程了嗎？': { en: 'Ready for your next snow adventure?', ja: '次のスノーシーズンを楽しみませんか？' },
  '快速開始下一次課程預約。': { en: 'Start booking your next lesson.', ja: '次のレッスンを予約しましょう。' },
  '開始預約': { en: 'Start booking', ja: '予約を始める' },
  '目前沒有即將到來的課程': { en: 'You have no upcoming lessons', ja: '現在、今後のレッスン予約はありません' },
  '我的滑雪學習紀錄': { en: 'My learning records', ja: '学習記録' },
  '查看全部': { en: 'View all', ja: 'すべて見る' },
  '教練評量整理中': { en: 'Your instructor is preparing the assessment', ja: 'インストラクターが評価を作成中です' },
  '我的 SnowLand 滑雪旅程': { en: 'My SnowLand journey', ja: 'SnowLandでのスノー体験' },
  '一起滑過的雪季': { en: 'Seasons with SnowLand', ja: '参加シーズン数' },
  '完成課程天數': { en: 'Lesson days completed', ja: '受講日数' },
  '去過的雪場': { en: 'Resorts visited', ja: '訪れたスキー場' },
  '即將到來': { en: 'Upcoming', ja: '受講予定' },
  '預約處理中': { en: 'Booking in progress', ja: '予約手続き中' },
  '查看課前資料': { en: 'View pre-lesson forms', ja: '受講前の登録情報を確認' },
  '查看預約詳情': { en: 'View booking details', ja: '予約詳細を確認' },
  '語言偏好無法儲存，本次仍可使用。': { en: 'Your language choice could not be saved, but is active for this visit.', ja: '言語設定を保存できませんでした。この画面では選択した言語を使用できます。' },
}

export function translateSiteText(locale: SiteLocale, source: string): string {
  return locale === 'zh-Hant' ? source : messages[source]?.[locale] ?? source
}
