import React, { useRef, useState } from 'react';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import instagramLatest from '../../data/site/instagramLatest';
import guidesArticles from '../../data/site/guidesArticles';
import { fetchSiteContent } from '../../api/booking';

function NewsPage() {
  const scrollerRef = useRef(null);
  const itemRefs = useRef([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [cmsSocialItems, setCmsSocialItems] = useState([]);
  const [cmsArticles, setCmsArticles] = useState([]);
  const categoryBadgeStyles = {
    "滑雪初心者": "bg-[var(--tag-beginner-bg)] text-[var(--tag-beginner-text)]",
    "北海道滑雪場": "bg-[var(--tag-resort-bg)] text-[var(--tag-resort-text)]",
    "行程規劃與實戰攻略": "bg-[var(--tag-itinerary-bg)] text-[var(--tag-itinerary-text)]",
    "裝備與技巧": "bg-[var(--tag-gear-bg)] text-[var(--tag-gear-text)]",
    "北海道生活": "bg-[var(--tag-lifestyle-bg)] text-[var(--tag-lifestyle-text)]",
    限時活動: "bg-[var(--tag-promo-bg)] text-[var(--tag-promo-text)]"
  };
  React.useEffect(() => {
    let mounted = true;
    Promise.all([
      fetchSiteContent({ content_type: 'social', location_key: 'news.social', limit: 8 }),
      fetchSiteContent({ content_type: 'article', location_key: 'news.articles', limit: 6 }),
    ])
      .then(([socialItems, articleItems]) => {
        if (!mounted) return;
        setCmsSocialItems(Array.isArray(socialItems) ? socialItems : []);
        setCmsArticles(Array.isArray(articleItems) ? articleItems : []);
      })
      .catch(() => {
        if (!mounted) return;
        setCmsSocialItems([]);
        setCmsArticles([]);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const instagramItems = cmsSocialItems.length
    ? cmsSocialItems.map((item) => ({
      shortcode: item.external_id || String(item.id),
      src: item.image_url,
      alt: item.title || 'SnowLand 社群動態',
      caption: item.summary || item.body || item.subtitle || '',
      href: item.link_url || '#',
    }))
    : instagramLatest.slice(0, 8).map((item) => ({
      ...item,
      href: `https://www.instagram.com/p/${item.shortcode}/`,
    }));

  const latestArticles = cmsArticles.length
    ? cmsArticles.map((item) => ({
      url: item.link_url || '#',
      title: item.title || '最新消息',
      date: (item.start_at || item.created_at || '').slice(0, 10).replace(/-/g, '.'),
      category: item.tags?.[0] || item.subtitle || '最新消息',
      image: item.image_url,
    }))
    : [...guidesArticles]
    .filter((item) => item?.date)
    .sort((a, b) => {
      const toTime = (value) => {
        const [year, month, day] = value.split('.').map(Number);
        return new Date(year, month - 1, day).getTime();
      };
      return toTime(b.date) - toTime(a.date);
    })
    .slice(0, 3);

  const scrollToIndex = (index) => {
    const scroller = scrollerRef.current;
    if (!scroller) return;
    const nextIndex = Math.max(0, Math.min(index, instagramItems.length - 1));
    const target = itemRefs.current[nextIndex];
    if (!target) return;
    scroller.scrollTo({ left: target.offsetLeft, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main className="max-w-5xl mx-auto px-6 pt-32 pb-24 flex-1 w-full">
        <div className="text-center">
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            News
          </p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
            最新消息
          </h1>
        </div>
        <section className="mt-10">
          <div className="mt-6 space-y-12 md:space-y-8">
            {latestArticles.map((article) => (
              <a
                key={article.url}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group grid gap-6 md:grid-cols-[minmax(0,1fr)_180px] md:items-start"
              >
                <div>
                  <span
                    className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-[0.2em] uppercase font-display ${categoryBadgeStyles[article.category] || "bg-[#e2e8f0] text-[#475569]"}`}
                  >
                    {article.category}
                  </span>
                  <h2 className="mt-4 text-2xl font-semibold text-[#111827] leading-snug">
                    {article.title}
                  </h2>
                  <p className="mt-2 text-sm text-[#64748b]">{article.date}</p>
                </div>
                <div className="relative aspect-square overflow-hidden rounded-sm bg-[#e2e8f0]">
                  <img
                    loading="lazy"
                    decoding="async"
                    src={article.image}
                    alt={article.title}
                    className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                  />
                </div>
              </a>
            ))}
          </div>
        </section>
        <div className="mt-12 border-t border-[#e2e8f0] pt-12 relative">
          <div className="text-center font-lora mb-10">
            <p className="text-base font-semibold text-slate-600">Follow us on Instagram</p>
            <a
              href="https://www.instagram.com/snowlandcz/"
              target="_blank"
              rel="noopener noreferrer"
              className="group mt-2 inline-block text-sm font-medium text-slate-900"
            >
              <span className="relative inline-block pb-1">
                @snowlandcz
                <span className="absolute left-0 bottom-0 h-px w-full origin-left scale-x-0 bg-current transition-transform duration-300 ease-out group-hover:scale-x-100" />
              </span>
            </a>
          </div>
          <div
            ref={scrollerRef}
            className="flex gap-4 overflow-x-auto snap-x snap-mandatory pb-2 -mx-6 px-6 md:mx-0 md:px-0 md:grid md:grid-cols-4 md:gap-4 md:overflow-visible"
            onScroll={(event) => {
              const scroller = event.currentTarget;
              const center = scroller.scrollLeft + scroller.clientWidth / 2;
              let closestIndex = 0;
              let closestDistance = Number.POSITIVE_INFINITY;
              itemRefs.current.forEach((item, index) => {
                if (!item) return;
                const itemCenter = item.offsetLeft + item.clientWidth / 2;
                const distance = Math.abs(center - itemCenter);
                if (distance < closestDistance) {
                  closestDistance = distance;
                  closestIndex = index;
                }
              });
              setActiveIndex(closestIndex);
            }}
          >
            {instagramItems.map((item, index) => (
              <a
                key={item.shortcode}
                ref={(node) => {
                  itemRefs.current[index] = node;
                }}
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                data-instagram-card="true"
                className="group relative aspect-[4/5] w-[85%] shrink-0 snap-center overflow-hidden rounded-sm bg-[#e2e8f0] shadow-[0_16px_30px_rgba(15,23,42,0.08)] md:w-auto"
              >
                <img
                  loading="lazy"
                  decoding="async"
                  src={item.src}
                  alt={item.alt}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                />
                <div className="absolute inset-0 bg-black/55 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                <div className="absolute inset-0 flex items-end p-4 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                  <p className="text-sm leading-relaxed text-white/90 max-h-28 overflow-hidden">
                    {item.caption || "查看貼文"}
                  </p>
                </div>
              </a>
            ))}
          </div>
          <button
            type="button"
            onClick={() => scrollToIndex(activeIndex - 1)}
            className="absolute left-4 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full bg-white/80 text-[#1f2937] shadow-md hover:bg-white transition-colors md:hidden"
            aria-label="Previous posts"
          >
            ←
          </button>
          <button
            type="button"
            onClick={() => scrollToIndex(activeIndex + 1)}
            className="absolute right-4 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full bg-white/80 text-[#1f2937] shadow-md hover:bg-white transition-colors md:hidden"
            aria-label="Next posts"
          >
            →
          </button>
          <div className="mt-4 flex justify-center gap-2 md:hidden">
            {instagramItems.map((item, index) => (
              <button
                key={`news-dot-${item.shortcode}`}
                type="button"
                onClick={() => scrollToIndex(index)}
                className={`h-2.5 w-2.5 rounded-full border ${
                  index === activeIndex
                    ? "border-slate-300 bg-slate-300"
                    : "border-slate-200 bg-slate-200/70"
                }`}
                aria-label={`切換到第 ${index + 1} 張`}
              />
            ))}
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

export default NewsPage;
