import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const dataDir = path.join(root, 'snowland-frontend', 'src', 'data', 'site');
const outputPath = path.join(root, 'snowland', 'Client', 'fixtures', 'site_content_defaults.json');

const readModuleValue = (filename, variableName) => {
  const source = fs
    .readFileSync(path.join(dataDir, filename), 'utf8')
    .replace(new RegExp(`export\\s+default\\s+${variableName}\\s*;?\\s*$`), '');
  return Function(`"use strict";\n${source}\nreturn ${variableName};`)();
};

const legacyPages = JSON.parse(fs.readFileSync(path.join(dataDir, 'legacyPages.json'), 'utf8'));
const guidesArticles = readModuleValue('guidesArticles.js', 'guidesArticles');
const faqSections = readModuleValue('faqContent.js', 'faqSections');
const skiResorts = readModuleValue('skiResorts.ts', 'skiResorts');
const resortLegacyData = readModuleValue('resortLegacyData.js', 'resortLegacyData');
const guideArticlesContent = readModuleValue('guideArticlesContent.js', 'guideArticlesContent');
const instagramLatest = readModuleValue('instagramLatest.js', 'instagramLatest');
const additionalResorts = [
  { slug: 'asahikawasantapresentpark', nameChinese: '聖誕禮物公園', nameEnglish: 'Asahikawa Santa Present Park', region: '道北', tags: ['夜滑雪道', '親子同樂', '新手友善', '城市近郊'], imagePlaceholder: '/legacy/guides/image-02.png', route: '/course/asahikawasantapresentpark' },
  { slug: 'furano', nameChinese: '富良野', nameEnglish: 'Furano Ski Resort', region: '道北', tags: ['Ski in-out', '新手友善', '夜滑雪道', '天然溫泉', '戶外活動豐富', '親子樂園', '觀光飯店'], imagePlaceholder: '/legacy/guides/image-03.png', route: '/course/furano' },
  { slug: 'pippu', nameChinese: '比布', nameEnglish: 'Pippu Ski Resort', region: '道北', tags: ['夜滑雪道', '長距離滑行', '新手友善', '親子同樂'], imagePlaceholder: '/legacy/guides/image-04.jpg', route: '/course/pippu' },
  { slug: 'canmore', nameChinese: '坎莫爾', nameEnglish: 'Canmore Ski Village - Higashikawa', region: '道北', tags: ['夜滑雪道', '鄰近旭川', '親子友善', '小型雪場'], imagePlaceholder: '/legacy/guides/image-05.png', route: '/course/canmore' },
  { slug: 'onze', nameChinese: 'ONZE', nameEnglish: 'Snow Cruise Onze', region: '道央', tags: ['夜滑雪道', '鄰近小樽', '新手友善', '市區近郊'], imagePlaceholder: '/legacy/guides/image-06.jpg', route: '/course/onze' },
  { slug: 'asari', nameChinese: '朝里川', nameEnglish: 'Asarigawa Onsen Ski Resort', region: '道央', tags: ['夜滑雪道', '鄰近小樽', '親子同樂', '溫泉'], imagePlaceholder: '/legacy/guides/image-07.png', route: '/course/asari' },
];
const siteResorts = [...skiResorts.filter((resort) => resort.slug !== 'niseko-annupuri'), ...additionalResorts];

