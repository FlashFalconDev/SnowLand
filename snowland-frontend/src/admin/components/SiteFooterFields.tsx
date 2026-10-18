import type {SiteContentWriteData} from '../api/siteContent'
import {footerSocials} from '../../data/site/footerSettings'

const inputClass = 'mt-1 min-h-11 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white'
export default function SiteFooterFields({value,onChange}:{value:SiteContentWriteData;onChange:(patch:Partial<SiteContentWriteData>)=>void}) {
  const metadata = value.metadata || {}
  const links = (metadata.social_links || {}) as Record<string,string>
  const meta = (patch:Record<string,unknown>)=>onChange({metadata:{...metadata,...patch}})
  return <section aria-label="頁尾與社群設定" className="space-y-4 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">2. 每一頁底部的公司與社群資訊</h3>
    <p className="text-xs leading-5 text-gray-600 dark:text-gray-300">沿用現有頁尾版型。清空欄位就不顯示；LINE與WhatsApp也會同步更新浮動客服按鈕。這裡只設定連結，不會啟用IG自動同步。</p>
    <label className="block text-sm text-gray-700 dark:text-gray-200">後台辨識名稱<input required className={inputClass} value={value.title} onChange={event=>onChange({title:event.target.value})}/></label>
    {[
      ['公司名稱（第一行）','company_name'], ['公司名稱（第二行，可留空）','company_name_secondary'],
      ['聯絡Email（可留空）','email'], ['版權文字（可留空）','copyright'],
    ].map(([label,key])=><label key={key} className="block text-sm text-gray-700 dark:text-gray-200">{label}<input type={key==='email'?'email':'text'} maxLength={key==='email'?254:300} value={String(metadata[key] || '')} className={inputClass} onChange={event=>meta({[key]:event.target.value})}/></label>)}
    <fieldset className="space-y-4"><legend className="text-sm font-semibold text-gray-900 dark:text-white">社群連結（貼上完整https網址；留空隱藏）</legend>
      {footerSocials.map(({key,label})=><label key={key} className="block text-sm text-gray-700 dark:text-gray-200">{label}網址<input type="url" pattern="https://.*" maxLength={2000} placeholder="https://…" value={links[key] || ''} className={inputClass} onChange={event=>meta({social_links:{...links,[key]:event.target.value}})}/></label>)}
    </fieldset>
    <p className="text-xs text-gray-500 dark:text-gray-400">設為「草稿／隱藏」會一起隱藏公司資訊與社群；既有導覽與回頂部按鈕仍保留。</p>
  </section>
}
