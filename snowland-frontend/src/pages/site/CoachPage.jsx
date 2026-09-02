import React, { forwardRef, useEffect, useRef, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import coaches from '../../data/site/coaches';
import cashReviews from '../../data/site/cashReviews';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import { fetchWebsiteCoaches } from '../../api/websiteCoaches';

const CashFadeIn = forwardRef(function CashFadeIn(
  { as: Tag = "div", className = "", delay = 0, style, children, ...props },
  forwardedRef
) {
  const ref = useRef(null);
  const [isVisible, setIsVisible] = useState(
    () => typeof window === "undefined" || typeof IntersectionObserver === "undefined"
  );

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof window === "undefined" || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setIsVisible(true);
        observer.unobserve(node);
      },
      {
        threshold: 0.15,
        rootMargin: "0px 0px -8% 0px",
      }
    );

    observer.observe(node);

    return () => observer.disconnect();
  }, []);

  const setRefs = (node) => {
    ref.current = node;

    if (typeof forwardedRef === "function") {
      forwardedRef(node);
      return;
    }

    if (forwardedRef && typeof forwardedRef === "object") {
      forwardedRef.current = node;
    }
  };

  const Component = Tag;
  void Component;

  return (
    <Component
      ref={setRefs}
      className={`opacity-0 transition-opacity duration-700 ease-out motion-reduce:opacity-100 motion-reduce:transition-none ${
        isVisible ? "opacity-100" : ""
      } ${className}`}
      style={{ transitionDelay: `${delay}ms`, ...style }}
      {...props}
    >
      {children}
    </Component>
  );
});

const CashScrollFade = forwardRef(function CashScrollFade(
  { as: Tag = "div", className = "", delay = 0, style, children, ...props },
  forwardedRef
) {
  const ref = useRef(null);
  const [isVisible, setIsVisible] = useState(
    () => typeof window === "undefined" || typeof IntersectionObserver === "undefined"
  );

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof window === "undefined" || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      {
        threshold: 0.45,
        rootMargin: "0px 0px -12% 0px",
      }
    );

    observer.observe(node);

    return () => observer.disconnect();
  }, []);

  const setRefs = (node) => {
    ref.current = node;

    if (typeof forwardedRef === "function") {
      forwardedRef(node);
      return;
    }

    if (forwardedRef && typeof forwardedRef === "object") {
      forwardedRef.current = node;
    }
  };

  const Component = Tag;
  void Component;

  return (
    <Component
      ref={setRefs}
      className={`opacity-0 translate-y-4 transition-all duration-700 ease-out motion-reduce:opacity-100 motion-reduce:translate-y-0 motion-reduce:transition-none ${
        isVisible ? "opacity-100 translate-y-0" : ""
      } ${className}`}
      style={{ transitionDelay: `${delay}ms`, ...style }}
      {...props}
    >
      {children}
    </Component>
  );
});

function CashPhotoCarousel({ images, mediaSurfaceClass, mediaShadowClass, label }) {
  const carouselRef = useRef(null);
  const slideRefs = useRef([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const node = carouselRef.current;
    if (!node || images.length === 0) return;

    slideRefs.current = slideRefs.current.slice(0, images.length);

    const updateCarouselState = () => {
      const maxScrollLeft = Math.max(node.scrollWidth - node.clientWidth, 0);
      const nextProgress = maxScrollLeft > 0 ? node.scrollLeft / maxScrollLeft : 1;
      const centerPoint = node.scrollLeft + node.clientWidth / 2;
      let nextIndex = 0;

      slideRefs.current.forEach((slide, index) => {
        if (!slide) return;
        const slideStart = slide.offsetLeft;
        const slideEnd = slideStart + slide.offsetWidth;
        if (centerPoint >= slideStart && centerPoint < slideEnd) {
          nextIndex = index;
        }
      });

      setScrollProgress((current) =>
        Math.abs(current - nextProgress) < 0.002 ? current : nextProgress
      );
      setActiveIndex((current) => (current === nextIndex ? current : nextIndex));
    };

    let rafId = 0;
    const requestUpdate = () => {
      if (rafId) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = 0;
        updateCarouselState();
      });
    };

    requestUpdate();
    node.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);

    return () => {
      if (rafId) window.cancelAnimationFrame(rafId);
      node.removeEventListener("scroll", requestUpdate);
      window.removeEventListener("resize", requestUpdate);
    };
  }, [images.length]);

  useEffect(() => {
    if (images.length < 2) return;

    const timer = window.setInterval(() => {
      const node = carouselRef.current;
      if (!node) return;
      const nextIndex = (activeIndex + 1) % images.length;
      const slide = slideRefs.current[nextIndex];
      if (!slide) return;

      node.scrollTo({
        left: slide.offsetLeft,
        behavior: "smooth",
      });
      setActiveIndex(nextIndex);

      const maxScrollLeft = Math.max(node.scrollWidth - node.clientWidth, 0);
      const nextProgress = maxScrollLeft > 0 ? slide.offsetLeft / maxScrollLeft : 1;
      setScrollProgress(nextProgress);
    }, 4800);

    return () => window.clearInterval(timer);
  }, [activeIndex, images.length]);

  const scrollToRelativeIndex = (step) => {
    if (images.length < 2) return;

    const node = carouselRef.current;
    if (!node) return;

    const nextIndex = (activeIndex + step + images.length) % images.length;
    const slide = slideRefs.current[nextIndex];
    if (!slide) return;

    node.scrollTo({
      left: slide.offsetLeft,
      behavior: "smooth",
    });
    setActiveIndex(nextIndex);

    const maxScrollLeft = Math.max(node.scrollWidth - node.clientWidth, 0);
    const nextProgress = maxScrollLeft > 0 ? slide.offsetLeft / maxScrollLeft : 1;
    setScrollProgress(nextProgress);
  };

  const handleFrameClick = (event) => {
    const node = carouselRef.current;
    if (!node) return;

    const rect = node.getBoundingClientRect();
    const isRightSide = event.clientX - rect.left >= rect.width / 2;
    scrollToRelativeIndex(isRightSide ? 1 : -1);
  };

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-label={label}
        onClick={handleFrameClick}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          scrollToRelativeIndex(1);
        }}
        className={`overflow-hidden rounded-sm ${mediaSurfaceClass} ${mediaShadowClass} cursor-pointer select-none`}
      >
        <div
          ref={carouselRef}
          className="flex overflow-x-auto snap-x snap-mandatory scroll-smooth hide-scrollbar"
        >
          {images.map((image, imageIndex) => (
            <figure
              key={`${label}-${imageIndex}`}
              ref={(node) => {
                slideRefs.current[imageIndex] = node;
              }}
              className="flex w-full shrink-0 snap-start overflow-hidden aspect-[495/400]"
            >
              <img loading="lazy" decoding="async"
                src={image.src}
                alt={image.alt}
                className="block h-full w-full object-cover"
                style={image.objectPosition ? { objectPosition: image.objectPosition } : undefined}
                loading="lazy"
              />
            </figure>
          ))}
        </div>
      </div>
      <div className="mt-2 flex items-center gap-4">
        <div className="relative h-px flex-1 bg-[#d7dde3]">
          <div
            className="absolute left-0 top-0 h-px rounded-full bg-[#2b5f8f] transition-all duration-700 ease-out"
            style={{
              width: `${scrollProgress * 100}%`,
              minWidth: scrollProgress > 0 ? "2px" : "0px",
            }}
          />
        </div>
        <p className="text-[10px] font-semibold tracking-[0.3em] text-[#94a3b8] font-display">
          {String(activeIndex + 1).padStart(2, "0")} / {String(images.length).padStart(2, "0")}
        </p>
      </div>
    </div>
  );
}

