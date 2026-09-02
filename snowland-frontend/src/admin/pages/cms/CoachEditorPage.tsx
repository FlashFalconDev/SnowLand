/**
 * 教練介紹 CMS — 採用 console 列表頁樣式
 */
import { useState } from 'react'
import { Search, Plus, Edit, Trash2, Eye, EyeOff, X, Image as ImageIcon } from 'lucide-react'

const PRIMARY = '#8b5cf6'

const mockCoaches = [
  { id: 1, slug: 'cash', name: 'Cash 校長', type: '單板 / 雙板', languages: '英/粵/中/台', priority: 'director', image: '/coach-images/Cash 校長.jpg', published: true },
  { id: 2, slug: 'lily', name: 'Lily 總監', type: '單板', languages: '中/英/日', priority: 'director', image: '/coach-images/Lily 總監.jpg', published: true },
  { id: 3, slug: 'qizhen', name: '七針', type: '單板 / 雙板', languages: '中/英', priority: 'Lv3', image: '/coach-images/七針.jpg', published: true },
  { id: 4, slug: 'dylan', name: 'Dylan', type: '雙板', languages: '中/英', priority: 'Lv2', image: '/coach-images/Dylan.jpg', published: true },
  { id: 5, slug: 'eric', name: 'Eric', type: '單板', languages: '中', priority: 'Lv2', image: '/coach-images/Eric.jpg', published: true },
  { id: 6, slug: 'naomi', name: 'Naomi', type: '雙板', languages: '中/日', priority: 'Lv1', image: '/coach-images/Naomi.jpg', published: false },
]

const priorityStyles: Record<string, string> = {
  director: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  Lv3: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  Lv2: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  Lv1: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
}

const priorityLabels: Record<string, string> = {
  director: '校長 / 總監',
  Lv3: 'Lv3',
  Lv2: 'Lv2',
  Lv1: 'Lv1',
}

