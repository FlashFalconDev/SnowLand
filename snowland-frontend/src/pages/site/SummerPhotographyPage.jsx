import React, { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';

function SummerPhotographyPage() {
  const scrollerRef = useRef(null);
  const itemRefs = useRef([]);
  const introRef = useRef(null);
  const stageSectionRef = useRef(null);
  const stageTextRef = useRef(null);
  const tomamuSectionRef = useRef(null);
  const tomamuTextRef = useRef(null);
  const whyRef = useRef(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [introVisible, setIntroVisible] = useState(false);
  const [stageTextVisible, setStageTextVisible] = useState(false);
  const [whyVisible, setWhyVisible] = useState(false);
  const [tomamuTextVisible, setTomamuTextVisible] = useState(false);
  const [openFaqIndex, setOpenFaqIndex] = useState(0);
  const [customTravelSlideIndex, setCustomTravelSlideIndex] = useState(0);
  const [lightWeddingSlideIndex, setLightWeddingSlideIndex] = useState(0);
  const [weddingSlideIndex, setWeddingSlideIndex] = useState(0);
  const hasAutoScrolledRef = useRef(false);
  const prefersReducedMotion = useReducedMotion();
  const photos = [
    "/legacy/photography-summer/20240529-Z-F-王妍如-Dylan-122.jpg",
    "/legacy/photography-summer/image-05.jpg",
    "/legacy/photography-summer/2023-10-13-TheStage Martin&Gigi 婚紗拍樣-169.jpg",
  ];
  const customTravelPhotos = [
    "/legacy/photography-summer/image-02.jpg",
    "/legacy/photography-summer/image-01.jpg",
    "/legacy/photography-summer/2022-12-30-Tiffany 全家福-015.jpg",
  ];
  const lightWeddingPhotos = [
    "/legacy/photography-summer/2021-12-15-The Stage 花蓮婚紗-Ron&Susie-130.jpg",
    "/legacy/photography-summer/image-04.jpg",
    "/legacy/photography-summer/2023-05-28-TheStage Abbie&Gael婚紗拍樣 (45 - 531).jpg",
    "/legacy/photography-summer/2023-05-28-TheStage Abbie&Gael婚紗拍樣 (74 - 531).jpg",
  ];
  const weddingPhotos = [
    "/legacy/photography-summer/2023-05-28-TheStage Abbie&Gael婚紗拍樣 (230 - 531).jpg",
    "/legacy/photography-summer/2023-05-28-TheStage Abbie&Gael婚紗拍樣 (264 - 531).jpg",
    "/legacy/photography-summer/image-06.jpg",
    "/legacy/photography-summer/2023-10-13-TheStage Martin&Gigi 婚紗拍樣-81.jpg",
  ];
  const baseUrl = import.meta.env.BASE_URL ?? "/";
  const withBaseUrl = (path) =>
    `${baseUrl}${path.startsWith("/") ? path.slice(1) : path}`;
  const totalPhotos = photos.length;
  const { scrollYProgress: stageScrollYProgress } = useScroll({
    target: stageSectionRef,
    offset: ["start end", "end start"],
  });
  const { scrollYProgress: tomamuScrollYProgress } = useScroll({
    target: tomamuSectionRef,
    offset: ["start end", "end start"],
  });
  const stageImageY = useTransform(stageScrollYProgress, [0, 1], ["0%", "28%"]);
  const stageTextY = useTransform(stageScrollYProgress, [0, 1], ["0%", "12%"]);
  const tomamuImageY = useTransform(tomamuScrollYProgress, [0, 1], ["0%", "24%"]);
  const tomamuTextY = useTransform(tomamuScrollYProgress, [0, 1], ["0%", "10%"]);

  const scrollToIndex = (index) => {
    const clampedIndex = ((index % totalPhotos) + totalPhotos) % totalPhotos;
    const scroller = scrollerRef.current;
    const target = itemRefs.current[clampedIndex];
    if (!scroller || !target) return;
    const offset =
      target.offsetLeft - (scroller.clientWidth - target.clientWidth) / 2;
    scroller.scrollTo({
      left: offset,
      behavior: "smooth",
    });
    setActiveIndex(clampedIndex);
  };

  useEffect(() => {
    const id = window.requestAnimationFrame(() => scrollToIndex(1));
    return () => window.cancelAnimationFrame(id);
  }, [totalPhotos]);

  useEffect(() => {
    const target = introRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIntroVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const target = stageTextRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setStageTextVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const target = tomamuTextRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTomamuTextVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const target = stageSectionRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (
          entry.isIntersecting &&
          !hasAutoScrolledRef.current &&
          entry.boundingClientRect.top >= 0
        ) {
          hasAutoScrolledRef.current = true;
          window.requestAnimationFrame(() => {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
          });
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const target = whyRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setWhyVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setCustomTravelSlideIndex((prev) => (prev + 1) % customTravelPhotos.length);
    }, 4000);
    return () => window.clearInterval(intervalId);
  }, [customTravelPhotos.length]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setLightWeddingSlideIndex((prev) => (prev + 1) % lightWeddingPhotos.length);
    }, 4000);
    return () => window.clearInterval(intervalId);
  }, [lightWeddingPhotos.length]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setWeddingSlideIndex((prev) => (prev + 1) % weddingPhotos.length);
    }, 4000);
    return () => window.clearInterval(intervalId);
  }, [weddingPhotos.length]);

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main className="max-w-5xl mx-auto px-6 pt-32 pb-24 flex-1 w-full">
        <div className="text-center">
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            Summer Photography
          </p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
            夏季旅拍攝影
          </h1>
        </div>
        <section className="mt-4 w-screen relative left-1/2 -translate-x-1/2">
          <div className="relative">
            <div
              ref={scrollerRef}
              className="flex gap-3 overflow-x-auto snap-x snap-mandatory scroll-smooth px-6 md:px-12 hide-scrollbar"
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
              {photos.map((src, index) => (
                <figure
                  key={src}
                  ref={(node) => {
                    itemRefs.current[index] = node;
                  }}
                  className="relative min-w-[85%] aspect-[4/3] md:aspect-auto md:min-w-[70%] md:h-[70vh] snap-center overflow-hidden bg-[#e2e8f0]"
                >
                  <img loading="lazy" decoding="async"
                    src={withBaseUrl(src)}
                    alt="Summer photography"
                    className="h-full w-full object-cover"
                  />
                </figure>
              ))}
            </div>
            <button
              type="button"
              onClick={() => scrollToIndex(activeIndex - 1)}
              className="absolute left-4 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full bg-white/80 text-[#1f2937] shadow-md hover:bg-white transition-colors"
              aria-label="Previous photo"
            >
              ←
            </button>
            <button
              type="button"
              onClick={() => scrollToIndex(activeIndex + 1)}
              className="absolute right-4 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full bg-white/80 text-[#1f2937] shadow-md hover:bg-white transition-colors"
              aria-label="Next photo"
            >
              →
            </button>
          </div>
          <div className="mt-6 flex items-center justify-center gap-6 text-xs text-[#94a3b8] font-display">
            <span className="flex items-center gap-3">
              <span className="w-16 h-px bg-[#e2e8f0]" />
              <span className="text-[10px] tracking-[0.4em] uppercase">
                {String(activeIndex + 1).padStart(2, "0")} /{" "}
                {String(totalPhotos).padStart(2, "0")}
              </span>
              <span className="w-16 h-px bg-[#e2e8f0]" />
            </span>
          </div>
        </section>
        <section className="mt-12 md:mt-16">
          <div
            ref={introRef}
            className={`px-6 py-10 text-center transition-all duration-700 ease-out md:px-12 md:py-14 ${
              introVisible ? "translate-y-0 opacity-100" : "translate-y-10 opacity-0"
            }`}
          >
            <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
              用光影記錄每段旅程
            </h2>
            <p className="mt-4 max-w-xl mx-auto text-base md:text-lg leading-relaxed text-[#475569]">
              <span className="block">為北海道夏季旅行打造最自在的影像記憶。</span>
              <span className="block">
                結合在地的專業攝影團隊，城市街拍、山林輕旅、薰衣草花海浪漫寫真或親子合影，我們以故事感的視角量身打造專屬於你的旅途亮點，留下珍貴的影像記憶。
              </span>
            </p>
            <div className="mt-8 flex justify-center">
              <a
                href="#"
                className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
              >
                預約夏季旅拍
              </a>
            </div>
          </div>
        </section>
        <section
          ref={stageSectionRef}
          className="mt-12 md:mt-16 w-screen relative left-1/2 -translate-x-1/2"
        >
          <div className="relative aspect-[3/4] w-full overflow-hidden md:aspect-auto md:h-screen">
            <motion.img
              src={withBaseUrl("/legacy/photography-summer/image-02.jpg")}
              alt="富良野花海背景"
              className="absolute inset-0 h-full w-full object-cover will-change-transform"
              style={prefersReducedMotion ? undefined : { y: stageImageY }}
            />
            <div className="absolute inset-x-0 bottom-[8%] px-6 md:bottom-[12%] md:px-16">
              <motion.div
                ref={stageTextRef}
                className={`mx-auto w-full max-w-4xl space-y-4 bg-white/80 px-6 py-6 text-center text-[#1f2937] transition-all duration-700 ease-out md:px-8 md:py-8 ${
                  stageTextVisible
                    ? "translate-y-0 opacity-100"
                    : "translate-y-10 opacity-0"
                }`}
                style={prefersReducedMotion ? undefined : { y: stageTextY }}
              >
                <div className="text-xs tracking-[0.4em] uppercase text-[#1f2937] font-display">
                  ▸  富良野的浪漫花海之旅
                </div>
                <p className="text-base md:text-lg leading-relaxed">
                  富良野以夏季盛開的薰衣草聞名，是戀人與家庭拍攝的首選。
                </p>
                <p className="text-base md:text-lg leading-relaxed">
                  無論是手牽手漫步在紫色花田的情侶寫真，或是孩子奔跑在向日葵與波斯菊間的歡笑畫面，我們都將為您捕捉最自然、動人的瞬間。
                </p>
              </motion.div>
            </div>
          </div>
        </section>
        <section ref={tomamuSectionRef} className="w-screen relative left-1/2 -translate-x-1/2">
          <div className="relative aspect-[3/4] w-full overflow-hidden md:aspect-auto md:h-screen">
            <motion.img
              src={withBaseUrl("/legacy/photography-summer/image-03.jpg")}
              alt="星野Tomamu夏季背景"
              className="absolute inset-0 h-full w-full object-cover will-change-transform"
              style={prefersReducedMotion ? undefined : { y: tomamuImageY }}
            />
            <div className="absolute inset-x-0 bottom-[8%] px-6 md:bottom-[12%] md:px-16">
              <motion.div
                ref={tomamuTextRef}
                className={`mx-auto w-full max-w-4xl space-y-4 bg-white/80 px-6 py-6 text-center text-[#1f2937] transition-all duration-700 ease-out md:px-8 md:py-8 ${
                  tomamuTextVisible
                    ? "translate-y-0 opacity-100"
                    : "translate-y-10 opacity-0"
                }`}
                style={prefersReducedMotion ? undefined : { y: tomamuTextY }}
              >
                <div className="text-xs tracking-[0.4em] uppercase text-[#1f2937] font-display">
                  ▸   星野Tomamu的山野秘境
                </div>
                <p className="text-base md:text-lg leading-relaxed">
                  星野度假村不只有冬季滑雪魅力，夏季更是一片綠意與清新的天地。
                  山景草原、雲海露台、玻璃教堂與森林小徑，構成多元又唯美的拍攝背景。
                  特別推薦給想要拍攝自然系婚紗或文青風格形象照的你。
                </p>
              </motion.div>
            </div>
          </div>
        </section>
        <section className="bg-[#e9eef3] w-screen relative left-1/2 -translate-x-1/2">
          <div className="max-w-6xl mx-auto px-6 md:px-10 py-16 md:py-24">
            <div className="text-center">
              <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                服務方案
              </h2>
              <p className="mt-3 text-sm md:text-base text-[#64748b]">
                ⚲ 地點：星野 Tomamu・富良野 Furano
              </p>
            </div>
            <div className="mt-12 bg-white px-6 py-10 md:px-10">
              <div className="text-left">
                <h3 className="font-semibold text-[#1f2937] font-display">
                  <span className="block text-sm md:text-base">客製化</span>
                  <span className="block text-xl md:text-2xl">旅拍專案</span>
                </h3>
              </div>
              <div className="mt-6 grid gap-10 md:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] md:items-start">
                <div>
                  <button
                    type="button"
                    onClick={() =>
                      setCustomTravelSlideIndex(
                        (customTravelSlideIndex + 1) % customTravelPhotos.length
                      )
                    }
                    className="relative aspect-[3/2] w-full overflow-hidden text-left"
                    aria-label="切換旅拍照片"
                  >
                    {customTravelPhotos.map((src, index) => (
                      <img loading="lazy" decoding="async"
                        key={src}
                        src={withBaseUrl(src)}
                        alt="旅拍照片"
                        className={`absolute inset-0 h-full w-full object-contain object-top transition-opacity duration-1000 ${
                          index === customTravelSlideIndex ? "opacity-100" : "opacity-0"
                        }`}
                      />
                    ))}
                    <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-2">
                      {customTravelPhotos.map((_, index) => (
                        <button
                          key={`dot-${index}`}
                          type="button"
                          onClick={() => setCustomTravelSlideIndex(index)}
                          className={`h-2.5 w-2.5 rounded-full border border-white/80 ${
                            index === customTravelSlideIndex
                              ? "bg-white"
                              : "bg-white/40"
                          }`}
                          aria-label={`切換到第 ${index + 1} 張`}
                        />
                      ))}
                    </div>
                  </button>
                </div>
                <div className="text-[#475569]">
                  <div className="space-y-6">
                    {[
                      {
                        title: "1小時快閃回憶",
                        details: ["可選擇1個景點", "保障20張以上照片"],
                        price: "NT$23,800",
                      },
                      {
                        title: "2小時經典旅行",
                        details: ["可選擇1～2個景點", "保障40張以上照片"],
                        price: "NT$32,800",
                      },
                      {
                        title: "4小時半日樂活",
                        details: ["可選擇2～3個景點", "保障70張以上照片"],
                        price: "NT$42,800",
                      },
                    ].map((plan) => (
                      <div key={plan.title} className="border-b border-[#d7dde3] pb-6">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div>
                            <h4 className="text-base md:text-lg font-semibold text-[#1f2937] font-display">
                              {plan.title}
                            </h4>
                            <div className="mt-2 space-y-1 text-sm">
                              {plan.details.map((item) => (
                                <p key={item}>{item}</p>
                              ))}
                            </div>
                          </div>
                          <p className="text-base font-semibold text-[#1f2937] font-display">
                            {plan.price}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-8 grid gap-6 text-sm md:grid-cols-2">
                    <div>
                      <p className="font-semibold text-[#1f2937]">▸ 方案包含</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>・照片全給</p>
                        <p>・不限人數</p>
                      </div>
                    </div>
                    <div>
                      <p className="font-semibold text-[#1f2937]">▸ 加購服務</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>・精修照片1500$/張</p>
                        <p>・女生妝髮5500$/位</p>
                        <p>・男生妝髮3500$/位</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-12 bg-white px-6 py-10 md:px-10">
              <div className="text-left">
                <h3 className="font-semibold text-[#1f2937] font-display">
                  <span className="block text-sm md:text-base">客製化</span>
                  <span className="block text-xl md:text-2xl">旅拍輕婚紗專案</span>
                </h3>
              </div>
              <div className="mt-6 grid gap-10 md:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] md:items-start">
                <div>
                  <button
                    type="button"
                    onClick={() =>
                      setLightWeddingSlideIndex(
                        (lightWeddingSlideIndex + 1) % lightWeddingPhotos.length
                      )
                    }
                    className="relative w-full text-left"
                    aria-label="切換旅拍輕婚紗照片"
                  >
                    <img loading="lazy" decoding="async"
                      src={withBaseUrl(lightWeddingPhotos[0])}
                      alt=""
                      aria-hidden="true"
                      className="w-full h-auto opacity-0 pointer-events-none"
                    />
                    {lightWeddingPhotos.map((src, index) => (
                      <img loading="lazy" decoding="async"
                        key={src}
                        src={withBaseUrl(src)}
                        alt="旅拍婚紗照片"
                        className={`absolute inset-0 w-full h-auto object-contain object-left transition-opacity duration-1000 ${
                          index === lightWeddingSlideIndex ? "opacity-100" : "opacity-0"
                        }`}
                      />
                    ))}
                    <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-2">
                      {lightWeddingPhotos.map((_, index) => (
                        <button
                          key={`light-dot-${index}`}
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setLightWeddingSlideIndex(index);
                          }}
                          className={`h-2.5 w-2.5 rounded-full border border-white/80 ${
                            index === lightWeddingSlideIndex
                              ? "bg-white"
                              : "bg-white/40"
                          }`}
                          aria-label={`切換到第 ${index + 1} 張`}
                        />
                      ))}
                    </div>
                  </button>
                </div>
                <div className="text-[#475569]">
                  <div className="space-y-6">
                    <div className="border-b border-[#d7dde3] pb-6">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <h4 className="text-base md:text-lg font-semibold text-[#1f2937] font-display">
                            2套6小時
                          </h4>
                          <div className="mt-2 space-y-1 text-sm">
                            <p>可選擇2個景點</p>
                            <p>保障30張以上照片</p>
                            <p>新娘一組妝髮</p>
                            <p>新郎一組妝髮</p>
                            <p>自備2套服裝</p>
                            <p>精修10張</p>
                          </div>
                        </div>
                        <p className="text-base font-semibold text-[#1f2937] font-display">
                          NT$58,900
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-8 grid gap-6 text-sm md:grid-cols-2">
                    <div>
                      <p className="font-semibold text-[#1f2937]">▸方案內含</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>・調光調色後原檔JPG全給</p>
                        <p>・環保雲端交件</p>
                      </div>
                    </div>
                    <div>
                      <p className="font-semibold text-[#1f2937]">▸加購內容</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>・精修NT$1,500/張</p>
                        <p>・精緻皮革相簿NT$5,500/本</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-12 bg-white px-6 py-10 md:px-10">
              <div className="text-left">
                <h3 className="font-semibold text-[#1f2937] font-display">
                  <span className="block text-sm md:text-base">客製化</span>
                  <span className="block text-xl md:text-2xl">旅拍婚紗專案</span>
                </h3>
              </div>
              <div className="mt-6 grid gap-10 md:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] md:items-start">
                <div>
                  <button
                    type="button"
                    onClick={() =>
                      setWeddingSlideIndex((weddingSlideIndex + 1) % weddingPhotos.length)
                    }
                    className="relative w-full text-left"
                    aria-label="切換旅拍婚紗照片"
                  >
                    <img loading="lazy" decoding="async"
                      src={withBaseUrl(weddingPhotos[0])}
                      alt=""
                      aria-hidden="true"
                      className="w-full h-auto opacity-0 pointer-events-none"
                    />
                    {weddingPhotos.map((src, index) => (
                      <img loading="lazy" decoding="async"
                        key={src}
                        src={withBaseUrl(src)}
                        alt="旅拍婚紗照片"
                        className={`absolute inset-0 w-full h-auto object-contain object-left transition-opacity duration-1000 ${
                          index === weddingSlideIndex ? "opacity-100" : "opacity-0"
                        }`}
                      />
                    ))}
                    <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-2">
                      {weddingPhotos.map((_, index) => (
                        <button
                          key={`wedding-dot-${index}`}
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setWeddingSlideIndex(index);
                          }}
                          className={`h-2.5 w-2.5 rounded-full border border-white/80 ${
                            index === weddingSlideIndex
                              ? "bg-white"
                              : "bg-white/40"
                          }`}
                          aria-label={`切換到第 ${index + 1} 張`}
                        />
                      ))}
                    </div>
                  </button>
                </div>
                <div className="text-[#475569]">
                  <div className="space-y-6">
                    {[
                      {
                        title: "1套4小時",
                        details: [
                          "可選擇1個景點",
                          "保障30張以上照片",
                          "一套禮服(一白)",
                          "新娘一組妝髮",
                          "新郎一組妝髮",
                          "精修10張",
                        ],
                        price: "NT$84,800",
                      },
                      {
                        title: "2套6小時",
                        details: [
                          "可選擇2個景點",
                          "保障50張以上照片",
                          "二套禮服(一白一晚)",
                          "新娘兩組妝髮",
                          "新郎一組妝髮",
                          "精修15張",
                        ],
                        price: "NT$98,800",
                      },
                      {
                        title: "3套8小時",
                        details: [
                          "可選擇2~3個景點",
                          "保障1000張以上照片",
                          "三套禮服(一白一晚一和)",
                          "新娘三組妝髮",
                          "新郎一組妝髮",
                          "精修25張",
                        ],
                        price: "NT$112,800",
                      },
                    ].map((plan) => (
                      <div key={plan.title} className="border-b border-[#d7dde3] pb-6">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div>
                            <h4 className="text-base md:text-lg font-semibold text-[#1f2937] font-display">
                              {plan.title}
                            </h4>
                            <div className="mt-2 space-y-1 text-sm">
                              {plan.details.map((item) => (
                                <p key={item}>{item}</p>
                              ))}
                            </div>
                          </div>
                          <p className="text-base font-semibold text-[#1f2937] font-display">
                            {plan.price}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-8 grid gap-6 text-sm md:grid-cols-2">
                    <div>
                      <p className="font-semibold text-[#1f2937]">方案內含</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>・調光調色後原檔JPG全給</p>
                        <p>・環保雲端交件</p>
                        <p>・精緻皮革相簿</p>
                      </div>
                    </div>
                    <div>
                      <p className="font-semibold text-[#1f2937]">加購內容</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>・精修NT$1,500/張</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section className="mt-12 md:mt-16">
          <div
            ref={whyRef}
            className="px-6 py-10 md:px-12 md:py-14 flex justify-center"
          >
            <div className="max-w-xl mx-auto text-left">
              <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                為什麼選擇 SnowLand
              </h2>
              <div className="mt-6 text-base md:text-lg text-[#475569] space-y-2">
                {[
                  "✓ 旅拍節奏與行程整合",
                  "✓ 專業引導・自然互動",
                  "✓ 毛片全給不加價",
                  "✓ 每小時至少 30 張以上",
                  "✓ 7 日內雲端交件",
                ].map((item, index) => (
                  <p
                    key={item}
                    className={`transition-all duration-700 ease-out ${
                      whyVisible ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
                    }`}
                    style={{ transitionDelay: `${index * 120}ms` }}
                  >
                    {item}
                  </p>
                ))}
              </div>
              <div className="mt-10">
                <div className="grid overflow-hidden md:grid-cols-3">
                  <a
                    href="#booking-flow"
                    className="flex items-center justify-center gap-3 px-6 py-4 text-sm font-semibold text-[#1f2937] transition-colors hover:bg-[#f8fafc]"
                  >
                    <svg
                      className="h-5 w-5"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <rect x="3" y="4" width="18" height="18" rx="2" />
                      <line x1="8" y1="2.5" x2="8" y2="6" />
                      <line x1="16" y1="2.5" x2="16" y2="6" />
                      <line x1="3" y1="10" x2="21" y2="10" />
                    </svg>
                    預約流程
                  </a>
                  <a
                    href="#faq"
                    className="flex items-center justify-center gap-3 border-t border-[#d7dde3] px-6 py-4 text-sm font-semibold text-[#1f2937] transition-colors hover:bg-[#f8fafc] md:border-t-0 md:border-l"
                  >
                    <svg
                      className="h-5 w-5"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <circle cx="12" cy="12" r="9" />
                      <path d="M9.5 9.5a2.5 2.5 0 1 1 4.2 1.8c-.9.6-1.2 1-1.2 2" />
                      <circle cx="12" cy="17" r="0.8" />
                    </svg>
                    精選Q&amp;A
                  </a>
                  <a
                    href="#related-content"
                    className="flex items-center justify-center gap-3 border-t border-[#d7dde3] px-6 py-4 text-sm font-semibold text-[#1f2937] transition-colors hover:bg-[#f8fafc] md:border-t-0 md:border-l"
                  >
                    <svg
                      className="h-5 w-5"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M10 13a5 5 0 0 1 0-7l1.4-1.4a5 5 0 0 1 7 7L17 12" />
                      <path d="M14 11a5 5 0 0 1 0 7L12.6 20.4a5 5 0 0 1-7-7L7 12" />
                    </svg>
                    相關內容
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section id="booking-flow" className="mt-12 md:mt-16 bg-[#e9eef3] w-screen relative left-1/2 -translate-x-1/2 scroll-mt-28 md:scroll-mt-32">
          <div className="max-w-5xl mx-auto px-6 md:px-12 py-12 md:py-16">
            <div className="text-center">
              <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                預約流程
              </h2>
            </div>
            <div className="mt-12">
              <div className="relative">
                <div className="absolute left-[10%] right-[10%] top-7 hidden md:block h-px bg-[#1f2937]/40" />
                <div className="grid gap-10 md:grid-cols-4">
                  {[
                    {
                      number: "01",
                      title: "預約旅拍攝影",
                      body: "選擇拍攝方案、地點及時間。",
                    },
                    {
                      number: "02",
                      title: "預約確認",
                      body:
                        "收到預約後，我們的客服將會與您聯繫確認。",
                    },
                    {
                      number: "03",
                      title: "線上付款",
                      body: "銀行匯款轉帳支付",
                    },
                    {
                      number: "04",
                      title: "預約成功",
                      body:
                        "與攝影師討論拍攝需求，並享受屬於您的旅行攝影。",
                    },
                  ].map((step) => (
                    <motion.div
                      key={step.number}
                      className="text-center"
                      initial={{ opacity: 0, y: 16 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ amount: 0.4, once: false }}
                      transition={{ duration: 0.4, ease: "easeOut" }}
                    >
                      <div className="relative">
                        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-[#1f2937]/60 bg-[#e9eef3] text-sm font-semibold text-[#1f2937]">
                          {step.number}
                        </div>
                      </div>
                      <h3 className="mt-6 text-base md:text-lg font-semibold text-[#1f2937] font-display">
                        {step.title}
                      </h3>
                      <p className="mt-3 text-sm md:text-base leading-relaxed text-[#475569]">
                        {step.body}
                      </p>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-10 flex justify-center">
              <SiteLink
                to="/photography/how-to-book"
                className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
              >
                查看預約流程細節
              </SiteLink>
            </div>
          </div>
        </section>
        <section id="faq" className="mt-12 md:mt-16 scroll-mt-28 md:scroll-mt-32">
          <div className="max-w-6xl mx-auto px-6 md:px-12 py-12 md:py-16">
            <div className="grid gap-10 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.6fr)]">
              <div>
                <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                  精選常見問題
                </h2>
              </div>
              <div className="space-y-6 text-[#475569]">
                {[
                  {
                    question: "拍攝後多久可以收到照片？",
                    answer: (
                      <p className="text-sm md:text-base leading-relaxed">
                        7 天內透過雲端交件。
                      </p>
                    ),
                  },
                  {
                    question: "服務內容包括影片？",
                    answer: (
                      <p className="text-sm md:text-base leading-relaxed">
                        目前僅提供靜態平面攝影，並不包含動態影片，側拍影片僅作為行銷用途，並不包含在旅拍攝影服務內。當您購買旅拍攝影服務即視為同意我們將拍攝的畫面用於 SnowLand 滑雪學校的推廣，傳遞北海道旅遊的樂趣與喜悅！
                      </p>
                    ),
                  },
                  {
                    question: "拍攝地點在哪裡？",
                    answer: (
                      <p className="text-sm md:text-base leading-relaxed">
                        拍攝地點在北海道星野Tomamu度假村內以及富良野周邊景點，會有數個優美景點提供挑選。
                      </p>
                    ),
                  },
                ].map((item, index) => {
                  const isOpen = openFaqIndex === index;
                  return (
                    <div key={item.question} className="border-b border-[#d7dde3] pb-6">
                      <button
                        type="button"
                        onClick={() => setOpenFaqIndex(isOpen ? -1 : index)}
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
                      {isOpen && <div className="mt-3">{item.answer}</div>}
                    </div>
                  );
                })}
                <div className="pt-4">
                  <SiteLink
                    to="/photography/how-to-book"
                    className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
                  >
                    查看更多常見問題
                  </SiteLink>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section id="related-content" className="scroll-mt-28 md:scroll-mt-32">
          <div className="max-w-6xl mx-auto px-6 md:px-12 py-6 md:py-8">
            <div className="grid gap-8 md:flex md:justify-center md:gap-8">
              <SiteLink
                to="/Gallery"
                className="group relative overflow-hidden aspect-[4/3] bg-[#d1d5db] text-[#1f2937] md:w-[calc((100%-4rem)/3)]"
              >
                <img loading="lazy" decoding="async"
                  src={withBaseUrl(
                    "/photography-gallery/gallery-023.jpg"
                  )}
                  alt="攝影作品"
                  className="absolute inset-0 h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-black/10 to-transparent transition-opacity duration-300 group-hover:opacity-90" />
                <div className="absolute bottom-0 left-0 p-6">
                  <h3 className="text-lg md:text-xl font-semibold tracking-wide text-white drop-shadow">
                    攝影作品 →
                  </h3>
                </div>
              </SiteLink>
              <SiteLink
                to="/photography/winter"
                className="group relative overflow-hidden aspect-[4/3] bg-[#d1d5db] text-[#1f2937] md:w-[calc((100%-4rem)/3)]"
              >
                <img loading="lazy" decoding="async"
                  src={withBaseUrl("/photography-gallery/gallery-074.jpg")}
                  alt="查看冬季雪地攝影"
                  className="absolute inset-0 h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-black/10 to-transparent transition-opacity duration-300 group-hover:opacity-90" />
                <div className="absolute bottom-0 left-0 p-6">
                  <h3 className="text-lg md:text-xl font-semibold tracking-wide text-white drop-shadow">
                    查看冬季雪地攝影 →
                  </h3>
                </div>
              </SiteLink>
            </div>
          </div>
        </section>
      </main>
      <div className="max-w-6xl mx-auto px-6 md:px-12 pb-12 -mt-6 text-xs md:text-sm text-[#94a3b8] leading-relaxed">
        <p className="font-semibold text-[#64748b]">※授權聲明：</p>
        <p>
          購買攝影服務即視為同意我們將拍攝的畫面用於SnowLand滑雪學校的推廣，傳遞北海道旅遊的樂趣與喜悅！
        </p>
      </div>
      <SiteFooter />
    </div>
  );
}

export default SummerPhotographyPage;
