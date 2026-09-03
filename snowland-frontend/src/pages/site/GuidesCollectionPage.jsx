import React, { useEffect, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import legacyPages from '../../data/site/legacyPages.json';
import guidesArticles from '../../data/site/guidesArticles';

function GuidesCollectionPage() {
  const { category } = useParams();
  const navigate = useNavigate();
  const categoryLabels = ["All", "滑雪初心者", "北海道滑雪場", "行程規劃與實戰攻略", "裝備與技巧", "北海道生活", "限時活動"];
  const [activeCategory, setActiveCategory] = useState(categoryLabels[0]);
  const page = legacyPages["guides"];
  const categoryBadgeStyles = {
    "滑雪初心者": "bg-[var(--tag-beginner-bg)] text-[var(--tag-beginner-text)]",
    "北海道滑雪場": "bg-[var(--tag-resort-bg)] text-[var(--tag-resort-text)]",
    "行程規劃與實戰攻略": "bg-[var(--tag-itinerary-bg)] text-[var(--tag-itinerary-text)]",
    "裝備與技巧": "bg-[var(--tag-gear-bg)] text-[var(--tag-gear-text)]",
    "北海道生活": "bg-[var(--tag-lifestyle-bg)] text-[var(--tag-lifestyle-text)]",
    限時活動: "bg-[var(--tag-promo-bg)] text-[var(--tag-promo-text)]"
  };
  const categorySlugMap = {
    All: null,
    "滑雪初心者": "beginner",
    "北海道滑雪場": "hokkaido_skiresorts",
    "行程規劃與實戰攻略": "plan",
    "裝備與技巧": "gear",
    "北海道生活": "lifestyle",
    限時活動: "promo"
  };
  const slugCategoryMap = {
    beginner: "滑雪初心者",
    hokkaido_skiresorts: "北海道滑雪場",
    plan: "行程規劃與實戰攻略",
    gear: "裝備與技巧",
    lifestyle: "北海道生活",
    promo: "限時活動"
  };
  const dateToNumber = (value = "") => {
    const parts = value.split(".").map((part) => part.trim());
    if (parts.length < 3) return 0;
    const [year, month, day] = parts.map((part) => Number.parseInt(part, 10) || 0);
    return year * 10000 + month * 100 + day;
  };
  const cards = (activeCategory === "All"
    ? guidesArticles
    : guidesArticles.filter((card) => card.category === activeCategory)
  ).slice().sort((a, b) => dateToNumber(b.date) - dateToNumber(a.date));
  const localArticleRoutes = {
    "https://land110602.com/%e6%9e%97%e9%96%93%e9%9b%aa%e9%81%93/": "/guides/best-hokkaido-tree-runs",
    "https://land110602.com/packing-checklist/": "/guides/packing-checklist",
    "https://land110602.com/%e7%ac%ac%e4%b8%80%e6%ac%a1%e6%bb%91%e9%9b%aa%ef%bc%8c%e6%96%b0%e6%89%8b%e6%87%b6%e4%ba%ba%e5%8c%85/": "/guides/preparation",
  };

  useEffect(() => {
    if (!category) return;
    const matchedCategory = slugCategoryMap[category];
    if (matchedCategory && matchedCategory !== activeCategory) {
      setActiveCategory(matchedCategory);
      return;
    }
    if (!matchedCategory) {
      navigate("/guides", { replace: true });
    }
  }, [category, activeCategory, navigate]);

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main className="max-w-6xl mx-auto px-6 pt-32 pb-24 flex-1 w-full">
        <div className="text-center">
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            {page?.subtitle ?? "Guides"}
          </p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display inline-flex flex-col items-center group">
            <span>{page?.title ?? "滑雪精選文章"}</span>
            <span className="mt-3 h-0.5 w-0 bg-[#111827] transition-all duration-300 group-hover:w-full" />
          </h1>
        </div>
        <div className="mt-10 border-b border-[#e2e8f0]">
          <div className="flex flex-wrap items-center justify-center gap-12 md:gap-16 text-base md:text-lg font-semibold text-[#6b7280] font-display">
            {categoryLabels.map((label) => {
              const isActive = label === activeCategory;
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => {
                    setActiveCategory(label);
                    const slug = categorySlugMap[label];
                    if (slug) {
                      navigate(`/guides/${slug}`);
                    } else {
                      navigate("/guides");
                    }
                  }}
                  className={`relative pb-4 transition-colors duration-200 group ${
                    isActive ? "text-[#111827]" : "hover:text-[#2b5f8f]"
                  }`}
                  aria-current={isActive ? "page" : undefined}
                >
                  {label}
                  <span
                    className={`absolute left-0 -bottom-[1px] h-0.5 transition-all duration-300 ${
                      isActive ? "w-full bg-[#111827]" : "w-0 bg-[#2b5f8f] group-hover:w-full"
                    }`}
                  />
                </button>
              );
            })}
          </div>
        </div>
        <section className="mt-12 grid w-full max-w-4xl mx-auto gap-6 md:grid-cols-2 lg:grid-cols-3">
          {cards.map((card) => {
            const localRoute = localArticleRoutes[card.url];
            const CardWrapper = localRoute ? SiteLink : "div";
            const wrapperProps = localRoute
              ? { to: localRoute }
              : { "aria-label": card.title };

            return (
              <CardWrapper
                key={card.url}
                {...wrapperProps}
                className="group bg-white rounded-sm overflow-hidden shadow-[0_16px_32px_rgba(15,23,42,0.08)] transition-transform duration-300 hover:-translate-y-1"
              >
              <div className="aspect-square bg-[#e2e8f0] overflow-hidden">
                <img loading="lazy" decoding="async"
                  src={card.image}
                  alt={card.title}
                  className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                />
              </div>
              <div className="p-5 space-y-3">
                {card.category && (
                  <span
                    className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-[0.2em] uppercase font-display ${categoryBadgeStyles[card.category] || "bg-[#e2e8f0] text-[#475569]"}`}
                  >
                    {card.category}
                  </span>
                )}
                {card.date && (
                  <p className="text-xs font-semibold tracking-[0.2em] uppercase text-[#94a3b8] font-display">
                    {card.date}
                  </p>
                )}
                <h2 className="text-base font-semibold text-[#1f2937] leading-relaxed">
                  {card.title}
                </h2>
                {card.excerpt && (
                  <p className="text-sm text-[#64748b] leading-relaxed line-clamp-2">
                    {card.excerpt}
                  </p>
                )}
              </div>
              </CardWrapper>
            );
          })}
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export default GuidesCollectionPage;
