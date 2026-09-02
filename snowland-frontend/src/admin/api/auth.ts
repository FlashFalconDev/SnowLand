/**
 * 後台認證 API
 *
 * 後台登入跟預約系統共用同一套 Google/LINE OAuth（一次登入處處可用）。
 * 這個檔案只剩下「驗證當前登入者是否為 manager」的 endpoint。
 */

export interface AdminUser {
  id: number
  username: string
  email: string
  name: string
  is_superuser?: boolean
  is_manager?: boolean
  is_coach?: boolean
  permissions?: string[]
}

export interface AdminMeResult {
  user: AdminUser | null
  errorCode: number | null
  errorMsg: string
}

function getClientCode(): string {
  const parts = window.location.pathname.split('/').filter(Boolean)
  if (parts[0] && parts[0] !== 'auth') return parts[0]

  const fromStorage = localStorage.getItem('client_code')
  if (fromStorage) return fromStorage

  return 'snowland'
}

/**
 * 取得當前登入的管理員資訊
 * 用原生 fetch 避免任何 axios 隱藏行為，明確帶 credentials
 * 走相對路徑（同 origin），由 vite proxy / nginx 轉到後端
 */
export async function fetchAdminMe(): Promise<AdminMeResult> {
  const clientCode = getClientCode()
  const url = `/api/admin/${clientCode}/me/`

  console.log('[AdminMe] Calling:', url)

  try {
    const res = await fetch(url, {
      method: 'GET',
      credentials: 'include',  // 強制帶 cookie
      headers: { 'Content-Type': 'application/json' },
    })

    console.log('[AdminMe] Status:', res.status)

    const data = await res.json().catch(() => ({}))
    console.log('[AdminMe] Body:', data)

    if (res.ok && data.code === 200) {
      return { user: data.data, errorCode: null, errorMsg: '' }
    }
    return {
      user: null,
      errorCode: res.status,
      errorMsg: data.msg || data.detail || `HTTP ${res.status}`,
    }
  } catch (e: any) {
    console.error('[AdminMe] Error:', e)
    return { user: null, errorCode: -1, errorMsg: e?.message || '網路錯誤' }
  }
}
