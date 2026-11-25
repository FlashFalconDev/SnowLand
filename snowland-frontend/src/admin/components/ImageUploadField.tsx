import { useRef, useState } from 'react'

export const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
export const DEFAULT_IMAGE_MAX_BYTES = 5 * 1024 * 1024

export function cleanImageValue(value: unknown): string {
  if (typeof value !== 'string') return ''
  const text = value.trim()
  return text === 'None' || text === 'null' || text === 'undefined' ? '' : text
}

export function validateImageFile(file: { type: string; size: number }, maxBytes = DEFAULT_IMAGE_MAX_BYTES): string | undefined {
  if (!IMAGE_TYPES.includes(file.type)) return '照片僅支援 JPEG、PNG、WebP'
  if (file.size <= 0) return '檔案是空的，請重新選擇'
  if (file.size > maxBytes) return `照片不可超過 ${Math.floor(maxBytes / 1024 / 1024)} MB`
}

interface Props {
  id: string
  name: string
  value: string
  onChange: (value: string) => void
  /** 未提供時隱藏上傳，只保留貼上網址／站內路徑。 */
  upload?: (file: File, onProgress: (percent: number) => void) => Promise<string>
  maxBytes?: number
  placeholder?: string
}

const inputClass = 'w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30'

/** 以上傳為主：選檔 → 驗證 → 上傳 → 預覽；下方仍可貼上網址或站內路徑。 */
export default function ImageUploadField({ id, name, value, onChange, upload, maxBytes = DEFAULT_IMAGE_MAX_BYTES, placeholder }: Props) {
  const [error, setError] = useState('')
  const [progress, setProgress] = useState<number | null>(null)
  const [broken, setBroken] = useState(false)
  const fileRef = useRef<HTMLInputElement | null>(null)
  const current = cleanImageValue(value)

  const handleFile = async (event: { target: { files?: FileList | null } }) => {
    const file = event.target.files?.[0]
    if (!file || !upload) return
    const invalid = validateImageFile(file, maxBytes)
    if (invalid) { setError(invalid); if (fileRef.current) fileRef.current.value = ''; return }
    setError(''); setProgress(0)
    try {
      onChange(await upload(file, setProgress)); setBroken(false)
    } catch (failure) {
      const message = failure && typeof failure === 'object' && 'message' in failure && typeof failure.message === 'string' ? failure.message : ''
      setError(message || '上傳失敗，請稍後再試，或改貼上照片網址')
    } finally {
      setProgress(null)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return <div className="space-y-2">
    <div className="flex items-center gap-3">
      <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 text-xs text-gray-400 dark:bg-gray-700">
        {current && !broken ? <img key={current} src={current} alt="照片預覽" className="h-full w-full coach-photo" onError={() => setBroken(true)} /> : '無預覽'}
      </div>
      {upload && <div className="min-w-0 flex-1">
        <input ref={fileRef} type="file" accept={IMAGE_TYPES.join(',')} aria-label="選擇照片檔案" disabled={progress !== null} onChange={handleFile} className="block w-full text-sm text-gray-700 dark:text-gray-300" />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">支援 JPEG、PNG、WebP，最大 {Math.floor(maxBytes / 1024 / 1024)} MB。</p>
        {progress !== null && <p role="status" className="mt-1 text-xs text-violet-600">上傳中 {progress}%</p>}
      </div>}
    </div>
    {error && <p role="alert" className="text-xs text-red-600 dark:text-red-400">{error}</p>}
    <input id={id} name={name} type="text" value={current} placeholder={placeholder} aria-label="照片網址（後備）"
      onChange={event => { setBroken(false); onChange(event.target.value) }} className={inputClass} />
  </div>
}
