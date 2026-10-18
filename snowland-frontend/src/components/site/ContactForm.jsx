import React, { useEffect, useRef, useState } from 'react';
import api from '../../api/axios';

export function contactError(error) {
  if (error?.response?.status === 429) return '送出次數較多，請稍候一分鐘再試。';
  const data = error?.response?.data;
  const messages = data && typeof data === 'object' ? Object.values(data).flat().filter(v => typeof v === 'string') : [];
  const message = messages.join('；');
  return message && message.length <= 2000 && !/<(?:html|!doctype|script)\b/i.test(message) ? message : '目前無法送出，資料已保留，請稍後再試。';
}

const inputClass = 'mt-3 min-h-11 w-full border-b border-[#1f2937]/40 bg-transparent pb-2 text-sm text-[#1f2937] placeholder:text-[#94a3b8] focus:border-[#1f2937] focus:outline-none';
const empty = {name: '', phone: '', email: '', subject: '', message: ''};

export default function ContactForm({ emailLabel='E-mail*', subjectLabel='主旨', messageLabel='訊息' }) {
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState(false);
  const [reload, setReload] = useState(0);
  const [values, setValues] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState('');
  const attempt = useRef(null);
  const inFlight = useRef(false);
  const receiptRef = useRef(null);
  useEffect(() => {
    let active = true;
    setConfig(null); setConfigError(false);
    api.get('/contact/').then(result => { if (active) setConfig(result); }).catch(() => { if (active) setConfigError(true); });
    return () => { active = false; };
  }, [reload]);
  useEffect(() => {
    if (receipt) {
      receiptRef.current?.focus();
      receiptRef.current?.scrollIntoView({block: 'center', behavior: 'smooth'});
    }
  }, [receipt]);

  const change = (key, value) => { setValues(v => ({...v, [key]: value})); setError(''); };
  const submit = async event => {
    event.preventDefault();
    if (inFlight.current || !config?.enabled || receipt) return;
    const fields = Object.fromEntries(Object.entries(values).map(([k,v]) => [k,v.trim()]));
    if (!fields.name || !fields.email || !fields.subject || !fields.message) { setError('請填寫姓名、Email、主旨與訊息。'); return; }
    const fingerprint = JSON.stringify(fields);
    if (!attempt.current || attempt.current.fingerprint !== fingerprint) attempt.current = {fingerprint, id: crypto.randomUUID()};
    inFlight.current = true; setBusy(true); setError('');
    try {
      const result = await api.post('/contact/', {...fields, submission_id: attempt.current.id}, {timeout: 20000});
      if (!result?.ok || !result.reference) throw new Error('Invalid receipt');
      setReceipt(result.reference);
    } catch (failure) { setError(contactError(failure)); }
    finally { inFlight.current = false; setBusy(false); }
  };
  const reset = () => { setReceipt(''); setValues(empty); setError(''); attempt.current = null; };
  return <form onSubmit={submit} className="min-w-0 space-y-6" aria-label="聯絡表單" aria-busy={busy}>
    {configError ? <p role="alert" className="text-sm text-red-700">表單狀態載入失敗。<button type="button" className="ml-2 min-h-11 underline" onClick={() => setReload(v=>v+1)}>重新載入表單</button></p>
      : !config ? <p role="status" className="text-sm text-[#475569]">表單載入中…</p>
      : !config.enabled ? <p role="status" className="rounded-sm border border-[#cbd5e1] bg-[#f1f5f9] px-4 py-3 text-sm leading-6 text-[#475569]">聯絡表單尚未啟用，這裡不會送出或儲存訊息。請使用本頁列出的 Email 或官方 LINE 聯絡我們。</p> : null}
    {receipt ? <div ref={receiptRef} role="status" tabIndex={-1} className="scroll-mt-24 rounded-sm border border-[#b7d5c3] bg-[#f1f8f3] p-4 text-sm leading-6 text-[#245436]">已收到您的訊息，我們會盡快回覆。<p className="mt-2 break-all text-xs">收件編號：{receipt}</p><button type="button" className="mt-3 min-h-11 underline" onClick={reset}>再送一則</button></div> : null}
    <fieldset disabled={!config?.enabled || busy || !!receipt} className="min-w-0 space-y-8">
      <div className="grid gap-6 md:grid-cols-2">
        <label className="block text-xs font-semibold tracking-[0.2em] text-[#475569]">姓名*<input required autoComplete="name" maxLength={100} value={values.name} onChange={e=>change('name',e.target.value)} className={inputClass} placeholder="請輸入姓名" /></label>
        <label className="block text-xs font-semibold tracking-[0.2em] text-[#475569]">電話<input type="tel" autoComplete="tel" maxLength={50} value={values.phone} onChange={e=>change('phone',e.target.value)} className={inputClass} placeholder="請輸入電話" /></label>
        <label className="block text-xs font-semibold tracking-[0.2em] text-[#475569]">{emailLabel}<input required type="email" autoComplete="email" maxLength={254} value={values.email} onChange={e=>change('email',e.target.value)} className={inputClass} placeholder="you@example.com" /></label>
        <label className="block text-xs font-semibold tracking-[0.2em] text-[#475569]">{subjectLabel}*<input required maxLength={200} value={values.subject} onChange={e=>change('subject',e.target.value)} className={inputClass} placeholder="請輸入主旨" /></label>
      </div>
      <label className="block text-xs font-semibold tracking-[0.2em] text-[#475569]">{messageLabel}*<textarea required rows={4} maxLength={10000} value={values.message} onChange={e=>change('message',e.target.value)} className={`${inputClass} resize-y`} placeholder="請輸入訊息" /></label>
      <p className="text-xs leading-5 text-[#64748b]">請勿在留言填寫身分證、護照或健康資料。請留下可聯絡的Email，我們會依序回覆。</p>
      <button type="submit" className="inline-flex min-h-11 w-full items-center justify-center rounded-full border border-[#1f2937] px-6 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:bg-[#2b5f8f] hover:text-white disabled:cursor-not-allowed disabled:opacity-50">{busy ? '送出中…' : '送出訊息'}</button>
    </fieldset>
    {error && <p role="alert" className="rounded-sm bg-red-50 p-3 text-sm leading-6 text-red-700">{error}</p>}
  </form>;
}
