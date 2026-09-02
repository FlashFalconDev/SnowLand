/**
 * 後台 API 專用 axios 實例
 * URL 結構：/api/admin/<client_code>/<resource>/
 */
import axios from 'axios'

const getCsrfToken = (): string | null => {
  const name = 'csrftoken'
  const cookies = document.cookie.split(';')
  for (let cookie of cookies) {
    cookie = cookie.trim()
    if (cookie.startsWith(name + '=')) {
      return cookie.substring(name.length + 1)
    }
  }
  return null
}

const getClientCode = (): string => {
  const pathParts = window.location.pathname.split('/').filter(Boolean)
  if (pathParts.length > 0 && pathParts[0] !== 'auth') {
    return pathParts[0]
  }

  const clientCode = localStorage.getItem('client_code')
  if (clientCode) return clientCode

  return 'snowland'
}

// 一律走相對路徑（vite proxy / nginx），讓前後端同 origin，避開跨站 cookie 問題
const getBaseURL = (): string => ''

const adminApi = axios.create({
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

adminApi.interceptors.request.use(
  (config) => {
    const clientCode = getClientCode()
    const baseURL = getBaseURL()
    config.baseURL = `${baseURL}/api/admin/${clientCode}`

    const csrfToken = getCsrfToken()
    if (csrfToken && config.headers) {
      config.headers['X-CSRFToken'] = csrfToken
    }

    return config
  },
  (error) => Promise.reject(error)
)

adminApi.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('[Admin API Error]', error.response?.status, error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export default adminApi
