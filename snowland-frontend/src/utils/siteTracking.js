// Optional public-site analytics. Never derive event data from forms, text or URLs.
const VERSION = 1;
const MAX_AGE = 90 * 24 * 60 * 60 * 1000;
const PUBLIC_SECTIONS = new Set(['course', 'coach', 'about', 'faq', 'news', 'guides', 'photography', 'specialoffers', 'Gallery', 'privacy-policy', 'membership-terms', 'cancellation-policy']);
const BUTTONS = new Set(['booking_start', 'view_courses', 'contact_open', 'membership_open']);

export function trackingConfig(item) {
  const m = item?.metadata;
  if (item?.status !== 'active' || m?.enabled !== true || m.auto_events_disabled !== true) return null;
  const ga4 = typeof m.ga4_id === 'string' && /^G-[A-Z0-9]{4,20}$/.test(m.ga4_id) ? m.ga4_id : '';
  const meta = typeof m.meta_pixel_id === 'string' && /^[0-9]{5,25}$/.test(m.meta_pixel_id) ? m.meta_pixel_id : '';
  return ga4 || meta ? {ga4, meta, fingerprint: `${VERSION}:${ga4}:${meta}`} : null;
}

export function publicTrackingPage(href, basePath, origin) {
  try {
    const url = new URL(href, origin);
    if (!basePath || url.origin !== origin || url.search || url.hash || /[%\\]/.test(url.pathname)) return '';
    if (url.pathname === basePath || url.pathname === `${basePath}/`) return 'home';
    if (!url.pathname.startsWith(`${basePath}/`)) return '';
    const section = url.pathname.slice(basePath.length + 1).split('/')[0];
    return PUBLIC_SECTIONS.has(section) ? section : '';
  } catch { return ''; }
}

