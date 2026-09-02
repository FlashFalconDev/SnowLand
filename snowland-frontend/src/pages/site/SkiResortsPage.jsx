import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import HokkaidoMap from '../../components/site/HokkaidoMap';
import ResortGrid from '../../components/site/ResortGrid';
import skiResorts from '../../data/site/skiResorts';
import guidesArticles from '../../data/site/guidesArticles';

function SkiResortsPage({ title = "雪場攻略", initialActiveSlug }) {
  const categoryBadgeStyles = {
    "滑雪初心者": "bg-[var(--tag-beginner-bg)] text-[var(--tag-beginner-text)]",
    "北海道滑雪場": "bg-[var(--tag-resort-bg)] text-[var(--tag-resort-text)]",
    "行程規劃與實戰攻略": "bg-[var(--tag-itinerary-bg)] text-[var(--tag-itinerary-text)]",
    "裝備與技巧": "bg-[var(--tag-gear-bg)] text-[var(--tag-gear-text)]",
    "北海道生活": "bg-[var(--tag-lifestyle-bg)] text-[var(--tag-lifestyle-text)]",
    限時活動: "bg-[var(--tag-promo-bg)] text-[var(--tag-promo-text)]"
  };
  const dateToNumber = (value = "") => {
    const parts = value.split(".").map((part) => part.trim());
    if (parts.length < 3) return 0;
    const [year, month, day] = parts.map((part) => Number.parseInt(part, 10) || 0);
    return year * 10000 + month * 100 + day;
  };
  const localArticleRoutes = {
    "https://land110602.com/%e6%9e%97%e9%96%93%e9%9b%aa%e9%81%93/": "/guides/best-hokkaido-tree-runs",
    "https://land110602.com/packing-checklist/": "/guides/packing-checklist",
    "https://land110602.com/%e7%ac%ac%e4%b8%80%e6%ac%a1%e6%bb%91%e9%9b%aa%ef%bc%8c%e6%96%b0%e6%89%8b%e6%87%b6%e4%ba%ba%e5%8c%85/": "/guides/preparation",
  };
  const relatedArticles = guidesArticles
    .filter((article) => article.category === "北海道滑雪場")
    .slice()
    .sort((a, b) => dateToNumber(b.date) - dateToNumber(a.date))
    .slice(0, 3);

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main className="max-w-6xl mx-auto px-6 pt-32 pb-24 flex-1 w-full">
        <section className="text-center">
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            Hokkaido Ski Resorts
          </p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
            {title}
          </h1>
        </section>

        <section className="mt-12">
          <div className="mt-6">
            <HokkaidoMap resorts={skiResorts} initialActiveSlug={initialActiveSlug} />
          </div>
        </section>

        <section className="mt-16 border-t border-[#e2e8f0] pt-12">
          <div className="text-center">
            <h2 className="text-2xl font-semibold text-[#1f2937] font-display">雪場列表總覽</h2>
          </div>
          <div className="mt-6">
            <ResortGrid resorts={skiResorts} />
          </div>
        </section>

        <section className="mt-16">
          <div className="flex items-center gap-4">
            <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
              延伸閱讀
            </h2>
            <div className="h-px flex-1 bg-[#e2e8f0]" />
          </div>
          <div className="mt-8 grid w-full max-w-4xl mx-auto gap-6 md:grid-cols-2 lg:grid-cols-3">
            {relatedArticles.map((article) => {
              const localRoute = localArticleRoutes[article.url];
              const CardWrapper = localRoute ? SiteLink : "a";
              const wrapperProps = localRoute
                ? { to: localRoute }
                : { href: article.url, target: "_blank", rel: "noreferrer" };

              return (
                <CardWrapper
                  key={article.url}
                  {...wrapperProps}
                  className="group bg-white rounded-sm overflow-hidden shadow-[0_16px_32px_rgba(15,23,42,0.08)] transition-transform duration-300 hover:-translate-y-1"
                >
                  <div className="aspect-square bg-[#e2e8f0] overflow-hidden">
                    <img loading="lazy" decoding="async"
                      src={article.image}
                      alt={article.title}
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                      loading="lazy"
                    />
                  </div>
                  <div className="p-5 space-y-3">
                    {article.category && (
                      <span
                        className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-[0.2em] uppercase font-display ${categoryBadgeStyles[article.category] || "bg-[#e2e8f0] text-[#475569]"}`}
                      >
                        {article.category}
                      </span>
                    )}
                    {article.date && (
                      <p className="text-xs font-semibold tracking-[0.2em] uppercase text-[#94a3b8] font-display">
                        {article.date}
                      </p>
                    )}
                    <h3 className="text-base font-semibold text-[#1f2937] leading-relaxed">
                      {article.title}
                    </h3>
                    {article.excerpt && (
                      <p className="text-sm text-[#64748b] leading-relaxed line-clamp-2">
                        {article.excerpt}
                      </p>
                    )}
                  </div>
                </CardWrapper>
              );
            })}
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export default SkiResortsPage;
