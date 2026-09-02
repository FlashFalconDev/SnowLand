# Site Data Layer - 待替換為 API

## 現況
這些檔案是從 kkrisw/snowland 搬過來的靜態資料，目前直接 import 使用。

## 替換計畫
未來應從 Django API 動態拉取，讓不同租戶有不同的資料。

### 替換對照表

| 靜態檔案 | Django Model | API 端點 | 使用的頁面 |
|---------|-------------|---------|-----------|
| `coaches.js` | `Coach` | `/api/{client}/coaches/` | HomePage, CoachTeamPage, CoachPage, BookingPage |
| `cashReviews.js`, `lilyReviews.js`, `reviews/*.json` | `Review` (待建) | `/api/{client}/reviews/` | CoachPage, HomePage |
| `faqContent.js` | `FAQ` (待建) | `/api/{client}/faq/` | FaqPage |
| `skiResorts.ts` | `Resorts` | `/api/{client}/resorts/` | SkiResortsPage, HokkaidoMap |
| `guidesArticles.js`, `guideArticlesContent.js` | `Article` (待建) | `/api/{client}/articles/` | GuidesCollectionPage |
| `instagramLatest.js` | 外部 API | Instagram API | HomePage |
| `legacyPages.json` | `Page` (待建) | `/api/{client}/pages/{key}/` | LegacyContentPage, AboutPage |
| `footerPagesContent.js` | 同上 | 同上 | BookingPage |
| `resortLegacyData.js`, `resortNavigation.js` | `Resorts` | `/api/{client}/resorts/{slug}/` | ResortCoursePage, TomamuCoursePage |
| `navigationLinks.js` | `SiteSetting` (待建) | `/api/{client}/settings/` | SiteHeader |
| `assetPaths.js` | `SiteSetting` | `/api/{client}/settings/` | 全站 |

### 替換步驟（每個資料源）

1. 確認 Django Model 和 API 已建好
2. 在 `src/api/site.ts` 建立 API 呼叫函數
3. 在頁面中用 React Query 替換靜態 import
4. 刪除對應的靜態檔案

### 範例：替換 coaches.js

```tsx
// 之前（靜態）
import coaches from '../../data/site/coaches';

// 之後（動態）
import { useQuery } from '@tanstack/react-query';
import { fetchCoaches } from '@/api/site';

const { data: coaches = [] } = useQuery({
  queryKey: ['coaches', clientCode],
  queryFn: () => fetchCoaches(clientCode),
  staleTime: 5 * 60 * 1000, // 5 分鐘快取
});
```
