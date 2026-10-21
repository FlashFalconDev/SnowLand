import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Bell, CalendarDays, ChevronRight, ClipboardCheck, Gift, GraduationCap, LogOut, ShoppingBag, Star, UserRound } from 'lucide-react';
import GoogleLoginButton from '../../components/auth/GoogleLoginButton';
import ClassGroupQRImage from '../../components/ClassGroupQRImage';
import SettlementSummary, { settlementAmount } from '../../components/booking/SettlementSummary';
import OrderAmendmentBalance from '../../components/OrderAmendmentBalance';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import SiteLink, { SiteBasePathContext } from '../../components/site/SiteLink';
import { useBookingStore } from '../../store/bookingStore';
import { formatLearningProgressEntry } from '../../utils/learningProgress';
import { birthDateStatus } from '../../utils/participantAge';
import { useSiteLocale } from '../../contexts/SiteLocale';

const navItems = [
  { key: 'overview', label: '會員總覽', path: '/membership', icon: UserRound },
  { key: 'notifications', label: '通知中心', path: '/membership/notifications', icon: Bell },
  { key: 'orders', label: '我的訂單', path: '/membership/orders', icon: ShoppingBag },
  { key: 'offers', label: '專屬優惠', path: '/membership/offers', icon: Gift },
  { key: 'forms', label: '課前資料', path: '/membership/pre-course-forms', icon: ClipboardCheck },
  { key: 'journey', label: '課程評量', path: '/membership/my-skiing-journey', icon: GraduationCap },
];

const sectionFromPath = (path) => path.includes('/notifications') ? 'notifications' : path.includes('/orders') ? 'orders'
  : path.includes('/offers') ? 'offers'
  : path.includes('/pre-course-forms') ? 'forms'
  : path.includes('/my-skiing-journey') ? 'journey' : 'overview';

