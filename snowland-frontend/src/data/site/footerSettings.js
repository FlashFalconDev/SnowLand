export const footerSocials = [
  {key:'facebook', label:'Facebook', icon:'footer_icon_fb.png'},
  {key:'instagram', label:'Instagram', icon:'instagram-logo.png'},
  {key:'threads', label:'Threads', icon:'footer_icon_threads.png'},
  {key:'youtube', label:'YouTube', icon:'footer_icon_yt.png'},
  {key:'line', label:'LINE', icon:'footer_icon_line.png'},
  {key:'whatsapp', label:'WhatsApp', icon:'footer_icon_wa.png'},
  {key:'tiktok', label:'TikTok', icon:'footer_icon_tikotok.png'},
  {key:'xiaohongshu', label:'小紅書', icon:'footer_icon_red note.png'},
];

// Old or imported CMS rows can bypass current validation; never render unsafe hrefs.
export function safeFooterLink(value) {
  if (typeof value !== 'string' || !value || value.length > 2000 || /[\s\\\x00-\x1f]/.test(value)) return '';
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && url.hostname && !url.username && !url.password ? value : '';
  } catch { return ''; }
}

export function footerSettings(item) {
  const metadata = item?.metadata || {};
  const text = key => typeof metadata[key] === 'string' ? metadata[key] : '';
  const email = text('email');
  return {
    companyName: text('company_name'), secondaryName: text('company_name_secondary'),
    copyright: text('copyright'), email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? email : '',
    links: footerSocials.map(social => ({...social, href:safeFooterLink(metadata.social_links?.[social.key])})).filter(social => social.href),
  };
}
