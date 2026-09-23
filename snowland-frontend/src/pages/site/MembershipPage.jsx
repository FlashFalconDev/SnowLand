import React, { useCallback, useContext, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { CalendarDays, ChevronRight, ClipboardCheck, Gift, GraduationCap, LogOut, ShoppingBag, UserRound } from 'lucide-react';
import GoogleLoginButton from '../../components/auth/GoogleLoginButton';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import SiteLink, { SiteBasePathContext } from '../../components/site/SiteLink';
import { useBookingStore } from '../../store/bookingStore';

const navItems = [
  { key: 'overview', label: '會員總覽', path: '/membership', icon: UserRound },
  { key: 'orders', label: '我的訂單', path: '/membership/orders', icon: ShoppingBag },
  { key: 'offers', label: '專屬優惠', path: '/membership/offers', icon: Gift },
  { key: 'forms', label: '課前資料', path: '/membership/pre-course-forms', icon: ClipboardCheck },
  { key: 'journey', label: '課程評量', path: '/membership/my-skiing-journey', icon: GraduationCap },
];

const sectionFromPath = (path) => path.includes('/orders') ? 'orders'
  : path.includes('/offers') ? 'offers'
  : path.includes('/pre-course-forms') ? 'forms'
  : path.includes('/my-skiing-journey') ? 'journey' : 'overview';

const formatDate = (value) => value
  ? new Intl.DateTimeFormat('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(`${value}T00:00:00`))
  : '日期安排中';

const paymentLabels = { unpaid: '待付款', pending: '付款確認中', paid: '已付款', expired: '付款已逾期', refunded: '已退款' };

async function requestJson(url, options = {}) {
  const response = await fetch(url, { credentials: 'include', ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || data.detail || '資料載入失敗');
    error.status = response.status;
    throw error;
  }
  return data;
}

function EmptyState({ title, description, action }) {
  return <div className="rounded-sm border border-dashed border-[#cbd5e1] bg-white px-6 py-14 text-center">
    <p className="text-xl font-semibold text-[#1f2937]">{title}</p>
    {description && <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-[#64748b]">{description}</p>}
    {action}
  </div>;
}

function AuthPanel({ onAuthenticated }) {
  const params = new URLSearchParams(window.location.search);
  const resetUid = params.get('reset_uid');
  const resetToken = params.get('reset_token');
  const [mode, setMode] = useState(resetUid && resetToken ? 'reset' : 'login');
  const [email, setEmail] = useState(localStorage.getItem('remembered_member_email') || '');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(Boolean(localStorage.getItem('remembered_member_email')));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true); setError(''); setMessage('');
    try {
      const action = mode === 'forgot' ? 'request_reset' : mode === 'reset' ? 'reset_password' : mode;
      const payload = { action, email: email.trim(), password };
      if (mode === 'reset') Object.assign(payload, { uid: resetUid, token: resetToken });
      const data = await requestJson('/booking/snowland/api/member-auth/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      if (mode === 'forgot') setMessage(data.message);
      else if (mode === 'reset') {
        window.history.replaceState({}, '', window.location.pathname);
        setMode('login'); setPassword(''); setMessage(data.message);
      } else {
        if (remember) localStorage.setItem('remembered_member_email', email.trim());
        else localStorage.removeItem('remembered_member_email');
        localStorage.setItem('user', JSON.stringify(data.member));
        await onAuthenticated();
      }
    } catch (submitError) { setError(submitError.message); }
    finally { setBusy(false); }
  };

  return <div className="min-h-screen bg-[#f7f8fa]">
    <SiteHeader forceTransparent forceDarkText={false} forceLogoColor={false} />
    <section className="bg-gradient-to-br from-[#1c3b5f] via-[#2b5f8f] to-[#7bbbe7] px-6 pb-20 pt-32 text-center text-white">
      <p className="text-xs font-semibold uppercase tracking-[0.3em] text-white/75">Membership</p>
      <h1 className="mt-4 text-3xl font-semibold md:text-4xl">會員專區</h1>
      <p className="mt-3 text-sm text-white/80">查看訂單、課前資料與每一次滑雪學習紀錄</p>
    </section>
    <section className="mx-auto -mt-8 max-w-2xl px-5 pb-24">
      <div className="relative rounded-sm border border-[#dbe3ec] bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.10)] md:p-10">
        {!['forgot', 'reset'].includes(mode) && <div className="grid grid-cols-2 border-b border-[#e2e8f0]">
          {['login', 'register'].map((key) => <button key={key} type="button" onClick={() => { setMode(key); setError(''); setMessage(''); }}
            className={`border-b-2 px-4 py-4 text-base font-semibold ${mode === key ? 'border-[#2b5f8f] text-[#1f2937]' : 'border-transparent text-[#94a3b8]'}`}>
            {key === 'login' ? '會員登入' : '註冊會員'}
          </button>)}
        </div>}
        <div className="mb-6 mt-7 text-center">
          <h2 className="text-xl font-semibold text-[#1f2937]">{mode === 'forgot' ? '忘記密碼' : mode === 'reset' ? '設定新密碼' : mode === 'register' ? '建立 SnowLand 帳號' : '歡迎回來'}</h2>
          <p className="mt-2 text-sm text-[#64748b]">{mode === 'forgot' ? '輸入註冊信箱，我們會寄送重設連結。' : mode === 'reset' ? '新密碼至少需要 8 個字元。' : '登入後即可查看只屬於您的課程資料。'}</p>
        </div>
        <form onSubmit={submit} className="space-y-5">
          {mode !== 'reset' && <label className="block text-sm font-semibold text-[#334155]">電子郵件
            <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" className="mt-2 w-full rounded-sm border border-[#cbd5e1] bg-[#f8fafc] px-4 py-3 text-base outline-none focus:border-[#2b5f8f] focus:ring-2 focus:ring-[#2b5f8f]/15" />
          </label>}
          {mode !== 'forgot' && <label className="block text-sm font-semibold text-[#334155]">密碼
            <input type="password" required minLength={mode === 'register' || mode === 'reset' ? 8 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} className="mt-2 w-full rounded-sm border border-[#cbd5e1] bg-[#f8fafc] px-4 py-3 text-base outline-none focus:border-[#2b5f8f] focus:ring-2 focus:ring-[#2b5f8f]/15" />
          </label>}
          {mode === 'login' && <div className="flex items-center justify-between gap-4 text-sm"><label className="flex items-center gap-2 text-[#475569]"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />記住帳號</label><button type="button" onClick={() => setMode('forgot')} className="font-semibold text-[#2b5f8f] hover:underline">忘記密碼</button></div>}
          {error && <p role="alert" className="rounded-sm bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
          {message && <p role="status" className="rounded-sm bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</p>}
          <button type="submit" disabled={busy} className="w-full rounded-full bg-[#2b5f8f] px-6 py-3.5 font-semibold text-white hover:bg-[#1c4f7b] disabled:opacity-55">{busy ? '處理中…' : mode === 'forgot' ? '寄送重設信' : mode === 'reset' ? '更新密碼' : mode === 'register' ? '建立帳號' : '會員登入'}</button>
          {['forgot', 'reset'].includes(mode) && <button type="button" onClick={() => setMode('login')} className="w-full text-sm font-semibold text-[#64748b]">返回登入</button>}
        </form>
        {['login', 'register'].includes(mode) && <div className="mt-7 border-t border-[#e2e8f0] pt-6">
          <p className="mb-4 text-center text-xs font-semibold uppercase tracking-[0.2em] text-[#94a3b8]">或使用</p>
          <GoogleLoginButton onLogin={onAuthenticated} />
          <button type="button" disabled title="需設定 LINE Login Channel" className="mt-3 flex w-full cursor-not-allowed items-center justify-center gap-3 rounded-sm bg-[#e2e8f0] px-4 py-3 text-sm font-semibold text-[#64748b]"><span className="flex h-6 w-6 items-center justify-center rounded bg-white text-[#06c755]">L</span>LINE 登入尚未啟用</button>
        </div>}
      </div>
    </section>
    <SiteFooter />
  </div>;
}

function OrderCard({ order, onQuickRebook }) {
  const reservation = order.reservations?.[0];
  const booking = reservation?.bookings?.[0];
  return <article className="rounded-sm border border-[#dbe3ec] bg-white p-5 shadow-[0_8px_25px_rgba(15,23,42,0.04)] md:p-6">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold tracking-[0.18em] text-[#94a3b8]">{order.order_number}</p><h3 className="mt-2 text-lg font-semibold">{formatDate(booking?.date)}｜{reservation?.resort || '雪場安排中'}</h3></div><span className="rounded-full bg-[#eef4fa] px-3 py-1 text-xs font-semibold text-[#2b5f8f]">{paymentLabels[order.payment_status] || order.payment_status}</span></div>
    <div className="mt-5 grid gap-3 text-sm text-[#475569] sm:grid-cols-3"><p><span className="block text-xs text-[#94a3b8]">課程</span>{reservation?.course_template || reservation?.course_type || '安排中'}</p><p><span className="block text-xs text-[#94a3b8]">教練</span>{reservation?.coach || '安排中'}</p><p><span className="block text-xs text-[#94a3b8]">人數</span>{reservation?.people || 0} 人</p></div>
    <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-[#eef2f7] pt-4"><button type="button" onClick={() => onQuickRebook(order.id)} className="rounded-full border border-[#2b5f8f] px-4 py-2 text-sm font-semibold text-[#2b5f8f] hover:bg-[#eef4fa]">再次預約</button><SiteLink to={`/membership/orders/${order.id}`} className="inline-flex items-center gap-1 rounded-full bg-[#2b5f8f] px-4 py-2 text-sm font-semibold text-white">查看詳情<ChevronRight size={16} /></SiteLink></div>
  </article>;
}

function Orders({ data, onQuickRebook }) {
  const location = useLocation();
  const id = Number(location.pathname.match(/\/orders\/(\d+)/)?.[1]);
  const selected = data.orders.find((order) => order.id === id);
  if (selected) return <div><SiteLink to="/membership/orders" className="text-sm font-semibold text-[#2b5f8f]">← 返回我的訂單</SiteLink><h2 className="mt-5 text-2xl font-semibold">訂單詳情</h2><div className="mt-6 space-y-5"><OrderCard order={selected} onQuickRebook={onQuickRebook} />{selected.reservations.map((reservation) => <div key={reservation.id} className="rounded-sm border border-[#dbe3ec] bg-white p-5"><h3 className="font-semibold">{reservation.resort}｜{reservation.course_template || reservation.course_type}</h3><p className="mt-2 text-sm text-[#64748b]">教練：{reservation.coach}　學員：{reservation.people} 人</p><div className="mt-4 space-y-2">{reservation.bookings.map((booking) => <p key={booking.id} className="rounded-sm bg-[#f8fafc] px-4 py-3 text-sm text-[#475569]">{formatDate(booking.date)}　{booking.start_time}–{booking.end_time}　{booking.course_name}</p>)}</div></div>)}</div></div>;
  return <div><h2 className="text-2xl font-semibold">我的訂單</h2><p className="mt-2 text-sm text-[#64748b]">查看付款狀態、課程明細及快速再次預約。</p><div className="mt-7 space-y-4">{data.orders.length ? data.orders.map((order) => <OrderCard key={order.id} order={order} onQuickRebook={onQuickRebook} />) : <EmptyState title="目前沒有訂單" action={<SiteLink to="/booking" className="mt-6 inline-flex rounded-full bg-[#2b5f8f] px-6 py-3 text-sm font-semibold text-white">開始預約</SiteLink>} />}</div></div>;
}

function Forms({ forms }) {
  return <div><h2 className="text-2xl font-semibold">課前資料</h2><p className="mt-2 text-sm text-[#64748b]">確認每位學員的程度、保險與聲明書是否完成。</p><div className="mt-7 space-y-4">{forms.length ? forms.map((form) => <article key={form.id} className="rounded-sm border border-[#dbe3ec] bg-white p-5"><div className="flex flex-wrap justify-between gap-3"><div><h3 className="font-semibold">{form.member_name}</h3><p className="mt-1 text-xs text-[#94a3b8]">{form.order_number}</p></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${form.insurance_completed && form.waiver_completed ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{form.insurance_completed && form.waiver_completed ? '資料完成' : '尚有資料未完成'}</span></div><div className="mt-4 grid gap-3 text-sm sm:grid-cols-3"><p>年齡：{form.age_range}</p><p>保險：{form.insurance_completed ? '完成' : '未完成'}</p><p>聲明書：{form.waiver_completed ? '完成' : '未完成'}</p></div><p className="mt-3 text-sm text-[#64748b]">程度：{[...form.snowboard_skills, ...form.ski_skills].join('、') || '尚未填寫'}</p></article>) : <EmptyState title="目前沒有待填寫的課前資料" description="完成預約並建立學員資料後，會自動顯示在這裡。" />}</div></div>;
}

function Journey({ records }) {
  return <div><h2 className="text-2xl font-semibold">課程評量</h2><p className="mt-2 text-sm text-[#64748b]">查看程度變化、教練建議與公開課程照片／影片。</p><div className="mt-7 space-y-5">{records.length ? records.map((record) => <article key={record.id} className="overflow-hidden rounded-sm border border-[#dbe3ec] bg-white">{record.media.length > 0 && <div className="grid max-h-80 grid-cols-2 overflow-hidden bg-[#e2e8f0]">{record.media.slice(0, 4).map((media) => media.type === 'video' ? <video key={media.id} controls className="h-full min-h-48 w-full object-cover" src={media.url} /> : <img key={media.id} src={media.url} alt={media.caption || `${record.resort} 課程照片`} className="h-full min-h-48 w-full object-cover" />)}</div>}<div className="p-5 md:p-6"><p className="text-xs font-semibold tracking-[0.18em] text-[#94a3b8]">{formatDate(record.date)}｜{record.order_number}</p><h3 className="mt-2 text-lg font-semibold">{record.resort}｜{record.course_name}</h3><p className="mt-3 text-sm text-[#64748b]">學員：{record.member_name}　教練：{record.coach}</p><div className="mt-5 rounded-sm bg-[#f8fafc] p-4"><p className="text-xs font-semibold text-[#2b5f8f]">教練建議</p><p className="mt-2 whitespace-pre-line text-sm leading-7 text-[#475569]">{record.coach_notes || '教練尚未填寫建議'}</p></div>{Object.keys(record.learning_progress || {}).length > 0 && <div className="mt-4 flex flex-wrap gap-2">{Object.entries(record.learning_progress).map(([key, value]) => <span key={key} className="rounded-full bg-[#eef4fa] px-3 py-1 text-xs text-[#2b5f8f]">{key}：{String(value)}</span>)}</div>}</div></article>) : <EmptyState title="尚無課程評量" description="教練完成課後評量後，紀錄與公開媒體會出現在這裡。" />}</div></div>;
}

function Overview({ data }) {
  const upcoming = data.orders.flatMap((order) => order.reservations.flatMap((reservation) => reservation.bookings.map((booking) => ({ order, reservation, booking })))).filter((item) => new Date(`${item.booking.date}T23:59:59`) >= new Date()).sort((a, b) => a.booking.date.localeCompare(b.booking.date))[0];
  return <div><p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#94a3b8]">My Journey</p><h2 className="mt-3 text-2xl font-semibold md:text-3xl">會員總覽</h2><div className="mt-7 grid gap-4 lg:grid-cols-[1.4fr_1fr]"><div className="rounded-sm bg-gradient-to-br from-[#8eb6d9] to-[#d8d7df] p-6 text-white md:p-8"><p className="text-sm">Hi, {data.member.name}!</p><h3 className="mt-5 text-2xl font-semibold">準備好下一趟滑雪旅程了嗎？</h3><p className="mt-3 text-sm leading-7 text-white/85">快速開始下一次課程預約。</p><SiteLink to="/booking" className="mt-6 inline-flex rounded-full bg-white/90 px-5 py-2.5 text-sm font-semibold text-[#2b5f8f]">開始預約</SiteLink></div><div className="rounded-sm border border-[#dbe3ec] bg-white p-6">{upcoming ? <><span className="rounded-full bg-orange-50 px-3 py-1 text-xs font-semibold text-orange-700">即將到來</span><p className="mt-5 text-xl font-semibold">{formatDate(upcoming.booking.date)}</p><p className="mt-2 font-semibold">{upcoming.reservation.resort}</p><p className="mt-2 text-sm text-[#64748b]">{upcoming.booking.start_time}–{upcoming.booking.end_time}｜{upcoming.reservation.people} 位學員</p><SiteLink to={`/membership/orders/${upcoming.order.id}`} className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-[#2b5f8f]">查看預約詳情<ChevronRight size={16} /></SiteLink></> : <><CalendarDays className="text-[#94a3b8]" /><p className="mt-5 font-semibold">目前沒有即將到來的課程</p></>}</div></div>{data.learning_records[0] && <div className="mt-8"><div className="flex items-center justify-between"><h3 className="text-xl font-semibold">我的滑雪學習紀錄</h3><SiteLink to="/membership/my-skiing-journey" className="text-sm font-semibold text-[#2b5f8f]">查看全部</SiteLink></div><div className="mt-4 rounded-sm border border-[#dbe3ec] bg-white p-5"><p className="text-sm font-semibold">{formatDate(data.learning_records[0].date)}｜{data.learning_records[0].resort}</p><p className="mt-3 line-clamp-3 text-sm leading-7 text-[#64748b]">{data.learning_records[0].coach_notes || '教練評量整理中'}</p></div></div>}<div className="mt-8"><h3 className="text-xl font-semibold">我的 SnowLand 滑雪旅程</h3><div className="mt-4 grid gap-4 sm:grid-cols-3">{[[data.journey.seasons, '一起滑過的雪季'], [data.journey.completed_course_days, '完成課程天數'], [data.journey.resorts, '去過的雪場']].map(([value, label]) => <div key={label} className="rounded-sm border border-[#dbe3ec] bg-white p-6 text-center"><p className="text-3xl font-semibold text-[#2b5f8f]">{value}</p><p className="mt-2 text-sm text-[#64748b]">{label}</p></div>)}</div></div></div>;
}

function MemberContent({ section, data, onQuickRebook }) {
  if (section === 'orders') return <Orders data={data} onQuickRebook={onQuickRebook} />;
  if (section === 'forms') return <Forms forms={data.pre_course_forms} />;
  if (section === 'journey') return <Journey records={data.learning_records} />;
  if (section === 'offers') return <div><h2 className="text-2xl font-semibold">專屬優惠</h2><p className="mt-2 text-sm text-[#64748b]">會員等級、點數與推薦碼集中在這裡。</p><div className="mt-7 grid gap-4 md:grid-cols-2"><div className="rounded-sm bg-gradient-to-br from-[#1c3b5f] to-[#2b5f8f] p-6 text-white"><Gift /><p className="mt-8 text-sm text-white/70">會員等級</p><p className="mt-1 text-2xl font-semibold">{data.level === 'new' ? '新會員' : data.level}</p><p className="mt-5 text-sm">可用點數：{data.points}</p></div><div className="rounded-sm border border-[#dbe3ec] bg-white p-6"><p className="text-sm font-semibold text-[#64748b]">我的推薦碼</p><p className="mt-4 break-all text-2xl font-semibold tracking-wider text-[#2b5f8f]">{data.referral_code}</p><p className="mt-4 text-sm leading-7 text-[#64748b]">提供給親友預約時使用；實際回饋依當期活動規則計算。</p></div></div></div>;
  return <Overview data={data} />;
}

export default function MembershipPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const basePath = useContext(SiteBasePathContext);
  const section = sectionFromPath(location.pathname);
  const [status, setStatus] = useState('loading');
  const [data, setData] = useState(null);
  const [notice, setNotice] = useState('');

  const loadMemberCenter = useCallback(async () => {
    setStatus('loading');
    try {
      const payload = await requestJson('/booking/snowland/api/member-center/');
      setData(payload); setStatus('ready'); localStorage.setItem('user', JSON.stringify(payload.member));
    } catch (error) {
      if (error.status === 401) { setData(null); setStatus('guest'); }
      else { setNotice(error.message); setStatus('error'); }
    }
  }, []);

  useEffect(() => { loadMemberCenter(); }, [loadMemberCenter]);

  const quickRebook = async (orderId) => {
    setNotice('正在複製上次預約設定…');
    try {
      const result = await requestJson('/booking/snowland/api/member-center/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quick_rebook_group_id: orderId }) });
      useBookingStore.getState().replaceCart(result.cart); navigate(`${basePath}/booking`);
    } catch (error) { setNotice(error.message); }
  };

  const logout = async () => {
    await fetch('/control/api/logout/', { method: 'POST', credentials: 'include' }).catch(() => undefined);
    localStorage.removeItem('user'); setData(null); setStatus('guest'); navigate(`${basePath}/membership`);
  };

  if (status === 'loading') return <div className="flex min-h-screen items-center justify-center bg-[#f7f8fa]"><div className="h-11 w-11 animate-spin rounded-full border-4 border-[#dbe3ec] border-t-[#2b5f8f]" /><span className="sr-only">載入會員資料</span></div>;
  if (status === 'guest') return <AuthPanel onAuthenticated={loadMemberCenter} />;
  if (status === 'error' || !data) return <div className="flex min-h-screen flex-col items-center justify-center gap-5 bg-[#f7f8fa] px-6 text-center"><p className="text-lg font-semibold">會員資料暫時無法載入</p><p className="text-sm text-[#64748b]">{notice}</p><button onClick={loadMemberCenter} className="rounded-full bg-[#2b5f8f] px-6 py-3 text-sm font-semibold text-white">重新載入</button></div>;

  return <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937]"><SiteHeader forceTransparent forceDarkText memberAuthenticated memberAvatarSrc="" /><main className="mx-auto max-w-7xl px-4 pb-24 pt-24 sm:px-6 md:pt-28"><nav aria-label="breadcrumb" className="mb-6 flex items-center gap-2 text-sm text-[#64748b]"><SiteLink to="/">首頁</SiteLink><span>/</span><span className="font-semibold text-[#1f2937]">會員專區</span></nav>{notice && <div role="status" className="mb-5 flex items-center justify-between rounded-sm bg-[#eef4fa] px-4 py-3 text-sm text-[#2b5f8f]"><span>{notice}</span><button onClick={() => setNotice('')} aria-label="關閉訊息">×</button></div>}<div className="grid gap-7 lg:grid-cols-[250px_minmax(0,1fr)]"><aside className="min-w-0 self-start rounded-sm border border-[#dbe3ec] bg-white p-3 lg:sticky lg:top-24 lg:p-5"><div className="flex items-center gap-3 border-b border-[#e2e8f0] pb-3 text-left lg:block lg:pb-5 lg:text-center"><div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[#eef4fa] text-[#2b5f8f] lg:mx-auto lg:h-20 lg:w-20"><UserRound size={30} /></div><div className="min-w-0"><p className="truncate font-semibold lg:mt-4">{data.member.name}</p><p className="mt-1 truncate text-xs text-[#64748b]">{data.member.email}</p></div></div><nav className="mt-3 flex gap-2 overflow-x-auto pb-1 lg:block" aria-label="會員功能">{navItems.map(({ key, label, path, icon: Icon }) => <SiteLink key={key} to={path} className={`flex shrink-0 items-center gap-2 rounded-full border px-3 py-2.5 text-sm font-semibold lg:gap-3 lg:rounded-none lg:border-x-0 lg:border-t-0 lg:border-b lg:border-[#eef2f7] lg:px-2 lg:py-3.5 ${section === key ? 'border-[#2b5f8f] bg-[#eef4fa] text-[#2b5f8f] lg:bg-transparent' : 'border-[#e2e8f0] text-[#64748b] hover:text-[#2b5f8f]'}`}><Icon size={17} />{label}</SiteLink>)}</nav><button type="button" onClick={logout} className="mt-2 flex items-center gap-2 px-3 py-2 text-sm font-semibold text-[#64748b] hover:text-red-600 lg:mt-4 lg:w-full lg:gap-3 lg:px-2 lg:py-3"><LogOut size={17} />登出</button></aside><section className="min-w-0"><MemberContent section={section} data={data} onQuickRebook={quickRebook} /></section></div></main><SiteFooter /></div>;
}