function CoachPage() {
  const { slug } = useParams();
  const coach = coaches.find((item) => item.slug === slug);
  const [enabledCoachSlugs, setEnabledCoachSlugs] = useState(null);
  const isCashCoach = coach?.slug === "cash";
  const isCashLikeCoach = true;
  const coachDetailImage = coach?.detailImage ?? coach?.image;
  const coachVideos = coach?.videos ?? [];
  const coachReviews = coach?.reviews ?? [];
  const coachAbilityTags = coach?.abilityTags ?? null;
  const coachHeroBadges = coach?.heroBadges ?? [];
  const coachHideTeachingLead = coach?.hideTeachingLead ?? !["cash", "lily", "qizhen"].includes(coach?.slug);
  const coachTypeTags = coach?.coachType
    ? coach.coachType.split("/").map((tag) => tag.trim()).filter(Boolean)
    : [];
  const coachLanguages = coach?.languages
    ? coach.languages.split("/").map((language) => language.trim()).filter(Boolean)
    : [];
  const coachExperienceSection = coach?.sections.find((section) => section.title === "個人經歷") ?? null;
  const coachTeachingSection = coach?.sections.find((section) => section.title === "教學理念") ?? null;
  const coachIntroSection = coach?.sections.find((section) => section.title === "自我介紹") ?? null;
  const coachSkiExperienceSection = coach?.sections.find((section) => section.title === "滑雪經驗") ?? null;
  const coachRenderedSectionTitles = new Set([
    "個人經歷",
    "教學理念",
    "專業證照",
    "自我介紹",
    "滑雪經驗",
    "滑雪證照",
  ]);
  const coachExtraSections = coach?.sections.filter((section) => !coachRenderedSectionTitles.has(section.title)) ?? [];
  const coachSplitTeachingCards = Boolean(coach?.splitTeachingCards);
  const coachCertificateSection = (() => {
    const professionalSection = coach?.sections.find((section) => section.title === "專業證照") ?? null;
    const skiCertificateSection = coach?.sections.find((section) => section.title === "滑雪證照") ?? null;

    if (!professionalSection && !skiCertificateSection) return null;

    return {
      ...(professionalSection ?? skiCertificateSection),
      media: [
        ...(professionalSection?.media ?? []),
        ...(skiCertificateSection?.media ?? []),
      ],
    };
  })();
  const cashCertificateSection = coachCertificateSection;
  const cashHeroSections = coach?.slug === "lin"
    ? [coachExperienceSection].filter(Boolean)
    : isCashLikeCoach
      ? [coachExperienceSection].filter(Boolean)
      : coach?.sections.slice(0, 2) ?? [];
  const cashAbilityTags = {
    snowboard: [
      "零經驗",
      "初階",
      "中階",
      "Powder 鬆雪",
      "Tree Run 樹林",
      "幼兒(4-6歲)",
      "兒童(7-10歲)",
      "親子",
      "高齡",
    ],
    ski: ["零經驗", "初階", "中階", "親子", "幼兒(4-6歲)", "兒童(7-10歲)", "高齡"],
  };
  const heroAbilityTags = isCashCoach ? cashAbilityTags : coachAbilityTags;
  const cashVideos = isCashCoach
    ? [
    {
      title: "SnowLand滑雪學校 Cash校長",
      src: "https://www.youtube.com/embed/g5DxnJtpKtE",
    },
    {
      title: "【北海道星野度假村 ❄️ EP04】小朋友可以滑雪嗎？",
      src: "https://www.youtube.com/embed/cnMoLz2uxZI",
    },
    {
      title: "【SnowLand 學員ShowTime】20240119 Cash 星野 SB KeithChen",
      src: "https://www.youtube.com/embed/MsCvncp8rbU",
    },
    {
      title: "【SnowLand 學員ShowTime】20231221 Cash 星野 SB WU",
      src: "https://www.youtube.com/embed/ZfuNOgIOfns",
    },
    {
      title: "【SnowLand 學員ShowTime】20231221 Cash 星野 SB半天 廣州 Mandy",
      src: "https://www.youtube.com/embed/jFJedgYH7IE",
    },
    {
      title: "【SnowLand 學員ShowTime】20231219-20 Cash 星野半天 SB Zheng 2P",
      src: "https://www.youtube.com/embed/G6Z8rkFGVFs",
    },
    {
      title: "【SnowLand 學員ShowTime】20231220 Cash 星野半天 SB Zheng Yunrong",
      src: "https://www.youtube.com/embed/WJ7eXDZzerE",
    },
    {
      title: "【SnowLand 學員ShowTime】20231220 Cash 星野 SB Becky 2p粵",
      src: "https://www.youtube.com/embed/OzOCHdr8EoA",
    },
    {
      title: "【SnowLand 學員ShowTime】20231219 Cash 星野 Ski 香港 Joe black",
      src: "https://www.youtube.com/embed/Imw4n6CK4DA",
    },
      ]
    : coachVideos;
  const cashStudentReviews = isCashCoach ? cashReviews : coachReviews;
  const cashVideoCarouselRef = useRef(null);
  const cashVideoSlideRefs = useRef([]);
  const cashCoachStackSectionRef = useRef(null);
  const cashReviewPreviewRefs = useRef({});
  const [cashVideoActiveIndex, setCashVideoActiveIndex] = useState(0);
  const [cashVideoScrollProgress, setCashVideoScrollProgress] = useState(0);
  const [selectedCashReview, setSelectedCashReview] = useState(null);
  const [selectedCashReviewPhoto, setSelectedCashReviewPhoto] = useState(null);
  const [cashReviewPaging, setCashReviewPaging] = useState({ slug, page: 1 });
  const [cashReviewHasMoreMap, setCashReviewHasMoreMap] = useState({});
  const cashReviewPage = cashReviewPaging.slug === slug ? cashReviewPaging.page : 1;
  const cashHeadingClass = "text-2xl font-semibold tracking-wide text-[#1f2937] font-display";
  const cashBodyClass = "text-sm md:text-base text-[#475569] leading-relaxed";
  const cashHeroTitleClass = "text-3xl md:text-4xl font-semibold tracking-wide text-[#111827] font-display";
  const pinIcon = (
    <span aria-hidden="true" className="inline-flex items-center text-[0.75rem] leading-none">
      📌
    </span>
  );

  useEffect(() => {
    let active = true;

    fetchWebsiteCoaches()
      .then((apiCoaches) => {
        if (!active) return;
        setEnabledCoachSlugs(new Set(apiCoaches.map((item) => item.slug).filter(Boolean)));
      })
      .catch(() => {
        if (!active) return;
        setEnabledCoachSlugs(null);
      });

    return () => {
      active = false;
    };
  }, []);
  const cashVideoSlides = cashVideos.map((video) => {
    const videoIdMatch = video.src.match(/(?:v=|\/embed\/|youtu\.be\/|shorts\/)([^?&#/]+)/);
    const videoId = videoIdMatch?.[1] ?? "";

    return {
      ...video,
      videoId,
      thumbnailSrc: videoId ? `https://img.youtube.com/vi/${videoId}/hqdefault.jpg` : "",
      watchUrl: videoId ? `https://www.youtube.com/watch?v=${videoId}` : video.src,
    };
  });
  const cashReviewPageSize = 4;
  const cashReviewPageCount = Math.max(1, Math.ceil(cashStudentReviews.length / cashReviewPageSize));
  const cashReviewCountLabel = `${cashStudentReviews.length} 則已評價`;
  const visibleCashStudentReviews = cashStudentReviews.slice(
    (cashReviewPage - 1) * cashReviewPageSize,
    cashReviewPage * cashReviewPageSize
  );
  const cashReviewPageItems = (() => {
    if (cashReviewPageCount <= 5) {
      return Array.from({ length: cashReviewPageCount }, (_, index) => index + 1);
    }

    const items = [1];

    const appendPage = (page) => {
      if (items[items.length - 1] !== page) {
        items.push(page);
      }
    };

    const appendEllipsis = () => {
      if (items[items.length - 1] !== "ellipsis") {
        items.push("ellipsis");
      }
    };

    if (cashReviewPage <= 3) {
      appendPage(2);
      appendPage(3);
      appendEllipsis();
    } else if (cashReviewPage >= cashReviewPageCount - 2) {
      appendEllipsis();
      appendPage(cashReviewPageCount - 2);
      appendPage(cashReviewPageCount - 1);
    } else {
      appendEllipsis();
      appendPage(cashReviewPage - 1);
      appendPage(cashReviewPage);
      appendPage(cashReviewPage + 1);
      appendEllipsis();
    }

    appendPage(cashReviewPageCount);
    return items;
  })();

  useEffect(() => {
    const rafId = window.requestAnimationFrame(() => {
      const nextHasMoreMap = {};

      visibleCashStudentReviews.forEach((review) => {
        const key = `${review.name}-${review.time}`;
        const node = cashReviewPreviewRefs.current[key];
        nextHasMoreMap[key] = Boolean(node && node.scrollHeight > node.clientHeight + 1);
      });

      setCashReviewHasMoreMap((current) => {
        const currentKeys = Object.keys(current);
        const nextKeys = Object.keys(nextHasMoreMap);
        if (
          currentKeys.length === nextKeys.length &&
          nextKeys.every((key) => current[key] === nextHasMoreMap[key])
        ) {
          return current;
        }

        return nextHasMoreMap;
      });
    });

    return () => window.cancelAnimationFrame(rafId);
  }, [cashReviewPage, cashStudentReviews.length, slug, visibleCashStudentReviews]);
  const createTeachingCard = (id, lines) => ({
    id,
    title: coachTeachingSection.title,
    type: "teaching",
    lead: isCashCoach
      ? "安全第一，陪你穩健進步，讓每一步都更有信心。"
      : coachHideTeachingLead
        ? ""
        : lines.find((line) => !line.startsWith("【")) ?? lines[0] ?? "",
    bgClass: "bg-[#dbe2f0]",
    textClass: "text-[#2b5f8f]",
    bodyClass: "text-[#2b5f8f]",
    metaClass: "text-[#2b5f8f]",
    mediaBorderClass: "border-[#d8e0ee]",
    mediaSurfaceClass: "bg-[#eef3fb]",
    mediaShadowClass: "shadow-[0_14px_32px_rgba(15,23,42,0.08)]",
    media: [],
    lines,
  });
  const coachTeachingCards = coachTeachingSection
    ? coachSplitTeachingCards && coachTeachingSection.lines.length > 1
      ? coachTeachingSection.lines.map((line, index) =>
          createTeachingCard(index === 0 ? "teaching" : `teaching-${index + 1}`, [line])
        )
      : [createTeachingCard("teaching", coachTeachingSection.lines)]
    : [];
  const cashCoachStackCards = [
    ...coachTeachingCards,
    coachIntroSection
      ? {
          id: "intro",
          title: coachIntroSection.title,
          type: "intro",
          lead: isCashCoach
            ? "多語教學、設計與運動生活，讓每段雪地故事更立體。"
            : coachIntroSection.lines[0] ?? "",
          bgClass: "bg-white",
          borderClass: "border-[#d7dde3]",
          textClass: "text-[#1f2937]",
          bodyClass: "text-[#475569]",
          metaClass: "text-[#94a3b8]",
          mediaBorderClass: "border-[#d7dde3]",
          mediaSurfaceClass: "bg-inherit",
          mediaShadowClass: "shadow-[0_14px_32px_rgba(15,23,42,0.08)]",
          media: isCashCoach
            ? [
                {
                  src: "https://land110602.com/wp-content/uploads/2023/10/A20210420-04-CR-0440w-495x400.jpg",
                  alt: "SnowLand 滑雪教練 Cash室內設計",
                },
                {
                  src: "https://land110602.com/wp-content/uploads/2023/10/048AAA75-636C-4D29-B6E0-9ED960F7FA56-495x400.jpg",
                  alt: "SnowLand 滑雪教練 Cash鐵馬",
                },
                {
                  src: "https://land110602.com/wp-content/uploads/2023/10/cash-%E9%A6%AC%E6%8B%89%E6%9D%BE-495x400.jpg",
                  alt: "SnowLand 滑雪教練 Cash馬拉松",
                },
              ]
            : coachIntroSection?.media ?? [],
          lines: coachIntroSection.lines,
        }
      : null,
    coachSkiExperienceSection
      ? {
          id: "ski-experience",
          title: coachSkiExperienceSection.title,
          type: "ski-experience",
          lead: isCashCoach
            ? "多國雪場的實戰經驗，持續轉化成穩定、清楚的教學節奏。"
            : coachSkiExperienceSection.lines[0] ?? "",
          bgClass: "bg-[#dbe2f0]",
          borderClass: "border-[#cfd8e8]",
          textClass: "text-[#1f2937]",
          bodyClass: "text-[#475569]",
          metaClass: "text-[#94a3b8]",
          mediaBorderClass: "border-[#cfd8e8]",
          mediaSurfaceClass: "bg-inherit",
          mediaShadowClass: "shadow-[0_14px_32px_rgba(15,23,42,0.08)]",
          media: isCashCoach
            ? [
                {
                  src: "https://land110602.com/wp-content/uploads/2023/10/%E7%9B%B8%E7%89%87-2024-2-29-10-27-09-495x400.jpg",
                  alt: "SnowLand 滑雪教練 Cash小朋友纜車",
                },
                {
                  src: "https://land110602.com/wp-content/uploads/2023/10/LINE_ALBUM_20240229-%E7%95%99%E5%A3%BD%E9%83%BD_240319_9-495x400.jpg",
                  alt: "SnowLand 滑雪教練 Cash小朋友教學",
                },
              ]
            : coachSkiExperienceSection?.media ?? [],
          lines: coachSkiExperienceSection.lines,
        }
      : null,
    ...coachExtraSections.map((section, index) => ({
      id: `extra-${index}`,
      title: section.title,
      type: section.media?.length ? "ski-experience" : "extra",
      lead: section.lines[0] ?? "",
      bgClass: "bg-[#dbe2f0]",
      borderClass: "border-[#cfd8e8]",
      textClass: "text-[#1f2937]",
      bodyClass: "text-[#475569]",
      metaClass: "text-[#94a3b8]",
      mediaBorderClass: "border-[#cfd8e8]",
      mediaSurfaceClass: "bg-inherit",
      mediaShadowClass: "shadow-[0_14px_32px_rgba(15,23,42,0.08)]",
      media: section.media ?? [],
      lines: section.lines,
    })),
  ].filter(Boolean);
  const cashTeachingCard = coachSplitTeachingCards
    ? null
    : cashCoachStackCards.find((card) => card.id === "teaching") ?? null;
  const cashCoachStackCardsBelowHero = coachSplitTeachingCards
    ? cashCoachStackCards
    : cashCoachStackCards.filter((card) => card.id !== "teaching");

  const renderStackCardMedia = (card) => {
    if (card.id === "intro" || card.id === "ski-experience" || card.type === "extra" || card.type === "ski-experience") {
      return (
        <CashPhotoCarousel
          images={card.media}
          mediaSurfaceClass={card.mediaSurfaceClass}
          mediaShadowClass={card.mediaShadowClass}
          label={`${card.title}-photos`}
        />
      );
    }

    return (
      <div className="space-y-3">
        <div
          className="flex gap-4 overflow-x-auto snap-x snap-mandatory scroll-smooth hide-scrollbar pb-2 touch-pan-x lg:flex-col lg:overflow-visible lg:snap-none lg:pb-0"
        >
          {card.media.map((image, imageIndex) => (
            <figure
              key={`${card.id}-media-${imageIndex}`}
              className="shrink-0 w-[220px] sm:w-[260px] lg:w-[280px] lg:shrink lg:snap-none"
            >
              <img loading="lazy" decoding="async"
                src={image.src}
                alt={image.alt}
                className="block w-full h-auto object-contain"
                loading="lazy"
              />
            </figure>
          ))}
        </div>
      </div>
    );
  };

  useEffect(() => {
    if (!isCashLikeCoach) return;

    const node = cashVideoCarouselRef.current;
    if (!node) return;

    cashVideoSlideRefs.current = cashVideoSlideRefs.current.slice(0, cashVideoSlides.length);
    let rafId = 0;

    const updateCarouselState = () => {
      rafId = 0;
      const slides = cashVideoSlideRefs.current;
      const maxScrollLeft = Math.max(node.scrollWidth - node.clientWidth, 0);
      const nextProgress = maxScrollLeft > 0 ? node.scrollLeft / maxScrollLeft : 1;
      const centerPoint = node.scrollLeft + node.clientWidth / 2;
      let nextIndex = 0;

      slides.forEach((slide, index) => {
        if (!slide) return;
        const slideStart = slide.offsetLeft;
        const slideEnd = slideStart + slide.offsetWidth;
        if (centerPoint >= slideStart && centerPoint < slideEnd) {
          nextIndex = index;
        }
      });

      const clampedProgress = Math.min(1, Math.max(0, nextProgress));

      setCashVideoScrollProgress((current) =>
        Math.abs(current - clampedProgress) < 0.002 ? current : clampedProgress
      );
      setCashVideoActiveIndex((current) => (current === nextIndex ? current : nextIndex));
    };

    const requestUpdate = () => {
      if (rafId) return;
      rafId = window.requestAnimationFrame(updateCarouselState);
    };

    requestUpdate();
    node.addEventListener("scroll", requestUpdate, { passive: true });
    node.addEventListener("touchmove", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);

    return () => {
      if (rafId) window.cancelAnimationFrame(rafId);
      node.removeEventListener("scroll", requestUpdate);
      node.removeEventListener("touchmove", requestUpdate);
      window.removeEventListener("resize", requestUpdate);
    };
  }, [cashVideoSlides.length, isCashLikeCoach]);

  const scrollCashVideoCarousel = (direction) => {
    const node = cashVideoCarouselRef.current;
    if (!node) return;

    const nextIndex = Math.max(
      0,
      Math.min(cashVideoActiveIndex + direction, cashVideoSlides.length - 1)
    );
    const slide = cashVideoSlideRefs.current[nextIndex];
    if (!slide) return;
    const maxScrollLeft = Math.max(node.scrollWidth - node.clientWidth, 0);
    const targetProgress = maxScrollLeft > 0 ? slide.offsetLeft / maxScrollLeft : 1;
    const clampedProgress = Math.min(1, Math.max(0, targetProgress));

    node.scrollTo({
      left: slide.offsetLeft,
      behavior: "smooth",
    });
    setCashVideoActiveIndex(nextIndex);
    setCashVideoScrollProgress(clampedProgress);
  };

  const groupTeachingQuoteBlocks = (lines) => {
    const blocks = [];
    let currentBlock = null;

    const flushBlock = () => {
      if (!currentBlock) return;
      blocks.push(currentBlock);
      currentBlock = null;
    };

    lines.forEach((line) => {
      const match = line.match(/^【([^】]+)】\s*(.*)$/);
      if (match) {
        flushBlock();
        currentBlock = {
          title: match[1],
          paragraphs: match[2] ? [match[2]] : [],
        };
        return;
      }

      if (!currentBlock) {
        currentBlock = {
          title: "",
          paragraphs: [line],
        };
        return;
      }

      currentBlock.paragraphs.push(line);
    });

    flushBlock();
    return blocks;
  };

  const renderTeachingQuoteBlock = (block, prefix, index) => (
    <blockquote
      key={`${prefix}-${index}`}
      className="relative overflow-hidden rounded-sm bg-white px-5 py-5 shadow-[0_10px_30px_rgba(15,23,42,0.04)] md:px-6 md:py-6"
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-4 top-1 text-5xl leading-none text-[#2b5f8f]/18 font-serif select-none"
      >
        “
      </span>
      <span
        aria-hidden="true"
        className="pointer-events-none absolute bottom-1 right-4 text-5xl leading-none text-[#2b5f8f]/18 font-serif select-none"
      >
        ”
      </span>
      <div className="relative space-y-3 pl-6 pr-6">
        {block.title ? (
          <h3 className="text-lg md:text-xl font-semibold tracking-tight text-[#111827] font-display">
            {block.title}
          </h3>
        ) : null}
        <div className="space-y-3">
          {block.paragraphs.map((paragraph, paragraphIndex) => (
            <p
              key={`${prefix}-${index}-${paragraphIndex}`}
              className="text-sm md:text-base leading-relaxed text-[#475569]"
            >
              {paragraph}
            </p>
          ))}
        </div>
      </div>
    </blockquote>
  );

  const renderTeachingQuoteSection = (section, prefix) => {
    const blocks = groupTeachingQuoteBlocks(section.lines);

    return (
      <div className="space-y-5">
        {blocks.map((block, index) => (
          <CashFadeIn
            key={`${prefix}-${index}`}
            as="div"
            delay={index * 140}
            className="transform-gpu"
          >
            {renderTeachingQuoteBlock(block, prefix, index)}
          </CashFadeIn>
        ))}
      </div>
    );
  };

  const renderReviewParagraphs = (paragraphs, className = "text-sm md:text-base leading-relaxed text-[#334155]") => (
    <div className="space-y-3">
      {paragraphs.map((paragraph, index) => (
        <p key={`${className}-${index}`} className={className}>
          {paragraph}
        </p>
      ))}
    </div>
  );

  const groupStackCardBlocks = (lines) => {
    const blocks = [];
    let currentBlock = null;

    const flushBlock = () => {
      if (!currentBlock) return;
      blocks.push(currentBlock);
      currentBlock = null;
    };

    lines.forEach((line) => {
      const match = line.match(/^【([^】]+)】\s*(.*)$/);
      if (match) {
        flushBlock();
        currentBlock = {
          title: match[1],
          paragraphs: match[2] ? [match[2]] : [],
        };
        return;
      }

      if (!currentBlock) {
        currentBlock = {
          title: "",
          paragraphs: [line],
        };
        return;
      }

      currentBlock.paragraphs.push(line);
    });

    flushBlock();
    return blocks;
  };

  const renderStackCardLines = (card) => {
    const isBulletedList = card.lines.length > 0 && card.lines.every((line) => line.trim().startsWith("•"));
    const stackBlocks = groupStackCardBlocks(card.lines);
    const hasSectionTitles = stackBlocks.some((block) => block.title);

    if (isBulletedList) {
      return (
        <ul className="space-y-3 pl-5 text-left list-disc">
          {card.lines.map((line, lineIndex) => (
            <li
              key={`cash-stack-${card.id}-${lineIndex}`}
              className={`${card.bodyClass} text-sm md:text-base leading-relaxed`}
            >
              {line.replace(/^•\s*/, "")}
            </li>
          ))}
        </ul>
      );
    }

    if (hasSectionTitles) {
      return (
        <div className="space-y-5 pt-4">
          {stackBlocks.map((block, blockIndex) => (
            <div key={`cash-stack-${card.id}-block-${blockIndex}`} className="space-y-3">
              {block.title ? (
                <h4 className="text-lg md:text-xl font-semibold tracking-tight text-brand-orange font-display">
                  {block.title}
                </h4>
              ) : null}
              {block.paragraphs.length > 0 && block.paragraphs.every((line) => line.trim().startsWith("•")) ? (
                <ul className="space-y-3 pl-5 text-left list-disc">
                  {block.paragraphs.map((paragraph, paragraphIndex) => (
                    <li
                      key={`cash-stack-${card.id}-block-${blockIndex}-paragraph-${paragraphIndex}`}
                      className={`${card.bodyClass} text-sm md:text-base leading-relaxed`}
                    >
                      {paragraph.replace(/^•\s*/, "")}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="space-y-4">
                  {block.paragraphs.map((paragraph, paragraphIndex) => (
                    <p
                      key={`cash-stack-${card.id}-block-${blockIndex}-paragraph-${paragraphIndex}`}
                      className={`${card.bodyClass} text-sm md:text-base leading-relaxed`}
                    >
                      {paragraph}
                    </p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      );
    }

    return (
      <div className="space-y-4 pt-4">
        {card.lines.map((line, lineIndex) => (
          <p
            key={`cash-stack-${card.id}-${lineIndex}`}
            className={`${card.bodyClass} text-sm md:text-base leading-relaxed`}
          >
            {line}
          </p>
        ))}
      </div>
    );
  };

  const isCoachEnabledForWebsite = enabledCoachSlugs === null || enabledCoachSlugs.has(slug);

  if (!coach || !isCoachEnabledForWebsite) {
    return (
      <div className="min-h-screen bg-[#f6f8fb] flex flex-col">
        <SiteHeader forceTransparent forceDarkText forceLogoColor />
        <main className="flex-1 flex items-center justify-center px-6 pt-28 pb-16">
          <div className="text-center">
            <h1 className="text-2xl font-semibold text-[#1f2937] font-display">找不到教練頁面</h1>
            <p className="mt-4 text-[#6b7280]">請返回首頁選擇其他教練。</p>
            <SiteLink
              to="/"
              className="mt-6 inline-flex items-center justify-center px-6 py-3 rounded-xl bg-brand-orange text-white font-semibold"
            >
              回到首頁
            </SiteLink>
          </div>
        </main>
        <SiteFooter />
      </div>
    );
  }

  const mainClassName = "pt-28 pb-0 flex-1 w-full";

  return (
    <div className="min-h-screen bg-[#f6f8fb] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main className={mainClassName}>
        {isCashLikeCoach ? (
          <>
            <section className="w-full bg-[#f7f8fa]">
              <div className="max-w-6xl mx-auto px-6 md:px-10 py-10 md:py-16">
                <CashFadeIn as="div" className="flex justify-start">
                  <nav
                    aria-label="breadcrumb"
                    className="text-sm font-semibold text-[#1f2937] font-display"
                  >
                    <div className="inline-flex items-center gap-1">
                      <SiteLink to="/" className="transition-colors hover:text-[#2b5f8f]">
                        首頁
                      </SiteLink>
                      <span className="text-[#cbd5e1]">/</span>
                      <SiteLink to="/coach" className="transition-colors hover:text-[#2b5f8f]">
                        教練團隊
                      </SiteLink>
                      <span className="text-[#cbd5e1]">/</span>
                      <span className="text-[#1f2937]">{coach.name}</span>
                    </div>
                  </nav>
                </CashFadeIn>

                <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] items-start">
                  <CashFadeIn
                    as="figure"
                    delay={40}
                    className="overflow-hidden rounded-sm bg-[#e2e8f0] lg:sticky lg:top-24 lg:h-[calc(100svh-12rem)] lg:w-fit lg:max-w-full lg:self-start"
                  >
                    <img loading="lazy" decoding="async"
                      src={coachDetailImage}
                      alt={coach.name}
                      className="block h-auto w-full object-cover object-top lg:h-full lg:w-auto lg:max-w-none lg:object-contain"
                    />
                  </CashFadeIn>

                  <CashFadeIn as="div" delay={120} className="space-y-8 text-center lg:pt-10">
                    <div className="space-y-4 max-w-2xl mx-auto">
                      <CashFadeIn as="h1" delay={180} className={cashHeroTitleClass}>
                        {coach.name}
                      </CashFadeIn>
                      <CashFadeIn
                        as="p"
                        delay={240}
                        className="flex flex-wrap items-center justify-center gap-4"
                      >
                        {coachTypeTags.map((tag) => {
                          const iconSrc = tag.includes("單板")
                            ? "/coach-images/icon-snowboard.png"
                            : "/coach-images/icon-skiing.png";

                          return (
                            <span
                              key={tag}
                              className="inline-flex h-7 items-center gap-1.5 rounded-full bg-gradient-to-br from-[#2b5f8f] via-[#3c78b6] to-[#5aa6c9] px-3 sm:px-4"
                            >
                              <img
                                src={iconSrc}
                                alt={tag}
                                className="h-4 w-4 object-contain brightness-0 invert"
                                loading="lazy"
                              />
                              <span className="text-[0.7rem] font-semibold tracking-wide text-white">
                                {tag}
                              </span>
                            </span>
                          );
                        })}
                        {coachHeroBadges.map((badge) => (
                          <span
                            key={badge}
                            className="inline-flex h-7 items-center gap-1.5 rounded-full bg-gradient-to-br from-[#2b5f8f] via-[#3c78b6] to-[#5aa6c9] px-3 sm:px-4"
                          >
                            <svg
                              aria-hidden="true"
                              viewBox="0 0 24 24"
                              className="h-4 w-4 shrink-0 text-white"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.8"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <path d="M4 7h3l1.5-2h7L17 7h3a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z" />
                              <circle cx="12" cy="13" r="3.2" />
                              <path d="M8 7l1-2" />
                            </svg>
                            <span className="text-[0.7rem] font-semibold tracking-wide text-white">
                              {badge}
                            </span>
                          </span>
                        ))}
                      </CashFadeIn>
                      <CashFadeIn
                        as="p"
                        delay={300}
                        className="text-sm md:text-base text-[#475569] leading-relaxed"
                      >
                        {coachLanguages.join(" / ")}
                      </CashFadeIn>
                    </div>

                    {cashHeroSections.map((section) => (
                      (() => {
                        const sectionHasBullets =
                          section.lines.length > 0 &&
                          section.lines.every((line) => line.trim().startsWith("•"));

                        return (
                      <CashFadeIn
                        key={section.title}
                        delay={420}
                        className={`space-y-4 max-w-2xl mx-auto border-t border-[#d7dde3] pt-6 ${
                          section.title === "個人經歷" ? "text-left" : "text-center"
                        }`}
                      >
                        <h3 className={cashHeadingClass}>{section.title}</h3>
                        {sectionHasBullets || section.title === "個人經歷" ? (
                          <ul className="space-y-3 pl-5 text-left list-disc">
                            {section.lines.map((line, lineIndex) => (
                              <li key={`${section.title}-${lineIndex}`} className={cashBodyClass}>
                                {line.replace(/^•\s*/, "")}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="space-y-3">
                            {section.lines.map((line, lineIndex) => (
                              <p key={`${section.title}-${lineIndex}`} className={cashBodyClass}>
                                {line}
                              </p>
                            ))}
                          </div>
                        )}
                      </CashFadeIn>
                        );
                      })()
                    ))}

                    {cashTeachingCard ? (
                      <CashFadeIn as="div" delay={520} className="mt-2 max-w-2xl mx-auto">
                        <div
                          className={`overflow-hidden rounded-sm shadow-[0_20px_50px_rgba(15,23,42,0.08)] ${cashTeachingCard.bgClass}`}
                        >
                          <div className="px-6 md:px-8 py-5 md:py-6 space-y-5">
                            <div className="space-y-4">
                              <h3 className={`${cashHeadingClass} ${cashTeachingCard.textClass} text-center`}>
                                {cashTeachingCard.title}
                              </h3>
                              {cashTeachingCard.lead ? (
                                <p className={`${cashTeachingCard.bodyClass} mx-auto max-w-xl text-center`}>
                                  {cashTeachingCard.lead}
                                </p>
                              ) : null}
                            </div>

                            <div className="space-y-5 pt-2">
                              {renderTeachingQuoteSection(
                                { title: cashTeachingCard.title, lines: cashTeachingCard.lines },
                                "cash-hero-teaching"
                              )}
                            </div>
                          </div>
                        </div>
                      </CashFadeIn>
                    ) : null}
                  </CashFadeIn>
                </div>
              </div>
            </section>

            <section className="max-w-6xl mx-auto px-6 md:px-10 py-14 md:py-16 border-t border-[#d7dde3]">
              <div
                className={`grid gap-10 ${
                  heroAbilityTags?.snowboard?.length || heroAbilityTags?.ski?.length
                    ? "lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]"
                    : "lg:grid-cols-1"
                } lg:items-start`}
              >
                {cashCertificateSection ? (
                  <CashFadeIn as="div" className="space-y-4">
                    <h2 className={cashHeadingClass}>{cashCertificateSection.title}</h2>
                    <ul className={`space-y-3 ${cashBodyClass}`}>
                      {cashCertificateSection.lines.map((line, index) => (
                        <li key={`cash-cert-${index}`} className="flex gap-2">
                          <span className="shrink-0 text-[#2b5f8f]" aria-hidden="true">
                            ▸
                          </span>
                          <span>{line}</span>
                        </li>
                      ))}
                    </ul>
                  </CashFadeIn>
                ) : null}

                <div className="space-y-6">
                  {heroAbilityTags?.snowboard?.length ? (
                    <CashFadeIn
                      as="div"
                      delay={80}
                      className="rounded-sm bg-white p-5 md:p-6 space-y-5 shadow-[0_10px_30px_rgba(15,23,42,0.04)] transition-colors duration-300 hover:bg-[#eaf4ff]"
                    >
                      <div className="flex flex-col items-center gap-3 text-center">
                        <div className="flex h-14 w-14 items-center justify-center">
                          <img
                            src="/coach-images/icon-snowboard.png"
                            alt="Snowboard icon"
                            className="h-8 w-8 object-contain"
                            loading="lazy"
                          />
                        </div>
                        <h3 className="text-lg md:text-xl font-semibold text-[#1f2937] font-display">
                          Snowboard 單板
                        </h3>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {heroAbilityTags.snowboard.map((tag) => (
                          <span
                            key={`snowboard-${tag}`}
                            className="inline-flex items-center rounded-full border border-[#d7dde3] bg-white px-3 py-1 text-xs md:text-sm font-semibold text-[#475569]"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </CashFadeIn>
                  ) : null}

                  {heroAbilityTags?.ski?.length ? (
                    <CashFadeIn
                      as="div"
                      delay={160}
                      className="rounded-sm bg-white p-5 md:p-6 space-y-5 shadow-[0_10px_30px_rgba(15,23,42,0.04)] transition-colors duration-300 hover:bg-[#eaf4ff]"
                    >
                      <div className="flex flex-col items-center gap-3 text-center">
                        <div className="flex h-14 w-14 items-center justify-center">
                          <img
                            src="/coach-images/icon-skiing.png"
                            alt="Skiing icon"
                            className="h-8 w-8 object-contain"
                            loading="lazy"
                          />
                        </div>
                        <h3 className="text-lg md:text-xl font-semibold text-[#1f2937] font-display">
                          Ski 雙板
                        </h3>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {heroAbilityTags.ski.map((tag) => (
                          <span
                            key={`ski-${tag}`}
                            className="inline-flex items-center rounded-full border border-[#d7dde3] bg-white px-3 py-1 text-xs md:text-sm font-semibold text-[#475569]"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </CashFadeIn>
                  ) : null}
                </div>
              </div>
            </section>

            {cashCoachStackCardsBelowHero.length > 0 ? (
              <section
                ref={cashCoachStackSectionRef}
                className="w-full pt-0 pb-14 md:pb-16 space-y-4 lg:space-y-0"
              >
                {cashCoachStackCardsBelowHero.map((card, index) => {
                  const renderCard = index === 1
                    ? {
                        ...card,
                        type: "ski-experience",
                        bgClass: "bg-[#dbe2f0]",
                        borderClass: "border-[#cfd8e8]",
                        mediaBorderClass: "border-[#cfd8e8]",
                        mediaSurfaceClass: "bg-inherit",
                        mediaShadowClass: "shadow-[0_14px_32px_rgba(15,23,42,0.08)]",
                      }
                    : card;
                  const isIntroCard = renderCard.type === "intro";

                  return (
                    <CashFadeIn
                      as="article"
                      key={renderCard.id}
                      delay={index * 160}
                      className={`${isIntroCard ? "relative md:sticky md:top-0" : "sticky top-0 md:top-0"} w-full`}
                      style={{ zIndex: index + 1 }}
                      >
                      <div
                        className={`rounded-sm shadow-[0_20px_50px_rgba(15,23,42,0.08)] ${
                          isIntroCard ? "overflow-visible md:overflow-hidden" : "overflow-hidden"
                        } ${renderCard.bgClass}`}
                      >
                        <div className="max-w-6xl mx-auto px-6 md:px-10 py-4 md:py-6">
                          <div className="flex items-center justify-between">
                            <p
                              className={`text-xs font-semibold tracking-[0.35em] uppercase font-display ${renderCard.metaClass}`}
                            >
                              教練介紹
                            </p>
                            <p
                              className={`text-xs font-semibold tracking-[0.3em] uppercase font-display ${renderCard.metaClass}`}
                            >
                              {String(index + 1).padStart(2, "0")}
                            </p>
                          </div>

                          {isIntroCard ? (
                            <div className="md:hidden sticky top-16 z-20 -mx-6 mt-6 bg-white/95 px-6 py-4 shadow-[0_8px_24px_rgba(15,23,42,0.06)] backdrop-blur">
                              <div className="space-y-4">
                                <div className="space-y-4">
                                  {renderStackCardMedia(renderCard)}
                                </div>
                                <h3 className={`${cashHeroTitleClass} ${renderCard.textClass}`}>
                                  {renderCard.title}
                                </h3>
                              </div>
                            </div>
                          ) : null}

                          <div
                            className={`grid gap-8 pt-8 md:pt-10 ${
                              renderCard.media.length > 0
                                ? "lg:grid-cols-[0.96fr_1.04fr] lg:gap-12 lg:items-start"
                                : "lg:grid-cols-1"
                            }`}
                          >
                            {renderCard.media.length > 0 ? (
                              <div
                                className={`space-y-4 lg:pt-8 ${
                                  isIntroCard ? "hidden md:block" : ""
                                }`}
                              >
                                {renderStackCardMedia(renderCard)}
                              </div>
                            ) : null}

                            <div className={`${isIntroCard ? "space-y-0 md:space-y-5" : "space-y-4 md:space-y-5"} lg:pt-8`}>
                              {!isIntroCard ? (
                                <div className="space-y-4">
                                  <h3
                                    className={`${cashHeroTitleClass} ${renderCard.textClass} ${
                                      renderCard.type === "teaching" ? "text-center" : ""
                                    }`}
                                  >
                                    {renderCard.title}
                                  </h3>
                                  {renderCard.type !== "intro" && renderCard.type !== "ski-experience" && renderCard.lead ? (
                                    <p
                                      className={`max-w-xl text-sm md:text-base leading-relaxed ${renderCard.bodyClass} ${
                                        renderCard.type === "teaching" ? "mx-auto text-center" : ""
                                      }`}
                                    >
                                      {renderCard.lead}
                                    </p>
                                  ) : null}
                                </div>
                              ) : null}

                              {renderCard.type === "teaching" ? (
                                <div className="space-y-5 pt-4">
                                  {renderTeachingQuoteSection(
                                    { title: renderCard.title, lines: renderCard.lines },
                                    `cash-stack-${renderCard.id}`
                                  )}
                                </div>
                              ) : (
                                renderStackCardLines(renderCard)
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </CashFadeIn>
                  );
                })}
              </section>
            ) : null}

            <section className="max-w-6xl mx-auto px-6 md:px-10 py-14 md:py-16 border-t border-[#d7dde3]">
              <div className="space-y-6">
                <CashFadeIn as="div" className="space-y-3 text-center">
                  <h2 className={cashHeroTitleClass}>影音短片</h2>
                </CashFadeIn>
                <CashFadeIn as="div" delay={80} className="flex items-center justify-end gap-4 pt-1">
                  <button
                    type="button"
                    onClick={() => scrollCashVideoCarousel(-1)}
                    disabled={cashVideoActiveIndex === 0}
                    aria-label="上一部影片"
                    className="text-[#1f2937] transition-colors hover:text-[#2b5f8f] disabled:cursor-not-allowed disabled:text-[#cbd5e1]"
                  >
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 24 24"
                      className="h-6 w-6"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M15 5l-7 7 7 7" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    onClick={() => scrollCashVideoCarousel(1)}
                    disabled={cashVideoActiveIndex === cashVideoSlides.length - 1}
                    aria-label="下一部影片"
                    className="text-[#1f2937] transition-colors hover:text-[#2b5f8f] disabled:cursor-not-allowed disabled:text-[#cbd5e1]"
                  >
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 24 24"
                      className="h-6 w-6"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </CashFadeIn>
              </div>

              <div className="mt-8">
                <CashFadeIn
                  as="div"
                  ref={cashVideoCarouselRef}
                  className="flex gap-4 overflow-x-auto snap-x snap-mandatory scroll-smooth hide-scrollbar"
                >
                  {cashVideoSlides.map((video, index) => (
                    <CashFadeIn
                      as="a"
                      key={video.src}
                      ref={(node) => {
                        cashVideoSlideRefs.current[index] = node;
                      }}
                      delay={index * 80}
                      data-cash-video-slide
                      href={video.watchUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="group shrink-0 snap-start w-[calc((100%-1rem)/2)] lg:w-[calc((100%-4.5rem)/4)]"
                    >
                      <article className="space-y-3">
                        <div className="relative overflow-hidden rounded-sm bg-black">
                          <div className="relative aspect-video">
                            <img
                              src={video.thumbnailSrc}
                              alt={video.title}
                              className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-[1.03]"
                              loading="lazy"
                            />
                            <div className="absolute inset-0 flex items-center justify-center">
                              <span className="flex h-12 w-12 items-center justify-center rounded-full border border-white/85 bg-black/30 text-white">
                                <span className="ml-0.5 text-lg leading-none" aria-hidden="true">
                                  ▶
                                </span>
                              </span>
                            </div>
                          </div>
                        </div>
                        <p className="line-clamp-2 text-sm md:text-base font-semibold leading-relaxed text-[#1f2937]">
                          {video.title}
                        </p>
                      </article>
                    </CashFadeIn>
                  ))}
                </CashFadeIn>

                <div className="mt-8 flex items-center gap-4">
                  <div className="relative h-px flex-1 overflow-hidden bg-[#d7dde3]">
                    <div
                      className="absolute left-0 top-0 h-px rounded-full bg-[#2b5f8f] transition-all duration-700 ease-out"
                      style={{
                        width: `${cashVideoScrollProgress * 100}%`,
                        minWidth: cashVideoScrollProgress > 0 ? "2px" : "0px",
                      }}
                    />
                  </div>
                </div>
              </div>
            </section>

            <section className="bg-[#eef3f8]">
              <div className="max-w-6xl mx-auto px-6 md:px-10 py-14 md:py-16 space-y-8">
                <CashFadeIn as="div" className="space-y-4 text-center">
                  <h2 className={cashHeroTitleClass}>學員評價</h2>
                  {cashStudentReviews.length > 0 ? (
                    <div className="flex flex-col items-center gap-2">
                      <div className="flex items-center gap-1 text-[#f5c542]">
                        {Array.from({ length: 5 }).map((_, starIndex) => (
                          <svg
                            key={`review-summary-star-${starIndex}`}
                            viewBox="0 0 24 24"
                            className="h-5 w-5 md:h-6 md:w-6"
                            fill="currentColor"
                            aria-hidden="true"
                          >
                            <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
                          </svg>
                        ))}
                      </div>
                      <div className="flex items-baseline gap-2 text-[#1f2937] font-display">
                        <span className="text-sm md:text-base font-semibold tracking-[0.18em] uppercase">
                          {cashReviewCountLabel}
                        </span>
                      </div>
                    </div>
                  ) : null}
                </CashFadeIn>

                {cashStudentReviews.length > 0 ? (
                  <>
                    <div className="grid gap-4 md:gap-6 lg:grid-cols-2">
                      {visibleCashStudentReviews.map((review, index) => (
                        <CashFadeIn
                          as="article"
                          key={`${review.name}-${review.time}`}
                          delay={index * 90}
                          role="button"
                          tabIndex={0}
                          onClick={() => setSelectedCashReview(review)}
                          onKeyDown={(event) => {
                            if (event.key !== "Enter" && event.key !== " ") return;
                            event.preventDefault();
                            setSelectedCashReview(review);
                          }}
                          className="group relative h-[260px] overflow-hidden rounded-sm border border-[#d7dde3] bg-white p-0 text-left shadow-[0_12px_30px_rgba(15,23,42,0.05)] transition-transform duration-300 hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2b5f8f]/40 md:h-[280px]"
                        >
                          <div className="pointer-events-none absolute right-4 top-4 flex items-center gap-0.5 text-[#f5c542] md:right-5 md:top-5">
                            {Array.from({ length: 5 }).map((_, starIndex) => (
                              <span key={`review-star-${review.name}-${starIndex}`} aria-hidden="true">
                                <svg
                                  viewBox="0 0 24 24"
                                  className="h-4 w-4 md:h-[18px] md:w-[18px]"
                                  fill="currentColor"
                                  aria-hidden="true"
                                >
                                  <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
                                </svg>
                              </span>
                            ))}
                          </div>
                          <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-5 md:gap-4 md:p-6">
                            <div className="flex items-start gap-4 pr-24 md:pr-28">
                              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#2b5f8f] via-[#3c78b6] to-[#5aa6c9] text-sm font-semibold text-white">
                                {review.name.slice(0, 1)}
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <h3 className="text-base font-semibold text-[#111827] font-display">
                                    {review.name}
                                  </h3>
                                  <span className="inline-flex items-center gap-1 text-xs font-semibold tracking-[0.2em] uppercase text-[#94a3b8]">
                                    <span>{review.time}</span>
                                    {review.pinned ? (
                                      <span className="inline-flex items-center text-[#2b5f8f]" aria-label="釘選">
                                        {pinIcon}
                                      </span>
                                    ) : null}
                                  </span>
                                </div>
                              </div>
                            </div>

                            <div className="space-y-2">
                              <p
                                ref={(node) => {
                                  const key = `${review.name}-${review.time}`;
                                  if (node) {
                                    cashReviewPreviewRefs.current[key] = node;
                                    return;
                                  }

                                  delete cashReviewPreviewRefs.current[key];
                                }}
                                className="line-clamp-3 text-sm md:text-base leading-relaxed text-[#334155]"
                              >
                                {review.paragraphs.join(" ")}
                              </p>
                              {cashReviewHasMoreMap[`${review.name}-${review.time}`] ? (
                                <p className="text-xs font-semibold tracking-[0.25em] uppercase text-[#94a3b8] font-lora leading-none">
                                  VIEW MORE
                                </p>
                              ) : null}
                            </div>

                            {review.photos?.length ? (
                              <div className="pt-2">
                                <div className="flex flex-wrap gap-2">
                                  {review.photos.map((photo, photoIndex) => (
                                    <button
                                      key={`${review.name}-photo-${photoIndex}`}
                                      type="button"
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        setSelectedCashReviewPhoto({
                                          src: photo.src,
                                          alt: photo.alt ?? `${review.name} 評價照片 ${photoIndex + 1}`,
                                        });
                                      }}
                                      className="h-10 w-10 overflow-hidden rounded-sm border border-[#d7dde3] bg-[#f8fafc] shadow-sm transition-transform duration-200 hover:-translate-y-0.5 hover:shadow-md md:h-12 md:w-12"
                                      aria-label={`放大 ${review.name} 的評價照片 ${photoIndex + 1}`}
                                    >
                                      <img
                                        src={photo.src}
                                        alt={photo.alt ?? `${review.name} 評價照片 ${photoIndex + 1}`}
                                        className="h-full w-full object-cover"
                                        loading="lazy"
                                      />
                                    </button>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        </CashFadeIn>
                      ))}
                    </div>

                    <div className="mt-2 flex items-center justify-center gap-4">
                      <button
                        type="button"
                        onClick={() => setCashReviewPaging({ slug, page: Math.max(1, cashReviewPage - 1) })}
                        disabled={cashReviewPage === 1}
                        aria-label="上一頁評價"
                        className="text-[#1f2937] transition-colors hover:text-[#2b5f8f] disabled:cursor-not-allowed disabled:text-[#cbd5e1]"
                      >
                        <svg
                          aria-hidden="true"
                          viewBox="0 0 24 24"
                          className="h-6 w-6"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M15 5l-7 7 7 7" />
                        </svg>
                      </button>

                      <div className="flex items-center gap-2 whitespace-nowrap text-[10px] font-semibold tracking-[0.3em] text-[#94a3b8] font-display">
                        {cashReviewPageItems.map((item, index) => {
                          if (item === "ellipsis") {
                            return (
                              <span key={`review-page-ellipsis-${index}`} className="px-1 text-[#cbd5e1]">
                                ...
                              </span>
                            );
                          }

                          return (
                            <button
                              key={`review-page-${item}`}
                              type="button"
                              onClick={() => setCashReviewPaging({ slug, page: item })}
                              aria-current={cashReviewPage === item ? "page" : undefined}
                              className={`transition-colors ${
                                cashReviewPage === item ? "text-[#1f2937]" : "text-[#94a3b8] hover:text-[#2b5f8f]"
                              }`}
                            >
                              {String(item).padStart(2, "0")}
                            </button>
                          );
                        })}
                      </div>

                      <button
                        type="button"
                        onClick={() => setCashReviewPaging({ slug, page: Math.min(cashReviewPageCount, cashReviewPage + 1) })}
                        disabled={cashReviewPage === cashReviewPageCount}
                        aria-label="下一頁評價"
                        className="text-[#1f2937] transition-colors hover:text-[#2b5f8f] disabled:cursor-not-allowed disabled:text-[#cbd5e1]"
                      >
                        <svg
                          aria-hidden="true"
                          viewBox="0 0 24 24"
                          className="h-6 w-6"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </div>
                  </>
                ) : (
                  <CashFadeIn
                    as="div"
                    className="mx-auto flex max-w-2xl flex-col items-center gap-5 rounded-sm border border-dashed border-[#cfd8e8] bg-white px-6 py-10 text-center shadow-[0_12px_30px_rgba(15,23,42,0.04)]"
                  >
                    <p className="text-base md:text-lg leading-relaxed text-[#475569]">
                      尚未有評價，立即登入為您喜歡的教練留下評價
                    </p>
                    <SiteLink
                      to="/membership"
                      className="inline-flex items-center justify-center rounded-full bg-[#a8d8f4] px-6 py-3 text-sm font-semibold text-[#1f3a57] shadow-[0_12px_30px_rgba(43,95,143,0.14)] transition-colors duration-200 hover:bg-[#94cdee]"
                    >
                      會員登入
                    </SiteLink>
                  </CashFadeIn>
                )}
              </div>
            </section>

            {selectedCashReview ? (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 px-4 py-8"
                role="dialog"
                aria-modal="true"
                aria-label="學員評價詳情"
                onClick={() => setSelectedCashReview(null)}
              >
                <button
                  type="button"
                  className="absolute right-4 top-4 rounded-full bg-white/10 px-3 py-2 text-sm font-semibold text-white backdrop-blur transition-colors hover:bg-white/20"
                  onClick={() => setSelectedCashReview(null)}
                >
                  關閉
                </button>
                <div
                  className="max-h-[88vh] w-full max-w-3xl overflow-hidden rounded-sm bg-white text-left shadow-[0_24px_80px_rgba(0,0,0,0.45)]"
                  onClick={(event) => event.stopPropagation()}
                >
                  <article className="max-h-[88vh] overflow-y-auto p-5 md:p-7">
                    <div className="flex items-start gap-4">
                      <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#2b5f8f] via-[#3c78b6] to-[#5aa6c9] text-base font-semibold text-white">
                        {selectedCashReview.name.slice(0, 1)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-xl font-semibold text-[#111827] font-display">
                            {selectedCashReview.name}
                          </h3>
                          <span className="inline-flex items-center gap-1 text-xs font-semibold tracking-[0.2em] uppercase text-[#94a3b8]">
                            <span>{selectedCashReview.time}</span>
                            {selectedCashReview.pinned ? (
                              <span className="inline-flex items-center text-[#2b5f8f]" aria-label="釘選">
                                {pinIcon}
                              </span>
                            ) : null}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 space-y-4">
                      {renderReviewParagraphs(
                        selectedCashReview.paragraphs,
                        "text-base md:text-lg leading-relaxed text-[#334155] whitespace-pre-line"
                      )}
                    </div>

                    {selectedCashReview.photos?.length ? (
                      <div className="mt-7 grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5">
                        {selectedCashReview.photos.map((photo, photoIndex) => (
                          <button
                            key={`${selectedCashReview.name}-modal-photo-${photoIndex}`}
                            type="button"
                            onClick={() =>
                              setSelectedCashReviewPhoto({
                                src: photo.src,
                                alt: photo.alt ?? `${selectedCashReview.name} 評價照片 ${photoIndex + 1}`,
                              })
                            }
                            className="aspect-square overflow-hidden rounded-sm border border-[#d7dde3] bg-[#f8fafc]"
                            aria-label={`放大 ${selectedCashReview.name} 的評價照片 ${photoIndex + 1}`}
                          >
                            <img
                              src={photo.src}
                              alt={photo.alt ?? `${selectedCashReview.name} 評價照片 ${photoIndex + 1}`}
                              className="h-full w-full object-cover"
                              loading="lazy"
                            />
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </article>
                </div>
              </div>
            ) : null}

            {selectedCashReviewPhoto ? (
              <div
                className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 px-4 py-8"
                role="dialog"
                aria-modal="true"
                aria-label="評價照片預覽"
                onClick={() => setSelectedCashReviewPhoto(null)}
              >
                <button
                  type="button"
                  className="absolute right-4 top-4 rounded-full bg-white/10 px-3 py-2 text-sm font-semibold text-white backdrop-blur transition-colors hover:bg-white/20"
                  onClick={() => setSelectedCashReviewPhoto(null)}
                >
                  關閉
                </button>
                <button
                  type="button"
                  className="max-h-[85vh] max-w-[92vw] overflow-hidden rounded-sm bg-white shadow-[0_24px_80px_rgba(0,0,0,0.45)]"
                  onClick={(event) => event.stopPropagation()}
                >
                  <img loading="lazy" decoding="async"
                    src={selectedCashReviewPhoto.src}
                    alt={selectedCashReviewPhoto.alt}
                    className="block max-h-[85vh] max-w-[92vw] object-contain"
                  />
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </main>
      <SiteFooter />
    </div>
  );
}

export default CoachPage;
