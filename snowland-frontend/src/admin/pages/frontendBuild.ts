export interface BuildEntry { path: string; file: File }

export function prepareFrontendBuild(files: File[]): { entries: BuildEntry[]; bytes: number } {
  const raw = files.map(file => ({ file, path: file.webkitRelativePath || file.name }))
  const directory = raw.length && raw.every(item => item.path.includes('/')) ? raw[0].path.split('/')[0] + '/' : ''
  if (directory && raw.some(item => !item.path.startsWith(directory))) throw new Error('請一次選擇一個完整的 dist 資料夾。')
  const entries = raw.map(item => ({ ...item, path: directory ? item.path.slice(directory.length) : item.path }))
    .filter(item => !item.path.split('/').some(part => part.startsWith('.') || part === '__MACOSX'))
  if (!entries.some(item => item.path === 'index.html' && item.file.size > 0)) throw new Error('資料夾根目錄找不到 index.html，請選擇建置完成的 dist。')
  if (entries.length > 3000) throw new Error('檔案超過 3,000 個，請確認選擇的是 dist，而非原始碼資料夾。')
  const seen = new Set<string>()
  for (const item of entries) {
    if (!item.path || item.path.length > 500 || /[\\:\x00<>|?*]/.test(item.path) || item.path.split('/').some(part => !part || part === '..')) throw new Error('資料夾包含不支援的路徑。')
    if (seen.has(item.path.toLowerCase())) throw new Error('資料夾包含重複的檔案路徑。')
    seen.add(item.path.toLowerCase())
    if (item.file.size > 100 * 1024 * 1024) throw new Error('單一檔案不得超過 100 MB。')
  }
  const bytes = entries.reduce((total, item) => total + item.file.size, 0)
  if (bytes > 1024 * 1024 * 1024) throw new Error('建置資料夾總大小不得超過 1 GB。')
  return { entries, bytes }
}