const officialNotice = (url) => `<p><strong>資料說明：</strong>目前顯示官方最後公布的 2025-26 雪季資訊；2026-27 日期與現場價格請以雪場公告為準。</p><p><a href="${url}" target="_blank" rel="noopener noreferrer">查看雪場官方最新公告</a></p>`;
const infoTable = (headers, rows) => `
  <div class="overflow-x-auto"><table><thead><tr>${headers.map((header) => `<th>${header}</th>`).join('')}</tr></thead>
  <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const cmsTab = (title, slug, html) => ({ title, slug, presentation: 'cms', html });

const additionalResortDetails = {
  asahikawasantapresentpark: {
    description: '距離 JR 旭川站約 15 分鐘車程的城市近郊雪場，從初學緩坡到進階路線皆有，夜間可俯瞰旭川市區夜景。',
    sourceUrl: 'https://www.asahikawasantapresentpark.com/',
    tabs: [
      cmsTab('雪道介紹', 'ski-slope', '<p>雪場曾舉辦兩次單板世界盃，適合初學者、家庭及進階滑雪者；夜滑是主要特色。</p><ul><li>一般冬季營運：約 12 月至 3 月，實際開放依積雪公告。</li><li>中心、黑色及綠色纜車最晚營運至 20:45～21:00，會依天候調整。</li></ul>'),
      cmsTab('租借雪具', 'rental', `${officialNotice('https://www.asahikawasantapresentpark.com/cont1/10.html')}${infoTable(['2025-26 參考項目', '2 小時', '5 小時', '1 日'], [['成人雙板／單板套裝', '¥3,500', '¥4,000', '¥4,500'], ['兒童雙板／單板套裝', '¥3,000', '¥3,500', '¥4,000'], ['成人套裝＋雪衣', '¥5,500', '¥6,000', '¥6,500'], ['兒童套裝＋雪衣', '¥5,000', '¥5,500', '¥6,000']])}<p>現場不接受租借預約，申請時需出示身分證件。</p>`),
      cmsTab('雪票', 'lift', `${officialNotice('https://www.asahikawasantapresentpark.com/cont1/8.html')}${infoTable(['2025-26 參考票種', '成人', '兒童'], [['2 小時券', '¥3,000', '¥2,500'], ['5 小時券', '¥3,600', '¥3,000'], ['日間券', '¥4,200', '¥3,300'], ['夜間券', '¥1,800', '¥1,100']])}`),
      cmsTab('住宿', 'accommodation', '<p>建議住宿旭川站周邊，餐飲及交通選擇較完整；從市區開車前往雪場約 15 分鐘。</p>'),
      cmsTab('交通', 'access', '<p>地址：北海道旭川市神居町富岡 555-2。</p><ul><li>旭川市中心開車約 15 分鐘。</li><li>冬季有道北巴士路線，年度班次需查閱最新時刻。</li></ul><p><a href="https://www.asahikawasantapresentpark.com/map.html" target="_blank" rel="noopener noreferrer">查看官方交通資訊</a></p>'),
    ],
  },
  furano: {
    description: '北海道代表性大型雪場之一，分為富良野與北之峰兩大區域，兼具長距離滑行、粉雪、夜滑與度假村住宿。',
    sourceUrl: 'https://www.princehotels.com/en/ski/furano/',
    tabs: [
      cmsTab('雪道介紹', 'ski-slope', '<p>富良野與北之峰兩區透過纜車及雪道相連，從寬闊初學坡到長距離進階路線都有；部分設施及雪道會依雪況分階段開放。</p><ul><li>2025-26 富良野區：2025/11/29～2026/05/06，日間 8:30～16:00 或日落；春季 9:00～16:00。</li><li>北之峰區：2025/12/20～2026/03/22，日間 8:30～16:00 或日落。</li><li>夜滑通常 16:00～18:00，年末年始及週末假日至 19:30；實際運行依天候與積雪調整。</li></ul>'),
      cmsTab('租借雪具', 'rental', `${officialNotice('https://www.princehotels.co.jp/ski/furano/winter/info/')}<p>官方與周邊店家皆提供雙板、單板、雪靴及雪衣租借，可提前線上預約。</p><ul><li>富良野纜車站：8:30～16:00 或日落。</li><li>北之峰航廈、新富良野王子大飯店：8:15～18:00 或 19:30。</li><li>最晚取件時間為各據點結束營業前 1 小時，並會隨纜車營運調整。</li></ul>`),
      cmsTab('雪票', 'lift', `${officialNotice('https://www.princehotels.com/en/ski/furano/')}${infoTable(['2025-26 參考票種', '成人', '60 歲以上'], [['一般季 1 日券', '¥8,000', '¥7,500'], ['季初／春季 1 日券', '¥6,500', '¥6,000'], ['3 小時券', '¥6,400', '¥5,900'], ['5 小時券', '¥7,200', '¥6,700']])}`),
      cmsTab('住宿', 'accommodation', '<p>新富良野王子大飯店位於富良野區；北之峰區亦有飯店、公寓及民宿。若重視 Ski-in/Ski-out，可優先選擇雪場周邊住宿。</p>'),
      cmsTab('交通', 'access', '<p>地址：北海道富良野市中御料。</p><ul><li>旭川機場開車約 1 小時。</li><li>JR 富良野站可轉乘巴士或計程車。</li><li>雪季巴士班次與預約方式請依官方公告。</li></ul>'),
    ],
  },
  pippu: {
    description: '可眺望大雪山連峰的道北雪場，設有 9 條多樣化雪道、夜滑、家庭票方案及雪場旁溫浴住宿設施。',
    sourceUrl: 'https://www.town.pippu.hokkaido.jp/ski/top.html',
    tabs: [
      cmsTab('雪道介紹', 'ski-slope', '<p>雪場共有 9 條路線，從初學者到進階滑雪者皆可使用；日間通常 9:00～16:00，夜滑通常 16:00～20:30，夜滑季至 2 月底。</p>'),
      cmsTab('租借雪具', 'rental', `${officialNotice('https://www.town.pippu.hokkaido.jp/ski/rental.html')}${infoTable(['2025-26 參考項目', '成人 4 小時', '成人 1 日', '兒童'], [['雙板套裝', '¥4,500', '¥5,500', '¥3,000'], ['單板套裝', '¥5,000', '¥6,000', '¥3,000'], ['雪衣', '¥4,000', '¥4,000', '¥2,500']])}<p>租借地點為雪番屋，平日受理至 16:00，週末及假日受理至 18:00。</p>`),
      cmsTab('雪票', 'lift', `${officialNotice('https://www.town.pippu.hokkaido.jp/ski/lift.html')}${infoTable(['2025-26 參考票種', '成人', '兒童／65 歲以上'], [['1 日券', '¥3,800', '¥2,800'], ['4 小時券', '¥3,000', '¥2,300'], ['夜間券', '¥1,200', '¥1,000'], ['成人＋兒童家庭 1 日套票', '¥4,500', '—']])}`),
      cmsTab('住宿', 'accommodation', '<p>雪場旁的「遊湯ぴっぷ」提供住宿與溫浴；1 日券及夜間券通常含入浴券，實際內容以當季票券說明為準。</p>'),
      cmsTab('交通', 'access', '<p>地址：北海道上川郡比布町北 7 線 17 號。</p><ul><li>JR 比布站至雪場在營業季通常有免費接駁。</li><li>旭川站至比布站搭普通列車約 30 分鐘。</li><li>札幌開車約 2 小時。</li></ul><p><a href="https://www.town.pippu.hokkaido.jp/ski/access.html" target="_blank" rel="noopener noreferrer">查看官方交通資訊</a></p>'),
    ],
  },
  canmore: {
    description: '距旭川機場約 15 分鐘、JR 旭川站約 30 分鐘的東川町雪場，規模精簡但路線完整，並提供夜滑。',
    sourceUrl: 'https://www.canmore-ski.jp/',
    tabs: [
      cmsTab('雪道介紹', 'ski-slope', '<p>具備初學、家庭與進階路線，日間營業通常 9:00～16:30，夜滑 16:30～20:30。2025-26 雪季已結束，2026-27 開放日待官方公告。</p>'),
      cmsTab('租借雪具', 'rental', `${officialNotice('https://www.canmore-ski.jp/rental/')}${infoTable(['2025-26 參考項目', '成人', '兒童／65 歲以上'], [['雙板／單板套裝 1 日', '¥6,000', '¥5,500'], ['套裝 3 小時', '¥5,000', '¥4,500'], ['套裝＋雪衣＋小物 1 日', '¥7,500', '¥6,500'], ['套裝＋1 日雪票', '¥7,500', '¥7,000']])}`),
      cmsTab('雪票', 'lift', `${officialNotice('https://www.canmore-ski.jp/price/')}${infoTable(['2025-26 參考票種', '成人', '兒童／65 歲以上'], [['1 日券', '¥3,000', '¥2,500'], ['3 小時券', '¥2,500', '¥2,000'], ['2 小時券', '¥2,000', '¥1,500'], ['夜間券', '¥500', '¥500']])}`),
      cmsTab('住宿', 'accommodation', '<p>建議住宿東川町或旭川市區。東川距雪場較近；旭川市區的飯店、餐飲與交通選擇較多。</p>'),
      cmsTab('交通', 'access', '<p>地址：北海道上川郡東川町西 5 號北 44。</p><ul><li>旭川機場開車約 15 分鐘。</li><li>JR 旭川站開車約 30 分鐘。</li><li>雪季部分日期有東川町內免費接駁，需查當季公告。</li></ul><p><a href="https://www.canmore-ski.jp/access/" target="_blank" rel="noopener noreferrer">查看官方交通資訊</a></p>'),
    ],
  },
  onze: {
    description: '位於札幌與小樽之間的海景雪場，交通方便、夜滑時間長，適合抵達北海道當天或市區行程搭配。',
    sourceUrl: 'https://onze.jp/',
    tabs: [
      cmsTab('雪道介紹', 'ski-slope', '<p>可眺望石狩灣，設有初學到進階雪道及夜滑。2025-26 雪季公告期間為 2025/12/19～2026/03/29，四人座纜車通常 9:00～22:45、雙人座纜車通常 10:00～15:45。2026-27 完整營業日期仍以官方公告為準。</p>'),
      cmsTab('租借雪具', 'rental', `<p><strong>資料說明：</strong>目前顯示官方已公布的 2026-27 雪季租借資訊，實際庫存與營業狀況請以現場公告為準。</p><p><a href="https://onze.jp/rental/" target="_blank" rel="noopener noreferrer">查看雪場官方最新公告</a></p>${infoTable(['2026-27 參考項目', '成人', '兒童'], [['雙板／單板套裝', '¥7,500', '¥5,200'], ['雪衣上下', '¥6,600', '¥4,600'], ['雪具＋雪衣完整套裝', '¥12,800', '¥9,000'], ['安全帽', '¥2,500', '¥1,500']])}<p>租借服務通常 8:45～22:30，現場不接受事前預約或網路申請。</p>`),
      cmsTab('雪票', 'lift', `<p><strong>資料說明：</strong>目前顯示官方已公布的 2026-27 一般雪季票價；春季折扣與臨時調整請以雪場公告為準。</p><p><a href="https://onze.jp/ticket/" target="_blank" rel="noopener noreferrer">查看雪場官方最新公告</a></p>${infoTable(['2026-27 一般雪季票種', '成人', '中高生／55 歲以上', '兒童'], [['1 日券', '¥5,600', '¥4,700', '¥3,700'], ['4 小時券', '¥4,500', '¥3,800', '¥2,800'], ['6 小時券', '¥5,000', '¥4,000', '¥3,000'], ['單次券', '¥800', '¥700', '¥500'], ['20:30 後夜滑券', '¥3,000', '¥2,500', '¥1,800']])}`),
      cmsTab('住宿', 'accommodation', '<p>可住小樽、札幌或手稻周邊。小樽適合搭配觀光，札幌的住宿與餐飲選擇最多。</p>'),
      cmsTab('交通', 'access', '<p>位於小樽市春香町，從札幌或小樽市區開車前往方便。大眾運輸與雪季接駁方式會依年度調整，請出發前確認官方公告。</p><p><a href="https://onze.jp/" target="_blank" rel="noopener noreferrer">查看官方最新資訊</a></p>'),
    ],
  },
  asari: {
    description: '鄰近小樽市區與朝里川溫泉的雪場，兼具石狩灣景觀、家庭滑雪與滑雪後泡湯行程。',
    sourceUrl: 'https://asari-ski.com/',
    tabs: [
      cmsTab('雪道介紹', 'ski-slope', '<p>雪場有初學至進階路線，可眺望石狩灣；2025-26 雪季於 2026/04/05 結束，2026-27 詳細營業日待官方公告。</p>'),
      cmsTab('租借雪具', 'rental', `${officialNotice('https://asari-ski.com/rental/')}${infoTable(['2025-26 參考項目', '成人', '中高生', '小學生以下'], [['雙板／單板套裝', '¥7,000', '¥5,500', '¥4,500'], ['雪衣上下', '¥5,500', '¥4,500', '¥4,000'], ['安全帽＋雪鏡', '¥3,000', '¥3,000', '¥3,000']])}<p>租借櫃檯位於雪場屋，通常 8:30 開始受理；現場申請並需出示身分證件。</p>`),
      cmsTab('雪票', 'lift', `<p><strong>資料說明：</strong>目前顯示官方網站於 2026/09/23 公布的票價；營業日期與現場調整請以雪場公告為準。</p><p><a href="https://www.asari-ski.com/en/" target="_blank" rel="noopener noreferrer">查看雪場官方最新公告</a></p>${infoTable(['官方目前票種', '成人', '60 歲以上', '中高生', '小學生'], [['1 日券', '¥6,500', '¥5,500', '¥4,500', '¥4,000'], ['4 小時券', '¥5,500', '¥4,800', '¥4,000', '¥3,500'], ['14:00 後券', '¥4,000', '¥4,000', '¥3,000', '¥2,000'], ['單次券', '¥1,000', '¥1,000', '¥1,000', '¥1,000']])}<p>另有 2～3 日票、家庭套票及北海道居民優惠；線上售價與資格條件請依官方頁面。</p>`),
      cmsTab('住宿', 'accommodation', '<p>朝里川溫泉區有溫泉旅館與飯店；也可住宿小樽市區，兼顧餐飲、觀光與交通。</p>'),
      cmsTab('交通', 'access', '<p>地址：北海道小樽市朝里川溫泉 1 丁目 394。</p><ul><li>從小樽市區開車約 20～30 分鐘。</li><li>可從 JR 小樽築港站或小樽站轉乘巴士。</li><li>冬季路況及班次請於出發前確認。</li></ul>'),
    ],
  },
};

const defaultRegularRows = Array.from({ length: 6 }, (_, index) => ({
  label: `${index + 1}人`,
  full: 19200 + index * 3000,
  half: 14400 + index * 3000,
}));
const defaultDiscountRows = defaultRegularRows.map((row, index) => ({
  label: row.label,
  full: row.full - 4000,
  half: row.half - (index < 2 ? 3000 : 2000),
}));
const fullDayPricing = {
  kamui: { discount: [15200, 18200, 21200, 24200, 27200, 30200], regular: [19200, 22200, 25200, 28200, 31200, 34200] },
  'mt-racey': { discount: [15200, 18200, 21200, 24200, 27200, 30200], regular: [19200, 22200, 25200, 28200, 31200, 34200] },
  rusutsu: { discount: [16000, 18500, 21000, 23500, 26000, 28500], regular: [19000, 21500, 24000, 26500, 29000, 31500] },
  teine: { discount: [13000, 15000, 17000, 19000, 21000, 23000], regular: [15000, 17000, 19000, 21000, 23000, 25000] },
  'sapporo-kokusai': { discount: [13000, 15000, 17000, 19000, 21000, 23000], regular: [15000, 17000, 19000, 21000, 23000, 25000] },
  sahoro: { discount: [15200, 18200, 21200, 24200, 27200, 30200], regular: [19200, 22200, 25200, 28200, 31200, 34200] },
};
const pricingForResort = (slug) => {
  const fullDay = fullDayPricing[slug];
  const makeRows = (values) => values.map((full, index) => ({ label: `${index + 1}人`, full }));
  return {
    season_label: '25-26 SEASON',
    currency: 'NT$',
    columns: fullDay ? ['full'] : ['full', 'half'],
    column_labels: { full: '全天5hrs', half: '半天3hrs' },
    plans: {
      discount: {
        label: '優惠時段',
        period: '季初 ~ 2025/12/15 & 2026/03/04 ~ 季末',
        rows: fullDay ? makeRows(fullDay.discount) : defaultDiscountRows,
      },
      regular: {
        label: '一般時段',
        period: '2025/12/16 ~ 2026/03/03',
        rows: fullDay ? makeRows(fullDay.regular) : defaultRegularRows,
      },
    },
    addons: [
      { title: '協助租借裝備加購', rows: [['1~3人', '+NT$1,000'], ['4~6人', '+NT$2,000']] },
      { title: '語言指定', rows: [['中文／粵語／英語', '依指定教練等級加指定費']] },
      { title: '教練指定費', rows: [['一般教練', '+NT$1,000'], ['Lv 2教練', '+NT$1,800'], ['Lv 3教練', '+NT$3,000'], ['校長／總監', '+NT$3,000']] },
    ],
    promotions: [
      { title: '早早鳥即日起至2025/6/30', lines: ['全日折扣500/人', '半天折扣300/人'] },
      { title: '早鳥2025/7/1~2025/9/30', lines: ['全日折扣300/人', '半天折扣200/人'] },
    ],
    fee_notes: ['包含教學費', '不含纜車費、雪具租賃等費用', '贈送課程時段特殊活動意外險'],
  };
};

const locationByPageKey = {
  about: 'about.snowland',
  contact: 'about.contact',
  'join-us': 'about.join-us',
  guides: 'guides.index',
  'guides-preparation': 'guides.preparation',
  'guides-faq': 'guides.faq-page',
  deals: 'news.offers',
  'deals-earlybird': 'offers.earlybird',
  'deals-referral': 'offers.referral',
  'deals-promo': 'offers.promo',
  'photography-how-to-book': 'photography.how-to-book',
};

const textFromBlocks = (blocks = []) =>
  blocks
    .filter((block) => block?.type === 'paragraph' && block.text)
    .map((block) => block.text)
    .join('\n\n');

const records = [];
const add = (record) => records.push({
  subtitle: '',
  summary: '',
  body: '',
  image_url: '',
  link_url: '',
  source: 'frontend-import',
  tags: [],
  metadata: {},
  status: 'active',
  display_order: 0,
  is_pinned: false,
  ...record,
});

[
  {
    external_id: 'home-offer-earlybird',
    title: '25-26雪季早鳥優惠',
    subtitle: '7.01 - 9.30日止',
    summary: '早鳥優惠內容與顯示期間可在後台更新。',
    image_url: '/homepage/Special offers-early bird.jpg',
    link_url: '/specialoffers/earlybird',
    metadata: { badge: '已結束' },
    status: 'ended',
  },
  {
    external_id: 'home-offer-referral',
    title: '舊生帶新生優惠',
    subtitle: '優惠內容整理中。',
    summary: '活動條件、圖片與連結可在後台更新。',
    image_url: '/homepage/Special offers-referal.jpg',
    link_url: '/specialoffers/referral',
    metadata: { badge: '進行中' },
    status: 'active',
  },
].forEach((offer, index) => add({
  content_type: 'offer',
  location_key: 'homepage.offers',
  tags: ['首頁限定優惠'],
  display_order: index + 1,
  ...offer,
}));

[
  ['Chingyee Lee', 'CL', '5歲初次接觸滑雪的小男生由 Cash 教練帶領，耐心又會教，滑了一天後完全愛上滑雪。'],
  ['Eunice Liu', 'EL', '教練耐心指導並即時糾正滑雪盲點，期待明年再回來上課。'],
  ['Wat Hans', 'WH', '初次滑雪參加一天雙板課程，講解清楚易懂，留下很好的旅行回憶。'],
  ['BESS LIN', 'BL', '教練一步一步確認基本功並指出問題，教學紮實且細心。'],
  ['OS', 'OS', '原本一直卡在落葉飄，這次終於學會 S Turn。'],
].forEach(([name, initials, summary], index) => add({
  content_type: 'review',
  location_key: 'homepage.reviews',
  external_id: `home-review-${index + 1}`,
  title: name,
  subtitle: initials,
  summary,
  tags: ['學生評價', 'Google評論'],
  metadata: { initials },
  display_order: index + 1,
}));

Object.entries(legacyPages).forEach(([key, page], index) => {
  add({
    content_type: 'page',
    location_key: locationByPageKey[key] ?? `legacy.${key}`,
    external_id: `legacy-page-${key}`,
    title: page.title ?? '',
    subtitle: page.subtitle ?? '',
    summary: page.summary ?? '',
    body: textFromBlocks(page.blocks),
    image_url: page.heroImage ?? '',
    metadata: { page_key: key, page },
    display_order: index + 1,
  });
});

guidesArticles.forEach((article, index) => {
  add({
    content_type: 'article',
    location_key: 'guides.articles',
    external_id: `guide-${index + 1}`,
    title: article.title ?? '',
    summary: article.excerpt ?? '',
    image_url: article.image ?? '',
    link_url: article.url ?? '',
    tags: article.category ? [article.category] : [],
    metadata: { ...article },
    display_order: index + 1,
  });
});

instagramLatest.forEach((post, index) => {
  add({
    content_type: 'social',
    location_key: 'news.social',
    external_id: post.shortcode,
    title: post.alt?.split('\n')[0]?.slice(0, 180) ?? 'Instagram',
    summary: post.caption ?? post.alt ?? '',
    image_url: post.src ?? '',
    link_url: `https://www.instagram.com/p/${post.shortcode}/`,
    source: 'instagram',
    tags: ['Instagram'],
    metadata: { ...post },
    display_order: index + 1,
  });
});

