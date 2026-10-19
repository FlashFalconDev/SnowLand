import React, {useContext, useEffect, useMemo, useState} from 'react';
import {useLocation} from 'react-router-dom';
import {useSiteContent} from '../../hooks/useSiteContent';
import {publicTrackingPage, siteTracking, trackingConfig} from '../../utils/siteTracking';
import SiteLink, {SiteBasePathContext} from './SiteLink';

export default function SiteTracking() {
  const basePath = useContext(SiteBasePathContext);
  const location = useLocation();
  const {items} = useSiteContent('site.tracking', {contentType: 'setting', limit: 1});
  const config = useMemo(() => trackingConfig(items[0]), [items]);
  const [open, setOpen] = useState(false);
  const [choice, setChoice] = useState({analytics: false, marketing: false});
  const [notice, setNotice] = useState('');
  useEffect(() => {
    setNotice('');
    const stored = siteTracking.configure(config, basePath, setNotice);
    setChoice(stored || {analytics: false, marketing: false});
    setOpen(Boolean(config && !stored));
  }, [config, basePath]);
  useEffect(() => { siteTracking.page(); }, [location.pathname, location.search, location.hash]);
  if (!config || !publicTrackingPage(window.location.href, basePath, window.location.origin)) return null;
  const save = value => { if (siteTracking.save(value)) {setChoice(value); setOpen(false);} };
  return <aside aria-label="隱私偏好" className="fixed bottom-3 left-3 right-3 z-[80] text-sm text-slate-800 sm:left-auto sm:w-[420px]">
    {!open ? <button type="button" onClick={() => setOpen(true)} className="ml-auto block min-h-11 rounded-xl border border-slate-300 bg-white px-4 shadow-lg">隱私設定</button> :
      <section aria-labelledby="tracking-preferences-title" className="max-h-[75vh] space-y-3 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-xl">
        <h2 id="tracking-preferences-title" className="text-lg font-bold">選擇網站分析偏好</h2>
        <p className="leading-6">不同意也能正常使用。選擇同意後，才會載入 Google／Meta，記錄公開頁面及導覽按鈕；不傳送會員、學員或訂單資料。平台仍會接收 IP、瀏覽器等技術資訊。</p>
        {siteTracking.isLocal() && <p className="rounded-lg bg-blue-50 p-2 text-blue-900">本機僅測試偏好，不載入外部追蹤。</p>}
        {siteTracking.privacySignal() && <p className="rounded-lg bg-amber-50 p-2 text-amber-900">已依瀏覽器的隱私訊號關閉追蹤。</p>}
        {config.ga4 && <label className="flex min-h-11 items-center gap-3"><input className="h-5 w-5" type="checkbox" checked={choice.analytics} disabled={siteTracking.privacySignal()} onChange={event => setChoice({...choice, analytics: event.target.checked})}/>Google 網站分析（選用）</label>}
        {config.meta && <label className="flex min-h-11 items-center gap-3"><input className="h-5 w-5" type="checkbox" checked={choice.marketing} disabled={siteTracking.privacySignal()} onChange={event => setChoice({...choice, marketing: event.target.checked})}/>Meta 行銷分析（選用）</label>}
        <p className="text-xs leading-5">偏好保留 90 天，可隨時從「隱私設定」撤回；撤回時會重新載入以停止追蹤，不會刪除平台已收到的資料。<SiteLink className="underline" to="/privacy-policy">查看隱私權政策</SiteLink></p>
        <div className="grid grid-cols-2 gap-3"><button type="button" onClick={() => save({analytics: false, marketing: false})} className="min-h-11 rounded-xl border border-slate-400 bg-white px-3 font-semibold">全部拒絕</button><button type="button" onClick={() => save(choice)} className="min-h-11 rounded-xl border border-[#2b5f8f] bg-[#2b5f8f] px-3 font-semibold text-white">儲存選擇</button></div>
      </section>}
    {notice && <p role="alert" className="mt-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-amber-900">{notice}</p>}
  </aside>;
}
