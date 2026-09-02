import React, { useState } from 'react';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import guideArticlesContent from '../../data/site/guideArticlesContent';
import guidesArticles from '../../data/site/guidesArticles';

function BestHokkaidoTreeRunsPage() {
  const article = guideArticlesContent["best-hokkaido-tree-runs"];
  const [isTocOpen, setIsTocOpen] = useState(true);
  const categoryBadgeStyles = {
    "滑雪初心者": "bg-[var(--tag-beginner-bg)] text-[var(--tag-beginner-text)]",
    "北海道滑雪場": "bg-[var(--tag-resort-bg)] text-[var(--tag-resort-text)]",
    "行程規劃與實戰攻略": "bg-[var(--tag-itinerary-bg)] text-[var(--tag-itinerary-text)]",
    "裝備與技巧": "bg-[var(--tag-gear-bg)] text-[var(--tag-gear-text)]",
    "北海道生活": "bg-[var(--tag-lifestyle-bg)] text-[var(--tag-lifestyle-text)]",
    限時活動: "bg-[var(--tag-promo-bg)] text-[var(--tag-promo-text)]"
  };
  const category = guidesArticles.find(
    (item) => item.url === "https://land110602.com/%e6%9e%97%e9%96%93%e9%9b%aa%e9%81%93/"
  )?.category;
  const relatedImages = guidesArticles.reduce((acc, item) => {
    acc[item.url] = item.image;
    acc[item.title] = item.image;
    return acc;
  }, {});
  const relatedMeta = guidesArticles.reduce((acc, item) => {
    acc[item.url] = item;
    acc[item.title] = item;
    return acc;
  }, {});
  const dateToNumber = (value = "") => {
    const parts = value.split(".").map((part) => part.trim());
    if (parts.length < 3) return 0;
    const [year, month, day] = parts.map((part) => Number.parseInt(part, 10) || 0);
    return year * 10000 + month * 100 + day;
  };
  const makeSlug = (text) =>
    text
      .trim()
      .toLowerCase()
      .replace(/[^\w\u4e00-\u9fa5]+/g, "-")
      .replace(/^-+|-+$/g, "");
  const headingRegex = /<h([2-4])>([\s\S]*?)<\/h\1>/g;
  const tocItems = [];
  const tocCounters = { 2: 0, 3: 0, 4: 0 };
  const articleHtml = article.html.replace(headingRegex, (match, level, rawTitle) => {
    const title = rawTitle.replace(/<[^>]*>/g, "").trim();
    if (!title) {
      return match;
    }
    const numericLevel = Number(level);
    if (numericLevel === 2) {
      tocCounters[2] += 1;
      tocCounters[3] = 0;
      tocCounters[4] = 0;
    } else if (numericLevel === 3) {
      tocCounters[3] += 1;
      tocCounters[4] = 0;
    } else if (numericLevel === 4) {
      tocCounters[4] += 1;
    }
    const numberParts = [tocCounters[2], tocCounters[3], tocCounters[4]].filter((value, index) => {
      if (index === 0) {
        return value > 0;
      }
      return value > 0;
    });
    const numberPrefix = numberParts.join(".");
    const hasLeadingNumber = /^\d+(\.\d+)*[.、]?\s*/.test(title);
    const displayTitle = hasLeadingNumber || !numberPrefix ? title : `${numberPrefix} ${title}`;
    const id = `section-${makeSlug(title)}`;
    tocItems.push({ id, title, displayTitle, level: numericLevel });
    return `<h${level} id="${id}">${rawTitle}</h${level}>`;
  });

  if (!article) {
    return (
      <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
        <SiteHeader forceTransparent forceDarkText forceLogoColor />
        <main className="flex-1 flex items-center justify-center px-6 pt-32 pb-24">
          <p className="text-sm text-[#64748b]">內容載入中。</p>
        </main>
        <SiteFooter />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main className="flex-1 pt-28 pb-20">
        <section className="max-w-5xl mx-auto px-6">
          <div className="text-center">
            <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
              Guides
            </p>
            {category && (
              <div className="mt-4 flex justify-center">
                <span
                  className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-[0.2em] uppercase font-display ${categoryBadgeStyles[category] || "bg-[#e2e8f0] text-[#475569]"}`}
                >
                  {category}
                </span>
              </div>
            )}
            <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
              {article.title}
            </h1>
            <p className="mt-3 text-xs font-semibold tracking-[0.2em] uppercase text-[#94a3b8] font-display">
              {article.date}
            </p>
          </div>

          <div className="mt-10 rounded-sm overflow-hidden bg-[#e2e8f0]">
            <img loading="lazy" decoding="async"
              src={article.heroImage}
              alt={article.title}
              className="w-full h-full object-cover"
            />
          </div>
        </section>

        <section className="max-w-5xl mx-auto px-6 mt-12">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
            {tocItems.length > 0 && (
              <aside className="order-first lg:order-none lg:w-64">
                <div className="w-full border-r border-[#e2e8f0] pr-8 text-left">
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-sm font-semibold text-[#1f2937] font-display">
                      目錄
                    </p>
                    <button
                      type="button"
                      onClick={() => setIsTocOpen((prev) => !prev)}
                      className="text-sm font-semibold text-[#94a3b8] hover:text-[#2b5f8f] transition-colors"
                      aria-expanded={isTocOpen}
                      aria-label={isTocOpen ? "收合目錄" : "展開目錄"}
                    >
                      {isTocOpen ? "−" : "+"}
                    </button>
                  </div>
                  {isTocOpen && (
                    <ul className="mt-4 space-y-2 text-sm text-[#64748b]">
                      {tocItems.map((item) => (
                        <li key={item.id}>
                          <a
                        href={`#${item.id}`}
                        className={`hover:text-[#2b5f8f] transition-colors ${
                          item.level === 3 ? "pl-4" : item.level === 4 ? "pl-8" : ""
                        }`}
                      >
                        {item.displayTitle ?? item.title}
                      </a>
                    </li>
                  ))}
                    </ul>
                  )}
                </div>
              </aside>
            )}
            <div className="order-last article-content text-sm md:text-base text-[#475569] leading-relaxed lg:order-none lg:pl-8">
              <p className="text-lg md:text-xl font-medium text-[#374151] leading-relaxed mb-8">
                {article.lead}
              </p>
              <div dangerouslySetInnerHTML={{ __html: articleHtml }} />
            </div>
          </div>
        </section>
        {article.relatedLinks && article.relatedLinks.length > 0 && (
          <section className="max-w-5xl mx-auto px-6 mt-16">
            <div className="flex items-center gap-4">
              <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                延伸閱讀
              </h2>
              <div className="h-px flex-1 bg-[#e2e8f0]" />
            </div>
            <div className="mt-8 grid w-full max-w-4xl mx-auto gap-6 md:grid-cols-2 lg:grid-cols-3">
              {article.relatedLinks
                .slice()
                .sort((a, b) => {
                  const metaA = relatedMeta[a.url] || relatedMeta[a.title] || {};
                  const metaB = relatedMeta[b.url] || relatedMeta[b.title] || {};
                  return dateToNumber(metaB.date) - dateToNumber(metaA.date);
                })
                .map((item) => (
                <a
                  key={item.url}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group bg-white rounded-sm overflow-hidden shadow-[0_16px_32px_rgba(15,23,42,0.08)] transition-transform duration-300 hover:-translate-y-1"
                >
                  {(relatedImages[item.url] || relatedImages[item.title]) && (
                    <div className="aspect-square overflow-hidden bg-[#e2e8f0]">
                      <img
                        src={relatedImages[item.url] || relatedImages[item.title]}
                        alt={item.title}
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                        loading="lazy"
                      />
                    </div>
                  )}
                  <div className="p-5 space-y-3">
                    {relatedMeta[item.url]?.category && (
                      <span
                        className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-[0.2em] uppercase font-display ${
                          categoryBadgeStyles[relatedMeta[item.url].category] || "bg-[#e2e8f0] text-[#475569]"
                        }`}
                      >
                        {relatedMeta[item.url].category}
                      </span>
                    )}
                    {relatedMeta[item.url]?.date && (
                      <p className="text-xs font-semibold tracking-[0.2em] uppercase text-[#94a3b8] font-display">
                        {relatedMeta[item.url].date}
                      </p>
                    )}
                    <h3 className="text-base font-semibold text-[#1f2937] leading-relaxed">
                      {item.title}
                    </h3>
                    {relatedMeta[item.url]?.excerpt && (
                      <p className="text-sm text-[#64748b] leading-relaxed line-clamp-2">
                        {relatedMeta[item.url].excerpt}
                      </p>
                    )}
                  </div>
                </a>
              ))}
            </div>
          </section>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

export default BestHokkaidoTreeRunsPage;