faqSections.forEach((section, sectionIndex) => {
  section.items.forEach((faq, itemIndex) => {
    add({
      content_type: 'faq',
      location_key: 'guides.faq',
      external_id: `faq-${sectionIndex + 1}-${itemIndex + 1}`,
      title: faq.q ?? '',
      body: faq.a ?? '',
      tags: [section.title],
      metadata: { section: section.title, question: faq.q ?? '', answer_html: faq.a ?? '' },
      display_order: sectionIndex * 100 + itemIndex + 1,
    });
  });
});

siteResorts.forEach((resort, index) => {
  add({
    content_type: 'page',
    location_key: 'course.resorts',
    external_id: resort.slug,
    title: resort.nameChinese ?? '',
    subtitle: resort.nameEnglish ?? '',
    image_url: resort.heroImage ?? resort.imagePlaceholder ?? '',
    link_url: resort.route ?? `/course/${resort.slug}`,
    tags: resort.tags ?? [],
    metadata: { ...resort },
    display_order: index + 1,
  });
});

siteResorts.forEach((resort, index) => {
  add({
    content_type: 'setting',
    location_key: 'course.pricing',
    external_id: resort.slug,
    title: `${resort.nameChinese}課程價目表`,
    subtitle: resort.nameEnglish ?? '',
    summary: '官網課程頁顯示的價目與加購費用；修改後前台會直接讀取後端資料。',
    tags: ['課程價格', resort.nameChinese],
    metadata: { slug: resort.slug, pricing: pricingForResort(resort.slug) },
    display_order: index + 1,
  });
});

