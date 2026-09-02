import React, { useMemo, useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import { motion, useScroll, useTransform } from 'framer-motion';
import aboutSnowland from '../../assets/site/About snowland.jpg';
import tomamuResort from '../../assets/site/Homepage-Tomamu ski resort.jpg';
import offPisteCourse from '../../assets/site/Homepage-course-Off piste.jpg';
import hokkaidoCourse from '../../assets/site/Homepage-course-Hokkaido.jpg';
import SpecialOffers from '../../components/site/SpecialOffers';
import staticCoaches from '../../data/site/coaches';
import { useWebsiteCoachCards } from '../../api/websiteCoaches';
import { fetchSiteContent } from '../../api/booking';
import legacyPages from '../../data/site/legacyPages.json';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';

function HomePage() {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"]
  });

  const y = useTransform(scrollYProgress, [0, 1], ["0%", "50%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);
  const [showAboutMore, setShowAboutMore] = useState(false);
  const [expandedCourses, setExpandedCourses] = useState({});
  const [isReviewsPaused, setIsReviewsPaused] = useState(false);
  const [expandedReviewIndex, setExpandedReviewIndex] = useState(null);
  const [cmsReviews, setCmsReviews] = useState([]);
  const reviewTextRefs = useRef([]);
  const [clampedReviewIndices, setClampedReviewIndices] = useState([]);
  const aboutParagraphs = [
    "SnowLand滑雪學校為星野Tomamu度假村／留壽都渡假村／手稻滑雪場 / 札幌國際雪場官方許可，於日本合法登記的滑雪學校，擁有多年北海道雪場教學經歷。",
    "提供中文、粵語、英文等多語言教學選擇，以確保每位學員都能在熟悉和舒適的語言環境中自在學習滑雪技巧。",
    "無論您是初次接觸滑雪的初心者，還是有一定滑雪經驗滑雪玩家，我們將根據您的需求和程度，量身定制最適合的教學計畫，以耐心與專業經驗陪你一起成長。我們注重教學的互動性和實踐性，通過系統化的教學流程，幫助您快速掌握滑雪技巧，並在過程中感受到樂趣和成就感。",
    "滑雪是一項能夠帶來無限樂趣和挑戰的運動，同時也是一種能夠拓展人生視野、增進人與大自然連結的方式。透過SnowLand滑雪學校的教學，啟發您對滑雪的熱情，我們希望陪你穩健的從零出發，也陪你愛上這片雪白的世界。",
  ];
  const coachImageByName = useMemo(() => {
    const imageByName = new Map();
    const coachBlocks = legacyPages["coach-team"]?.blocks ?? [];
    for (let index = 0; index < coachBlocks.length; index += 1) {
      const block = coachBlocks[index];
      const nextBlock = coachBlocks[index + 1];
      if (block?.type === "image" && nextBlock?.type === "heading") {
        imageByName.set(nextBlock.text, block.src);
        index += 1;
      }
    }
    return imageByName;
  }, []);
  const coachCards = useWebsiteCoachCards(staticCoaches, coachImageByName);
  const coachScrollerRef = useRef(null);
  const coachItemRefs = useRef([]);
  const [activeCoachIndex, setActiveCoachIndex] = useState(0);
  const totalCoachCards = coachCards.length;
  const resortCards = [
    {
      title: "星野 TOMAMU",
      image: tomamuResort,
      description:
        "在北海道中心體驗世界級粉雪，星野 Tomamu 擁有 29 條雪道，涵蓋初、中、進階不同難度，及開放夜間滑雪。從新手友善的平坦滑坡到具挑戰性的道外與樹林區，適合各程度的滑雪者。滑雪之外還有豐富的雪上活動設施：雪地卡丁車、夢幻的愛絲冰城，以及可俯瞰山谷與森林的霧冰平台，不滑雪也能盡情欣賞雪山美景。",
      cta: "立即查看課程",
      href: "/course/tomamu"
    },
    {
      title: "野雪嚮導",
      image: offPisteCourse,
      description:
        "探索真正的粉雪天堂，由具國際認證的嚮導專業帶領，深入北海道山岳地形，體驗滑出雪道邊界的自由與純粹。適合進階滑雪玩家挑戰極致的樂趣。嚮導團隊具備雪崩安全知識與山岳滑行經驗，依每日雪況與天氣做風險評估，即時規劃安全又具挑戰性的路線，全程專業陪伴，帶你體驗北海道原始雪山的壯闊與自由。",
      cta: "立即查看課程",
      href: "/course/off-piste-guide"
    },
    {
      title: "北海道",
      image: hokkaidoCourse,
      description:
        "SnowLand 的滑雪課程遍佈北海道各地：神居、聖誕禮物公園、比布、夕張與佐幌等熱門雪場。讓您依興趣與程度選擇最適合的學習環境。每個雪場皆有不同特色與風景。我們的專業教練團隊將協助您規劃最適合您的滑雪體驗。",
      cta: "立即查看課程",
      href: "/course/hokkaido"
    }
  ];
  React.useEffect(() => {
    let mounted = true;
    fetchSiteContent({ content_type: 'review', location_key: 'homepage.reviews', limit: 12 })
      .then((items) => {
        if (mounted) setCmsReviews(Array.isArray(items) ? items : []);
      })
      .catch(() => {
        if (mounted) setCmsReviews([]);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const staticReviews = [
    {
      name: 'Chingyee Lee',
      initials: 'CL',
      media: 'placeholder',
      textPrimary:
        '5歲初次接觸滑雪的小男生給cash教練帶，因為性格內向又黏人所以媽媽本身很擔心他會很抵觸。',
      textSecondary:
        '但cash教練帶小朋友很耐心、又很會教，結果滑了一天超愛滑雪，從山上滑到山下，完全不找爸媽，又指定下一定要讓cash叔叔帶滑！只有唯一的缺點是現在鋼琴課也不想上了，說只想學滑雪！期待明年再見面！'
    },
    {
      name: 'Eunice Liu',
      initials: 'EL',
      media: 'placeholder',
      textPrimary:
        '超感謝教練耐心指導即時糾正我滑雪時的盲點！不僅幽默還很會聊天🤣期待明年再來找教練滑雪⛷️',
      textSecondary: ''
    },
    {
      name: 'Wat Hans',
      initials: 'WH',
      media: 'placeholder',
      textPrimary:
        '初次滑雪找到七針教練\n參加了一天雙板課程\n講解十分容易明白\n感謝教練 令我們日本旅遊留下歡笑回憶',
      textSecondary: ''
    },
    {
      name: 'BESS LIN',
      initials: 'BL',
      media: 'placeholder',
      textPrimary:
        '對於一年只滑一次，每次只能滑個四五天的我們來說，只恨自己沒有早點找中文教練教學，非常謝謝Cash及七針教練細心的教學，不躁進讓我們挑戰更進階，而是一步一步紮實反覆確認我們的基本功並點出我們的問題！真的非常感謝~非常棒😍',
      textSecondary: ''
    },
    {
      name: 'OS',
      initials: 'OS',
      textPrimary:
        '謝謝Lily教練的教學，原本一直卡在落葉飄，這次終於學會S Turn了!!真的很神奇',
      textSecondary: ''
    }
  ];
  const reviews = useMemo(() => {
    if (!cmsReviews.length) return staticReviews;
    return cmsReviews.map((item) => ({
      name: item.title || 'SnowLand 學員',
      initials: item.metadata?.initials || (item.title || 'SL').slice(0, 2).toUpperCase(),
      media: item.image_url ? 'image' : 'placeholder',
      image: item.image_url || '',
      textPrimary: item.summary || item.body || item.subtitle || '',
      textSecondary: item.summary && item.body ? item.body : '',
    }));
  }, [cmsReviews]);
  const reviewsLoop = useMemo(() => [...reviews, ...reviews], [reviews]);

  React.useEffect(() => {
    const updateClamped = () => {
      const nextClamped = reviewsLoop.map((_, index) => {
        const node = reviewTextRefs.current[index];
        if (!node) return false;
        return node.scrollHeight > node.clientHeight + 1;
      });
      setClampedReviewIndices((current) => {
        if (
          current.length === nextClamped.length &&
          current.every((value, index) => value === nextClamped[index])
        ) {
          return current;
        }
        return nextClamped;
      });
    };

    updateClamped();
    window.addEventListener("resize", updateClamped);
    return () => window.removeEventListener("resize", updateClamped);
  }, [reviewsLoop, expandedReviewIndex]);

  const scrollToCoachIndex = (index) => {
    if (!totalCoachCards) return;
    const clampedIndex = Math.min(
      Math.max(index, 0),
      totalCoachCards - 1
    );
    const scroller = coachScrollerRef.current;
    const target = coachItemRefs.current[clampedIndex];
    if (!scroller || !target) return;
    const offset =
      target.offsetLeft - (scroller.clientWidth - target.clientWidth) / 2;
    scroller.scrollTo({ left: offset, behavior: "smooth" });
    setActiveCoachIndex(clampedIndex);
  };

  const renderCoachCardContent = (coach) => (
    <>
      <div className="w-full aspect-[5/4] bg-[#f8fafc]">
        {coach.image ? (
          <img loading="lazy" decoding="async"
            src={coach.image}
            alt={coach.name}
            className="w-full h-full object-cover object-top"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-[#eef3f8] text-3xl font-semibold text-[#94a3b8] font-display">
            {coach.name?.slice(0, 1)}
          </div>
        )}
      </div>

      <div className="px-8 py-10">
        <h3 className="text-lg font-semibold text-[#1f2937] font-lora">
          {coach.name}
        </h3>
        {coach.coachType && (
          <p className="mt-4 text-sm font-semibold text-[#4b5563]">
            {coach.coachType}
          </p>
        )}
        {coach.cardBio && (
          <p className="mt-4 text-sm text-[#6b7280] leading-relaxed">
            {coach.cardBio}
          </p>
        )}
        {coach.languages && (
          <p className="mt-4 text-sm font-semibold text-[#64748b]">
            {coach.languages}
          </p>
        )}
      </div>
    </>
  );

  return (
    <div className="w-full font-sans">
      <SiteHeader />
      <div ref={containerRef} className="relative w-full h-screen overflow-hidden">

        {/* Background Video (YouTube) */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0">
          <div className="absolute top-1/2 left-1/2 min-w-full min-h-full w-[177.77vh] h-[56.25vw] -translate-x-1/2 -translate-y-1/2 pointer-events-none">
            <iframe
              className="w-full h-full scale-105" // Slight scale to prevent edge flickering
              src="https://www.youtube.com/embed/m-4vgzqVNqI?autoplay=1&mute=1&controls=0&loop=1&playlist=m-4vgzqVNqI&playsinline=1&showinfo=0&rel=0&iv_load_policy=3&disablekb=1&modestbranding=1&autohide=1&enablejsapi=1"
              title="Background Video"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            ></iframe>
          </div>
        </div>

        {/* Dark Overlay with Gradient */}
        <div className="absolute top-0 left-0 w-full h-full bg-linear-to-b from-black/60 via-black/40 to-black/70 z-10 pointer-events-none"></div>

        {/* Content Container */}
        <motion.div
          style={{ y, opacity }}
          className="relative z-20 w-full h-full flex flex-col items-center justify-center text-center px-4 md:px-8 text-white max-w-7xl mx-auto"
        >

          {/* Main Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
            className="text-2xl md:text-4xl lg:text-5xl font-bold mb-6 tracking-wide drop-shadow-xl font-display leading-tight"
          >
            北海道星野TOMAMU<br />
            官方許可滑雪學校
          </motion.h1>

          {/* Subhead CN */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4, ease: "easeOut" }}
            className="text-base md:text-lg lg:text-xl font-medium mb-4 tracking-wider drop-shadow-md opacity-95 text-balance"
          >
            安心的親子共學旅程，一起創造難忘的滑雪回憶
          </motion.p>

          {/* Subhead EN */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6, ease: "easeOut" }}
            className="text-xs md:text-sm lg:text-base font-light mb-16 tracking-wide font-inter italic opacity-80 max-w-3xl mx-auto"
          >
            Enjoy a joyful family ski experience — create unforgettable memories together.
          </motion.p>

          {/* CTA Button */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.8, ease: "easeOut" }}
          >
            <SiteLink
              to="/booking"
              className="group relative inline-flex items-center justify-center px-10 py-5 text-sm md:text-base font-bold text-white transition-all duration-300 bg-[#8ec8f0] rounded-full hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden"
            >
              {/* Shimmer Effect */}
              <div className="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>

              <span className="relative z-10">預約課程</span>
              <svg
                className="w-5 h-5 ml-2 -mr-1 transition-transform duration-300 group-hover:translate-x-1 relative z-10"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path>
              </svg>
            </SiteLink>
          </motion.div>
        </motion.div>

        <a
          href="#about-snowland"
          aria-label="Scroll down"
          className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20 text-white/80 hover:text-white transition-colors"
        >
          <div className="w-10 h-10 flex items-center justify-center">
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M6 9l6 6 6-6" />
            </svg>
          </div>
        </a>
      </div>

      <section id="about-snowland" className="bg-white">
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6 md:gap-12 lg:gap-16 items-center">
          <div className="w-full h-72 md:h-[420px] lg:h-full min-h-[420px]">
            <img loading="eager" decoding="async" fetchpriority="high"
              src={aboutSnowland}
              alt="Snowland 滑雪學校"
              className="w-full h-full object-cover"
            />
          </div>

          <div className="px-6 md:px-10 pt-10 pb-16 md:py-24">
            <div className="max-w-2xl text-[#2b2b2b] text-sm md:text-base leading-relaxed space-y-6">
              <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                Snowland 滑雪學校
              </h2>
              <p>
                SnowLand滑雪學校為
                <span className="font-semibold">
                  星野Tomamu度假村／留壽都渡假村／手稻滑雪場 / 札幌國際雪場
                </span>
                官方許可，於日本合法登記的滑雪學校，擁有多年北海道雪場教學經歷。
              </p>
              <p>
                提供
                <span className="font-semibold">中文、粵語、英文</span>
                等多語言教學選擇，以確保每位學員都能在熟悉和舒適的語言環境中自在學習滑雪技巧。
              </p>
              {showAboutMore &&
                aboutParagraphs.slice(2).map((text, index) => (
                  <p key={`about-more-${index}`}>{text}</p>
                ))}
              <button
                type="button"
                onClick={() => setShowAboutMore((prev) => !prev)}
                className="inline-flex items-center text-sm font-semibold text-[#1f2937] hover:text-[#0f172a] transition-colors underline underline-offset-4"
              >
                {showAboutMore ? "收起" : "展開"}
              </button>
              <div className="flex justify-center">
                <SiteLink
                  to="/about"
                  className="relative z-10 pointer-events-auto inline-flex items-center justify-center px-6 py-2 rounded-full border border-[#1f2937] text-sm font-semibold text-[#1f2937] hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white transition-colors"
                >
                  了解更多
                </SiteLink>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-white">
        <div className="max-w-6xl mx-auto px-6 md:px-10 py-16 md:py-24">
          <div className="text-center mb-12 md:mb-16">
            <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
              Course
            </p>
            <h2 className="text-2xl font-semibold text-[#1f2937] mt-4 font-display">
              熱門課程
            </h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 md:gap-16">
            {resortCards.map((resort) => (
              <article
                key={resort.title}
                className="group flex flex-col items-center w-full max-w-md mx-auto"
              >
                <h3 className="text-xl font-semibold text-[#2b2b2b] font-display tracking-wide text-center">
                  {resort.title}
                </h3>

                <div className="mt-6 w-full">
                  <div className="relative w-full h-56 md:h-60 shadow-[0_16px_28px_rgba(15,23,42,0.12)] overflow-hidden">
                    <img loading="lazy" decoding="async"
                      src={resort.image}
                      alt={`${resort.title} Course`}
                      className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/35 via-black/10 to-transparent opacity-70 transition-opacity duration-300 group-hover:opacity-90"></div>
                  </div>
                </div>

                <div className="mt-6 text-[#3f3f3f] text-sm leading-relaxed w-full">
                  <p
                    style={
                      expandedCourses[resort.title]
                        ? undefined
                        : {
                          display: "-webkit-box",
                          WebkitLineClamp: 3,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }
                    }
                  >
                    {resort.description}
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedCourses((prev) => ({
                        ...prev,
                        [resort.title]: !prev[resort.title],
                      }))
                    }
                    className="mt-3 inline-flex items-center text-sm font-semibold text-[#1f2937] hover:text-[#0f172a] transition-colors underline underline-offset-4"
                  >
                    {expandedCourses[resort.title] ? "收起" : "展開"}
                  </button>
                  <div className="w-12 h-px bg-[#c4c4c4] my-6 mx-auto"></div>
                  <div className="mt-6 text-center">
                    <SiteLink
                      to={resort.href}
                      className="inline-flex items-center justify-center px-8 py-2 rounded-full border border-[#1f2937] text-sm font-semibold text-[#1f2937] hover:border-[#4A6B8A] hover:bg-[#4A6B8A] hover:text-white transition-colors"
                    >
                      {resort.cta}
                    </SiteLink>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="homepage-reviews" className="bg-[#f3f6f9] scroll-mt-24">
        <div className="max-w-6xl mx-auto px-6 md:px-10 pt-16 md:pt-24">
          <div className="text-center mb-12 md:mb-16">
            <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
              Reviews
            </p>
            <h2 className="text-2xl font-semibold text-[#1f2937] mt-4 font-display">
              學員好評
            </h2>
            <p className="mt-4 text-sm text-[#6b7280]">
              5.0 ⭐⭐⭐⭐⭐ 176{" "}
              <a
                href="https://share.google/jDAaMDoQQX6g8LUs9"
                className="relative group inline-flex items-center text-[#6b7280] hover:text-[#2b5f8f] transition-colors"
                target="_blank"
                rel="noopener noreferrer"
              >
                Google Reviews
                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-[#2b5f8f] transition-all duration-300 group-hover:w-full"></span>
              </a>
            </p>
          </div>
        </div>

        <div
          className="group relative w-full overflow-x-hidden"
          onTouchStart={() => setIsReviewsPaused(true)}
          onTouchEnd={() => setIsReviewsPaused(false)}
          onTouchCancel={() => setIsReviewsPaused(false)}
        >
          <div className="py-6">
            <div
              className={`review-marquee-track flex gap-6 ${isReviewsPaused ? "is-paused" : ""}`}
            >
              {reviewsLoop.map((review, index) => (
                <article
                  key={`${review.name}-${index}`}
                  className={`review-card group w-[280px] sm:w-[320px] md:w-[360px] shrink-0 bg-[#f9fafb] border border-[#eef2f7] rounded-lg p-6 md:p-7 shadow-[0_10px_24px_rgba(15,23,42,0.06)] ${review.media ? "has-media" : "no-media"
                    } ${expandedReviewIndex === index ? "is-expanded" : ""}`}
                  onClick={() =>
                    setExpandedReviewIndex((prev) => (prev === index ? null : index))
                  }
                >
                  {review.media === "placeholder" && (
                    <div className="review-image mb-5 w-full rounded-lg bg-gradient-to-br from-[#d9e6f2] via-[#eef3f8] to-[#f9fbfd] flex items-center justify-center text-xs tracking-[0.2em] uppercase text-[#8aa0b5]">
                      Image Holder
                    </div>
                  )}
                  {review.media === "image" && review.image && (
                    <img
                      loading="lazy"
                      decoding="async"
                      src={review.image}
                      alt={review.name}
                      className="review-image mb-5 w-full rounded-lg object-cover"
                    />
                  )}
                  <div className="review-body">
                    <div className="flex flex-col gap-2">
                      <p className="text-base font-semibold text-[#2b5f8f] whitespace-nowrap">
                        {review.name}
                      </p>
                      <div className="flex gap-1">
                        {[...Array(5)].map((_, starIndex) => (
                          <svg
                            key={starIndex}
                            className="w-4 h-4 text-[#f5c542]"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            aria-hidden="true"
                          >
                            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.286 3.965a1 1 0 00.95.69h4.173c.969 0 1.371 1.24.588 1.81l-3.377 2.455a1 1 0 00-.364 1.118l1.286 3.965c.3.921-.755 1.688-1.54 1.118l-3.377-2.455a1 1 0 00-1.176 0l-3.377 2.455c-.784.57-1.838-.197-1.539-1.118l1.286-3.965a1 1 0 00-.364-1.118L2.02 9.392c-.783-.57-.38-1.81.588-1.81h4.174a1 1 0 00.95-.69l1.317-3.965z" />
                          </svg>
                        ))}
                      </div>
                    </div>
                    <p
                      ref={(node) => {
                        reviewTextRefs.current[index] = node;
                      }}
                      className={`review-text text-sm text-[#4b5563] leading-relaxed whitespace-pre-line ${expandedReviewIndex === index ? "" : "review-clamp"
                        } ${clampedReviewIndices[index] ? "is-clamped" : ""}`}
                    >
                      {review.textSecondary
                        ? `${review.textPrimary}\n${review.textSecondary}`
                        : review.textPrimary}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
        <div className="pb-16 md:pb-24"></div>
      </section>

      <section id="homepage-coaches" className="bg-white scroll-mt-24">
        <div className="max-w-6xl mx-auto px-6 md:px-10 py-16 md:py-24">
          <div className="text-center mb-12 md:mb-16">
            <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
              COACH
            </p>
            <h2 className="text-2xl font-semibold text-[#1f2937] mt-4 font-display">
              <SiteLink
                to="/coach"
                className="no-underline text-[#1f2937] hover:text-[#1f2937]"
              >
                教練團隊
              </SiteLink>
            </h2>
          </div>

          <div className="md:hidden">
            <div
              ref={coachScrollerRef}
              className="flex gap-6 overflow-x-auto snap-x snap-mandatory scroll-smooth -mx-6 px-6 pb-4 hide-scrollbar"
              onScroll={(event) => {
                const scroller = event.currentTarget;
                const center = scroller.scrollLeft + scroller.clientWidth / 2;
                let closestIndex = 0;
                let closestDistance = Number.POSITIVE_INFINITY;
                coachItemRefs.current.forEach((item, index) => {
                  if (!item) return;
                  const itemCenter = item.offsetLeft + item.clientWidth / 2;
                  const distance = Math.abs(center - itemCenter);
                  if (distance < closestDistance) {
                    closestDistance = distance;
                    closestIndex = index;
                  }
                });
                setActiveCoachIndex(closestIndex);
              }}
            >
              {coachCards.map((coach, index) => {
                const className = "snap-center min-w-[80%] bg-white border border-[#e5e9f2] rounded-sm overflow-hidden text-center shadow-[0_20px_40px_rgba(15,23,42,0.08)]";
                const setCardRef = (node) => {
                  coachItemRefs.current[index] = node;
                };

                if (coach.slug) {
                  return (
                    <SiteLink
                      key={coach.name}
                      ref={setCardRef}
                      to={`/coach/${coach.slug}`}
                      className={className}
                    >
                      {renderCoachCardContent(coach)}
                    </SiteLink>
                  );
                }

                return (
                  <article key={coach.name} ref={setCardRef} className={className}>
                    {renderCoachCardContent(coach)}
                  </article>
                );
              })}
            </div>
            <div className="mt-4 flex items-center justify-center gap-2">
              {coachCards.map((coach, index) => (
                <button
                  key={`coach-dot-${coach.name}`}
                  type="button"
                  onClick={() => scrollToCoachIndex(index)}
                  aria-label={`View ${coach.name}`}
                  className={`h-2 w-2 rounded-full transition-colors ${activeCoachIndex === index ? "bg-[#2b5f8f]" : "bg-[#cbd5e1]"
                    }`}
                />
              ))}
            </div>
          </div>

          <div className="hidden md:grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 md:gap-10">
            {coachCards.map((coach) => {
              const className = "bg-white border border-[#e5e9f2] rounded-sm overflow-hidden text-center shadow-[0_20px_40px_rgba(15,23,42,0.08)] transition-transform duration-300 hover:-translate-y-1";

              if (coach.slug) {
                return (
                  <SiteLink key={coach.name} to={`/coach/${coach.slug}`} className={className}>
                    {renderCoachCardContent(coach)}
                  </SiteLink>
                );
              }

              return (
                <article key={coach.name} className={className}>
                  {renderCoachCardContent(coach)}
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <SpecialOffers />

      <section className="bg-white">
        <div className="max-w-4xl mx-auto px-6 md:px-10 py-16 md:py-20 text-center">
          <div
            className="relative mx-auto w-full max-w-[724px] overflow-hidden rounded-sm border border-[#e2e8f0] px-6 py-8 md:h-[190px] md:px-10 md:py-0 flex flex-col items-center justify-center bg-cover"
            style={{
              backgroundImage: "url(/Course/off-piste-guide/off-piste-guide-006.jpg)",
              backgroundPosition: "center 60%",
            }}
          >
            <div className="absolute inset-0 bg-black/20" />
            <div className="relative z-10">
              <h2 className="text-2xl font-semibold text-white font-display">
                <span className="block md:inline">不知道該選哪個雪場</span>
                <span className="block md:inline">或課程天數？</span>
              </h2>
              <p className="mt-4 text-sm md:text-base text-white/90 leading-relaxed">
                <span className="block md:inline">歡迎與我們聯繫，協助你規劃</span>
                <span className="block md:inline">最適合你的滑雪旅程。</span>
              </p>
              <div className="mt-8">
                <SiteLink
                  to="/contact"
                  className="inline-flex items-center justify-center rounded-full bg-[#8ec8f0] px-6 py-3 text-sm font-semibold text-white hover:bg-[#7bbbe7] transition-colors"
                >
                  立即諮詢
                </SiteLink>
              </div>
            </div>
          </div>
        </div>
      </section>

      <SiteFooter />

    </div>
  );
}

export default HomePage;
