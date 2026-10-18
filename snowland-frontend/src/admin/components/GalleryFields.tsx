import { useState } from 'react'
import type { SiteContentItem } from '../api/siteContent'

const inputClass = 'mt-1 min-h-11 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white'

export function youtubeId(value: string): string {
  const text = value.trim()
  if (/^[A-Za-z0-9_-]{11}$/.test(text)) return text
  try {
    const url = new URL(text)
    if (!['http:', 'https:'].includes(url.protocol)) return ''
    const host = url.hostname.toLowerCase().replace(/^www\./, '')
    const id = host === 'youtu.be' ? url.pathname.slice(1)
      : ['youtube.com', 'm.youtube.com'].includes(host)
        ? url.searchParams.get('v') || url.pathname.match(/^\/(?:embed|shorts)\/([^/]+)$/)?.[1] || '' : ''
    return /^[A-Za-z0-9_-]{11}$/.test(id) ? id : ''
  } catch { return '' }
}

export default function GalleryFields({ metadata, imageUrl, items, published, onChange, onImageChange }: {
  metadata: Record<string, unknown>; imageUrl: string; items: SiteContentItem[]; published: boolean
  onChange: (metadata: Record<string, unknown>) => void; onImageChange: (url: string) => void
}) {
  const [newType, setNewType] = useState('')
  const [videoInput, setVideoInput] = useState(String(metadata.video_id || ''))
  const selected = Array.isArray(metadata.shoot_types) ? metadata.shoot_types.filter((v): v is string => typeof v === 'string') : []
  const choices = [...new Set([...items.flatMap(item => Array.isArray(item.metadata?.shoot_types) ? item.metadata.shoot_types.filter((v): v is string => typeof v === 'string') : []), ...selected])]
  const locations = [...new Set(items.map(item => item.metadata?.location).filter((v): v is string => typeof v === 'string' && !!v))]
  const set = (key: string, value: unknown) => onChange({ ...metadata, [key]: value })
  const isVideo = metadata.media_type === 'video'
  return <fieldset className="space-y-4 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
    <legend className="px-1 text-sm font-semibold text-gray-900 dark:text-white">作品與分類設定</legend>
    <label className="block text-sm text-gray-800 dark:text-gray-200">作品類型
      <select aria-label="作品類型" className={inputClass} value={isVideo ? 'video' : 'photo'} onChange={event => set('media_type', event.target.value)}>
        <option value="photo">照片</option><option value="video">YouTube影片</option>
      </select>
    </label>
    {isVideo ? <label className="block text-sm text-gray-800 dark:text-gray-200">YouTube影片網址或代號
      <input required={published} className={inputClass} value={videoInput} onChange={event => {
        setVideoInput(event.target.value); set('video_id', youtubeId(event.target.value))
      }} placeholder="貼上YouTube影片網址" />
      {videoInput && !youtubeId(videoInput) && <span role="alert" className="text-xs text-red-600 dark:text-red-300">請填寫有效YouTube網址或11碼代號；未修正不能公開。</span>}
    </label> : <label className="block text-sm text-gray-800 dark:text-gray-200">作品照片網址
      <input required={published} maxLength={500} className={inputClass} value={imageUrl} onChange={event => onImageChange(event.target.value)} placeholder="https://… 或 /photography-gallery/…" />
    </label>}
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="block text-sm text-gray-800 dark:text-gray-200">拍攝地點
        <input list="gallery-locations" maxLength={80} className={inputClass} value={typeof metadata.location === 'string' ? metadata.location : ''} onChange={event => set('location', event.target.value)} placeholder="選擇既有地點或輸入新地點" />
        <datalist id="gallery-locations">{locations.map(value => <option key={value} value={value} />)}</datalist>
      </label>
      <label className="block text-sm text-gray-800 dark:text-gray-200">地點內的景點（選填）
        <input maxLength={80} className={inputClass} value={typeof metadata.section === 'string' ? metadata.section : ''} onChange={event => set('section', event.target.value)} placeholder="例如森林、湖畔" />
      </label>
    </div>
    <div className="text-sm text-gray-800 dark:text-gray-200">
      <p>拍攝分類（可複選）</p>
      <div className="mt-2 flex flex-wrap gap-x-4">{choices.map(value => <label key={value} className="flex min-h-11 items-center gap-2">
        <input type="checkbox" checked={selected.includes(value)} onChange={event => set('shoot_types', event.target.checked ? [...selected, value] : selected.filter(v => v !== value))} />{value}
      </label>)}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        <label className="min-w-0 flex-1">新增拍攝分類<input maxLength={50} className={inputClass} value={newType} onChange={event => setNewType(event.target.value)} /></label>
        <button type="button" disabled={!newType.trim() || selected.length >= 20} className="min-h-11 self-end rounded-lg border border-gray-300 px-3 disabled:opacity-50 dark:border-gray-600" onClick={() => {
          set('shoot_types', [...new Set([...selected, newType.trim()])]); setNewType('')
        }}>新增並勾選</button>
      </div>
      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">儲存並設為進行中後，分類會出現在官網作品頁；不會更改其他作品的分類。</p>
    </div>
  </fieldset>
}