Object.entries(resortLegacyData)
  .filter(([slug]) => slug !== 'niseko-annupuri')
  .forEach(([slug, resort], index) => {
  add({
    content_type: 'page',
    location_key: 'course.resort-pages',
    external_id: slug,
    title: resort.title ?? resort.name ?? slug,
    image_url: resort.heroImage ?? '',
    metadata: { slug, resort },
    display_order: index + 1,
  });
  });

additionalResorts.forEach((resort, index) => {
  const details = additionalResortDetails[resort.slug];
  add({
    content_type: 'page',
    location_key: 'course.resort-pages',
    external_id: resort.slug,
    title: resort.nameChinese,
    image_url: resort.heroImage ?? resort.imagePlaceholder,
    metadata: {
      slug: resort.slug,
      resort: {
        description: details.description,
        tags: resort.tags,
        slopes: [],
        heroImage: resort.heroImage ?? resort.imagePlaceholder,
        officialUrl: details.sourceUrl,
        lastVerifiedAt: '2026-09-23',
        tabs: details.tabs,
      },
    },
    display_order: 100 + index,
  });
});

Object.entries(guideArticlesContent).forEach(([slug, article], index) => {
  add({
    content_type: 'article',
    location_key: 'guides.article-pages',
    external_id: slug,
    title: article.title ?? '',
    summary: article.excerpt ?? '',
    image_url: article.heroImage ?? '',
    link_url: `/guides/${slug}`,
    tags: article.category ? [article.category] : [],
    metadata: { slug, article },
    display_order: index + 1,
  });
});

