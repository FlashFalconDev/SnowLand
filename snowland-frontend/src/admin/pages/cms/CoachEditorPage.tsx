import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Edit, Loader2, Image as ImageIcon } from 'lucide-react'
import PromptModal from '../../components/PromptModal'
import { useNotification } from '../../context'
import { fetchWebsiteCoachEditor, updateWebsiteCoach, type WebsiteCoach, type WebsiteCoachWrite } from '../../api/websiteCoachEditor'

const KEY = ['admin', 'website-coach-editor']
const PROFILE_SECTIONS = ['個人經歷', '教學理念', '自我介紹', '滑雪經驗']

export function profileSectionText(profile: Record<string, unknown> | undefined, title: string): string {
  const section = (Array.isArray(profile?.sections) ? profile.sections : []).find(item => item && item.title === title)
  return Array.isArray(section?.lines) ? section.lines.filter((line: unknown) => typeof line === 'string').join('\n') : ''
}

export function websiteCoachValues(values: Record<string, string>, existing?: WebsiteCoach): WebsiteCoachWrite {
  const profile = existing?.website_profile || {}
  const sections = Array.isArray(profile.sections) ? profile.sections.filter(section => section && typeof section.title === 'string').map(section => ({ ...section })) : []
  for (const title of PROFILE_SECTIONS) {
    const text = values['profile_' + title]
    if (text === undefined) continue
    const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean)
    const index = sections.findIndex(section => section.title === title)
    if (index >= 0) sections[index] = { ...sections[index], lines }
    else if (lines.length) sections.push({ title, lines })
  }
  return {
    img: values.img.trim(),
    website_slug: values.website_slug.trim().toLowerCase(),
    website_sort_order: Number(values.website_sort_order),
    website_card_bio: values.website_card_bio.trim(),
    website_enabled: values.website_enabled === 'true',
    ...(existing ? { website_profile: { ...profile, sections } } : {}),
  }
}

export function validateWebsiteCoach(values: Record<string, string>): string | undefined {
  const data = websiteCoachValues(values)
  if (data.website_enabled && !data.website_slug) return '上架前請填寫官網代號'
  if (data.website_slug && !/^[a-z0-9_-]+$/.test(data.website_slug)) return '官網代號只能使用英文字母、數字、短橫線或底線'
  if (!values.website_sort_order.trim() || !Number.isSafeInteger(data.website_sort_order) || data.website_sort_order < -2147483648 || data.website_sort_order > 2147483647) return '排序請填寫有效整數'
  if (data.website_card_bio.length > 160) return '卡片簡介最多160字'
  if (data.img) {
    const message = '照片請填寫 http/https 網址或站內圖片路徑（最多200字）'
    if (data.img.length > 200 || /[\\\x00-\x1f\x7f]/.test(values.img)) return message
    if (!/^\/(?!\/)/.test(data.img)) {
      try {
        const url = new URL(data.img)
        if (!/^https?:$/.test(url.protocol) || !url.hostname) return message
      } catch { return message }
    }
  }
}

