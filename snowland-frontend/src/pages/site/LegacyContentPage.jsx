import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSiteLocale } from '../../contexts/SiteLocale';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import { siteContentToArticle, siteContentToPage, useSiteContent } from '../../hooks/useSiteContent';

const headingStyles = {
  1: "text-2xl font-semibold text-[#111827] font-display",
  2: "text-xl font-semibold text-[#111827] font-display",
  3: "text-lg font-semibold text-[#1f2937] font-display",
  4: "text-base font-semibold text-[#1f2937] font-display",
};

const renderTextWithLinks = (text) => {
  const linkRegex = /(https?:\/\/[^\s]+)/g;
  const linkTest = /^https?:\/\/[^\s]+$/;
  const parts = text.split(linkRegex);
  return parts.map((part, index) => {
    if (linkTest.test(part)) {
      return (
        <a
          key={`link-${index}`}
          href={part}
          className="text-[#2b5f8f] underline underline-offset-2 break-all"
          target="_blank"
          rel="noopener noreferrer"
        >
          {part}
        </a>
      );
    }
    return <span key={`text-${index}`}>{part}</span>;
  });
};

const renderBlock = (block, index) => {
  if (block.type === "heading") {
    const HeadingTag = `h${Math.min(block.level, 4)}`;
    return (
      <HeadingTag
        key={`heading-${index}`}
        id={block.id}
        className={headingStyles[block.level] ?? headingStyles[3]}
      >
        {block.text}
      </HeadingTag>
    );
  }
  if (block.type === "paragraph") {
    return (
      <p key={`paragraph-${index}`} className="text-sm md:text-base text-[#475569] leading-relaxed">
        {renderTextWithLinks(block.text)}
      </p>
    );
  }
  if (block.type === "list") {
    const ListTag = block.ordered ? "ol" : "ul";
    const listStyle = block.ordered ? "list-decimal" : "list-disc";
    return (
      <ListTag
        key={`list-${index}`}
        className={`pl-5 space-y-2 text-sm md:text-base text-[#475569] leading-relaxed ${listStyle}`}
      >
        {block.items.map((item, itemIndex) => (
          <li key={`list-item-${index}-${itemIndex}`}>{renderTextWithLinks(item)}</li>
        ))}
      </ListTag>
    );
  }
  return null;
};

const renderImageGroup = (images, startIndex, useArticleStyle = false, imageStyle = {}) => {
  const figureClass = useArticleStyle
    ? "rounded-sm overflow-hidden"
    : "rounded-3xl overflow-hidden bg-[#e2e8f0]";
  const defaultImageClass = useArticleStyle ? "w-full h-auto" : "w-full h-full object-cover";
  if (images.length === 1) {
    const image = images[0];
    const figureClassName = imageStyle.figureClassName ?? figureClass;
    const imageClassName = imageStyle.imageClassName ?? defaultImageClass;
    return (
      <figure key={`image-${startIndex}`} className={figureClassName}>
        <img
          src={image.src}
          alt={image.alt || "Content image"}
          className={imageClassName}
          loading="lazy"
        />
      </figure>
    );
  }
  if (useArticleStyle) {
    return (
      <div key={`image-group-${startIndex}`} className="space-y-6">
        {images.map((image, index) => (
          <figure
            key={`image-${startIndex + index}`}
            className={figureClass}
          >
            <img
              src={image.src}
              alt={image.alt || "Content image"}
              className={defaultImageClass}
              loading="lazy"
            />
          </figure>
        ))}
      </div>
    );
  }
  const columnClass = images.length >= 3 ? "md:grid-cols-3" : "md:grid-cols-2";
  return (
    <div key={`image-group-${startIndex}`} className={`grid gap-4 ${columnClass}`}>
      {images.map((image, index) => (
        <figure
          key={`image-${startIndex + index}`}
          className={figureClass}
        >
          <img
            src={image.src}
            alt={image.alt || "Content image"}
            className={defaultImageClass}
            loading="lazy"
          />
        </figure>
      ))}
    </div>
  );
};

const splitParagraphs = (text = "") => {
  if (!text) return [];
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return [];
  const parts = normalized.split(/(?<=[。！？])\s*/).filter(Boolean);
  return parts.length ? parts : [normalized];
};

const getSectionParagraphs = (blocks = [], headingText) => {
  const index = blocks.findIndex(
    (block) => block.type === "heading" && block.text === headingText
  );
  if (index === -1) return [];
  const paragraphs = [];
  for (let i = index + 1; i < blocks.length; i += 1) {
    const block = blocks[i];
    if (block.type === "heading") break;
    if (block.type === "paragraph") paragraphs.push(block.text);
  }
  return paragraphs.flatMap((text) => splitParagraphs(text));
};

const stripLeadingBullet = (text = "") => text.replace(/^[–-]\s*/, "").trim();

const CMS_LOCATION_BY_PAGE_KEY = {
  about: "about.snowland",
  "join-us": "about.join-us",
  "guides-preparation": "guides.preparation",
  "guides-faq": "guides.faq",
  deals: "news.offers",
  "deals-earlybird": "offers.earlybird",
  "deals-referral": "offers.referral",
  "deals-promo": "offers.promo",
  "photography-how-to-book": "photography.how-to-book",
};

function LegacyContentPage({ pageKey, forceDarkHeader = false, forceLogoColor = false }) {
  const { t } = useSiteLocale();
  const cmsLocationKey = CMS_LOCATION_BY_PAGE_KEY[pageKey] ?? `legacy.${pageKey}`;
  const { items: cmsPageItems, isLoading: pageLoading, error: pageError } = useSiteContent(cmsLocationKey, { limit: 20 });
  const { items: articleItems } = useSiteContent('guides.articles');
  const page = siteContentToPage(cmsPageItems[0]);
  const aboutValues = page?.layout?.values;
  const aboutUnavailable = ['about','join-us'].includes(pageKey) && !(page?.layout?.version === 1 && page.layout.page_key === pageKey && aboutValues && typeof aboutValues === 'object' && !Array.isArray(aboutValues) && Object.keys(aboutValues).length && Object.values(aboutValues).every(value => typeof value === 'string'));
  if (!page || aboutUnavailable) return <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
    <SiteHeader forceTransparent />
    <main className="flex-1 flex items-center justify-center px-6 pt-32 pb-24">
      <p role={pageError ? 'alert' : 'status'} className={`text-sm ${pageError ? 'text-red-600' : 'text-[#64748b]'}`}>
        {pageError ? t('內容暫時無法載入，請稍後再試。') : pageLoading ? t('內容載入中。') : aboutUnavailable ? t('{section}內容更新中，請稍後再查看。', { section: t(pageKey === 'about' ? '學校介紹' : '教練招募') }) : t('目前沒有已發布的內容。')}
      </p>
    </main><SiteFooter />
  </div>;
  return <LegacyContentLayout key={pageKey} pageKey={pageKey} page={page} guidesArticles={articleItems.map(siteContentToArticle)} forceDarkHeader={forceDarkHeader} forceLogoColor={forceLogoColor} />;
}