export default function CoachEditorPage() {
  const [search, setSearch] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')

  const filtered = mockCoaches.filter((c) => {
    const matchSearch =
      !search ||
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.slug.includes(search.toLowerCase())
    const matchStatus =
      !statusFilter ||
      (statusFilter === 'published' && c.published) ||
      (statusFilter === 'draft' && !c.published)
    const matchPriority = !priorityFilter || c.priority === priorityFilter
    return matchSearch && matchStatus && matchPriority
  })

  const editing = editingId ? mockCoaches.find((c) => c.id === editingId) : null

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* 頁面標題 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            教練介紹
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            編輯官網顯示的教練資料、照片、簡介
          </p>
        </div>
        <button
          className="px-4 py-2 text-white font-medium rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2"
          style={{ backgroundColor: PRIMARY }}
        >
          <Plus size={18} />
          新增教練
        </button>
      </div>

      {/* 搜尋與篩選 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={18} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:border-transparent"
              style={{ '--tw-ring-color': PRIMARY } as any}
              placeholder="搜尋教練姓名或代號..."
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2"
          >
            <option value="">全部狀態</option>
            <option value="published">上架</option>
            <option value="draft">下架</option>
          </select>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2"
          >
            <option value="">全部等級</option>
            <option value="director">校長 / 總監</option>
            <option value="Lv3">Lv3</option>
            <option value="Lv2">Lv2</option>
            <option value="Lv1">Lv1</option>
          </select>
        </div>
      </div>

      {/* 表格 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
            <tr>
              <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">教練</th>
              <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden md:table-cell">板型</th>
              <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden lg:table-cell">語言</th>
              <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">等級</th>
              <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">狀態</th>
              <th className="px-5 py-3 text-right font-medium text-gray-600 dark:text-gray-300">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {filtered.map((coach) => (
              <tr
                key={coach.id}
                className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-gray-100 dark:bg-gray-700 overflow-hidden flex-shrink-0">
                      <img src={coach.image} alt={coach.name} className="w-full h-full object-cover" loading="lazy" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{coach.name}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 font-mono">/{coach.slug}</p>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-4 text-sm text-gray-600 dark:text-gray-300 hidden md:table-cell">{coach.type}</td>
                <td className="px-5 py-4 text-sm text-gray-600 dark:text-gray-300 hidden lg:table-cell">{coach.languages}</td>
                <td className="px-5 py-4">
                  <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${priorityStyles[coach.priority]}`}>
                    {priorityLabels[coach.priority]}
                  </span>
                </td>
                <td className="px-5 py-4">
                  {coach.published ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                      <Eye size={12} />上架
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                      <EyeOff size={12} />下架
                    </span>
                  )}
                </td>
                <td className="px-5 py-4 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => setEditingId(coach.id)}
                      className="p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                      style={{ '--hover-color': PRIMARY } as any}
                      onMouseEnter={(e) => (e.currentTarget.style.color = PRIMARY)}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '')}
                    >
                      <Edit size={16} />
                    </button>
                    <button className="p-2 text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors">
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-16 text-center text-sm text-gray-500 dark:text-gray-400">
                  沒有符合條件的教練
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {/* 分頁 */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            共 <span className="font-medium">{filtered.length}</span> 位教練
          </div>
        </div>
      </div>

      {/* 編輯抽屜 */}
      {editing && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50 animate-fadeIn"
            onClick={() => setEditingId(null)}
          />
          <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col animate-slideIn">
            {/* Header - 漸層 */}
            <div
              className="px-6 py-4 flex items-center justify-between"
              style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #1f4a6f 100%)` }}
            >
              <h2 className="text-lg font-semibold text-white">
                編輯教練：{editing.name}
              </h2>
              <button
                onClick={() => setEditingId(null)}
                className="text-white/80 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {/* Form */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* 大頭照 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">大頭照</label>
                <div className="flex items-center gap-4">
                  <div className="h-24 w-24 rounded-lg bg-gray-50 dark:bg-gray-700 overflow-hidden border-2 border-dashed border-gray-300 dark:border-gray-600">
                    <img src={editing.image} alt="" className="w-full h-full object-cover" />
                  </div>
                  <div>
                    <button className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors flex items-center gap-2">
                      <ImageIcon size={14} />
                      更換照片
                    </button>
                    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">建議 800×1000，最大 2MB</p>
                  </div>
                </div>
              </div>

              {/* 基本資料 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                    姓名 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    defaultValue={editing.name}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">代號 (URL)</label>
                  <input
                    type="text"
                    defaultValue={editing.slug}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white font-mono focus:outline-none focus:ring-2"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">板型</label>
                  <select className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2">
                    <option>單板</option>
                    <option>雙板</option>
                    <option>單板 / 雙板</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">教學語言</label>
                  <input
                    type="text"
                    defaultValue={editing.languages}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2"
                    placeholder="例如：中/英/日"
                  />
                </div>
              </div>

              {/* 卡片簡介 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">卡片簡介</label>
                <textarea
                  rows={3}
                  defaultValue="救護專業及多國雪場經歷，重視安全，陪伴學生探索無限可能性。"
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 resize-none"
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">顯示在首頁與教練列表的簡短介紹（建議 50 字內）</p>
              </div>

              {/* 詳細介紹 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">詳細介紹</label>
                <div className="border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden">
                  <div className="flex items-center gap-1 px-3 py-2 border-b border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700">
                    <button className="px-2 py-1 text-xs hover:bg-white dark:hover:bg-gray-600 rounded">B</button>
                    <button className="px-2 py-1 text-xs hover:bg-white dark:hover:bg-gray-600 rounded italic">I</button>
                    <button className="px-2 py-1 text-xs hover:bg-white dark:hover:bg-gray-600 rounded">H2</button>
                    <button className="px-2 py-1 text-xs hover:bg-white dark:hover:bg-gray-600 rounded">• 列表</button>
                    <div className="h-4 w-px bg-gray-300 dark:bg-gray-600" />
                    <button className="px-2 py-1 text-xs hover:bg-white dark:hover:bg-gray-600 rounded">插入圖片</button>
                  </div>
                  <textarea
                    rows={6}
                    placeholder="教練的個人經歷、教學理念、專業證照..."
                    className="w-full px-3 py-2 bg-white dark:bg-gray-800 text-sm dark:text-white focus:outline-none resize-none"
                  />
                </div>
              </div>

              {/* 上架狀態 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">官網顯示</label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    defaultChecked={editing.published}
                    className="h-4 w-4 rounded border-gray-300"
                    style={{ accentColor: PRIMARY }}
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">在官網教練列表顯示</span>
                </label>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
              <button className="text-sm text-red-600 hover:text-red-700 dark:text-red-400">
                刪除教練
              </button>
              <div className="flex gap-3">
                <button
                  onClick={() => setEditingId(null)}
                  className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
                >
                  取消
                </button>
                <button
                  className="px-4 py-2 text-white font-medium rounded-lg hover:opacity-90 transition-opacity"
                  style={{ backgroundColor: PRIMARY }}
                >
                  儲存變更
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
