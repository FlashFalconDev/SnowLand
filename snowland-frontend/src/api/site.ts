/**
 * Site (brand website) API calls
 *
 * 目前官網資料都是靜態 JSON/JS，未來替換成這些 API 呼叫。
 * 每個函數對應一個靜態資料檔案，替換時只需：
 *   1. 在頁面中用 React Query 呼叫這些函數
 *   2. 刪除對應的 data/site/ 靜態檔案
 *
 * 所有 API 都帶 clientCode，實現多租戶隔離。
 */

import api from './axios'

// ============ 教練 ============
// 替換: data/site/coaches.js
export async function fetchCoaches(clientCode: string) {
  const res = await api.get(`/api/${clientCode}/site/coaches/`)
  return res.data
}

// 替換: data/site/cashReviews.js, lilyReviews.js, reviews/*.json
export async function fetchCoachReviews(clientCode: string, coachSlug: string) {
  const res = await api.get(`/api/${clientCode}/site/coaches/${coachSlug}/reviews/`)
  return res.data
}

// ============ 雪場 ============
// 替換: data/site/skiResorts.ts, resortLegacyData.js, resortNavigation.js
export async function fetchResorts(clientCode: string) {
  const res = await api.get(`/api/${clientCode}/site/resorts/`)
  return res.data
}

export async function fetchResortDetail(clientCode: string, resortSlug: string) {
  const res = await api.get(`/api/${clientCode}/site/resorts/${resortSlug}/`)
  return res.data
}

// ============ 文章/攻略 ============
// 替換: data/site/guidesArticles.js, guideArticlesContent.js
export async function fetchArticles(clientCode: string, category?: string) {
  const params = category ? { category } : {}
  const res = await api.get(`/api/${clientCode}/site/articles/`, { params })
  return res.data
}

// ============ FAQ ============
// 替換: data/site/faqContent.js
export async function fetchFAQ(clientCode: string) {
  const res = await api.get(`/api/${clientCode}/site/faq/`)
  return res.data
}

// ============ 頁面內容 ============
// 替換: data/site/legacyPages.json, footerPagesContent.js
export async function fetchPageContent(clientCode: string, pageKey: string) {
  const res = await api.get(`/api/${clientCode}/site/pages/${pageKey}/`)
  return res.data
}

// ============ 評論（首頁用） ============
// 替換: HomePage 裡寫死的 reviews 陣列
export async function fetchReviews(clientCode: string) {
  const res = await api.get(`/api/${clientCode}/site/reviews/`)
  return res.data
}

// ============ 網站設定 ============
// 替換: data/site/assetPaths.js, navigationLinks.js
export async function fetchSiteSettings(clientCode: string) {
  const res = await api.get(`/api/${clientCode}/site/settings/`)
  return res.data
}

// ============ Instagram ============
// 替換: data/site/instagramLatest.js
export async function fetchInstagramPosts(clientCode: string) {
  const res = await api.get(`/api/${clientCode}/site/instagram/`)
  return res.data
}

// ============ 優惠活動 ============
// 替換: SpecialOffers 裡寫死的資料
export async function fetchSpecialOffers(clientCode: string) {
  const res = await api.get(`/api/${clientCode}/site/offers/`)
  return res.data
}
