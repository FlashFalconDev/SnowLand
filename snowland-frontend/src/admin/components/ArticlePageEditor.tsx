import { useState } from 'react'

type HtmlField = { id: number; label: string; kind: 'text' | 'image' | 'link'; node: Node }
type Article = { title?: string; date?: string; heroImage?: string; lead?: string; html?: string; relatedLinks?: {title: string; url: string}[] }
const inputClass = 'mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-white'
const record = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}

function readDraft(html: string) {
  const document = new DOMParser().parseFromString(html, 'text/html')
  const fields: HtmlField[] = []
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  let node: Node | null
  while ((node = walker.nextNode())) {
    if (!node.textContent?.trim() || node.parentElement?.closest('script,style,template')) continue
    const heading = node.parentElement?.closest('h1,h2,h3,h4,h5,h6')
    fields.push({id: fields.length, label: heading ? `小標題：${heading.textContent}` : `原文段落 ${fields.length + 1}`, kind: 'text', node})
  }
  let imageNumber = 0
  for (const image of document.body.querySelectorAll('img')) {
    imageNumber += 1
    fields.push({id: fields.length, label: `圖片：${image.alt || `第${imageNumber}張`}`, kind: 'image', node: image})
  }
  for (const link of document.body.querySelectorAll('a[href]')) fields.push({id: fields.length, label: `連結：${link.textContent || fields.length + 1}`, kind: 'link', node: link})
  return {document, fields}
}
const valueOf = (field: HtmlField) => field.kind === 'text' ? field.node.textContent || '' : (field.node as Element).getAttribute(field.kind === 'image' ? 'src' : 'href') || ''

export default function ArticlePageEditor({ metadata, onChange }: { metadata: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void }) {
  const article = record(metadata.article) as Article
  const [draft, setDraft] = useState(() => readDraft(typeof article.html === 'string' ? article.html : ''))
  const [search, setSearch] = useState('')
  const [matches, setMatches] = useState<number[] | null>(null)
  const update = (patch: Partial<Article>) => onChange({...metadata, article: {...article, ...patch}})
  const edit = (field: HtmlField, value: string) => {
    if (field.kind === 'text') field.node.textContent = value
    else {
      const element = field.node as Element
      element.setAttribute(field.kind === 'image' ? 'src' : 'href', value)
      // A legacy srcset would otherwise keep showing the old picture.
      if (field.kind === 'image') { element.removeAttribute('srcset'); element.removeAttribute('sizes') }
    }
    update({html: draft.document.body.innerHTML})
  }
  const add = (kind: 'text' | 'image') => {
    const element = draft.document.createElement(kind === 'text' ? 'p' : 'img')
    if (kind === 'text') element.textContent = '新的段落'
    else element.setAttribute('src', '')
    draft.document.body.appendChild(element)
    const node = kind === 'text' ? element.firstChild! : element
    const fields = [...draft.fields, {id: Math.max(-1, ...draft.fields.map(field => field.id)) + 1, label: kind === 'text' ? '新增段落' : '新增圖片', kind, node}]
    setDraft({...draft, fields}); setSearch(''); setMatches(null)
    update({html: draft.document.body.innerHTML})
  }
  const removeImage = (field: HtmlField) => {
    field.node.parentNode?.removeChild(field.node)
    setDraft({...draft, fields:draft.fields.filter(item => item.id !== field.id)})
    update({html:draft.document.body.innerHTML})
  }
  const visible = draft.fields.filter(field => !search.trim() || matches?.includes(field.id))
  return <section aria-label="原文章編輯" className="space-y-4">
    <p className="rounded-lg bg-blue-50 p-3 text-sm leading-6 text-blue-900 dark:bg-blue-950/40 dark:text-blue-200">這裡直接編輯官網的原文章，保留原本表格、條列與文字格式。搜尋原文可快速找到段落；不需要編寫HTML。儲存後官網才會更新。</p>
    {([['title','文章標題'],['date','顯示日期'],['heroImage','首圖網址'],['lead','開頭說明']] as const).map(([key,label]) => <label key={key} className="block text-sm text-gray-700 dark:text-gray-200">{label}<textarea rows={key === 'lead' ? 4 : 2} className={inputClass} value={article[key] || ''} onChange={event => update({[key]:event.target.value})} /></label>)}
    <label className="block text-sm text-gray-700 dark:text-gray-200">搜尋原文章（{visible.length}/{draft.fields.length} 欄位）<input type="search" className={inputClass} value={search} placeholder="輸入原文、圖片說明或網址" onChange={event => {
      const query = event.target.value.trim().toLowerCase()
      setSearch(event.target.value)
      setMatches(draft.fields.filter(field => `${field.label} ${valueOf(field)}`.toLowerCase().includes(query)).map(field => field.id))
    }} /></label>
    <div className="flex gap-2"><button type="button" className="min-h-11 rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-600" onClick={() => add('text')}>＋新增段落</button><button type="button" className="min-h-11 rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-600" onClick={() => add('image')}>＋新增圖片</button></div>
    {!visible.length && <p className="text-sm text-gray-500 dark:text-gray-400">目前沒有符合的欄位。<button type="button" className="ml-2 min-h-11 underline" onClick={() => setSearch('')}>清除搜尋</button></p>}
    {visible.map(field => <label key={field.id} className="block rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">{field.label}
      <textarea aria-label={field.label} rows={field.kind === 'text' ? 3 : 2} className={inputClass} value={valueOf(field)} onChange={event => edit(field,event.target.value)} />
      {field.kind === 'image' && <button type="button" className="mt-2 min-h-11 rounded-lg border border-red-200 px-3 text-sm text-red-600 dark:border-red-900 dark:text-red-300" onClick={() => removeImage(field)}>移除此圖片</button>}
    </label>)}
    {Array.isArray(article.relatedLinks) && article.relatedLinks.length > 0 && <details className="rounded-lg border border-gray-200 p-3 dark:border-gray-700"><summary className="cursor-pointer text-sm">延伸閱讀連結</summary><div className="mt-3 space-y-3">{article.relatedLinks.map((link,index) => <div key={index} className="space-y-2">{(['title','url'] as const).map(key => <label key={key} className="block text-sm">{key === 'title' ? '連結名稱' : '連結網址'}<input className={inputClass} value={link[key]} onChange={event => update({relatedLinks:article.relatedLinks!.map((item,i) => i === index ? {...item,[key]:event.target.value} : item)})} /></label>)}</div>)}</div></details>}
  </section>
}
