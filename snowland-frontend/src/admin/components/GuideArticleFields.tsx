type Props = {metadata:Record<string,unknown>; mode:string; categories:string[]; onChange:(value:Record<string,unknown>)=>void}
const inputClass='mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-white'

export default function GuideArticleFields({metadata,mode,categories,onChange}:Props) {
  const update=(patch:Record<string,unknown>)=>onChange({...metadata,...patch})
  return <section aria-label="文章分類與閱讀方式" className="space-y-4 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">文章分類與閱讀方式</h3>
    <label className="block text-sm text-gray-700 dark:text-gray-200">文章分類
      <input list="guide-article-categories" maxLength={60} value={String(metadata.category || '')} className={inputClass} placeholder="選擇分類，或輸入新分類名稱" onChange={event=>update({category:event.target.value})} />
      <datalist id="guide-article-categories">{categories.map(category=><option key={category} value={category} />)}</datalist>
    </label>
    <p className="text-xs leading-5 text-gray-500 dark:text-gray-400">可選既有分類，或輸入新名稱。公開文章後，分類會出現在官網，不必另外設定。</p>
    <label className="block text-sm text-gray-700 dark:text-gray-200">文章顯示日期
      <input type="date" value={String(metadata.date || '').replace(/\./g,'-')} className={inputClass} onChange={event=>update({date:event.target.value})} />
    </label>
    <label className="block text-sm text-gray-700 dark:text-gray-200">閱讀方式
      <select value={mode} className={inputClass} onChange={event=>update({article_mode:event.target.value})}>
        <option value="internal">本站文章：在下方編輯完整內文</option>
        <option value="external">連結既有文章：填寫文章網址</option>
      </select>
    </label>
    <p className="text-xs leading-5 text-gray-500 dark:text-gray-400">{mode === 'internal' ? '儲存後自動產生本站文章網址；標題、分類、摘要與內文由同一筆資料管理。' : '保留既有文章連結；卡片會開啟該網址，不會另建一份空白內頁。'}</p>
  </section>
}
