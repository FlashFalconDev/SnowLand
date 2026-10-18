import type {SiteContentWriteData} from '../api/siteContent'
type Props = {value:SiteContentWriteData; onChange:(patch:Partial<SiteContentWriteData>)=>void}
const inputClass='mt-1 min-h-11 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white'
export default function HomepagePresentationFields({value,onChange}:Props) {
  const hero=value.location_key==='homepage.hero',metadata=value.metadata || {}
  const meta=(patch:Record<string,unknown>)=>onChange({metadata:{...metadata,...patch}})
  const extras=Array.isArray(metadata.extra_paragraphs)?metadata.extra_paragraphs as string[]:[]
  const text=(label:string,key:'title'|'summary'|'subtitle',multiline=false)=><label key={key} className="block text-sm text-gray-700 dark:text-gray-200">{label}{multiline?<textarea value={value[key]} rows={3} className={inputClass} onChange={event=>onChange({[key]:event.target.value})}/>:<input value={value[key]} className={inputClass} onChange={event=>onChange({[key]:event.target.value})}/>}</label>
  const metaText=(label:string,key:string)=><label key={key} className="block text-sm text-gray-700 dark:text-gray-200">{label}<textarea rows={2} value={String(metadata[key] || '')} className={inputClass} onChange={event=>meta({[key]:event.target.value})}/></label>
  return <section aria-label={hero?'首頁主視覺設定':'首頁學校介紹設定'} className="space-y-4 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{hero?'2. 首頁第一屏':'2. 首頁學校介紹'}</h3>
    <p className="text-xs leading-5 text-gray-600 dark:text-gray-300">沿用官網原版型，儲存後才會更新。此處只修改展示內容，不影響課程價格或學校介紹內頁。</p>
    {text('標題','title',hero)}
    {hero?<>
      {text('中文說明','summary',true)}{text('英文說明','subtitle',true)}
      <label className="block text-sm text-gray-700 dark:text-gray-200">背景方式<select value={String(metadata.media_type || 'none')} className={inputClass} onChange={event=>meta({media_type:event.target.value})}><option value="youtube">YouTube影片</option><option value="image">圖片</option><option value="none">純色背景</option></select></label>
      {metadata.media_type==='youtube' && <label className="block text-sm text-gray-700 dark:text-gray-200">YouTube影片網址或代號<input value={String(metadata.youtube_id || '')} maxLength={2000} placeholder="直接貼上YouTube或youtu.be影片網址" className={inputClass} onChange={event=>meta({youtube_id:event.target.value})}/><span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">可直接貼影片網址，不用自己找代號；儲存後系統自動轉換，首頁會靜音循環播放。</span></label>}
    </>:<>
      {metaText('第1段：開頭','opening_text')}{metaText('第1段：粗體雪場名稱','resort_names')}{metaText('第1段：後半段','opening_suffix')}
      {metaText('第2段：開頭','language_prefix')}{metaText('第2段：粗體語言名稱','languages')}{metaText('第2段：後半段','language_suffix')}
      <fieldset className="space-y-3"><legend className="text-sm font-semibold text-gray-900 dark:text-white">按「展開」才顯示的段落</legend>{extras.map((paragraph,index)=><div key={index} className="space-y-2"><label className="block text-sm text-gray-700 dark:text-gray-200">展開第{index+1}段<textarea rows={4} value={paragraph} className={inputClass} onChange={event=>meta({extra_paragraphs:extras.map((text,i)=>i===index?event.target.value:text)})}/></label><button type="button" className="min-h-11 px-3 text-sm text-red-600 dark:text-red-400" onClick={()=>meta({extra_paragraphs:extras.filter((_,i)=>i!==index)})}>移除第{index+1}段</button></div>)}<button type="button" disabled={extras.length>=20} className="min-h-11 rounded-lg border border-gray-300 px-4 text-sm text-gray-700 disabled:opacity-50 dark:border-gray-600 dark:text-gray-200" onClick={()=>meta({extra_paragraphs:[...extras,'']})}>新增展開段落</button></fieldset>
      <label className="flex min-h-11 items-center gap-3 text-sm text-gray-700 dark:text-gray-200"><input type="checkbox" checked={metadata.image_asset==='original-school-photo'} onChange={event=>meta({image_asset:event.target.checked?'original-school-photo':''})}/>未填新圖片時，使用原有學校照片</label>
    </>}
    {(!hero || metadata.media_type==='image') && <label className="block text-sm text-gray-700 dark:text-gray-200">{hero?'背景圖片網址':'新照片網址（可留空）'}<input value={value.image_url} className={inputClass} placeholder="/homepage/example.jpg 或 https://…" onChange={event=>onChange({image_url:event.target.value})}/></label>}
    <div className="grid gap-4 sm:grid-cols-2"><label className="block text-sm text-gray-700 dark:text-gray-200">按鈕文字<input value={String(metadata.button_text || '')} className={inputClass} onChange={event=>meta({button_text:event.target.value})}/></label><label className="block text-sm text-gray-700 dark:text-gray-200">按鈕連結<input value={value.link_url} className={inputClass} placeholder="例如 /booking 或 /about" onChange={event=>onChange({link_url:event.target.value})}/></label></div>
    <p className="text-xs text-gray-500 dark:text-gray-400">不顯示按鈕時清空連結；隱藏整區請調整上方「狀態」。</p>
  </section>
}
