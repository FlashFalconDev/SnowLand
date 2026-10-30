// Authentication is shared; application data and browser state are school-scoped.
const reserved = new Set(['auth', 'api', 'booking', 'control', 'admin', 'login', 'payment'])
export function clientCodeFromPath(pathname: string): string | null {
  const first = pathname.split('/').filter(Boolean)[0] || ''
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,49}$/.test(first) && !reserved.has(first.toLowerCase()) ? first : null
}
export function currentClientCode(): string {
  const fromPath = typeof window !== 'undefined' ? clientCodeFromPath(window.location.pathname) : null
  if (fromPath) return fromPath
  // Only authentication callbacks may resume a previously selected school.
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/auth/')) {
    const stored = localStorage.getItem('client_code') || ''
    const code = clientCodeFromPath('/' + stored)
    if (code && code === stored) return code
  }
  throw new Error('請先選擇學校，再繼續操作')
}
export function campusScopeKey(clientCode: string): string {
  return `admin-campus-scope:${clientCode}`
}

export function tenantReturnPath(value: string | null, clientCode: string): string {
  const fallback = `/${clientCode}`
  if (!value?.startsWith('/') || value.startsWith('//')) return fallback
  try {
    const url = new URL(value, 'https://tenant.invalid')
    if (url.origin !== 'https://tenant.invalid' || clientCodeFromPath(url.pathname) !== clientCode) return fallback
    return url.pathname + url.search + url.hash
  } catch { return fallback }
}

export function schoolBookingApiPath(path: string): string {
  return `/booking/${encodeURIComponent(currentClientCode())}/api${path}`
}
