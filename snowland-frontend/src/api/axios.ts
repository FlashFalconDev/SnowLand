import axios from 'axios'

// 🔥 從 Cookie 中獲取 CSRF Token
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

// 🔥 獲取當前的 client_code
const getClientCode = (): string => {
  // 1. 從 URL 獲取（例如：/snowland/xxx），避免舊 localStorage 打到錯租戶
  const pathParts = window.location.pathname.split('/').filter(Boolean)
  if (pathParts.length > 0 && pathParts[0] !== 'auth') {
    return pathParts[0]
  }

  // 2. 沒有網址租戶時才使用 localStorage
  const clientCode = localStorage.getItem('client_code')
  if (clientCode) return clientCode

  // 3. 預設值（開發用）
  return 'snowland'
}

// 🔥 後端 API URL — 一律走相對路徑，由 vite proxy（dev）或 nginx（prod）轉到後端
// 這樣前後端在同一個 origin，瀏覽器把 cookie 當 first-party，不會被 Chrome 148 的
// Storage Access policies 擋掉（sec-fetch-storage-access: none 問題）
const getBaseURL = (): string => '/booking'

// 建立 axios 實例
const api = axios.create({
  baseURL: `${getBaseURL()}/api`, // 🔥 會在請求攔截器中動態加入 client_code
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // 🔥 允許跨域攜帶 cookie（用於 session）
})

// 請求攔截器
api.interceptors.request.use(
  (config) => {
    // 🔥 動態加入 client_code 到 URL
    const clientCode = getClientCode()

    // 🔥 修改 baseURL：保留原本的 baseURL，只修改路徑部分
    if (config.baseURL) {
      const baseURL = getBaseURL()
      config.baseURL = `${baseURL}/${clientCode}/api`
    }

    // 🔥 加入 CSRF Token 到 header（Django CSRF 保護）
    const csrfToken = getCsrfToken()
    if (csrfToken && config.headers) {
      config.headers['X-CSRFToken'] = csrfToken
    }

    // 可以在這裡加入 token
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 響應攔截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default api