function LegacyContentLayout({ pageKey, page, guidesArticles, forceDarkHeader = false, forceLogoColor = false }) {
  const { t } = useSiteLocale();
  const isAboutPage = pageKey === "about";
  const j = (key) => page.layout?.values?.[key] ?? "";
  const aboutContent = page.layout;
  const c = (key) => aboutContent?.values?.[key] ?? "";
  const isJoinUsPage = pageKey === "join-us";
  const isGuidesFaqPage = pageKey === "guides-faq";
  const isGuidesPreparationPage = pageKey === "guides-preparation";
  const isPhotographyHowToBookPage = pageKey === "photography-how-to-book";
  const isDealsPage = pageKey?.startsWith("deals");
  const isDealsPromoPage = pageKey === "deals-promo";
  const dealsCategoryLinks = [
    { label: "早早鳥/早鳥優惠", key: "deals-earlybird", href: "/specialoffers/earlybird" },
    { label: "舊生帶新生優惠", key: "deals-referral", href: "/specialoffers/referral" },
    { label: "限時活動", key: "deals-promo", href: "/specialoffers/promo" },
  ];
  const [openFaqIndex, setOpenFaqIndex] = useState(0);
  const [aboutActiveIndex, setAboutActiveIndex] = useState(0);
  const aboutSectionRefs = useRef([]);
  const [joinUsActiveStep, setJoinUsActiveStep] = useState(-1);
  const joinUsStepRefs = useRef([]);
  const [joinUsMobileSlide, setJoinUsMobileSlide] = useState(0);
  const joinUsMobileCarouselRef = useRef(null);
  const [isTocOpen, setIsTocOpen] = useState(true);
  const prefersReducedMotion = useReducedMotion();
  const activeDealsKey = pageKey === "deals" ? "deals-earlybird" : pageKey;
  const categoryBadgeStyles = {
    "滑雪初心者": "bg-[var(--tag-beginner-bg)] text-[var(--tag-beginner-text)]",
    "北海道滑雪場": "bg-[var(--tag-resort-bg)] text-[var(--tag-resort-text)]",
    "行程規劃與實戰攻略": "bg-[var(--tag-itinerary-bg)] text-[var(--tag-itinerary-text)]",
    "裝備與技巧": "bg-[var(--tag-gear-bg)] text-[var(--tag-gear-text)]",
    "北海道生活": "bg-[var(--tag-lifestyle-bg)] text-[var(--tag-lifestyle-text)]",
    限時活動: "bg-[var(--tag-promo-bg)] text-[var(--tag-promo-text)]"
  };
  const localArticleRoutes = {
    "https://land110602.com/%e6%9e%97%e9%96%93%e9%9b%aa%e9%81%93/": "/guides/best-hokkaido-tree-runs",
  };
  const preparationArticleUrl =
    "https://land110602.com/%e7%ac%ac%e4%b8%80%e6%ac%a1%e6%bb%91%e9%9b%aa%ef%bc%8c%e6%96%b0%e6%89%8b%e6%87%b6%e4%ba%ba%e5%8c%85/";
  const preparationArticle = isGuidesPreparationPage
    ? guidesArticles.find((article) => article.url === preparationArticleUrl)
    : null;
  const dateToNumber = (value = "") => {
    const parts = value.split(/[.-]/).map((part) => part.trim());
    if (parts.length < 3) return 0;
    const [year, month, day] = parts.map((part) => Number.parseInt(part, 10) || 0);
    return year * 10000 + month * 100 + day;
  };
  const promoArticles = guidesArticles
    .filter((card) => card.category === "限時活動")
    .slice()
    .sort((a, b) => dateToNumber(b.date) - dateToNumber(a.date));

  let blocks = page.blocks ?? [];
  const normalizedTitle = page.title?.replace(/\s+/g, "");
  if (
    blocks[0]?.type === "heading" &&
    blocks[0]?.text?.replace(/\s+/g, "") === normalizedTitle
  ) {
    blocks = blocks.slice(1);
  }
  const joinUsBenefits = isJoinUsPage
    ? [
        j("join_015"),
        j("join_016"),
        j("join_017"),
        j("join_018"),
        j("join_019"),
      ]
    : [];
  const joinUsResponsibilities = isJoinUsPage
    ? [
        {
          title: j("join_020"),
          englishTitle: j("join_021"),
          items: [j("join_022"), j("join_023"), j("join_024")],
        },
        {
          title: j("join_025"),
          englishTitle: j("join_026"),
          items: [j("join_027")],
        },
        {
          title: j("join_028"),
          englishTitle: j("join_029"),
          items: [
            j("join_030"),
            j("join_031"),
            j("join_032"),
            j("join_033"),
          ],
        },
        {
          title: j("join_034"),
          id: "language",
          englishTitle: j("join_035"),
          items: [
            j("join_036"),
            j("join_037"),
          ],
        },
      ]
    : [];
  const joinUsQualities = isJoinUsPage
    ? j("join_038").split("\n").filter(Boolean).map(stripLeadingBullet)
    : [];
  const joinUsLanguageNote = isJoinUsPage
    ? j("join_039")
    : "";
  const joinUsPriority = isJoinUsPage
    ? [
        j("join_040"),
        j("join_041"),
        j("join_042"),
        j("join_043"),
        j("join_044"),
        j("join_045"),
        j("join_046"),
        j("join_047"),
        j("join_048"),
      ]
    : [];
  const joinUsSalary = isJoinUsPage
    ? j("join_049").split("\n").filter(Boolean).map(stripLeadingBullet)
    : [];
  const joinUsSteps = isJoinUsPage ? [{title:j("join_001"),text:j("join_002")},{title:j("join_003"),text:j("join_004")},{title:j("join_005"),text:j("join_006")},{title:j("join_007"),text:j("join_008")},{title:j("join_009"),text:j("join_010")},{title:j("join_011"),text:j("join_012")},{title:j("join_013"),text:j("join_014")}] : [];
  const joinUsReachedStep = joinUsActiveStep;
  const { scrollY } = useScroll();
  const joinUsHeroY = useTransform(scrollY, [0, 900], ["0%", "32%"]);
  const aboutHeroY = useTransform(scrollY, [0, 900], ["0%", "30%"]);
  const aboutVisionY = useTransform(scrollY, [1100, 2100], ["0%", "12%"]);
  const JoinUsFade = ({ children, className = "", delay = 0 }) => (
    <motion.div
      className={className}
      initial={prefersReducedMotion ? false : "hidden"}
      whileInView={prefersReducedMotion ? undefined : "visible"}
      viewport={prefersReducedMotion ? undefined : { once: false, amount: 0.4 }}
      variants={
        prefersReducedMotion
          ? undefined
          : {
              hidden: { opacity: 0, y: 16 },
              visible: {
                opacity: 1,
                y: 0,
                transition: { duration: 0.55, ease: "easeOut", delay },
              },
            }
      }
    >
      {children}
    </motion.div>
  );
  useEffect(() => {
    if (!isJoinUsPage) return;
    setJoinUsActiveStep(-1);
  }, [isJoinUsPage, joinUsSteps.length]);
  useEffect(() => {
    if (!isJoinUsPage) return;
    joinUsStepRefs.current = joinUsStepRefs.current.slice(0, joinUsSteps.length);
    let rafId = 0;
    const updateActiveStep = () => {
      rafId = 0;
      const triggerLine = window.innerHeight * 0.74;
      let nextActiveStep = -1;
      joinUsStepRefs.current.forEach((node, index) => {
        if (!node) return;
        const rect = node.getBoundingClientRect();
        if (rect.top <= triggerLine) {
          nextActiveStep = index;
        }
      });
      setJoinUsActiveStep((current) => (current === nextActiveStep ? current : nextActiveStep));
    };
    const requestUpdate = () => {
      if (rafId) return;
      rafId = window.requestAnimationFrame(updateActiveStep);
    };
    requestUpdate();
    window.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);
    return () => {
      if (rafId) window.cancelAnimationFrame(rafId);
      window.removeEventListener("scroll", requestUpdate);
      window.removeEventListener("resize", requestUpdate);
    };
  }, [isJoinUsPage, joinUsSteps.length]);
  useEffect(() => {
    if (!isJoinUsPage) return;
    const node = joinUsMobileCarouselRef.current;
    if (!node) return;

    const slides = Array.from(node.querySelectorAll("[data-join-us-slide]"));
    const updateActiveSlide = () => {
      if (slides.length === 0) return;
      const centerPoint = node.scrollLeft + node.clientWidth / 2;
      let nextIndex = 0;
      slides.forEach((slide, index) => {
        const start = slide.offsetLeft;
        const end = start + slide.offsetWidth;
        if (centerPoint >= start && centerPoint < end) {
          nextIndex = index;
        }
      });
      setJoinUsMobileSlide((current) => (current === nextIndex ? current : nextIndex));
    };

    updateActiveSlide();
    node.addEventListener("scroll", updateActiveSlide, { passive: true });
    window.addEventListener("resize", updateActiveSlide);
    return () => {
      node.removeEventListener("scroll", updateActiveSlide);
      window.removeEventListener("resize", updateActiveSlide);
    };
  }, [isJoinUsPage]);

  if (isJoinUsPage) {
    return (
      <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
        <SiteHeader forceTransparent />
        <main className="flex-1 w-full">
          <section className="relative min-h-[56vh] overflow-hidden md:min-h-[76vh]">
            <div className="absolute inset-0">
              <motion.img
                src={j("join_050")}
                alt={j("join_051")}
                className="h-full w-full object-cover object-[center_25%] scale-[1.08] md:scale-[1.12] will-change-transform"
                style={prefersReducedMotion ? undefined : { y: joinUsHeroY }}
              />
              <div className="absolute inset-0 bg-black/25" />
            </div>
            <div className="relative mx-auto flex min-h-[56vh] max-w-5xl items-center justify-center px-6 py-24 md:min-h-[76vh] md:px-10 md:py-28">
              <JoinUsFade className="max-w-3xl space-y-6 text-center">
                <p className="text-sm font-semibold tracking-[0.35em] uppercase text-white/75 font-display">
                  {j("join_052")}</p>
                <h1 className="text-3xl md:text-5xl font-semibold tracking-wide font-display text-white">
                  {j("join_053")}</h1>
                <p className="text-sm md:text-lg leading-relaxed text-white/90">
                  {j("join_054")}<br />
                  {j("join_055")}</p>
              </JoinUsFade>
            </div>
          </section>

          <section className="bg-white">
            <div className="max-w-5xl mx-auto px-6 md:px-10 py-16 md:py-24">
              <JoinUsFade className="max-w-4xl mx-auto text-center space-y-6" delay={0.05}>
                <h2 className="text-2xl md:text-3xl font-semibold font-display text-[#1f2937]">
                  {j("join_056")}</h2>
                <p className="text-sm md:text-base leading-relaxed text-[#475569]">
                  {j("join_057")}</p>
                <p className="text-sm md:text-base leading-relaxed text-[#475569]">
                  {j("join_058")}</p>
              </JoinUsFade>

              <JoinUsFade className="mt-12 grid grid-cols-2 gap-4 md:grid-cols-4 md:gap-6" delay={0.08}>
                {[j("join_059"), j("join_060"), j("join_061"), j("join_062")].map((tag, index) => (
                  <motion.div
                    key={tag}
                    className="group relative mx-auto flex aspect-square w-full max-w-[7.5rem] items-center justify-center overflow-hidden rounded-full border border-[#d7dde3] bg-[#f8fafc] px-3 text-center text-xs md:text-sm font-semibold text-[#1f2937] shadow-[0_10px_30px_rgba(15,23,42,0.04)] transition-[box-shadow,transform,border-color] duration-300 md:hover:border-[#8fc8f0] md:hover:shadow-[0_0_24px_rgba(143,200,240,0.45),0_10px_30px_rgba(15,23,42,0.04)] md:hover:-translate-y-0.5"
                    initial={prefersReducedMotion ? false : "hidden"}
                    whileInView={prefersReducedMotion ? undefined : "visible"}
                    viewport={prefersReducedMotion ? undefined : { once: true, amount: 0.75 }}
                    variants={
                      prefersReducedMotion
                        ? undefined
                        : {
                            hidden: { opacity: 0, scale: 0.82, x: -12 },
                            visible: {
                              opacity: 1,
                              scale: 1,
                              x: 0,
                              transition: {
                                duration: 0.55,
                                ease: "easeOut",
                                delay: index * 0.12,
                              },
                            },
                          }
                    }
                  >
                    <span className="max-w-[4.5rem]">{tag}</span>
                  </motion.div>
                ))}
              </JoinUsFade>
            </div>
          </section>

          <section className="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-20">
            <div className="lg:hidden w-screen relative left-1/2 -translate-x-1/2 pb-4 md:pb-16">
              <div
                ref={joinUsMobileCarouselRef}
                className="flex gap-3 overflow-x-auto snap-x snap-mandatory scroll-smooth px-0 hide-scrollbar"
              >
                <figure
                  data-join-us-slide
                  className="relative min-w-[85%] md:min-w-[70%] snap-center overflow-hidden bg-[#f8fafc]"
                >
                  <img loading="lazy" decoding="async"
                    src={j("join_063")}
                    alt={j("join_064")}
                    className="h-[240px] sm:h-[280px] w-full object-cover"
                  />
                </figure>
                <figure
                  data-join-us-slide
                  className="relative min-w-[85%] md:min-w-[70%] snap-center overflow-hidden bg-[#f8fafc]"
                >
                  <img loading="lazy" decoding="async"
                    src={j("join_065")}
                    alt={j("join_066")}
                    className="h-[240px] sm:h-[280px] w-full object-cover"
                  />
                </figure>
                <figure
                  data-join-us-slide
                  className="relative min-w-[85%] md:min-w-[70%] snap-center overflow-hidden bg-[#f8fafc]"
                >
                  <img loading="lazy" decoding="async"
                    src={j("join_067")}
                    alt={j("join_068")}
                    className="h-[240px] sm:h-[280px] w-full object-cover"
                  />
                </figure>
              </div>
              <div className="mt-4 flex items-center justify-center gap-2">
                {[0, 1, 2].map((index) => (
                  <button
                    key={`join-us-dot-${index}`}
                    type="button"
                    aria-label={t('顯示第 {count} 張照片',{count:index+1})}
                    aria-pressed={index === joinUsMobileSlide}
                    onClick={() => {
                      const node = joinUsMobileCarouselRef.current;
                      if (!node) return;
                      const slide = node.querySelectorAll("[data-join-us-slide]")[index];
                      slide?.scrollIntoView({ behavior: "smooth", inline: "start", block: "nearest" });
                    }}
                    className="flex h-11 w-11 items-center justify-center"
                  >
                    <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full transition-all duration-300 ${
                      index === joinUsMobileSlide
                        ? "scale-125 bg-[#2b5f8f]"
                        : "bg-[#cbd5e1] hover:bg-[#94a3b8]"
                    }`} />
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] items-start">
              <div className="hidden lg:block space-y-4 lg:sticky lg:top-28">
                <figure className="overflow-hidden rounded-sm border border-[#e2e8f0] bg-[#eef2f6] aspect-[4/5]">
                  <img loading="lazy" decoding="async"
                    src={j("join_063")}
                    alt={j("join_069")}
                    className="h-full w-full object-cover object-center"
                  />
                </figure>
                <div className="grid gap-4 sm:grid-cols-2">
                  <figure className="overflow-hidden rounded-sm border border-[#e2e8f0] bg-[#f0f4f8] aspect-[4/3]">
                    <img loading="lazy" decoding="async"
                      src={j("join_065")}
                      alt={j("join_070")}
                      className="h-full w-full object-cover object-center"
                    />
                  </figure>
                  <figure className="overflow-hidden rounded-sm border border-[#e2e8f0] bg-[#f0f4f8] aspect-[4/3]">
                    <img loading="lazy" decoding="async"
                      src={j("join_067")}
                      alt={j("join_071")}
                      className="h-full w-full object-cover object-center"
                    />
                  </figure>
                </div>
              </div>

              <div className="space-y-12">
                <JoinUsFade className="space-y-4">
                  <div className="space-y-6 text-sm md:text-base text-[#475569] leading-relaxed">
                    {joinUsResponsibilities.map((group) => (
                      <div key={group.title} className="space-y-3">
                        {group.englishTitle ? (
                          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                            {group.englishTitle}
                          </p>
                        ) : null}
                        <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                          {group.title}
                        </h2>
                        <ul className="space-y-3">
                          {group.items.map((item, itemIndex) => {
                            const isLanguagePriorityItem =
                              group.id === "language" && itemIndex === 1;
                            const isNoteItem = item.startsWith("※");
                            if (isNoteItem) {
                              return (
                                <li key={item} className="pl-5">
                                  <p className="text-xs md:text-sm text-[#94a3b8] leading-relaxed">
                                    {item}
                                  </p>
                                </li>
                              );
                            }
                            return (
                              <li key={item} className="flex gap-3">
                                <span
                                  className={`mt-2 h-1.5 w-1.5 rounded-full shrink-0 ${
                                    isLanguagePriorityItem ? "bg-[#d97706]" : "bg-[#2b5f8f]"
                                  }`}
                                />
                                <div className="space-y-1">
                                  <span>{item}</span>
                                  {isLanguagePriorityItem && joinUsLanguageNote ? (
                                    <p className="text-xs md:text-sm text-[#94a3b8] leading-relaxed">
                                      {joinUsLanguageNote}
                                    </p>
                                  ) : null}
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    ))}
                  </div>
                </JoinUsFade>

                <JoinUsFade className="space-y-4" delay={0.05}>
                  <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                    {j("join_072")}</p>
                  <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                    {j("join_073")}</h2>
                  <ul className="space-y-3 text-sm md:text-base text-[#475569] leading-relaxed">
                    {joinUsQualities.map((item) => (
                      <li key={item} className="flex gap-3">
                        <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[#2b5f8f] shrink-0" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                  {joinUsPriority.length > 0 ? (
                    <div className="pt-2 space-y-3">
                      <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                        {j("join_074")}</p>
                      <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                        {j("join_075")}</h2>
                      <ul className="space-y-3 text-sm md:text-base text-[#475569] leading-relaxed">
                        {joinUsPriority.map((item) => (
                          <li key={item} className="flex gap-3">
                            <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[#d97706] shrink-0" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  <p className="text-xs md:text-sm text-[#94a3b8] leading-relaxed">
                    {j("join_076")}</p>
                </JoinUsFade>

                <JoinUsFade className="space-y-4" delay={0.1}>
                  <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                    {j("join_077")}</p>
                  <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                    {j("join_078")}</h2>
                  <ul className="space-y-3 text-sm md:text-base text-[#475569] leading-relaxed">
                    {joinUsBenefits.map((item) => (
                      <li key={item} className="flex gap-3">
                        <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[#2b5f8f] shrink-0" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </JoinUsFade>

                <JoinUsFade className="space-y-4" delay={0.12}>
                  <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                    {j("join_079")}</p>
                  <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                    {j("join_080")}</h2>
                  <ul className="space-y-3 text-sm md:text-base text-[#475569] leading-relaxed">
                    {joinUsSalary.map((item) => (
                      <li key={item} className="flex gap-3">
                        <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[#2b5f8f] shrink-0" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </JoinUsFade>
              </div>
            </div>
          </section>

          <section className="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-20">
            <JoinUsFade className="border-t border-[#d7dde3] pt-6 md:pt-10">
              <div className="max-w-4xl space-y-4">
                <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                  {j("join_081")}</p>
                <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                  {j("join_082")}</h2>
                <p className="text-sm md:text-base leading-relaxed text-[#475569]">
                  {j("join_083")}</p>
              </div>
            </JoinUsFade>
          </section>

          <section className="max-w-6xl mx-auto px-6 md:px-10 py-14 md:py-20">
            <div className="space-y-8 border-t border-[#d7dde3] pt-10">
              <div className="flex items-end justify-between gap-6">
                <div className="space-y-3">
                  <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                    {j("join_084")}</p>
                  <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                    {j("join_085")}</h2>
                </div>
                <div className="hidden md:block h-px flex-1 bg-[#e2e8f0]" />
              </div>

              <div className="relative">
                <div className="absolute left-4 top-0 bottom-0 w-px bg-[#d7dde3] md:left-1/2 md:-translate-x-1/2" />
                <div
                  className="absolute left-4 top-0 w-px rounded-full bg-[#2b5f8f] transition-all duration-700 ease-out md:left-1/2 md:-translate-x-1/2"
                  style={{
                    height: `${((Math.max(joinUsReachedStep, -1) + 1) / Math.max(joinUsSteps.length, 1)) * 100}%`,
                  }}
                />
                <div className="space-y-8 md:space-y-12">
                  {joinUsSteps.map((step, index) => (
                    <article
                      key={step.title}
                      ref={(node) => {
                        joinUsStepRefs.current[index] = node;
                      }}
                      data-index={index}
                      className="relative grid gap-4 pl-10 md:pl-0 md:grid-cols-[minmax(0,1fr)_5rem_minmax(0,1fr)] md:items-start"
                    >
                      <div
                        className={`w-fit max-w-full rounded-sm border border-[#e2e8f0] bg-white p-5 shadow-[0_8px_24px_rgba(15,23,42,0.04)] ${
                          index % 2 === 0
                            ? "md:col-start-1 md:justify-self-end md:pr-10 md:text-right"
                            : "md:col-start-3 md:justify-self-start md:pl-10"
                        }`}
                      >
                        <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                          {step.title}
                        </p>
                        <p
                          className={`mt-3 text-base md:text-lg font-semibold font-display transition-colors ${
                            index <= joinUsReachedStep ? "text-[#2b5f8f]" : "text-[#94a3b8]"
                          }`}
                        >
                          {step.text}
                        </p>
                      </div>

                      <div className="absolute left-4 top-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-white ring-4 ring-[#f7f8fa] md:left-1/2 md:-translate-x-1/2 md:top-1">
                        <span
                          className={`h-2.5 w-2.5 rounded-full transition-colors duration-700 ${
                            index <= joinUsReachedStep ? "bg-[#2b5f8f]" : "bg-[#cbd5e1]"
                          }`}
                        />
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section className="max-w-6xl mx-auto px-6 md:px-10 py-14 md:py-20">
            <div className="relative max-w-3xl mx-auto overflow-hidden rounded-sm border border-[#e2e8f0] bg-[#f8fafc] px-6 py-10 md:px-10 md:py-12 text-center shadow-[0_18px_40px_rgba(15,23,42,0.12)]">
              <div className="absolute inset-0">
                <img loading="lazy" decoding="async"
                  src={j("join_086")}
                  alt={j("join_087")}
                  className="h-full w-full scale-[1.12] object-cover object-[100%_center]"
                />
              </div>
              <div className="absolute inset-0 bg-black/25" />
              <JoinUsFade className="relative z-10">
                <p className="text-xs font-semibold tracking-[0.3em] uppercase text-white/80 font-display">
                  {j("join_088")}</p>
                <h2 className="mt-3 text-2xl md:text-3xl font-semibold tracking-wide font-display text-white">
                  {j("join_089")}</h2>
                <div className="mt-6 flex justify-center">
                  <SiteLink
                    to={j("join_apply_url")}
                    target="_blank" rel="noopener noreferrer"
                    data-recruit-apply="true"
                    className="inline-flex items-center justify-center rounded-full bg-[#8ec8f0] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#7bbbe7]"
                  >
                    {j("join_090")}</SiteLink>
                </div>
                {/^https?:\/\//i.test(j("join_apply_url")) && <p data-recruit-notice="true" className="mt-3 text-xs leading-6 text-white">{t("目前開啟外部應徵表單；站內招募表單建置中。")}</p>}
              </JoinUsFade>
            </div>
          </section>

        </main>
        <SiteFooter />
      </div>
    );
  }

  if (isAboutPage) {
    const aboutOverlineClass =
      "text-xs md:text-sm font-semibold tracking-[0.3em] uppercase font-display";
    const aboutIntro = [
      "SnowLand在北海道已經經營多個雪季，",
      "起源於我們多年在日本的親子滑雪教學經驗。",
      "滑雪是一個能夠創造美好回憶的機會。",
      "在滑雪的冒險中",
      "家長與孩子一起克服困難",
      "建立彼此的信任與依賴。",
    ];
    const aboutResortsHighlight = (
      <span className="text-brand-blue font-bold">
        {c("about_001")}</span>
    );
    const aboutSections = [
      {
        id: "origin",
        englishTitle: c("about_002"),
        title: c("about_003"),
        paragraphs: [
          c("about_004"),
          c("about_005"),
          c("about_006"),
        ],
        image: c("about_007"),
      },
      {
        id: "school",
        englishTitle: c("about_008"),
        title: c("about_009"),
        paragraphs: [
          <>{c("about_010")}{aboutResortsHighlight}{c("about_011")}</>,
          c("about_012"),
          c("about_013"),
        ],
        image: c("about_014"),
      },
      {
        id: "feedback",
        englishTitle: c("about_015"),
        title: c("about_016"),
        paragraphs: c("about_017").split("\n").filter(Boolean),
        image: c("about_018"),
      },
      {
        id: "booking",
        englishTitle: c("about_019"),
        title: c("about_020"),
        paragraphs: c("about_021").split("\n").filter(Boolean),
        image: c("about_022"),
      },
    ];
    const visionParagraphs = [
      c("about_023"),
      c("about_024"),
    ];

    useEffect(() => {
      aboutSectionRefs.current = aboutSectionRefs.current.slice(0, aboutSections.length);
    }, [aboutSections.length]);

    useEffect(() => {
      if (!aboutSections.length) return;
      const observer = new IntersectionObserver(
        (entries) => {
          const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
          if (!visible) return;
          const index = Number(visible.target.dataset.index);
          if (!Number.isNaN(index)) {
            setAboutActiveIndex(index);
          }
        },
        { rootMargin: "0px 0px -25% 0px", threshold: [0.15, 0.35, 0.55] }
      );
      aboutSectionRefs.current.forEach((node) => {
        if (node) observer.observe(node);
      });
      return () => observer.disconnect();
    }, [aboutSections]);

    return (
      <div className="min-h-screen bg-[#f7f6f3] text-[#1f2937] flex flex-col">
        <SiteHeader forceTransparent />
        <main className="flex-1 w-full">
          <section className="relative h-[70vh] min-h-[520px] w-full overflow-hidden">
            <div className="absolute inset-0">
              <motion.img
                src={c("about_025")}
                alt={c("about_026")}
                className="absolute inset-0 h-full w-full object-cover object-center scale-[1.08] md:scale-[1.12]"
                style={prefersReducedMotion ? undefined : { y: aboutHeroY }}
              />
              <div className="absolute inset-0 bg-black/35" />
            </div>
            <div className="relative z-10 flex h-full items-center justify-center px-6 text-center text-white">
              <div className="max-w-2xl space-y-6">
                <p className={`${aboutOverlineClass} text-white/80`}>{c("about_027")}</p>
                <h1 className="text-3xl md:text-5xl font-semibold tracking-wide font-display">
                  {c("about_028")}</h1>
                <div className="text-base md:text-lg leading-relaxed text-white/90">
                  <p>{c("about_029")}</p>
                  <p>{c("about_030")}</p>
                </div>
              </div>
            </div>
          </section>

          <section className="max-w-6xl mx-auto px-6 py-20">
            <div className="grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
              <div className="relative hidden lg:block">
                <div className="sticky top-28">
                  <div className="relative aspect-[4/5] overflow-hidden rounded-sm bg-[#e6e2db] shadow-[0_20px_40px_rgba(15,23,42,0.12)]">
                    {aboutSections.map((section, index) => (
                      <img
                        key={`about-sticky-${section.id}`}
                        src={section.image}
                        alt={section.title}
                        className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-700 ${
                          aboutActiveIndex === index ? "opacity-100" : "opacity-0"
                        }`}
                        loading="lazy"
                      />
                    ))}
                  </div>
                </div>
              </div>
              <div className="space-y-16">
                {aboutSections.map((section, index) => (
                  <section
                    key={section.id}
                    ref={(node) => {
                      aboutSectionRefs.current[index] = node;
                    }}
                    data-index={index}
                    className="space-y-6"
                  >
                    <div
                      className={`lg:hidden rounded-sm overflow-hidden bg-[#e6e2db] shadow-[0_16px_32px_rgba(15,23,42,0.12)] ${
                        index % 2 === 0 ? "" : "lg:order-2"
                      } ${section.id === "feedback" ? "aspect-[4/3]" : ""}`}
                    >
                      <img
                        src={section.image}
                        alt={section.title}
                        className={`w-full object-cover ${
                          section.id === "feedback"
                            ? "h-full object-[50%_85%]"
                            : "h-auto"
                        }`}
                        loading="lazy"
                      />
                    </div>
                    <div className="space-y-2">
                      {section.englishTitle ? (
                        <p className={`${aboutOverlineClass} text-[#94a3b8]`}>
                          {section.englishTitle}
                        </p>
                      ) : null}
                      <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                        {section.title}
                      </h2>
                    </div>
                    <div className="space-y-4 text-sm md:text-base text-[#475569] leading-relaxed">
                      {section.paragraphs.map((text, paragraphIndex) => (
                        <p key={`${section.id}-p-${paragraphIndex}`}>{text}</p>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          </section>

          <section className="relative w-full overflow-hidden bg-[#f7f6f3]">
            <div className="absolute inset-0">
              <motion.img
                src={c("about_031")}
                alt={c("about_032")}
                className="absolute -top-[24%] left-0 right-0 h-[148%] w-full object-cover object-top scale-[1.05] md:scale-[1.08]"
                style={prefersReducedMotion ? undefined : { y: aboutVisionY }}
              />
              <div className="absolute inset-0 bg-black/35" />
            </div>
            <div className="relative z-10 max-w-4xl mx-auto px-6 py-24 text-center text-white">
              <h2 className="text-2xl font-semibold tracking-wide font-display">
                {c("about_033")}</h2>
              <div className="mt-8 space-y-4 text-sm md:text-base leading-relaxed text-white/90">
                {visionParagraphs.map((text, index) => (
                  <p key={`vision-${index}`}>{text}</p>
                ))}
              </div>
            </div>
          </section>
        </main>
        <SiteFooter />
      </div>
    );
  }
  const stripPreparationToc = (items) => {
    if (items[0]?.type === "paragraph" && items[0]?.text?.trim() === "目錄") {
      let index = 1;
      while (items[index]?.type === "list") {
        index += 1;
      }
      return items.slice(index);
    }
    return items;
  };
  const makeSlug = (text) =>
    text
      .trim()
      .toLowerCase()
      .replace(/[^\w\u4e00-\u9fa5]+/g, "-")
      .replace(/^-+|-+$/g, "");
  let preparationHeroImage = null;
  let preparationLead = null;
  let preparationToc = [];
  let preparationBlocks = blocks;
  let preparationRelatedLinks = [];
  if (isGuidesPreparationPage) {
    const cleanedBlocks = stripPreparationToc(blocks);
    const heroIndex = cleanedBlocks.findIndex((block) => block.type === "image");
    if (heroIndex >= 0) {
      preparationHeroImage = cleanedBlocks[heroIndex];
    }
    const withoutHero = heroIndex >= 0
      ? cleanedBlocks.filter((_, index) => index !== heroIndex)
      : cleanedBlocks;
    const leadIndex = withoutHero.findIndex(
      (block) => block.type === "paragraph" && (block.text?.length ?? 0) > 40
    );
    if (leadIndex >= 0) {
      preparationLead = withoutHero[leadIndex];
    }
    const withoutLead = leadIndex >= 0
      ? withoutHero.filter((_, index) => index !== leadIndex)
      : withoutHero;
    const tocCounters = { 2: 0, 3: 0, 4: 0 };
    preparationBlocks = withoutLead.map((block) => {
      if (block.type !== "heading" || block.level < 2 || block.level > 4) {
        return block;
      }
      const title = block.text?.trim() ?? "";
      if (!title) {
        return block;
      }
      if (block.level === 2) {
        tocCounters[2] += 1;
        tocCounters[3] = 0;
        tocCounters[4] = 0;
      } else if (block.level === 3) {
        tocCounters[3] += 1;
        tocCounters[4] = 0;
      } else if (block.level === 4) {
        tocCounters[4] += 1;
      }
      const numberParts = [tocCounters[2], tocCounters[3], tocCounters[4]].filter(
        (value, index) => {
          if (index === 0) {
            return value > 0;
          }
          return value > 0;
        }
      );
      const numberPrefix = numberParts.join(".");
      const hasLeadingNumber = /^\d+(\.\d+)*[.、]?\s*/.test(title);
      const displayTitle = hasLeadingNumber || !numberPrefix ? title : `${numberPrefix} ${title}`;
      const id = `section-${makeSlug(title)}`;
      preparationToc.push({ id, title, displayTitle, level: block.level });
      return { ...block, id };
    });
    const relatedTitles = [
      "精選5條林間雪道，自由穿梭森林，體驗滑雪快感也要顧及安全",
      "粉雪控必去！旭川神居滑雪場交通、住宿、教練全指南",
      "旭川景點完整指南：北海道旭川自由行必去景點、美食與住宿推薦",
    ];
    preparationRelatedLinks = relatedTitles
      .map((title) => {
        const match = guidesArticles.find((article) => article.title === title);
        if (!match) return null;
        const localRoute = localArticleRoutes[match.url];
        return {
          title: match.title,
          image: match.image,
          category: match.category,
          date: match.date,
          excerpt: match.excerpt,
          href: localRoute || match.url,
          isExternal: !localRoute,
        };
      })
      .filter(Boolean)
      .sort((a, b) => dateToNumber(b.date) - dateToNumber(a.date));
  }
  const content = [];
  const imageStyle = isPhotographyHowToBookPage
    ? {
        figureClassName:
          "w-full max-w-2xl mx-auto rounded-sm overflow-hidden border border-[#e2e8f0]",
        imageClassName: "w-full h-auto object-cover",
      }
    : undefined;
  let imageBuffer = [];

  const faqSections = [];
  if (isGuidesFaqPage) {
    let currentSection = { title: null, items: [] };
    let currentItem = null;
    const isQuestion = (text = "") => /[?？]\s*$/.test(text.trim());
    const pushItem = () => {
      if (currentItem) {
        currentSection.items.push(currentItem);
        currentItem = null;
      }
    };
    const pushSection = () => {
      if (currentSection.title || currentSection.items.length) {
        faqSections.push(currentSection);
      }
      currentSection = { title: null, items: [] };
    };

    blocks.forEach((block) => {
      if (block.type === "heading" && block.level === 2) {
        pushItem();
        pushSection();
        currentSection.title = block.text;
        return;
      }
      if (block.type === "paragraph" && isQuestion(block.text)) {
        pushItem();
        currentItem = { question: block.text, answers: [] };
        return;
      }
      if (!currentItem) {
        return;
      }
      currentItem.answers.push(block);
    });

    pushItem();
    pushSection();
  } else {
    const blocksForRender = isGuidesPreparationPage ? preparationBlocks : blocks;
    blocksForRender.forEach((block, index) => {
      if (block.type === "image") {
        imageBuffer.push(block);
        return;
      }
      if (imageBuffer.length) {
        content.push(renderImageGroup(imageBuffer, index, true, imageStyle));
        imageBuffer = [];
      }
      const renderedBlock = renderBlock(block, index);
      if (renderedBlock) {
        content.push(renderedBlock);
      }
    });

    if (imageBuffer.length) {
      content.push(
        renderImageGroup(
          imageBuffer,
          blocksForRender.length,
          true,
          imageStyle
        )
      );
    }
  }
  let faqSectionsWithIndex = [];
  if (isGuidesFaqPage) {
    let faqIndex = 0;
    faqSectionsWithIndex = faqSections.map((section) => ({
      ...section,
      items: section.items.map((item) => ({
        ...item,
        index: faqIndex++,
      })),
    }));
  }

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      {isGuidesPreparationPage ? (
        <main className="flex-1 pt-28 pb-20">
          <section className="max-w-5xl mx-auto px-6">
            <div className="text-center">
              <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                {page.subtitle}
              </p>
              {preparationArticle?.category && (
                <div className="mt-4 flex justify-center">
                  <span
                    className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-[0.2em] uppercase font-display ${
                      categoryBadgeStyles[preparationArticle.category] ||
                      "bg-[#e2e8f0] text-[#475569]"
                    }`}
                  >
                    {preparationArticle.category}
                  </span>
                </div>
              )}
              <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
                {page.title}
              </h1>
              {preparationArticle?.date && (
                <p className="mt-3 text-xs font-semibold tracking-[0.2em] uppercase text-[#94a3b8] font-display">
                  {preparationArticle.date}
                </p>
              )}
            </div>
            {preparationHeroImage && (
              <div className="mt-10 rounded-sm overflow-hidden bg-[#e2e8f0]">
                <img loading="lazy" decoding="async"
                  src={preparationHeroImage.src}
                  alt={preparationHeroImage.alt || page.title}
                  className="w-full h-full object-cover"
                />
              </div>
            )}
          </section>

          <section className="max-w-5xl mx-auto px-6 mt-12">
            <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
              {preparationToc.length > 0 && (
                <aside className="order-first lg:order-none lg:w-64">
                  <div className="w-full border-r border-[#e2e8f0] pr-8 text-left">
                    <div className="flex items-center justify-between gap-4">
                      <p className="text-sm font-semibold text-[#1f2937] font-display">{t("目錄")}</p>
                      <button
                        type="button"
                        onClick={() => setIsTocOpen((prev) => !prev)}
                        className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center text-sm font-semibold text-[#64748b] hover:text-[#2b5f8f] transition-colors"
                        aria-expanded={isTocOpen}
                        aria-label={t(isTocOpen ? "收合目錄" : "展開目錄")}
                      >
                        {isTocOpen ? "−" : "+"}
                      </button>
                    </div>
                    {isTocOpen && (
                      <ul className="mt-4 space-y-2 text-sm text-[#64748b]">
                        {preparationToc.map((item) => (
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
                {preparationLead && (
                  <p className="text-sm md:text-base text-[#475569] leading-relaxed mb-8">
                    {renderTextWithLinks(preparationLead.text)}
                  </p>
                )}
                <div className="space-y-6">
                  {content}
                </div>
              </div>
            </div>
          </section>
          {preparationRelatedLinks.length > 0 && (
            <section className="max-w-5xl mx-auto px-6 mt-16">
              <div className="flex items-center gap-4">
                <h2 className="text-2xl font-semibold text-[#1f2937] font-display">{t("延伸閱讀")}</h2>
                <div className="h-px flex-1 bg-[#e2e8f0]" />
              </div>
              <div className="mt-8 grid w-full max-w-4xl mx-auto gap-6 md:grid-cols-2 lg:grid-cols-3">
                {preparationRelatedLinks.map((item) => (
                  <a
                    key={item.title}
                    href={item.href}
                    className="group bg-white rounded-sm overflow-hidden shadow-[0_16px_32px_rgba(15,23,42,0.08)] transition-transform duration-300 hover:-translate-y-1"
                    target={item.isExternal ? "_blank" : undefined}
                    rel={item.isExternal ? "noopener noreferrer" : undefined}
                  >
                    <div className="aspect-square overflow-hidden bg-[#e2e8f0]">
                      <img
                        src={item.image}
                        alt={item.title}
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                        loading="lazy"
                      />
                    </div>
                    <div className="p-5 space-y-3">
                      {item.category && (
                        <span
                          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-[0.2em] uppercase font-display ${
                            categoryBadgeStyles[item.category] || "bg-[#e2e8f0] text-[#475569]"
                          }`}
                        >
                          {item.category}
                        </span>
                      )}
                      {item.date && (
                        <p className="text-xs font-semibold tracking-[0.2em] uppercase text-[#94a3b8] font-display">
                          {item.date}
                        </p>
                      )}
                      <h3 className="text-base font-semibold text-[#1f2937] leading-relaxed">
                        {item.title}
                      </h3>
                      {item.excerpt && (
                        <p className="text-sm text-[#64748b] leading-relaxed line-clamp-2">
                          {item.excerpt}
                        </p>
                      )}
                    </div>
                  </a>
                ))}
              </div>
            </section>
          )}
        </main>
      ) : (
        <main className="max-w-5xl mx-auto px-6 pt-32 pb-24 flex-1 w-full">
          <div className="text-center">
            <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
              {page.subtitle}
            </p>
            <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
              {page.title}
            </h1>
          </div>
          {isDealsPage && (
            <div className="mt-10 border-b border-[#e2e8f0]">
              <div className="flex flex-wrap items-center justify-center gap-12 md:gap-16 text-base md:text-lg font-semibold text-[#6b7280] font-display">
                {dealsCategoryLinks.map((link) => {
                  const isActive = link.key === activeDealsKey;
                  return (
                    <SiteLink
                      key={link.key}
                      to={link.href}
                      className={`relative inline-flex min-h-11 items-center pb-4 transition-colors duration-200 group ${
                        isActive ? "text-[#111827]" : "hover:text-[#2b5f8f]"
                      }`}
                      aria-current={isActive ? "page" : undefined}
                    >
                      {t(link.label)}
                      <span
                        className={`absolute left-0 -bottom-[1px] h-0.5 transition-all duration-300 ${
                          isActive ? "w-full bg-[#111827]" : "w-0 bg-[#2b5f8f] group-hover:w-full"
                        }`}
                      />
                    </SiteLink>
                  );
                })}
              </div>
            </div>
          )}
          {isGuidesFaqPage ? (
            <section className="mt-10 space-y-6">
              <div className="space-y-10">
                {faqSectionsWithIndex.map((section) => (
                  <div key={section.title ?? "faq-section"} className="space-y-6">
                    {section.title && (
                      <h2 className={headingStyles[2] ?? headingStyles[3]}>
                        {section.title}
                      </h2>
                    )}
                    <div className="space-y-6">
                      {section.items.map((item) => {
                        const isOpen = openFaqIndex === item.index;
                        return (
                          <div key={item.question} className="border-b border-[#d7dde3] pb-6">
                            <button
                              type="button"
                              onClick={() => setOpenFaqIndex(isOpen ? -1 : item.index)}
                              className="flex w-full items-start justify-between gap-6 text-left"
                              aria-expanded={isOpen}
                            >
                              <h3 className="text-lg font-semibold text-[#1f2937]">
                                {item.question}
                              </h3>
                              <span className="text-[#94a3b8] text-lg">
                                {isOpen ? "−" : "＋"}
                              </span>
                            </button>
                            {isOpen && (
                              <div className="mt-3 space-y-3">
                                {item.answers.map((answer, answerIndex) => {
                                  if (answer.type === "paragraph") {
                                    return (
                                      <p
                                        key={`faq-answer-${answerIndex}`}
                                        className="text-sm md:text-base leading-relaxed text-[#475569]"
                                      >
                                        {renderTextWithLinks(answer.text)}
                                      </p>
                                    );
                                  }
                                  if (answer.type === "list") {
                                    return (
                                      <ul
                                        key={`faq-list-${answerIndex}`}
                                        className="pl-5 space-y-2 list-disc text-sm md:text-base text-[#475569] leading-relaxed"
                                      >
                                        {answer.items.map((listItem, listIndex) => (
                                          <li key={`faq-list-item-${answerIndex}-${listIndex}`}>
                                            {renderTextWithLinks(listItem)}
                                          </li>
                                        ))}
                                      </ul>
                                    );
                                  }
                                  if (answer.type === "heading") {
                                    return (
                                      <p
                                        key={`faq-heading-${answerIndex}`}
                                        className="text-sm md:text-base font-semibold text-[#1f2937]"
                                      >
                                        {answer.text}
                                      </p>
                                    );
                                  }
                                  return null;
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : (
            <section className="mt-10 space-y-6">
              {content}
            </section>
          )}
          {isDealsPromoPage && promoArticles.length > 0 && (
            <section className="mt-12 grid w-full max-w-4xl mx-auto gap-6 md:grid-cols-2 lg:grid-cols-3">
              {promoArticles.map((item) => (
                <SiteLink
                  key={item.url}
                  to={item.url}
                  target={item.url.startsWith('/') ? undefined : '_blank'}
                  rel="noopener noreferrer"
                  className="group bg-white rounded-sm overflow-hidden shadow-[0_16px_32px_rgba(15,23,42,0.08)] transition-transform duration-300 hover:-translate-y-1"
                >
                  <div className="aspect-square bg-[#e2e8f0] overflow-hidden">
                    <img loading="lazy" decoding="async"
                      src={item.image}
                      alt={item.title}
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                    />
                  </div>
                  <div className="p-5 space-y-3">
                    {item.category && (
                      <span
                        className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-[0.2em] uppercase font-display ${categoryBadgeStyles[item.category] || "bg-[#e2e8f0] text-[#475569]"}`}
                      >
                        {item.category}
                      </span>
                    )}
                    {item.date && (
                      <p className="text-xs font-semibold tracking-[0.2em] uppercase text-[#94a3b8] font-display">
                        {item.date}
                      </p>
                    )}
                    <h3 className="text-base font-semibold text-[#1f2937] leading-relaxed">
                      {item.title}
                    </h3>
                    {item.excerpt && (
                      <p className="text-sm text-[#64748b] leading-relaxed line-clamp-2">
                        {item.excerpt}
                      </p>
                    )}
                  </div>
                </SiteLink>
              ))}
            </section>
          )}
          {isAboutPage && (
            <div className="mt-12 flex justify-center">
              <SiteLink
                to="/contact"
                className="inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#1f3f5f]"
              >{t("聯絡我們")}</SiteLink>
            </div>
          )}
        </main>
      )}
      <SiteFooter />
    </div>
  );
}

export default LegacyContentPage;
