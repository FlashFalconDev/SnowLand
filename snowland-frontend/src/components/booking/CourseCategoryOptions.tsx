export default function CourseCategoryOptions({ categories, status, selected, onSelect, onRetry }: {
  categories: {id: number; name: string}[]; status: 'loading' | 'ready' | 'error'; selected: number | null
  onSelect: (id: number, name: string) => void; onRetry: () => void
}) {
  if (status === 'loading') return <p role="status" className="py-8 text-center text-sm text-[#6b7280]">載入課程大類中...</p>
  if (status === 'error') return <div role="alert" className="py-8 text-center text-sm text-red-600">
    <p>課程資料暫時無法載入，請稍後再試。</p>
    <button type="button" onClick={onRetry} className="mt-3 min-h-11 rounded-full border border-current px-5">重新載入課程</button>
  </div>
  if (!categories.length) return <p role="status" className="py-8 text-center text-sm text-[#6b7280]">目前尚未開放此服務的可預約課程，請改選其他服務或聯絡我們。</p>
  return <div className="mx-auto grid max-w-3xl grid-cols-1 gap-3 md:grid-cols-2">{categories.map(category => <button key={category.id} type="button"
    aria-pressed={selected === category.id} onClick={() => onSelect(category.id, category.name)}
    className={`rounded-sm border-2 p-5 text-left transition-colors ${selected === category.id ? 'border-[#2b5f8f] bg-[#e9eef3]' : 'border-[#e5e9f2] bg-white hover:border-[#2b5f8f]'}`}>
    <span className="font-semibold text-[#1f2937] font-display">{category.name}</span>
  </button>)}</div>
}
