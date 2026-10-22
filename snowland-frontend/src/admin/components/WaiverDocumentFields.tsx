import type { SiteContentWriteData } from '../api/siteContent'

export default function WaiverDocumentFields({value,onChange}:{value:SiteContentWriteData;onChange:(patch:Partial<SiteContentWriteData>)=>void}) {
  const input='mt-2 w-full rounded-lg border border-gray-300 bg-white px-3 py-3 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-white'
  return <section aria-label="聲明書內容與版本" className="space-y-4 rounded-lg border border-gray-200 p-4 dark:border-gray-700">
    <h3 className="font-semibold text-gray-900 dark:text-white">聲明書內容與版本</h3>
    <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm leading-6 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200">修改標題或正文後，儲存時會自動建立新版本；公開後，已簽舊版的會員需要重新簽署。只改排序不會要求重簽。原簽名與文件快照會保留。</p>
    <p className="break-all text-xs text-gray-600 dark:text-gray-300">目前版本：{String(value.metadata?.version || '儲存時自動產生')}（不需自行編號）</p>
    <label className="block text-sm text-gray-700 dark:text-gray-200">聲明書標題<input required value={value.title} onChange={e=>onChange({title:e.target.value})} className={input}/></label>
    <label className="block text-sm text-gray-700 dark:text-gray-200">聲明書完整正文<textarea required rows={12} value={value.body} onChange={e=>onChange({body:e.target.value})} className={input}/></label>
    <label className="flex min-h-11 items-start gap-3 text-sm leading-6 text-gray-700 dark:text-gray-200"><input type="checkbox" className="mt-1 h-4 w-4 shrink-0" checked={Boolean(value.metadata?.is_draft)} onChange={e=>onChange({metadata:{...value.metadata,is_draft:e.target.checked}})}/>文件仍待法務確認（會員端會顯示提示）</label>
    <p className="text-xs leading-6 text-gray-500 dark:text-gray-400">上方「草稿」只保存、不公開；選擇「進行中」後儲存，才會成為會員使用的文件。此處不會代會員簽署。</p>
  </section>
}
