import type {SiteContentWriteData} from '../api/siteContent'

const inputClass = 'mt-1 min-h-11 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white'

export default function SiteTrackingFields({value,onChange}:{value:SiteContentWriteData;onChange:(patch:Partial<SiteContentWriteData>)=>void}) {
  const metadata = value.metadata || {}
  const change = (key:string,text:string|boolean)=>{
    const next = {...metadata,[key]:text}
    if (next.auto_events_disabled !== true || !(next.ga4_id || next.meta_pixel_id)) next.enabled = false
    onChange({metadata:next})
  }
  return <section aria-label="分析追蹤設定" className="space-y-4 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">GA4 與 Meta Pixel</h3>
    <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">預設關閉。設為公開且勾選啟用後，仍須訪客自行同意才載入；本機網址不載入外部追蹤。只有總部管理員能儲存此設定。</p>
    <label className="block text-sm text-gray-700 dark:text-gray-200">後台辨識名稱<input required className={inputClass} value={value.title} onChange={event=>onChange({title:event.target.value})}/></label>
    <label className="block text-sm text-gray-700 dark:text-gray-200">GA4 評估 ID（可留空）<input className={inputClass} maxLength={22} pattern="G-[A-Z0-9]{4,20}" placeholder="G-XXXXXXXXXX" value={String(metadata.ga4_id || '')} onChange={event=>change('ga4_id',event.target.value.trim())}/></label>
    <label className="block text-sm text-gray-700 dark:text-gray-200">Meta Pixel ID（可留空）<input className={inputClass} inputMode="numeric" maxLength={25} pattern="[0-9]{5,25}" placeholder="請填寫數字 ID" value={String(metadata.meta_pixel_id || '')} onChange={event=>change('meta_pixel_id',event.target.value.trim())}/></label>
    <label className="flex min-h-11 items-start gap-3 text-sm text-gray-700 dark:text-gray-200"><input type="checkbox" className="mt-1 h-5 w-5 shrink-0" checked={metadata.auto_events_disabled === true} onChange={event=>change('auto_events_disabled',event.target.checked)}/><span>已在 GA4 關閉增強型評估，並在 Meta 關閉自動事件及自動進階配對（避免自動讀取表單與個資）。</span></label>
    <label className="flex min-h-11 items-center gap-3 text-sm font-semibold text-gray-900 dark:text-white"><input type="checkbox" className="h-5 w-5" checked={metadata.enabled === true} disabled={metadata.auto_events_disabled !== true || !(metadata.ga4_id || metadata.meta_pixel_id)} onChange={event=>change('enabled',event.target.checked)}/>啟用公開頁面與導覽按鈕追蹤</label>
    <p className="text-xs leading-5 text-gray-600 dark:text-gray-300">只需 ID，不需密碼、Token 或程式碼。只統計公開介紹頁與導覽按鈕；會員、訂課、付款、聯絡表單不載入。停用後不再載入，新設定不會替訪客同意。平台仍會接收必要技術資訊（例如IP與瀏覽器）；這不是匿名統計，也不同於官方 IG 貼文同步。</p>
  </section>
}