const formatDate = (value) => value
  ? new Intl.DateTimeFormat('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(`${value}T00:00:00`))
  : '日期安排中';

const paymentLabels = { payment_records_review: '付款紀錄待核對', unpaid: '待付款', pending: '付款確認中', paid: '已付款', expired: '付款已逾期', refunded: '已退款', all_cancelled: '已取消', collecting_class: '待成班', pending_coach_approval: '待教練確認', scheduling_failed: '待安排課程' };
const paymentHoldMessages = { expired: '付款保留期已結束，請聯絡客服改期或取消', payment_records_review: '此訂單有既有收款或退款紀錄，請先聯絡客服核對；請勿再次付款。', all_cancelled: '此訂單已取消，無需付款。', collecting_class: '團體班尚未成班，滿人後才會開放付款。', pending_coach_approval: '等待教練確認接課，確認前不需要付款。', scheduling_failed: '課程正在重新安排，確認排課前不需要付款。' };
const cancellationLabels = { requested: '取消審核中', approved: '已取消・退款處理中', rejected: '取消申請未通過', refunded: '已退款' };
const refundMoney=(base,settlement,t)=>settlement?.currency==='JPY'
  ? settlement.refund_amount==null?(t?t('待核對實收款'):'待核對實收款')
    : t?t('日幣 JPY ¥ {amount}',{amount:Number(settlement.refund_amount).toLocaleString()}):`日幣 JPY ¥ ${Number(settlement.refund_amount).toLocaleString()}`
  : base==null?(t?t('待核對實收款'):'待核對實收款'):`NT$ ${Number(base).toLocaleString()}`;
const ageOptions = ['4-6y', '7-12y', '13-18y', '19-24y', '25-35y', '36-45y', '46-55y', '56y以上'];
const ageLabel = (value, t) => {
  if (!t) return value ? value.replace('y', ' 歲') : '未填寫';
  if (!value) return t('未填寫');
  const range = value.match(/^(\d+)-(\d+)y$/);
  if (range) return t('{from}-{to} 歲', {from:range[1],to:range[2]});
  const above = value.match(/^(\d+)y以上$/);
  return above ? t('{age} 歲以上',{age:above[1]}) : value;
};

async function requestJson(url, options = {}) {
  const headers = new Headers(options.headers);
  if (!['GET', 'HEAD', 'OPTIONS'].includes((options.method || 'GET').toUpperCase())) {
    const csrf = document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith('csrftoken='));
    if (csrf) headers.set('X-CSRFToken', csrf.slice('csrftoken='.length));
  }
  const response = await fetch(url, { credentials: 'include', ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.error || data.detail || data.msg || Object.values(data).flat().filter(value => typeof value === 'string').join('；') || '資料載入失敗';
    const error = new Error(response.status === 403 && String(detail).startsWith('CSRF Failed:')
      ? '頁面驗證已失效，請重新整理後再試；本次操作未送出。' : detail);
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
  const {t}=useSiteLocale();
  const params = new URLSearchParams(window.location.search);
  const resetUid = params.get('reset_uid');
  const resetToken = params.get('reset_token');
  const [mode, setMode] = useState(resetUid && resetToken ? 'reset' : 'login');
  const [name, setName] = useState('');
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
      if (mode === 'register') payload.name = name.trim();
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
      <h1 className="mt-4 text-3xl font-semibold md:text-4xl">{t('會員專區')}</h1>
      <p className="mt-3 text-sm text-white/80">{t('查看訂單、課前資料與每一次滑雪學習紀錄')}</p>
    </section>
    <section className="mx-auto -mt-8 max-w-2xl px-5 pb-24">
      <div className="relative rounded-sm border border-[#dbe3ec] bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.10)] md:p-10">
        {!['forgot', 'reset'].includes(mode) && <div className="grid grid-cols-2 border-b border-[#e2e8f0]">
          {['login', 'register'].map((key) => <button key={key} type="button" onClick={() => { setMode(key); setError(''); setMessage(''); }}
            className={`border-b-2 px-4 py-4 text-base font-semibold ${mode === key ? 'border-[#2b5f8f] text-[#1f2937]' : 'border-transparent text-[#94a3b8]'}`}>
            {t(key === 'login' ? '會員登入' : '註冊會員')}
          </button>)}
        </div>}
        <div className="mb-6 mt-7 text-center">
          <h2 className="text-xl font-semibold text-[#1f2937]">{t(mode === 'forgot' ? '忘記密碼' : mode === 'reset' ? '設定新密碼' : mode === 'register' ? '建立 SnowLand 帳號' : '歡迎回來')}</h2>
          <p className="mt-2 text-sm text-[#64748b]">{t(mode === 'forgot' ? '輸入註冊信箱，我們會寄送重設連結。' : mode === 'reset' ? '新密碼至少需要 8 個字元。' : '登入後即可查看只屬於您的課程資料。')}</p>
        </div>
        {params.get('resume_checkout') === '1' && <p role="status" className="mb-5 rounded-sm bg-[#eef4fa] px-4 py-3 text-sm leading-6 text-[#2b5f8f]">{t('請重新登入後送出訂單。購物車已保留，登入後會回到資料確認頁。')}</p>}
        {params.get('invite') && <p role="status" className="mb-5 rounded-sm bg-[#eef4fa] px-4 py-3 text-sm leading-6 text-[#2b5f8f]">{t('您收到同行學員邀請。請登入您自己的帳號；登入後仍需確認綁定，不會自動認領。')}</p>}
        <form onSubmit={submit} className="space-y-5">
          {mode === 'register' && <label className="block text-sm font-semibold text-[#334155]">{t('會員姓名')}
            <input type="text" required maxLength={150} value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" placeholder={t('請填寫實際姓名')} className="mt-2 w-full rounded-sm border border-[#cbd5e1] bg-[#f8fafc] px-4 py-3 text-base outline-none focus:border-[#2b5f8f] focus:ring-2 focus:ring-[#2b5f8f]/15" />
          </label>}
          {mode !== 'reset' && <label className="block text-sm font-semibold text-[#334155]">{t('電子郵件')}
            <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" className="mt-2 w-full rounded-sm border border-[#cbd5e1] bg-[#f8fafc] px-4 py-3 text-base outline-none focus:border-[#2b5f8f] focus:ring-2 focus:ring-[#2b5f8f]/15" />
          </label>}
          {mode !== 'forgot' && <label className="block text-sm font-semibold text-[#334155]">{t('密碼')}
            <input type="password" required minLength={mode === 'register' || mode === 'reset' ? 8 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} className="mt-2 w-full rounded-sm border border-[#cbd5e1] bg-[#f8fafc] px-4 py-3 text-base outline-none focus:border-[#2b5f8f] focus:ring-2 focus:ring-[#2b5f8f]/15" />
          </label>}
          {mode === 'login' && <div className="flex items-center justify-between gap-4 text-sm"><label className="flex items-center gap-2 text-[#475569]"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />{t('記住帳號')}</label><button type="button" onClick={() => setMode('forgot')} className="min-h-11 font-semibold text-[#2b5f8f] hover:underline">{t('忘記密碼')}</button></div>}
          {error && <p role="alert" className="rounded-sm bg-red-50 px-4 py-3 text-sm text-red-700">{t(error)}</p>}
          {message && <p role="status" className="rounded-sm bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{t(message)}</p>}
          <button type="submit" disabled={busy} className="w-full rounded-full bg-[#2b5f8f] px-6 py-3.5 font-semibold text-white hover:bg-[#1c4f7b] disabled:opacity-55">{t(busy ? '處理中…' : mode === 'forgot' ? '寄送重設信' : mode === 'reset' ? '更新密碼' : mode === 'register' ? '建立帳號' : '會員登入')}</button>
          {['forgot', 'reset'].includes(mode) && <button type="button" onClick={() => setMode('login')} className="min-h-11 w-full text-sm font-semibold text-[#64748b]">{t('返回登入')}</button>}
        </form>
        {['login', 'register'].includes(mode) && <div className="mt-7 border-t border-[#e2e8f0] pt-6">
          <p className="mb-4 text-center text-xs font-semibold uppercase tracking-[0.2em] text-[#94a3b8]">{t('或使用')}</p>
          <GoogleLoginButton onLogin={onAuthenticated} />
          <button type="button" disabled title={t('需設定 LINE Login Channel')} className="mt-3 flex w-full cursor-not-allowed items-center justify-center gap-3 rounded-sm bg-[#e2e8f0] px-4 py-3 text-sm font-semibold text-[#64748b]"><span className="flex h-6 w-6 items-center justify-center rounded bg-white text-[#06c755]">L</span>{t('LINE 登入尚未啟用')}</button>
        </div>}
      </div>
    </section>
    <SiteFooter />
  </div>;
}

function OrderCard({ order, onQuickRebook, showActions = true, showOrderNumber = false }) {
  const { t } = useSiteLocale();
  const activeCourses = (order.reservations || []).filter(item => !['cancelled', 'deleted'].includes(item.status));
  const courses = activeCourses.length ? activeCourses : (order.reservations || []).filter(item => item.status !== 'deleted');
  const reservation = courses[0];
  const dates = [...new Set(courses.flatMap(item => (item.bookings || []).map(booking => booking.date).filter(Boolean)))].sort();
  const dateLabel = dates.length > 1 ? `${formatDate(dates[0])}–${formatDate(dates[dates.length - 1])}` : formatDate(dates[0]);
  const coachChoice = reservation?.service_type === 'photo' ? (reservation.coach && reservation.coach !== '安排中' ? reservation.coach : '由學校安排') : reservation?.is_shared_class ? '由學校安排'
    : reservation?.is_preferred_coach ? (reservation.coach && reservation.coach !== '安排中' ? reservation.coach : '指定教練待安排') : '不指定';
  const canPay = order.payment_status === 'unpaid' && !order.payment_hold_status;
  const cancellationStage = ['paid', 'refunded'].includes(order.payment_status) ? order.cancellation?.status : null;
  const settledCancellation = ['approved', 'refunded'].includes(order.cancellation?.status);
  const fullyCancelled = Boolean(order.reservations?.length) && order.reservations.every(item => ['cancelled', 'deleted'].includes(item.status));
  const displayAmount = settledCancellation ? order.cancellation.original_amount
    : fullyCancelled ? (order.historical_amount ?? order.total_amount) : order.total_amount;
  return <article className="rounded-sm border border-[#dbe3ec] bg-white p-5 shadow-[0_8px_25px_rgba(15,23,42,0.04)] md:p-6">
    <div className="flex flex-wrap items-start justify-between gap-3"><div>{showOrderNumber && <p className="break-all text-xs font-semibold tracking-[0.18em] text-[#94a3b8]">{order.order_number}</p>}<h3 className="mt-2 text-lg font-semibold">{dateLabel === '日期安排中' ? t(dateLabel) : dateLabel}｜{reservation?.resort || t('雪場安排中')}</h3>{courses.length > 1 && <p className="mt-2 text-xs text-[#64748b]">{t('另有 {count} 項課程，',{count:courses.length-1})}{t(showOrderNumber ? '以下列出全部課程。' : '請查看詳情。')}</p>}</div><span className="rounded-full bg-[#eef4fa] px-3 py-1 text-xs font-semibold text-[#2b5f8f]">{t(cancellationLabels[cancellationStage] || paymentLabels[order.payment_hold_status || order.payment_status] || order.payment_status)}</span></div>
    <div className="mt-5 grid gap-3 text-sm text-[#475569] sm:grid-cols-2 lg:grid-cols-4"><p><span className="block text-xs text-[#94a3b8]">{t(reservation?.service_type === 'photo' ? '攝影方案' : '課程')}</span>{reservation?.course_template || reservation?.course_type || t('安排中')}</p><p><span className="block text-xs text-[#94a3b8]">{t(reservation?.service_type === 'photo' ? '攝影師' : '教練')}</span>{['由學校安排','指定教練待安排','不指定'].includes(coachChoice) ? t(coachChoice) : coachChoice}</p><p><span className="block text-xs text-[#94a3b8]">{t(reservation?.service_type === 'photo' ? '預約數量' : '人數')}</span>{t(reservation?.service_type === 'photo' ? '{count} 組' : '{count} 人',{count:reservation?.people || 0})}</p><p><span className="block text-xs text-[#94a3b8]">{t('天數')}</span>{dates.length ? t('{count} 天',{count:dates.length}) : t('待安排')}</p></div>
    <p className="mt-4 text-sm font-semibold text-[#1f2937]">{t(settledCancellation ? '原訂單金額' : fullyCancelled ? '取消前訂單金額' : '訂單金額')} NT$ {Number(displayAmount || 0).toLocaleString()}</p>
    {!fullyCancelled && (!order.cancellation||order.cancellation.status==='rejected') && <SettlementSummary settlement={order.settlement} />}
    {order.cancellation?.settlement?.currency==='JPY'&&order.cancellation.status!=='rejected'&&<p className="mt-3 text-sm leading-7 text-[#1e4e73]">{t('取消前日幣金額：{amount}；{stage}：{refund}。',{amount:t('日幣 JPY ¥ {amount}',{amount:Number(order.cancellation.settlement.original_amount).toLocaleString()}),stage:t(order.cancellation.status==='refunded'?'已記錄退款':order.cancellation.status==='approved'?'核准退款':'預估退款'),refund:order.cancellation.settlement.refund_amount==null?t('待核對實收款'):t('日幣 JPY ¥ {amount}',{amount:Number(order.cancellation.settlement.refund_amount).toLocaleString()})})}</p>}
    {showActions && <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-[#eef2f7] pt-4"><button type="button" onClick={() => onQuickRebook(order.id)} className="min-h-11 rounded-full border border-[#2b5f8f] px-4 py-2 text-sm font-semibold text-[#2b5f8f] hover:bg-[#eef4fa]">{t('再次預約')}</button><SiteLink to={`/membership/orders/${order.id}`} className="inline-flex min-h-11 items-center gap-1 rounded-full border border-[#2b5f8f] px-4 py-2 text-sm font-semibold text-[#2b5f8f]">{t('查看詳情')}<ChevronRight size={16} /></SiteLink>{canPay && <SiteLink to={`/payment?reservation_group=${order.id}`} className="inline-flex min-h-11 items-center rounded-full bg-[#2b5f8f] px-4 py-2 text-sm font-semibold text-white">{t('前往付款')}</SiteLink>}</div>}
  </article>;
}

function CancellationForm({ order, onDone }) {
  const { t } = useSiteLocale();
  const [preview, setPreview] = useState(null);
  const [reason, setReason] = useState('schedule');
  const [reasonNote, setReasonNote] = useState('');
  const [bank, setBank] = useState({ bank_name: '', account_number: '', account_holder: '',overseas_details:'' });
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const bankComplete = !preview?.requires_bank_account || ['bank_name','account_number','account_holder'].every((key) => bank[key].trim());

  const open = async () => {
    setBusy(true); setMessage('');
    try { setPreview(await requestJson(`/booking/snowland/api/member-cancellations/${order.id}/`)); }
    catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };
  const submit = async () => {
    setBusy(true); setMessage('');
    try {
      await requestJson(`/booking/snowland/api/member-cancellations/${order.id}/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason, reason_note: reasonNote, ...bank,...(preview.settlement?.currency==='JPY'?{currency:'JPY',expected_refund_amount:preview.settlement.refund_amount}:{}) }),
      });
      setMessage('取消申請已送出；審核通過前課程仍保留，核准後另行處理退款。');
      onDone();
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };

  if (!preview) return <div className="mt-5 border-t border-[#eef2f7] pt-4"><button type="button" disabled={busy} onClick={open} className="min-h-11 text-sm font-semibold text-red-600 hover:underline disabled:opacity-50">{busy ? t("載入退款資料…") : t("申請取消訂單")}</button>{message && <p role="alert" className="mt-2 text-sm text-red-600">{t(message)}</p>}</div>;
  return <div className="mt-5 rounded-sm border border-red-100 bg-red-50/50 p-5">
    <h3 className="font-semibold text-[#1f2937]">{t("確認取消與退款資料")}</h3>
    <p className="mt-2 text-sm text-[#64748b]">{preview.requires_cash_review?t("訂單有未結清補款或退款差額，需由 SnowLand 核對實收款後確認退款金額，這裡不會自動試算。"):t('預估退款 {amount}。',{amount:refundMoney(preview.refund_amount,preview.settlement,t)})}{t("送出後由 SnowLand 審核，尚未核准前不會直接取消課程。")}</p>
    {preview.settlement?.currency==='JPY'&&<p className="mt-2 text-sm leading-7 text-[#64748b]">{t('沿用原訂單匯率1 TWD＝{rate} JPY，台幣退款計價基準 {amount}。請提供可接收日幣的退款帳戶。',{rate:preview.settlement.rate,amount:refundMoney(preview.refund_amount,null,t)})}</p>}
    {preview.request_status === 'rejected' && <p role="status" className="mt-4 rounded-sm bg-white px-4 py-3 text-sm font-semibold text-[#9a3412]">{t("上次申請未通過；若仍需取消，可重新填寫並送出。")}</p>}
    {preview.request_status && preview.request_status !== 'rejected' ? <p className="mt-4 rounded-sm bg-white px-4 py-3 text-sm font-semibold text-[#2b5f8f]">{t('目前狀態：{status}',{status:t(cancellationLabels[preview.request_status] || preview.request_status)})}</p> : <div className="mt-4 grid gap-3 md:grid-cols-2">
      <label className="text-sm font-semibold">{t("取消原因")}<select value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] bg-white px-3 py-2"><option value="schedule">{t("行程變更")}</option><option value="health">{t("健康因素")}</option><option value="weather">{t("天候因素")}</option><option value="duplicate">{t("重複訂單")}</option><option value="other">{t("其他")}</option></select></label>
      <label className="text-sm font-semibold">{t("補充說明")}<input maxLength={1000} value={reasonNote} onChange={(event) => setReasonNote(event.target.value)} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] bg-white px-3 py-2" /></label>
      {preview.requires_bank_account && <><label className="text-sm font-semibold">{t("退款銀行")}<input required maxLength={100} value={bank.bank_name} onChange={(event) => setBank({ ...bank, bank_name: event.target.value })} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] bg-white px-3 py-2" /></label><label className="text-sm font-semibold">{t("退款帳號")}<input required maxLength={100} value={bank.account_number} onChange={(event) => setBank({ ...bank, account_number: event.target.value })} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] bg-white px-3 py-2" /></label><label className="text-sm font-semibold">{t("戶名")}<input required maxLength={100} value={bank.account_holder} onChange={(event) => setBank({ ...bank, account_holder: event.target.value })} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] bg-white px-3 py-2" /></label></>}
      {preview.settlement?.currency==='JPY'&&preview.requires_bank_account&&<label className="text-sm font-semibold">{t("海外退款資料（選填）")}<textarea maxLength={1000} value={bank.overseas_details} onChange={event=>setBank({...bank,overseas_details:event.target.value})} className="mt-1 min-h-24 w-full rounded-sm border border-[#cbd5e1] bg-white p-3"/></label>}
      <div className="flex items-end gap-2"><button type="button" disabled={busy} onClick={() => setPreview(null)} className="min-h-11 rounded-full border border-[#cbd5e1] bg-white px-4 py-2 text-sm font-semibold disabled:opacity-50">{t("返回")}</button><button type="button" disabled={busy || !bankComplete} onClick={submit} className="min-h-11 rounded-full bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy ? t("送出中…") : t("確認送出")}</button></div>
    </div>}
    {message && <p role="alert" className="mt-3 text-sm text-red-700">{t(message)}</p>}
  </div>;
}

function SharedClassSummary({ summary }) {
  const { t } = useSiteLocale();
  if (!summary) return null;
  return <section aria-label={t('同班報名與程度')} className="mt-4 rounded-sm border border-[#b6d6ec] bg-[#eef4fa] p-4 text-sm text-[#1e4e73]">
    <h4 className="font-semibold">{t('同班報名與程度')}</h4>
    {summary.status === 'cancelled' ? <p className="mt-2">{t('這個團體班已取消，請聯絡 SnowLand 確認安排。')}</p> : <>
      <p className="mt-2">{t(summary.status === 'ready' ? '已成班' : '湊班中')} · {t('已報名 {count} 人，滿 {minimum} 人成班',{count:summary.registered_students,minimum:summary.minimum_students})}</p>
      <p className="mt-2 font-semibold">{summary.other_students > 0 ? <>{t('同班其他學員：{count} 人',{count:summary.other_students})} · {summary.ability_level_label}</> : t('目前尚無其他學員報名')}</p>
      <p className="mt-2 text-xs leading-5 text-[#64748b]">{t('這是同程度團體班；只顯示人數與程度，不公開其他學員的姓名、聯絡資料或訂單。')}</p>
    </>}
  </section>;
}

function Orders({ data, onQuickRebook, onRefresh }) {
  const { t } = useSiteLocale();
  const location = useLocation();
  const id = Number(location.pathname.match(/\/orders\/(\d+)/)?.[1]);
  const selected = data.orders.find((order) => order.id === id);
  if (id && !selected) return <EmptyState title={t("找不到這筆訂單")} description={t("請確認連結，或使用建立這筆訂單的會員帳號登入。")} action={<SiteLink to="/membership/orders" className="mt-6 inline-flex rounded-full bg-[#2b5f8f] px-6 py-3 text-sm font-semibold text-white">{t("返回我的訂單")}</SiteLink>} />;
  if (selected) return <div><SiteLink to="/membership/orders" className="text-sm font-semibold text-[#2b5f8f]">{t("← 返回我的訂單")}</SiteLink><h2 className="mt-5 text-2xl font-semibold">{t("訂單詳情")}</h2><div className="mt-6 space-y-5"><OrderCard order={selected} onQuickRebook={onQuickRebook} showActions={false} showOrderNumber />
    <OrderAmendmentBalance orderId={selected.id} requestJson={requestJson} onRefresh={onRefresh} cancellationStatus={selected.cancellation?.status}/>
    {selected.received_settlement?.currency==='JPY'&&<p role="status" className="rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5 text-sm font-semibold text-[#1e4e73]">{t('SnowLand已核對原訂單收款：{amount}。修改後補退差額請看上方個別紀錄，實際入帳以銀行紀錄為準。',{amount:settlementAmount(selected.received_settlement,selected.received_settlement.base_amount)})}</p>}
    {selected.payment_hold_status && selected.payment_status === 'unpaid' && <p role="status" className="rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5 text-sm font-semibold text-[#1e4e73]">{t(paymentHoldMessages[selected.payment_hold_status] || selected.payment_hold_status)}</p>}
    {selected.payment_status === 'unpaid' && !selected.payment_hold_status && <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5"><p className="text-sm font-semibold text-[#1e4e73]">{t("這筆訂單尚未付款，可查看匯款資料與付款期限。")}</p><SiteLink to={`/payment?reservation_group=${selected.id}`} className="inline-flex rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white">{t("前往付款")}</SiteLink></div>}
    {selected.payment_status === 'pending' && <p className="rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5 text-sm font-semibold text-[#1e4e73]">{t("匯款資料已送出，等待 SnowLand 確認付款。")}</p>}
    {(selected.line_group_url || selected.line_group_qr_url) && <section className="rounded-sm border border-[#b6d6ec] bg-[#eef4fa] p-5"><h3 className="font-semibold text-[#1e4e73]">{t("上課群組")}</h3><p className="mt-2 text-sm leading-6 text-[#64748b]">{t("SnowLand 已準備好這筆課程的聯絡群組，課前資訊會在群組內確認。")}</p>{selected.line_group_url && <a href={selected.line_group_url} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex min-h-11 items-center rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white">{t("加入上課群組 ↗")}</a>}<ClassGroupQRImage url={selected.line_group_qr_url || ''} appearance="light" /></section>}
    {selected.cancellation?.status === 'requested' && <p role="status" className="rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5 text-sm font-semibold text-[#1e4e73]">{t("取消申請已送出，等待 SnowLand 審核；核准前課程仍保留。")}</p>}
    {selected.cancellation?.status === 'rejected' && <p role="status" className="rounded-sm border border-[#fed7aa] bg-[#fff7ed] p-5 text-sm font-semibold text-[#9a3412]">{t("上次取消申請未通過，課程仍保留；若仍需取消，可在下方重新提出。")}</p>}
    {selected.cancellation?.status === 'approved' && selected.payment_status === 'paid' && <p role="status" className="rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5 text-sm font-semibold text-[#1e4e73]">{t('訂單已取消，退款處理中。核准退款金額 {amount}。',{amount:refundMoney(selected.cancellation.refund_amount,selected.cancellation.settlement,t)})}</p>}
    {selected.cancellation?.status === 'refunded' && <p role="status" className="rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5 text-sm font-semibold text-[#1e4e73]">{t('訂單已退款 {amount}。',{amount:refundMoney(selected.cancellation.refund_amount,selected.cancellation.settlement,t)})}</p>}
    {selected.reservations.map((reservation) => <div key={reservation.id} className="rounded-sm border border-[#dbe3ec] bg-white p-5">
      <h3 className="font-semibold">{reservation.resort}｜{reservation.course_template || reservation.course_type}{reservation.status === 'cancelled' && t('（已取消）')}</h3>
      <p className="mt-2 text-sm text-[#64748b]">{reservation.service_type === 'photo' ? t("攝影師") : t("授課教練")}：{reservation.coach === '安排中' ? t("由學校安排") : reservation.coach}　{reservation.service_type === 'photo' ? t("預約數量") : t("學員")}：{t(reservation.service_type==='photo'?'{count} 組':'{count} 人',{count:reservation.people})}</p>
      <SharedClassSummary summary={reservation.shared_class_summary} />
      <div className="mt-4 space-y-2">{reservation.bookings.map((booking) => <p key={booking.id} className="rounded-sm bg-[#f8fafc] px-4 py-3 text-sm text-[#475569]">{formatDate(booking.date)}　{booking.start_time}–{booking.end_time}　{booking.course_name}</p>)}</div>
      {!['cancelled', 'deleted'].includes(reservation.status) && <SiteLink to={`/membership/pre-course-forms?reservation=${reservation.id}`} className="mt-4 inline-flex min-h-11 items-center rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white">{t("填寫學員與課前資料")}</SiteLink>}
    </div>)}
    {selected.payment_status === 'paid' && !['requested', 'approved', 'refunded'].includes(selected.cancellation?.status) && <CancellationForm order={selected} onDone={onRefresh} />}
    <div className="flex justify-end"><button type="button" onClick={() => onQuickRebook(selected.id)} className="rounded-full border border-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-[#2b5f8f]">{t("再次預約")}</button></div></div></div>;
  return <div><h2 className="text-2xl font-semibold">{t("我的訂單")}</h2><p className="mt-2 text-sm text-[#64748b]">{t("查看付款狀態、課程明細及快速再次預約。")}</p><div className="mt-7 space-y-4">{data.orders.length ? data.orders.map((order) => <OrderCard key={order.id} order={order} onQuickRebook={onQuickRebook} />) : <EmptyState title={t("目前沒有訂單")} action={<SiteLink to="/booking" className="mt-6 inline-flex rounded-full bg-[#2b5f8f] px-6 py-3 text-sm font-semibold text-white">{t("開始預約")}</SiteLink>} />}</div></div>;
}

function PreCourseForm({ form, waiverDocument, skillOptions, onSaved }) {
  const { t } = useSiteLocale();
  const [editing, setEditing] = useState(false);
  const savedDraft = () => ({ age_range: form.age_range, insurance_data: form.insurance_data || {}, snowboard_skills: form.snowboard_skills || [], ski_skills: form.ski_skills || [], waiver_signature: form.waiver_resign_required ? '' : form.waiver_signature || '', waiver_agreed: form.waiver_completed, media_consent: form.media_consent || '' });
  const [draft, setDraft] = useState(savedDraft);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const updateInsurance = (key, value) => setDraft(current => ({ ...current, insurance_data: { ...current.insurance_data, [key]: value }, ...(['birth_date', 'waiver_signer_role'].includes(key) ? { waiver_agreed: false, waiver_signature: '' } : {}) }));
  const birthStatus = birthDateStatus(draft.insurance_data.birth_date || '', waiverDocument.reference_date || '');
  const guardianAgeLimit = waiverDocument.guardian_age_limit || 18;
  const requiresGuardian = birthStatus.age !== null && birthStatus.age < guardianAgeLimit;
  const guardianSigning = requiresGuardian || draft.insurance_data.waiver_signer_role === 'guardian';
  const missingGuardianDetails = guardianSigning && (!draft.insurance_data.guardian_name?.trim() || !draft.insurance_data.guardian_relationship?.trim());
  const toggleSkill = (field, value) => setDraft(current => {
    const skills = current[field];
    const selected = skills.includes(value);
    return { ...current, [field]: selected ? skills.filter(skill => skill !== value) : value === '無經驗' ? [value] : [...skills.filter(skill => skill !== '無經驗'), value] };
  });
  const save = async () => {
    setBusy(true); setMessage('');
    try {
      const result = await requestJson('/booking/snowland/api/member-center/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'update_pre_course_form', member_id: form.id, age_range: draft.age_range, snowboard_skills: draft.snowboard_skills, ski_skills: draft.ski_skills, insurance_data: { ...draft.insurance_data, waiver_signer_role: guardianSigning ? 'guardian' : 'self' }, waiver_agreed: draft.waiver_agreed, waiver_signature: draft.waiver_signature, waiver_document_version: waiverDocument.version, waiver_course_revision: form.waiver_course_revision, media_consent: draft.media_consent }) });
      setMessage(result.message); setEditing(false); await onSaved();
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };
  return <article className="rounded-sm border border-[#dbe3ec] bg-white p-5"><div className="flex flex-wrap justify-between gap-3"><div><h3 className="font-semibold">{form.insurance_data?.full_name || t('學員 {number}（待填寫姓名）',{number:form.student_number || ''})}</h3><p className="mt-1 break-all text-xs text-[#94a3b8]">{form.order_number}｜{form.resort}</p></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${form.insurance_completed && form.waiver_completed ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{form.insurance_completed && form.waiver_completed ? t("資料完成") : t("尚有資料未完成")}</span></div>
    {form.waiver_resign_required && <p role="status" className="mt-4 rounded-sm border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{t("課程日期或模板已修改，請重新閱讀並簽署聲明書。原簽署已留底；如已投保，將由行政重新核對。")}</p>}
    {!editing ? <>
      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3"><p>{t('年齡：{age}',{age:ageLabel(form.age_range,t)})}</p><p>{t('保險資料：{status}',{status:t(form.insurance_completed?'已填寫':'待補齊')})}</p><p>{t('聲明書：{status}',{status:t(form.waiver_completed?'完成':'需補齊或重新簽署')})}</p></div>
      <p className="mt-3 text-sm text-[#64748b]">{t('投保作業：{status}。填妥資料不代表已完成投保，作業狀態由行政核對及登錄。',{status:t(({pending:'尚未投保',checking:'行政核對中',processing:'行政處理中',insured:'已投保完成'})[form.insurance_processing_status] || '待行政確認')})}</p>
      <p className="mt-3 text-sm text-[#64748b]">{t('程度：{level}',{level:[...form.snowboard_skills,...form.ski_skills].map(value => t(value)).join('、') || t('尚未填寫')})}</p>
      <button type="button" onClick={() => { setDraft(savedDraft()); setMessage(''); setEditing(true); }} className="mt-4 min-h-11 rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white">{t("填寫／修改資料")}</button>
    </> : <div className="mt-5 space-y-5">
      <p className="text-sm text-[#64748b]">{t("先填這位學員的姓名與年齡即可儲存；保險資料與聲明書可稍後補齊。")}</p>
      <div className="grid gap-4 md:grid-cols-2">
        <label className="text-sm font-semibold">{t("年齡區間")}<select value={draft.age_range} onChange={(event) => setDraft({ ...draft, age_range: event.target.value })} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] px-3 py-2"><option value="">{t("請選擇年齡區間")}</option>{ageOptions.map((option) => <option key={option} value={option}>{ageLabel(option,t)}</option>)}</select></label>
        {[['full_name', '學員姓名（保險用）'], ['birth_date', '出生日期'], ['id_number', '身分證／護照號碼'], ['phone', '聯絡電話'], ['emergency_contact', '緊急聯絡人'], ['emergency_phone', '緊急聯絡電話']].map(([key, label]) => <label key={key} className="text-sm font-semibold">{t(label)}<input type={key === 'birth_date' ? 'date' : 'text'} max={key === 'birth_date' ? waiverDocument.reference_date : undefined} value={draft.insurance_data[key] || ''} onChange={(event) => updateInsurance(key, event.target.value)} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] px-3 py-2" /></label>)}
      </div>
      {birthStatus.error && <p role="alert" className="text-sm text-red-700">{t(birthStatus.error)}</p>}
      {requiresGuardian && <p role="status" className="rounded-sm bg-[#eef4fa] p-3 text-sm text-[#2b5f8f]">{t('依出生日期，這位學員目前未滿 {age} 歲，請由法定代理人簽署並填寫下方資料；也可以先儲存草稿。',{age:guardianAgeLimit})}</p>}
      <details className="rounded-sm border border-[#dbe3ec] p-4">
        <summary className="min-h-11 cursor-pointer text-sm font-semibold">{t("過往滑雪經驗（選填）")}</summary>
        <div className="mt-3 grid gap-4 md:grid-cols-2">{[['snowboard_skills', '單板經驗'], ['ski_skills', '雙板經驗']].map(([field, label]) => <fieldset key={field}><legend className="text-sm font-semibold">{t(label)}</legend><div className="mt-2 max-h-64 overflow-y-auto">{(skillOptions?.[field] || []).map(([value, text]) => <label key={value} className="flex min-h-11 items-center gap-2 py-2 text-sm"><input type="checkbox" checked={draft[field].includes(value)} onChange={() => toggleSkill(field, value)} />{t(text)}</label>)}</div></fieldset>)}</div>
      </details>
      <div className="rounded-sm border border-[#dbe3ec] bg-[#f8fafc] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">{waiverDocument.title}</p><span className="rounded-full bg-white px-3 py-1 text-xs text-[#64748b]">{t('版本 {version}',{version:waiverDocument.version})}{waiverDocument.is_draft ? t("｜法務確認中") : ''}</span></div>
        <div className="mt-3 max-h-72 overflow-y-auto break-words rounded-sm border border-[#dbe3ec] bg-white p-4 text-sm leading-7 text-[#475569] whitespace-pre-wrap">{waiverDocument.body.replace(/\*\*/g, '').replace(/^\s*[#>]+\s*/gm, '')}</div>
        <a href={waiverDocument.source_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex text-sm font-semibold text-[#2b5f8f] hover:underline">{t("開啟客戶提供的原始文件")}</a>
        <fieldset className="mt-4"><legend className="text-sm font-semibold">{t("由誰簽署聲明書？")}</legend><div className="mt-2 flex flex-wrap gap-4 text-sm"><label className={`flex min-h-11 items-center gap-2 ${requiresGuardian ? 'text-[#94a3b8]' : ''}`}><input type="radio" name={`signer-role-${form.id}`} disabled={requiresGuardian} checked={!guardianSigning} onChange={() => updateInsurance('waiver_signer_role', 'self')} />{t("學員本人簽署")}</label><label className="flex min-h-11 items-center gap-2"><input type="radio" name={`signer-role-${form.id}`} checked={guardianSigning} onChange={() => updateInsurance('waiver_signer_role', 'guardian')} />{t("法定代理人代簽")}</label></div><p className="mt-2 text-xs text-[#64748b]">{t("簽署前需填寫出生日期。更改出生日期或簽署身分後，需重新確認並簽名。")}</p></fieldset>
        {guardianSigning && <div className="mt-3 grid gap-4 rounded-sm border border-[#dbe3ec] bg-white p-4 sm:grid-cols-2"><p className="text-sm leading-6 text-[#64748b] sm:col-span-2">{t("請填實際代簽人的資料；代簽人不需要另外建立會員帳號。")}</p><label className="text-sm font-semibold">{t("法定代理人姓名")}<input value={draft.insurance_data.guardian_name || ''} onChange={event => updateInsurance('guardian_name', event.target.value)} maxLength={120} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] px-3 py-2" /></label><label className="text-sm font-semibold">{t("與學員的關係")}<input value={draft.insurance_data.guardian_relationship || ''} onChange={event => updateInsurance('guardian_relationship', event.target.value)} maxLength={120} placeholder={t("例如：父親、母親、監護人")} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] px-3 py-2" /></label></div>}
        <fieldset className="mt-4"><legend className="text-sm font-semibold">{t("宣傳影像授權（不影響上課權益）")}</legend><div className="mt-2 flex flex-wrap gap-4 text-sm"><label className="flex min-h-11 items-center gap-2"><input type="radio" name={`media-consent-${form.id}`} checked={draft.media_consent === 'agree'} onChange={() => setDraft({ ...draft, media_consent: 'agree' })} />{t("同意公開宣傳")}</label><label className="flex min-h-11 items-center gap-2"><input type="radio" name={`media-consent-${form.id}`} checked={draft.media_consent === 'decline'} onChange={() => setDraft({ ...draft, media_consent: 'decline' })} />{t("不同意公開宣傳")}</label></div></fieldset>
        <label className="mt-4 flex items-start gap-2 text-sm"><input type="checkbox" checked={draft.waiver_agreed} onChange={(event) => setDraft({ ...draft, waiver_agreed: event.target.checked })} className="mt-1" />{t("本人已完整閱讀並同意此版本聲明書")}</label>
        <label className="mt-3 block text-sm font-semibold">{t("立書人（本人或法定代理人）簽名")}<input value={draft.waiver_signature} onChange={(event) => setDraft({ ...draft, waiver_signature: event.target.value })} className="mt-1 min-h-11 w-full rounded-sm border border-[#cbd5e1] bg-white px-3 py-2" /></label>
        {draft.waiver_agreed && missingGuardianDetails && <p role="alert" className="mt-2 text-sm text-amber-800">{t("請補齊法定代理人姓名及與學員的關係後再儲存簽署。")}</p>}
      </div>
      {(!draft.age_range || !draft.insurance_data.full_name?.trim()) && <p className="text-sm text-amber-800">{t("請先填寫學員姓名與年齡區間。")}</p>}
      <div className="flex gap-2"><button type="button" disabled={busy} onClick={() => setEditing(false)} className="min-h-11 rounded-full border border-[#cbd5e1] px-5 py-2.5 text-sm font-semibold disabled:opacity-50">{t("取消")}</button><button type="button" disabled={busy || Boolean(birthStatus.error) || !draft.age_range || !draft.insurance_data.full_name?.trim() || (draft.waiver_agreed && (birthStatus.age === null || !draft.waiver_signature.trim() || !draft.media_consent || missingGuardianDetails))} onClick={save} className="min-h-11 rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy ? t("儲存中…") : t("儲存課前資料")}</button></div>
    </div>}
    {message && <p role="status" className="mt-3 text-sm text-[#2b5f8f]">{t(message)}</p>}
    {message.includes('課程已變更') && <button type="button" disabled={busy} onClick={() => { setEditing(false); onSaved(); }} className="mt-3 min-h-11 rounded-full border border-[#cbd5e1] px-5 py-2.5 text-sm font-semibold">{t("重新載入（放棄未儲存內容）")}</button>}
  </article>;
}

function MissingStudents({ order, reservation, onSaved }) {
  const { t } = useSiteLocale();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const prepare = async () => {
    setBusy(true); setError('');
    try {
      await requestJson('/booking/snowland/api/member-center/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'prepare_pre_course_forms', reservation_id: reservation.id }) });
      await onSaved();
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  };
  return <article className="rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5"><p className="break-all text-xs text-[#64748b]">{order.order_number}</p><h3 className="mt-2 font-semibold">{reservation.resort}｜{reservation.course_template || reservation.course_type}</h3><p className="mt-3 text-sm leading-7 text-[#475569]">{t('這門課訂了 {people} 人，目前還有 {missing} 位尚未建立學員欄位。按下方按鈕後，逐位填寫姓名與課前資料即可，不會增加訂課人數或費用。',{people:reservation.people,missing:reservation.missing_students})}</p><button type="button" disabled={busy} onClick={prepare} className="mt-4 min-h-11 rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy ? t("建立中…") : t("建立學員資料")}</button>{error && <p role="alert" className="mt-3 text-sm text-red-700">{t(error)}</p>}</article>;
}

function ParticipantRoster({ order, reservation, onSaved }) {
  const { t, locale } = useSiteLocale();
  const basePath = useContext(SiteBasePathContext);
  const [busy, setBusy] = useState(null);
  const [links, setLinks] = useState({});
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const act = async (memberId, revoke = false) => {
    if (busy !== null) return;
    setBusy(memberId); setError(''); setMessage('');
    try {
      const result = await requestJson('/booking/snowland/api/member-center/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: revoke ? 'revoke_participant_invitation' : 'invite_participant', member_id: memberId }),
      });
      setLinks(previous => ({ ...previous, [memberId]: revoke ? null : {
        url: `${window.location.origin}${basePath}/membership?invite=${result.token}`,
        expires: result.expires_at,
      } }));
      setMessage(result.message);
      await onSaved();
    } catch (failure) { setError(failure.message); }
    finally { setBusy(null); }
  };
  const copy = async (url) => {
    setError(''); setMessage('');
    try { await navigator.clipboard.writeText(url); setMessage('已複製，請只傳給對應的學員或家長。'); }
    catch { setMessage('瀏覽器無法自動複製，請選取下方完整網址後複製。'); }
  };
  return <article className="rounded-sm border border-[#dbe3ec] bg-white p-5 md:p-6">
    <h3 className="font-semibold">{t("同行學員綁定")}</h3>
    <p className="mt-2 text-sm text-[#64748b]">{order.order_number}｜{reservation.resort}</p>
    <p className="mt-3 text-sm leading-7 text-[#64748b]">{t("未綁定的學員可由您代填，也可邀請本人或家長登入後綁定。綁定後，個人課前資料與學習紀錄只由該帳號管理，您不再看到他的個資。")}</p>
    {order.payment_status !== 'paid' && <p className="mt-3 text-sm text-[#64748b]">{t("付款完成後開放邀請；目前仍可先代填課前資料。")}</p>}
    <ul className="mt-4 divide-y divide-[#e2e8f0]">{(reservation.participants || []).map(participant => <li key={participant.id} className="py-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-semibold">{t("學員")}{participant.student_number}</p><p className="mt-1 text-sm text-[#64748b]">{participant.binding_status === 'bound' ? t("已綁定，由本人或家長管理") : participant.binding_status === 'pending' ? t("已產生邀請，等待確認") : t("尚未綁定，可由您代填")}</p></div>
        {participant.can_invite && <div className="flex flex-wrap gap-2"><button type="button" disabled={busy !== null} onClick={() => act(participant.id)} className="min-h-11 rounded-full border border-[#2b5f8f] px-4 py-2 text-sm font-semibold text-[#2b5f8f] disabled:opacity-40">{busy === participant.id ? t("處理中…") : participant.binding_status === 'pending' ? t("重新產生邀請") : t("產生邀請連結")}</button>{participant.binding_status === 'pending' && <button type="button" disabled={busy !== null} onClick={() => act(participant.id, true)} className="min-h-11 px-3 py-2 text-sm font-semibold text-[#64748b] disabled:opacity-40">{t("撤銷邀請")}</button>}</div>}
      </div>
      {links[participant.id] && participant.binding_status !== 'bound' && <div className="mt-3 rounded-sm bg-[#f8fafc] p-3"><label className="text-sm font-semibold">{t('學員 {number} 的邀請網址',{number:participant.student_number})}<input readOnly onFocus={event => event.target.select()} value={links[participant.id].url} className="mt-2 min-h-11 w-full rounded-sm border border-[#cbd5e1] bg-white px-3 py-2 text-sm" /></label><p className="mt-2 text-xs leading-6 text-[#64748b]">{t('有效至 {date}。重新產生會讓舊連結失效，請勿公開分享。',{date:new Date(links[participant.id].expires).toLocaleDateString(locale==='zh-Hant'?'zh-TW':locale)})}</p><button type="button" onClick={() => copy(links[participant.id].url)} className="mt-2 min-h-11 rounded-full bg-[#2b5f8f] px-4 py-2 text-sm font-semibold text-white">{t("複製邀請連結")}</button></div>}
    </li>)}</ul>
    {error && <p role="alert" className="mt-3 rounded-sm bg-red-50 p-3 text-sm text-red-700">{t(error)}</p>}
    {message && <p role="status" className="mt-3 rounded-sm bg-[#eef4fa] p-3 text-sm text-[#2b5f8f]">{t(message)}</p>}
  </article>;
}

function ParticipantInvitation({ token, onAccepted }) {
  const { t } = useSiteLocale();
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [role, setRole] = useState('self');
  const [confirmed, setConfirmed] = useState(false);
  const load = useCallback(async () => {
    setLoading(true); setError(''); setPreview(null);
    try {
      if (!/^[0-9a-f-]{36}$/i.test(token)) throw new Error('邀請連結格式不正確，請向訂購人索取完整連結。');
      setPreview(await requestJson(`/booking/snowland/api/participant-invitations/${token}/`));
    } catch (failure) { setError(failure.message); }
    finally { setLoading(false); }
  }, [token]);
  useEffect(() => { setConfirmed(false); load(); }, [load]);
  const accept = async () => {
    if (busy || !confirmed) return;
    setBusy(true); setError('');
    try {
      const result = await requestJson(`/booking/snowland/api/participant-invitations/${token}/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirmed: true, role }) });
      await onAccepted(result.reservation_id, result.message);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  };
  return <section className="mb-7 rounded-sm border border-[#dbe3ec] bg-white p-5 md:p-6" aria-label={t("同行學員邀請")}>
    <h2 className="text-xl font-semibold">{t("確認同行學員綁定")}</h2>
    {loading ? <p role="status" className="mt-4 text-sm text-[#64748b]">{t("正在檢查邀請連結…")}</p> : <>
      {preview && <><p className="mt-3 text-sm leading-7 text-[#64748b]">{preview.resort}｜{preview.dates.map(formatDate).join('、') || t('日期安排中')}｜{t('學員 {number}',{number:preview.student_number})}</p>
        {preview.accepted ? <><p className="mt-4 text-sm text-[#2b5f8f]">{t("這位學員已綁定您的帳號。")}</p><button type="button" onClick={() => onAccepted(preview.reservation_id, '')} className="mt-4 min-h-11 rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white">{t("前往課前資料")}</button></> : <>
          <p className="mt-3 text-sm leading-7 text-[#64748b]">{t("請確認目前顯示的是您要使用的會員帳號。綁定會保留訂購人已填的資料，但不代表您已簽署聲明書；請到課前資料檢查。")}</p>
          <fieldset className="mt-4"><legend className="text-sm font-semibold">{t("這位學員是誰？")}</legend><div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">{[['self', '我本人'], ['guardian', '我的子女／受監護人']].map(([value, label]) => <label key={value} className="flex min-h-11 items-center gap-2 text-sm"><input type="radio" name="invitation-role" value={value} checked={role === value} onChange={() => { setRole(value); setError(''); }} />{t(label)}</label>)}</div></fieldset>
          <label className="mt-3 flex items-start gap-3 text-sm leading-7"><input type="checkbox" className="mt-1.5 h-4 w-4 shrink-0" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{t("我確認這是本人或子女的學員名額，同意綁定到目前帳號。")}</label>
          <button type="button" disabled={!confirmed || busy} onClick={accept} className="mt-4 min-h-11 rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{busy ? t("綁定中…") : t("確認綁定")}</button>
        </>}
      </>}
      {error && <div role="alert" className="mt-4 rounded-sm bg-red-50 p-3 text-sm text-red-700">{t(error)}</div>}
      {!preview && <button type="button" onClick={load} className="mt-3 min-h-11 text-sm font-semibold text-[#2b5f8f]">{t("重新檢查邀請")}</button>}
    </>}
  </section>;
}

function Forms({ forms, orders, waiverDocument, skillOptions, onSaved }) {
  const { t } = useSiteLocale();
  const reservationId = Number(new URLSearchParams(useLocation().search).get('reservation'));
  const visibleForms = reservationId ? forms.filter(form => form.reservation_id === reservationId) : forms;
  const missing = orders.flatMap(order => order.reservations.filter(reservation => reservation.missing_students > 0 && !['cancelled', 'deleted'].includes(reservation.status) && (!reservationId || reservation.id === reservationId)).map(reservation => ({ order, reservation })));
  const rosterCourses = orders.flatMap(order => order.reservations.filter(reservation => reservation.participants?.length > 0 && !['cancelled', 'deleted'].includes(reservation.status) && (!reservationId || reservation.id === reservationId)).map(reservation => ({ order, reservation })));
  return <div><h2 className="text-2xl font-semibold">{t("學員與課前資料")}</h2><p className="mt-2 text-sm leading-7 text-[#64748b]">{t("依訂課人數逐位填寫年齡、保險與聲明書。您可以代填尚未綁定的同行學員；已綁定者請由本人或家長登入填寫。")}</p>{reservationId > 0 && <SiteLink to="/membership/pre-course-forms" className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-[#2b5f8f]">{t("查看全部課程的學員")}</SiteLink>}<div className="mt-7 space-y-4">{rosterCourses.map(({order, reservation}) => <ParticipantRoster key={`roster-${reservation.id}`} order={order} reservation={reservation} onSaved={onSaved} />)}{missing.map(({order, reservation}) => <MissingStudents key={reservation.id} order={order} reservation={reservation} onSaved={onSaved} />)}{visibleForms.map(form => <PreCourseForm key={form.id} form={form} waiverDocument={waiverDocument} skillOptions={skillOptions} onSaved={onSaved} />)}{!missing.length && !visibleForms.length && !rosterCourses.length && <EmptyState title={t("目前沒有待填寫的課前資料")} description={t("完成訂課或確認同行學員邀請後，學員資料會出現在這裡。")} action={<SiteLink to="/membership/orders" className="mt-5 inline-flex min-h-11 items-center font-semibold text-[#2b5f8f]">{t("查看我的訂單")}</SiteLink>} />}</div></div>;
}

function SatisfactionForm({ record, onSaved }) {
  const { t } = useSiteLocale();
  const existing = record.self_assessment?.satisfaction_rating;
  const [rating, setRating] = useState(existing || 0);
  const [feedback, setFeedback] = useState(record.self_assessment?.satisfaction_feedback || '');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (busy) return;
    setBusy(true);
    try { const result = await requestJson('/booking/snowland/api/member-center/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'submit_satisfaction', evaluation_id: record.id, rating, feedback }) }); setMessage(result.message); await onSaved(); }
    catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };
  return <div className="mt-5 border-t border-[#eef2f7] pt-5"><p className="text-sm font-semibold">{t("課後滿意度")}</p><div className="mt-3 flex gap-2" aria-label={t("課程評分")}>{[1, 2, 3, 4, 5].map((value) => <button type="button" key={value} onClick={() => { setRating(value); setMessage(''); }} aria-label={t('{score} 分',{score:value})} aria-pressed={value===rating} className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2b5f8f] ${value <= rating ? 'text-amber-500' : 'text-[#cbd5e1]'}`}><Star size={25} fill="currentColor" /></button>)}</div><textarea value={feedback} onChange={(event) => { setFeedback(event.target.value); setMessage(''); }} placeholder={t("可填寫對課程或教練的回饋")} className="mt-3 min-h-24 w-full rounded-sm border border-[#cbd5e1] px-3 py-2 text-sm" /><button type="button" disabled={!rating || busy} onClick={submit} className="mt-3 rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{busy ? t("儲存中…") : existing ? t("更新評價") : t("送出評價")}</button>{message && <p role="status" className="mt-2 text-sm text-[#2b5f8f]">{t(message)}</p>}</div>;
}

function Journey({ records, onSaved }) {
  const { t } = useSiteLocale();
  return <div><h2 className="text-2xl font-semibold">{t("課程評量與學習紀錄")}</h2><p className="mt-2 text-sm text-[#64748b]">{t("查看程度變化、教練建議、課程照片／影片，並填寫課後評價。")}</p><div className="mt-7 space-y-5">{records.length ? records.map((record) => <article key={record.id} className="overflow-hidden rounded-sm border border-[#dbe3ec] bg-white">{record.media.length > 0 && <div className={`grid overflow-hidden bg-[#e2e8f0] ${record.media.length === 1 ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2"}`}>{record.media.map((media) => media.type === 'video' ? <video key={media.id} controls preload="metadata" className="aspect-video w-full object-contain" src={media.url} /> : <a key={media.id} href={media.url} target="_blank" rel="noreferrer" aria-label={t("開啟課程照片原圖")}><img loading="lazy" src={media.url} alt={media.caption || t('{resort} 課程照片',{resort:record.resort})} className="aspect-video w-full object-contain" /></a>)}</div>}<div className="p-5 md:p-6"><p className="text-xs font-semibold tracking-[0.18em] text-[#94a3b8]">{formatDate(record.date)}｜{record.order_number}</p><h3 className="mt-2 text-lg font-semibold">{record.resort}｜{record.course_name}</h3><p className="mt-3 text-sm text-[#64748b]">{t('學員：{name}',{name:record.member_name})}　{t('教練：{name}',{name:record.coach})}</p>{record.trail_names?.length > 0 && <p className="mt-3 text-sm text-[#64748b]">{t('本次雪道：{trails}',{trails:record.trail_names.join('、')})}</p>}<div className="mt-5 rounded-sm bg-[#f8fafc] p-4"><p className="text-xs font-semibold text-[#2b5f8f]">{t("教練建議")}</p><p className="mt-2 whitespace-pre-line text-sm leading-7 text-[#475569]">{record.coach_notes || t('教練尚未填寫建議')}</p></div>{Object.keys(record.learning_progress || {}).length > 0 && <div className="mt-4 flex flex-wrap gap-2">{Object.entries(record.learning_progress).map(([key, value]) => <span key={key} className="rounded-full bg-[#eef4fa] px-3 py-1 text-xs text-[#2b5f8f]">{formatLearningProgressEntry(key, value,t)}</span>)}</div>}<SatisfactionForm record={record} onSaved={onSaved} /></div></article>) : <EmptyState title={t("尚無課程評量")} description={t("教練完成課後評量後，紀錄與您有權查看的課程附件會出現在這裡。")} />}</div></div>;
}

function Overview({ data }) {
  const {t}=useSiteLocale();
  const ownedUpcoming = data.orders.flatMap((order) => order.reservations.flatMap((reservation) => reservation.bookings.map((booking) => ({ order, reservation, booking })))).filter((item) =>
    new Date(`${item.booking.date}T23:59:59`) >= new Date()
    && item.order.payment_hold_status !== 'all_cancelled'
    && !['refunded', 'expired'].includes(item.order.payment_status)
    && !['cancelled', 'deleted'].includes(item.reservation.status)
  ).sort((a, b) => a.booking.date.localeCompare(b.booking.date))[0];
  const attendingUpcoming = (data.participant_courses || []).filter(course => course.payment_status === 'paid' && !['cancelled', 'deleted'].includes(course.status)).flatMap(course => course.bookings.map(booking => ({
    order: { is_participant: true, payment_status: course.payment_status },
    reservation: { id: course.id, resort: course.resort, people: course.student_count }, booking,
  }))).filter(item => new Date(`${item.booking.date}T23:59:59`) >= new Date()).sort((a, b) => a.booking.date.localeCompare(b.booking.date))[0];
  const upcoming = [ownedUpcoming, attendingUpcoming].filter(Boolean).sort((a, b) => a.booking.date.localeCompare(b.booking.date))[0];
  const upcomingStatus = upcoming?.order.payment_hold_status
    ? paymentLabels[upcoming.order.payment_hold_status]
    : upcoming?.order.payment_status === 'paid' ? '即將到來' : paymentLabels[upcoming?.order.payment_status] || '預約處理中';
  return <div>
<p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#94a3b8]">My Journey</p>
<h2 className="mt-3 text-2xl font-semibold md:text-3xl">{t('會員總覽')}</h2>
<div className="mt-7 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
<div className="rounded-sm bg-gradient-to-br from-[#8eb6d9] to-[#d8d7df] p-6 text-white md:p-8">
<p className="text-sm">Hi, {data.member.name}!</p>
<h3 className="mt-5 text-2xl font-semibold">{t('準備好下一趟滑雪旅程了嗎？')}</h3>
<p className="mt-3 text-sm leading-7 text-white/85">{t('快速開始下一次課程預約。')}</p>
<SiteLink to="/booking" className="mt-6 inline-flex rounded-full bg-white/90 px-5 py-2.5 text-sm font-semibold text-[#2b5f8f]">{t('開始預約')}</SiteLink>
</div>
<div className="rounded-sm border border-[#dbe3ec] bg-white p-6">{upcoming ? <>
<span className="rounded-full bg-orange-50 px-3 py-1 text-xs font-semibold text-orange-700">{t(upcomingStatus)}</span>
<p className="mt-5 text-xl font-semibold">{formatDate(upcoming.booking.date)}</p>
<p className="mt-2 font-semibold">{upcoming.reservation.resort}</p>
<p className="mt-2 text-sm text-[#64748b]">{upcoming.booking.start_time}–{upcoming.booking.end_time}｜{t('{count} 位學員',{count:upcoming.reservation.people})}</p>
<SiteLink to={upcoming.order.is_participant ? `/membership/pre-course-forms?reservation=${upcoming.reservation.id}` : `/membership/orders/${upcoming.order.id}`} className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-[#2b5f8f]">{t(upcoming.order.is_participant ? '查看課前資料' : '查看預約詳情')}<ChevronRight size={16} />
</SiteLink>
</> : <>
<CalendarDays className="text-[#94a3b8]" />
<p className="mt-5 font-semibold">{t('目前沒有即將到來的課程')}</p>
</>}</div>
</div>{data.learning_records[0] && <div className="mt-8">
<div className="flex items-center justify-between">
<h3 className="text-xl font-semibold">{t('我的滑雪學習紀錄')}</h3>
<SiteLink to="/membership/my-skiing-journey" className="text-sm font-semibold text-[#2b5f8f]">{t('查看全部')}</SiteLink>
</div>
<div className="mt-4 rounded-sm border border-[#dbe3ec] bg-white p-5">
<p className="text-sm font-semibold">{formatDate(data.learning_records[0].date)}｜{data.learning_records[0].resort}</p>
<p className="mt-3 line-clamp-3 text-sm leading-7 text-[#64748b]">{data.learning_records[0].coach_notes || t('教練評量整理中')}</p>
</div>
</div>}<div className="mt-8">
<h3 className="text-xl font-semibold">{t('我的 SnowLand 滑雪旅程')}</h3>
<div className="mt-4 grid gap-4 sm:grid-cols-3">{[[data.journey.seasons, '一起滑過的雪季'], [data.journey.completed_course_days, '完成課程天數'], [data.journey.resorts, '去過的雪場']].map(([value, label]) => <div key={t(label)} className="rounded-sm border border-[#dbe3ec] bg-white p-6 text-center">
<p className="text-3xl font-semibold text-[#2b5f8f]">{value}</p>
<p className="mt-2 text-sm text-[#64748b]">{t(label)}</p>
</div>)}</div>
</div>
</div>;
}

function ParticipantCourses({ courses }) {
  const { t } = useSiteLocale();
  if (!courses?.length) return null;
  return <section className="space-y-5"><div><h2 className="text-2xl font-semibold">{t("我參加的課程")}</h2><p className="mt-2 text-sm leading-7 text-[#64748b]">{t("已綁定的本人或子女課程。訂單付款與取消由原訂購人管理。")}</p></div>
    {courses.map(course => <article key={course.id} className="rounded-sm border border-[#dbe3ec] bg-white p-5 md:p-6">
      <p className="text-xs font-semibold text-[#64748b]">{course.status === 'cancelled' ? t("課程已取消") : course.payment_status === 'refunded' ? t("已退款") : t("已綁定課程")}</p>
      <h3 className="mt-2 text-lg font-semibold">{course.resort}｜{course.course_name}</h3>
      <p className="mt-3 text-sm leading-7 text-[#64748b]">{t('學員：{name}',{name:course.student_names.join('、')})}<br />{t('教練：{name}',{name:course.coach})}</p>
      <ul className="mt-3 space-y-2 text-sm text-[#475569]">{course.bookings.map(booking => <li key={booking.id}>{formatDate(booking.date)}｜{booking.start_time}–{booking.end_time}</li>)}</ul>
      <div className="mt-4 flex flex-wrap gap-3"><SiteLink to={`/membership/pre-course-forms?reservation=${course.id}`} className="inline-flex min-h-11 items-center rounded-full bg-[#2b5f8f] px-5 py-2 text-sm font-semibold text-white">{t("查看課前資料")}</SiteLink>{course.line_group_url && <a href={course.line_group_url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center rounded-full border border-[#2b5f8f] px-5 py-2 text-sm font-semibold text-[#2b5f8f]">{t("加入上課群組 ↗")}</a>}</div>
      <ClassGroupQRImage url={course.line_group_qr_url || ''} appearance="light" />
    </article>)}
  </section>;
}

function MemberNotifications() {
  const { t, locale } = useSiteLocale();
  const headingRef = useRef(null);
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true); setData(null); setError(''); setErrorCode(null); setMessage('');
    requestJson(`/booking/snowland/api/member-notifications/?page=${page}`)
      .then(result => { if (alive) setData(result); })
      .catch(failure => { if (alive) { setErrorCode(failure.status); setError(failure.status === 404 ? '這頁通知已不存在，請返回第一頁。' : failure.message); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [page, reload]);
  useEffect(() => {
    if (!loading && data && headingRef.current) {
      window.scrollTo({ top: Math.max(0, window.scrollY+headingRef.current.getBoundingClientRect().top-96), behavior: 'auto' });
    }
  }, [loading, data?.page]);
  const markRead = async (id) => {
    if (busyId !== null) return;
    setBusyId(id); setMessage(''); setError(''); setErrorCode(null);
    try {
      const result = await requestJson(`/booking/snowland/api/member-notifications/${id}/read/`, { method: 'POST' });
      setData(previous => ({ ...previous, unread_count: result.unread_count, results: previous.results.map(row => row.id === id ? { ...row, read_at: result.read_at } : row) }));
      setMessage(result.message);
    } catch (failure) { setError(failure.message); setErrorCode(failure.status); if ([401, 404].includes(failure.status)) setData(null); }
    finally { setBusyId(null); }
  };
  return <section><h2 ref={headingRef} className="text-2xl font-semibold">{t("通知中心")}</h2><p className="mt-2 text-sm leading-7 text-[#64748b]">{t("這裡顯示本帳號的站內通知，以及 Email 成功寄出後同步保存的內容。更新前的舊郵件不會補入；LINE 推播請到 LINE 查看。")}</p>
    {data && !loading && <p className="mt-3 text-sm font-semibold text-[#2b5f8f]">{t('{unread} 則未讀・共 {count} 則通知',{unread:data.unread_count,count:data.count})}</p>}
    {message && <p role="status" className="mt-4 rounded-sm bg-[#eef4fa] p-3 text-sm text-[#2b5f8f]">{t(message)}</p>}
    {error && <div role="alert" className="mt-4 rounded-sm bg-red-50 p-4 text-sm text-red-700"><p>{t(error)}</p>{errorCode === 401 ? <SiteLink to="/membership/notifications?login=1" className="mt-2 inline-flex min-h-11 items-center font-semibold underline">{t("重新登入")}</SiteLink> : <button type="button" className="mt-2 min-h-11 font-semibold underline" onClick={() => { setPage(1); setReload(value => value+1); }}>{t("重新載入第一頁")}</button>}</div>}
    {loading ? <p role="status" className="mt-7 text-sm text-[#64748b]">{t("正在載入通知…")}</p> : data && <div className="mt-6 space-y-4">
      {data.results.map(row => <article key={row.id} className={`rounded-sm border bg-white p-5 md:p-6 ${row.read_at ? 'border-[#dbe3ec]' : 'border-[#8eb6d9]'}`}>
        <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1"><p className="text-xs font-semibold text-[#64748b]">{row.read_at ? t("已讀") : t("未讀")}{!row.active && t('・已失效')}{row.sent_at && `｜${new Date(row.sent_at).toLocaleString(locale)}`}</p><h3 className="mt-2 break-words text-lg font-semibold">{row.active ? row.subject : t(row.subject)}</h3></div><button type="button" disabled={Boolean(row.read_at) || busyId !== null} onClick={() => markRead(row.id)} className="min-h-11 rounded-full border border-[#2b5f8f] px-4 py-2 text-sm font-semibold text-[#2b5f8f] disabled:opacity-40">{busyId === row.id ? t("儲存中…") : row.read_at ? t("已讀") : t("標為已讀")}</button></div>
        <p className="mt-4 whitespace-pre-line break-words text-sm leading-7 text-[#475569]">{row.active ? row.body : t(row.body)}</p>
        {row.active && row.line_group_qr_url && <ClassGroupQRImage url={row.line_group_qr_url} appearance="light" />}
        {row.active && <div className="mt-4 flex flex-wrap gap-3">{row.action_path && <SiteLink to={row.action_path} className="inline-flex min-h-11 items-center rounded-full bg-[#2b5f8f] px-5 py-2 text-sm font-semibold text-white">{row.action_path.startsWith('/membership/pre-course-forms?') ? t("填寫課前資料") : t("查看我的課程")}</SiteLink>}{row.line_group_url && <a href={row.line_group_url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center rounded-full border border-[#2b5f8f] px-5 py-2 text-sm font-semibold text-[#2b5f8f]">{t("加入上課群組 ↗")}</a>}</div>}
      </article>)}
      {!data.results.length && <EmptyState title={t("目前沒有站內通知")} description={t("有新的課程提醒時，會顯示在這裡。")} />}
      {(data.has_previous || data.has_next) && <nav aria-label={t("通知分頁")} className="flex flex-wrap items-center justify-between gap-3"><button type="button" disabled={!data.has_previous || busyId !== null} onClick={() => setPage(value => value-1)} className="min-h-11 rounded-full border border-[#cbd5e1] px-5 py-2 text-sm disabled:opacity-40">{t("上一頁")}</button><span className="text-sm text-[#64748b]">{t('第 {page} 頁',{page:data.page})}</span><button type="button" disabled={!data.has_next || busyId !== null} onClick={() => setPage(value => value+1)} className="min-h-11 rounded-full border border-[#cbd5e1] px-5 py-2 text-sm disabled:opacity-40">{t("下一頁")}</button></nav>}
    </div>}
  </section>;
}

function MemberSection({ section, data, onQuickRebook, onRefresh }) {
  const { t } = useSiteLocale();
  if (section === 'notifications') return <MemberNotifications />;
  if (section === 'orders') return <>{(data.orders.length > 0 || !data.participant_courses?.length) && <Orders data={data} onQuickRebook={onQuickRebook} onRefresh={onRefresh} />}{data.participant_courses?.length > 0 && <div className={data.orders.length ? 'mt-8' : ''}><ParticipantCourses courses={data.participant_courses} /></div>}</>;
  if (section === 'forms') return <Forms forms={data.pre_course_forms} orders={data.orders} waiverDocument={data.waiver_document} skillOptions={data.skill_options} onSaved={onRefresh} />;
  if (section === 'journey') return <Journey records={data.learning_records} onSaved={onRefresh} />;
  if (section === 'offers') return <div><h2 className="text-2xl font-semibold">{t("專屬優惠")}</h2><p className="mt-2 text-sm text-[#64748b]">{t("會員等級、點數與推薦碼集中在這裡。")}</p><div className="mt-7 grid gap-4 md:grid-cols-2"><div className="rounded-sm bg-gradient-to-br from-[#1c3b5f] to-[#2b5f8f] p-6 text-white"><Gift /><p className="mt-8 text-sm text-white/70">{t("會員等級")}</p><p className="mt-1 text-2xl font-semibold">{t({ new: '新會員', alumni: '舊生', silver: '銀級', gold: '金級' }[data.level] || data.level)}</p><p className="mt-3 text-sm">{data.alumni_verified ? t("舊生身分已確認") : t("舊生身分尚未確認；如曾上課，請聯絡 SnowLand 核對。")}</p><p className="mt-5 text-sm">{t('目前點數：{count}',{count:data.points})}</p><p className="mt-1 text-sm text-white/80">{t('其中歷史補登：{count} 點',{count:data.previous_points || 0})}</p></div><div className="rounded-sm border border-[#dbe3ec] bg-white p-6"><p className="text-sm font-semibold text-[#64748b]">{t("我的推薦碼")}</p><p className="mt-4 break-all text-2xl font-semibold tracking-wider text-[#2b5f8f]">{data.referral_code}</p><p className="mt-4 text-sm leading-7 text-[#64748b]">{t("實際折扣與回饋以 SnowLand 已公布、啟用的活動為準；顯示推薦碼不代表已套用優惠。")}</p></div></div></div>;
  return <Overview data={data} />;
}

function MemberContent(props) {
  const { t } = useSiteLocale();
  const location = useLocation();
  const navigate = useNavigate();
  const basePath = useContext(SiteBasePathContext);
  const params = new URLSearchParams(location.search);
  const token = params.get('invite');
  const onAccepted = async (reservationId, notice) => {
    await props.onRefresh();
    navigate(`${basePath}/membership/pre-course-forms?reservation=${reservationId}${notice ? '&bound=1' : ''}`);
  };
  return <>{token && <ParticipantInvitation token={token} onAccepted={onAccepted} />}{params.get('bound') === '1' && <p role="status" className="mb-5 rounded-sm bg-[#eef4fa] p-4 text-sm text-[#2b5f8f]">{t("綁定完成，您可以填寫自己的課前資料。")}</p>}<MemberSection {...props} /></>;
}

export default function MembershipPage() {
  const {t}=useSiteLocale();
  const location = useLocation();
  const navigate = useNavigate();
  const basePath = useContext(SiteBasePathContext);
  const section = sectionFromPath(location.pathname);
  const [status, setStatus] = useState('loading');
  const [data, setData] = useState(null);
  const [notice, setNotice] = useState('');
  const qc = useQueryClient();
  const logoutPending = useRef(false);
  const memberLoadRevision = useRef(0);
  const [loggingOut, setLoggingOut] = useState(false);

  const loadMemberCenter = useCallback(async (options = {}) => {
    if (logoutPending.current) return;
    const revision = ++memberLoadRevision.current;
    const silent = options?.silent === true;
    if (!silent) setStatus('loading');
    try {
      const payload = await requestJson('/booking/snowland/api/member-center/');
      if (revision !== memberLoadRevision.current || logoutPending.current) return;
      setData(payload); setStatus('ready'); localStorage.setItem('user', JSON.stringify(payload.member));
      if (!silent) {
        const returnTo = new URLSearchParams(location.search).get('return_to');
        if (returnTo === 'booking') {
          const loginParams = new URLSearchParams(location.search);
          const bookingParams = new URLSearchParams();
          if (loginParams.get('staff_link')) bookingParams.set('staff_link', loginParams.get('staff_link'));
          if (loginParams.get('resume_checkout') === '1') bookingParams.set('resume_checkout', '1');
          navigate(`${basePath}/booking${bookingParams.size ? `?${bookingParams}` : ''}`);
        }
        else if (returnTo === 'console') navigate(`${basePath}/console`);
      }
    } catch (error) {
      if (revision !== memberLoadRevision.current || logoutPending.current) return;
      if (error.status === 401) { setData(null); setStatus('guest'); }
      else { setNotice(error.message); setStatus('error'); }
    }
  }, [basePath, location.search, navigate]);

  useEffect(() => {
    loadMemberCenter();
    return () => { memberLoadRevision.current += 1; };
  }, [loadMemberCenter]);

  const quickRebook = async (orderId) => {
    if (logoutPending.current) return;
    const revision = memberLoadRevision.current;
    setNotice('正在複製上次預約設定…');
    try {
      const result = await requestJson('/booking/snowland/api/member-center/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quick_rebook_group_id: orderId }) });
      if (revision !== memberLoadRevision.current || logoutPending.current) return;
      useBookingStore.getState().replaceCart(result.cart); navigate(`${basePath}/booking?rebook=1`);
    } catch (error) {
      if (revision === memberLoadRevision.current && !logoutPending.current) setNotice(error.message);
    }
  };

  const logout = async () => {
    if (logoutPending.current) return;
    logoutPending.current = true; setLoggingOut(true); setNotice('');
    memberLoadRevision.current += 1;
    try {
      const result = await requestJson('/control/api/logout/', { method: 'POST' });
      if (result.code !== 200) throw new Error('logout not confirmed');
      const invite = new URLSearchParams(location.search).get('invite');
      qc.clear();
      localStorage.removeItem('user'); setData(null); setStatus('guest'); navigate(`${basePath}/membership${invite ? `?invite=${encodeURIComponent(invite)}` : ''}`);
    } catch {
      setNotice('無法確認登出，請重試；確認成功前，請勿將裝置交給他人。');
    } finally {
      logoutPending.current = false; setLoggingOut(false);
    }
  };

  if (status === 'loading') return <div className="flex min-h-screen items-center justify-center bg-[#f7f8fa]"><div className="h-11 w-11 animate-spin rounded-full border-4 border-[#dbe3ec] border-t-[#2b5f8f]" /><span className="sr-only">{t('載入會員資料')}</span></div>;
  if (status === 'guest') return <AuthPanel onAuthenticated={loadMemberCenter} />;
  if (status === 'error' || !data) return <div className="flex min-h-screen flex-col items-center justify-center gap-5 bg-[#f7f8fa] px-6 text-center"><p className="text-lg font-semibold">{t('會員資料暫時無法載入')}</p><p className="text-sm text-[#64748b]">{t(notice)}</p><button onClick={loadMemberCenter} className="rounded-full bg-[#2b5f8f] px-6 py-3 text-sm font-semibold text-white">{t('重新載入')}</button></div>;

  return <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937]">
<SiteHeader forceCompact forceDarkText forceLogoColor memberAuthenticated memberAvatarSrc="" />
<main className="mx-auto max-w-7xl px-4 pb-24 pt-24 sm:px-6 md:pt-28">
<nav aria-label="breadcrumb" className="mb-6 flex items-center gap-2 text-sm text-[#64748b]">
<SiteLink to="/">{t('首頁')}</SiteLink>
<span>/</span>
<span className="font-semibold text-[#1f2937]">{t('會員專區')}</span>
</nav>{notice && <div role="status" className="mb-5 flex items-center justify-between rounded-sm bg-[#eef4fa] px-4 py-3 text-sm text-[#2b5f8f]">
<span>{t(notice)}</span>
<button onClick={() => setNotice('')} aria-label={t('關閉訊息')}>×</button>
</div>}<div className="grid gap-7 lg:grid-cols-[250px_minmax(0,1fr)]">
<aside className="min-w-0 self-start rounded-sm border border-[#dbe3ec] bg-white p-3 lg:sticky lg:top-24 lg:p-5">
<div className="flex items-center gap-3 border-b border-[#e2e8f0] pb-3 text-left lg:block lg:pb-5 lg:text-center">
<div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[#eef4fa] text-[#2b5f8f] lg:mx-auto lg:h-20 lg:w-20">
<UserRound size={30} />
</div>
<div className="min-w-0">
<p className="truncate font-semibold lg:mt-4">{data.member.name}</p>
<p className="mt-1 truncate text-xs text-[#64748b]">{data.member.email}</p>
</div>
</div>
<nav className="mt-3 grid grid-cols-2 gap-2 lg:block" aria-label={t('會員功能')}>{navItems.map(({ key, label, path, icon: Icon }) => <SiteLink key={key} to={path} className={`flex min-h-11 items-center gap-2 rounded-full border px-3 py-2.5 text-sm font-semibold lg:gap-3 lg:rounded-none lg:border-x-0 lg:border-t-0 lg:border-b lg:border-[#eef2f7] lg:px-2 lg:py-3.5 ${section === key ? 'border-[#2b5f8f] bg-[#eef4fa] text-[#2b5f8f] lg:bg-transparent' : 'border-[#e2e8f0] text-[#64748b] hover:text-[#2b5f8f]'}`}>
<Icon size={17} />{t(label)}</SiteLink>)}</nav>
<button type="button" onClick={logout} disabled={loggingOut} aria-busy={loggingOut} className="mt-2 flex min-h-11 items-center gap-2 px-3 py-2 text-sm font-semibold text-[#64748b] hover:text-red-600 disabled:opacity-50 lg:mt-4 lg:w-full lg:gap-3 lg:px-2 lg:py-3">
<LogOut size={17} />{t(loggingOut ? '登出中…' : '登出')}</button>
</aside>
<section className="min-w-0">
<MemberContent section={section} data={data} onQuickRebook={quickRebook} onRefresh={() => loadMemberCenter({ silent: true })} />
</section>
</div>
</main>
<SiteFooter />
</div>;
}