export default function CoachEditorPage() {
  const notify = useNotification()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [editing, setEditing] = useState<WebsiteCoach | null>(null)
  const { data: coaches = [], isLoading, error, refetch } = useQuery({ queryKey: KEY, queryFn: fetchWebsiteCoachEditor })
  const mutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: WebsiteCoachWrite }) => updateWebsiteCoach(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY })
      qc.invalidateQueries({ queryKey: ['admin', 'coaches'] })
      notify.success('官網教練資料已更新')
      setEditing(null)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || e.response?.data?.detail || Object.values(e.response?.data || {}).flat().join('；') || '儲存失敗，請重試'),
  })
  const keyword = search.trim().toLowerCase()
  const filtered = coaches.filter(coach => (!keyword || (coach.name + ' ' + coach.website_slug).toLowerCase().includes(keyword))
    && (!status || String(coach.website_enabled) === status))

  return <div className="space-y-6 text-gray-900 dark:text-white">
    <div>
      <h1 className="text-2xl font-bold">教練介紹</h1>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">與「教練管理」使用同一份資料；此處只調整官網照片、卡片簡介、排序與上架狀態。</p>
      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">新增教練、姓名、教學語言、證照及排課設定，請由管理員在「基本設定 → 教練管理」修改。</p>
    </div>
    <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 sm:flex-row">
      <input aria-label="搜尋教練" placeholder="搜尋姓名或官網代號" value={search} onChange={e => setSearch(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900 dark:text-white" />
      <select aria-label="官網顯示狀態" value={status} onChange={e => setStatus(e.target.value)} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900 dark:text-white">
        <option value="">全部狀態</option><option value="true">官網上架</option><option value="false">官網下架</option>
      </select>
    </div>
    {isLoading ? <div className="flex justify-center py-12"><Loader2 className="animate-spin" aria-label="載入教練資料" /></div>
      : error ? <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-5 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">無法載入教練資料。<button type="button" onClick={() => refetch()} className="ml-3 underline">重新載入</button></div>
      : <div className="space-y-3">
        <p className="text-sm text-gray-500 dark:text-gray-400">共 {filtered.length} 位教練</p>
        {!filtered.length && <div className="rounded-xl border border-gray-200 bg-white p-8 text-center text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">{coaches.length ? '沒有符合條件的教練，請調整搜尋或狀態。' : '尚無教練資料，請先由管理員在教練管理建立。'}</div>}
        {filtered.map(coach => <div key={coach.id} className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 dark:bg-gray-700">{coach.img ? <img key={coach.img} src={coach.img} alt={coach.name} loading="lazy" className="h-full w-full object-cover" onError={e => { e.currentTarget.hidden = true }} /> : <ImageIcon className="text-gray-400" />}</div>
          <div className="min-w-0 flex-1"><p className="break-words font-semibold">{coach.name}</p><p className="mt-1 break-all text-xs text-gray-500 dark:text-gray-400">{coach.website_slug || '尚未設定官網代號'} · 排序 {coach.website_sort_order}</p><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{coach.website_enabled ? '官網上架' : '官網下架'}</p></div>
          <button type="button" disabled={!coach.can_manage} title={coach.can_manage ? '編輯官網資料' : '跨校區教練請由總部修改'} onClick={() => setEditing(coach)} className="flex min-h-11 shrink-0 items-center gap-1 rounded-lg px-3 text-sm text-violet-600 hover:bg-violet-50 disabled:opacity-50 dark:text-violet-400 dark:hover:bg-violet-900/20" aria-label={'編輯' + coach.name}><Edit size={16} />{coach.can_manage ? '編輯' : '總部管理'}</button>
        </div>)}
      </div>}
    <PromptModal open={!!editing} title={'編輯官網介紹：' + (editing?.name || '')} description="儲存後，官網列表重新載入即使用這份設定。下架不會刪除教練或影響既有課程。"
      fields={[
        { name: 'img', label: '照片網址', defaultValue: editing?.img || '', placeholder: 'https://… 或站內圖片路徑' },
        { name: 'website_slug', label: '官網代號', defaultValue: editing?.website_slug || '', helper: '修改代號會改變對外網址，請同步更新已分享的連結。' },
        { name: 'website_card_bio', label: '卡片簡介（最多160字）', type: 'textarea', defaultValue: editing?.website_card_bio || '' },
        { name: 'website_sort_order', label: '顯示排序（數字小的在前）', type: 'number', required: true, defaultValue: String(editing?.website_sort_order ?? 0) },
        { name: 'website_enabled', label: '官網顯示', type: 'select', defaultValue: String(editing?.website_enabled ?? false), options: [{ value: 'true', label: '上架' }, { value: 'false', label: '下架' }] },
        ...PROFILE_SECTIONS.map(title => ({ name: 'profile_' + title, label: title, type: 'textarea' as const,
          defaultValue: profileSectionText(editing?.website_profile, title),
          helper: '每行一個段落；儲存文字不會移除原有圖片或影片。' })),
      ]} submitLabel="儲存變更" validate={validateWebsiteCoach} onCancel={() => setEditing(null)}
      onSubmit={async values => { if (!editing) return; try { await mutation.mutateAsync({ id: editing.id, data: websiteCoachValues(values, editing) }) } catch { /* Keep the form open; onError shows the server response. */ } }} />
  </div>
}