const gallerySections = [
  '霧冰平台', 'CENTER', '高農場騎馬', '高農場冰滑梯', '溜滑梯公園',
  '螢火蟲餐廳街', '森林餐廳', 'Club Med', '冰上釣魚',
];
const familyIndices = new Set([5, 6, 7, 8, ...Array.from({ length: 12 }, (_, i) => i + 13), ...Array.from({ length: 17 }, (_, i) => i + 27), 47, 48]);
const skiIndices = new Set([44, 45, 46]);
const portraitIndices = new Set([1, 2, 3, 4, ...Array.from({ length: 4 }, (_, i) => i + 9), 25, 26, ...Array.from({ length: 16 }, (_, i) => i + 49)]);
for (let index = 1; index <= 72; index += 1) {
  const shootTypes = [];
  if (familyIndices.has(index)) shootTypes.push('親子');
  if (skiIndices.has(index)) shootTypes.push('滑雪側拍');
  if (portraitIndices.has(index)) shootTypes.push('個人寫真');
  const section = gallerySections[Math.floor((index - 1) / 8)];
  add({
    content_type: 'media',
    location_key: 'photography.gallery',
    external_id: `gallery-${String(index).padStart(3, '0')}`,
    title: `${section}作品 ${index}`,
    image_url: `/photography-gallery/gallery-${String(index).padStart(3, '0')}.jpg`,
    tags: ['星野', section, ...shootTypes],
    metadata: { media_type: 'photo', location: '星野', section, shoot_types: shootTypes },
    display_order: index,
  });
}

[
  ['nPFLW9HsjdU', 'Gallery Video 01'],
  ['s5OAiq3woco', 'Gallery Video 02'],
  ['RM7SCH0oxAo', 'Gallery Video 03'],
  ['nDpetYyg6M4', 'Gallery Video 04'],
].forEach(([videoId, title], index) => add({
  content_type: 'media',
  location_key: 'photography.gallery',
  external_id: `youtube-${videoId}`,
  title,
  link_url: `https://www.youtube.com/watch?v=${videoId}`,
  tags: ['影片'],
  metadata: { media_type: 'video', video_id: videoId },
  display_order: 1000 + index,
}));

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(records, null, 2)}\n`);
console.log(`Wrote ${records.length} CMS records to ${outputPath}`);