export function trackingButton(to) {
  if (typeof to !== 'string' || /[?#]/.test(to)) return '';
  const section = to.split('/')[1];
  return {booking: 'booking_start', course: 'view_courses', contact: 'contact_open', membership: 'membership_open'}[section] || '';
}

export function createTrackingRuntime(win) {
  let config = null, basePath = '', choice = null, started = false, halted = false, lastPage = '', cleanup = () => {};
  let ownGtag = null, ownFbq = null, notice = () => {};
  const key = () => `snowland:tracking:${basePath}`;
  const privacySignal = () => win.navigator.globalPrivacyControl === true || win.navigator.doNotTrack === '1';
  const local = () => /^(localhost|127\.0\.0\.1|\[::1\])$|\.localhost$/.test(win.location.hostname) || win.location.protocol !== 'https:';
  const page = () => publicTrackingPage(win.location.href, basePath, win.location.origin);
  const referrerSafe = () => {
    if (!win.document.referrer) return true;
    try {
      const ref = new URL(win.document.referrer);
      return !ref.search && !ref.hash && (ref.origin !== win.location.origin || Boolean(publicTrackingPage(ref.href, basePath, win.location.origin)));
    } catch { return false; }
  };
  function stop() {
    halted = true;
    if (config?.ga4) win[`ga-disable-${config.ga4}`] = true;
    try { if (ownGtag) ownGtag('consent', 'update', {analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'}); } catch { /* Vendor failures must not block navigation. */ }
    try { if (ownFbq) ownFbq('consent', 'revoke'); } catch { /* Full navigation removes the failed SDK. */ }
  }
  function guardNavigation() {
    const originals = {};
    for (const method of ['pushState', 'replaceState']) {
      const original = win.history[method];
      originals[method] = original;
      const guarded = function(state, unused, url) {
        if (url != null && !publicTrackingPage(url, basePath, win.location.origin)) {
          stop(); cleanup();
          win.location[method === 'replaceState' ? 'replace' : 'assign'](new URL(url, win.location.href).href);
          return;
        }
        return original.call(win.history, state, unused, url);
      };
      win.history[method] = guarded;
      originals[`${method}Guard`] = guarded;
    }
    const pop = () => { if (!page()) { stop(); cleanup(); win.location.reload(); } };
    win.addEventListener('popstate', pop);
    cleanup = () => {
      for (const method of ['pushState', 'replaceState']) {
        if (win.history[method] === originals[`${method}Guard`]) win.history[method] = originals[method];
      }
      win.removeEventListener('popstate', pop);
    };
  }
  function script(src) {
    const node = win.document.createElement('script');
    node.async = true; node.src = src; node.referrerPolicy = 'no-referrer';
    node.onerror = () => { stop(); notice('追蹤服務無法載入，已停止追蹤；不影響網站使用。'); };
    win.document.head.appendChild(node);
  }
  function sendPage() {
    const category = page();
    if (!started || halted || privacySignal() || !category || win.location.href === lastPage) return;
    lastPage = win.location.href;
    if (ownGtag && choice.analytics) ownGtag('event', 'page_view', {
      send_to: config.ga4, page_title: category,
      page_location: `${win.location.origin}${basePath}/${category === 'home' ? '' : category}`,
      page_referrer: '',
    });
    if (ownFbq && choice.marketing) ownFbq('trackSingle', config.meta, 'PageView', {page_category: category});
  }
  function start() {
    if (!config || !choice || halted || privacySignal() || !page() || !referrerSafe() || local()) return;
    if (started) { sendPage(); return; }
    const ga = choice.analytics && config.ga4, meta = choice.marketing && config.meta;
    if (!ga && !meta) return;
    if ((ga && ((win.gtag && win.gtag !== ownGtag) || (win.dataLayer && !ownGtag))) || (meta && ((win.fbq && win.fbq !== ownFbq) || (win._fbq && win._fbq !== ownFbq)))) {
      notice('偵測到其他追蹤程式，已停止載入，請管理員檢查設定。'); return;
    }
    guardNavigation(); started = true;
    if (ga) {
      win.dataLayer = win.dataLayer || [];
      ownGtag = function() { win.dataLayer.push(arguments); };
      win.gtag = ownGtag; win[`ga-disable-${ga}`] = false;
      ownGtag('consent', 'default', {analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'});
      ownGtag('consent', 'update', {analytics_storage: 'granted', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'});
      ownGtag('js', new Date());
      ownGtag('config', ga, {send_page_view: false, allow_google_signals: false, allow_ad_personalization_signals: false,
        page_title: page(), page_referrer: '', page_location: `${win.location.origin}${basePath}/${page() === 'home' ? '' : page()}`});
      script(`https://www.googletagmanager.com/gtag/js?id=${ga}`);
    }
    if (meta) {
      ownFbq = function() { if (ownFbq.callMethod) ownFbq.callMethod.apply(ownFbq, arguments); else ownFbq.queue.push(arguments); };
      ownFbq.queue = []; ownFbq.loaded = true; ownFbq.version = '2.0'; ownFbq.disablePushState = true;
      win.fbq = ownFbq; win._fbq = ownFbq;
      ownFbq('consent', 'grant'); ownFbq('set', 'autoConfig', false, meta); ownFbq('init', meta);
      script('https://connect.facebook.net/en_US/fbevents.js');
    }
    sendPage();
  }
  function safely(action) {
    try { action(); }
    catch { stop(); notice('追蹤服務無法執行，已停止追蹤；不影響網站使用。'); }
  }
  return {
    configure(next, base, onNotice = () => {}) {
      notice = onNotice;
      if (started && (next?.fingerprint !== config?.fingerprint || base !== basePath)) { stop(); win.location.reload(); return null; }
      config = next; basePath = base; choice = null;
      if (!config) return null;
      try {
        const stored = JSON.parse(win.localStorage.getItem(key()) || 'null');
        if (stored?.fingerprint === config.fingerprint && stored.expires > Date.now() && stored.expires <= Date.now() + MAX_AGE && typeof stored.analytics === 'boolean' && typeof stored.marketing === 'boolean') choice = stored;
      } catch { notice('無法讀取隱私偏好，追蹤保持關閉。'); }
      if (privacySignal()) choice = {analytics: false, marketing: false};
      safely(start); return choice;
    },
    save(next) {
      if (!config) return false;
      const selected = {analytics: !privacySignal() && next.analytics === true && Boolean(config.ga4), marketing: !privacySignal() && next.marketing === true && Boolean(config.meta)};
      try { win.localStorage.setItem(key(), JSON.stringify({...selected, fingerprint: config.fingerprint, expires: Date.now() + MAX_AGE})); }
      catch { notice('無法儲存隱私偏好，追蹤保持關閉。'); return false; }
      choice = selected;
      if (started) { stop(); win.location.reload(); } else safely(start);
      return true;
    },
    page: () => safely(sendPage),
    button(name) {
      if (!started || halted || privacySignal() || !page() || !BUTTONS.has(name)) return;
      safely(() => {
        if (ownGtag && choice.analytics) ownGtag('event', 'navigation_click', {send_to: config.ga4, button_name: name});
        if (ownFbq && choice.marketing) ownFbq('trackSingleCustom', config.meta, 'NavigationClick', {button_name: name});
      });
    },
    isLocal: local,
    privacySignal,
  };
}

export const siteTracking = typeof window === 'undefined' ? null : createTrackingRuntime(window);
