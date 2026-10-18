import React, { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import PhotographyContentGate from '../../components/site/PhotographyContentGate';
import SiteHeader from '../../components/site/SiteHeader';

function SummerPhotographyLayout({ content }) {
  const c = (key) => content.values[key] ?? '';
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
    c("summer_001"),
    c("summer_002"),
    c("summer_003"),
  ];
  const customTravelPhotos = [
    c("summer_004"),
    c("summer_005"),
    c("summer_006"),
  ];
  const lightWeddingPhotos = [
    c("summer_007"),
    c("summer_008"),
    c("summer_009"),
    c("summer_010"),
  ];
  const weddingPhotos = [
    c("summer_011"),
    c("summer_012"),
    c("summer_013"),
    c("summer_014"),
  ];
  const baseUrl = import.meta.env.BASE_URL ?? "/";
  const withBaseUrl = (path) =>
    /^https?:\/\//i.test(path) ? path : `${baseUrl}${path.startsWith("/") ? path.slice(1) : path}`;
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
            {c("summer_015")}</p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
            {c("summer_016")}</h1>
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
                    alt={c("summer_017")}
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
              {c("summer_018")}</h2>
            <p className="mt-4 max-w-xl mx-auto text-base md:text-lg leading-relaxed text-[#475569]">
              <span className="block">{c("summer_019")}</span>
              <span className="block">
                {c("summer_020")}</span>
            </p>
            <div className="mt-8 flex justify-center">
              <SiteLink to="/booking?service=photo"
                className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
              >
                {c("summer_021")}</SiteLink>
            </div>
          </div>
        </section>
        <section
          ref={stageSectionRef}
          className="mt-12 md:mt-16 w-screen relative left-1/2 -translate-x-1/2"
        >
          <div className="relative aspect-[3/4] w-full overflow-hidden md:aspect-auto md:h-screen">
            <motion.img
              src={withBaseUrl(c("summer_022"))}
              alt={c("summer_023")}
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
                  {c("summer_024")}</div>
                <p className="text-base md:text-lg leading-relaxed">
                  {c("summer_025")}</p>
                <p className="text-base md:text-lg leading-relaxed">
                  {c("summer_026")}</p>
              </motion.div>
            </div>
          </div>
        </section>
        <section ref={tomamuSectionRef} className="w-screen relative left-1/2 -translate-x-1/2">
          <div className="relative aspect-[3/4] w-full overflow-hidden md:aspect-auto md:h-screen">
            <motion.img
              src={withBaseUrl(c("summer_027"))}
              alt={c("summer_028")}
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
                  {c("summer_029")}</div>
                <p className="text-base md:text-lg leading-relaxed">
                  {c("summer_030")}</p>
              </motion.div>
            </div>
          </div>
        </section>
        <section className="bg-[#e9eef3] w-screen relative left-1/2 -translate-x-1/2">
          <div className="max-w-6xl mx-auto px-6 md:px-10 py-16 md:py-24">
            <div className="text-center">
              <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                {c("summer_031")}</h2>
              <p className="mt-3 text-sm md:text-base text-[#64748b]">
                {c("summer_032")}</p>
            </div>
            <div className="mt-12 bg-white px-6 py-10 md:px-10">
              <div className="text-left">
                <h3 className="font-semibold text-[#1f2937] font-display">
                  <span className="block text-sm md:text-base">{c("summer_033")}</span>
                  <span className="block text-xl md:text-2xl">{c("summer_034")}</span>
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
                        alt={c("summer_035")}
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
                        title: c("summer_036"),
                        details: [c("summer_037"), c("summer_038")],
                        price: c("summer_136"),
                      },
                      {
                        title: c("summer_039"),
                        details: [c("summer_040"), c("summer_041")],
                        price: c("summer_137"),
                      },
                      {
                        title: c("summer_042"),
                        details: [c("summer_043"), c("summer_044")],
                        price: c("summer_138"),
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
                      <p className="font-semibold text-[#1f2937]">{c("summer_045")}</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>{c("summer_046")}</p>
                        <p>{c("summer_047")}</p>
                      </div>
                    </div>
                    <div>
                      <p className="font-semibold text-[#1f2937]">{c("summer_048")}</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>{c("summer_049")}</p>
                        <p>{c("summer_050")}</p>
                        <p>{c("summer_051")}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-12 bg-white px-6 py-10 md:px-10">
              <div className="text-left">
                <h3 className="font-semibold text-[#1f2937] font-display">
                  <span className="block text-sm md:text-base">{c("summer_052")}</span>
                  <span className="block text-xl md:text-2xl">{c("summer_053")}</span>
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
                      alt={c("summer_054")}
                      aria-hidden="true"
                      className="w-full h-auto opacity-0 pointer-events-none"
                    />
                    {lightWeddingPhotos.map((src, index) => (
                      <img loading="lazy" decoding="async"
                        key={src}
                        src={withBaseUrl(src)}
                        alt={c("summer_055")}
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
                            {c("summer_056")}</h4>
                          <div className="mt-2 space-y-1 text-sm">
                            <p>{c("summer_057")}</p>
                            <p>{c("summer_058")}</p>
                            <p>{c("summer_059")}</p>
                            <p>{c("summer_060")}</p>
                            <p>{c("summer_061")}</p>
                            <p>{c("summer_062")}</p>
                          </div>
                        </div>
                        <p className="text-base font-semibold text-[#1f2937] font-display">
                          {c("summer_063")}</p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-8 grid gap-6 text-sm md:grid-cols-2">
                    <div>
                      <p className="font-semibold text-[#1f2937]">{c("summer_064")}</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>{c("summer_065")}</p>
                        <p>{c("summer_066")}</p>
                      </div>
                    </div>
                    <div>
                      <p className="font-semibold text-[#1f2937]">{c("summer_067")}</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>{c("summer_068")}</p>
                        <p>{c("summer_069")}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-12 bg-white px-6 py-10 md:px-10">
              <div className="text-left">
                <h3 className="font-semibold text-[#1f2937] font-display">
                  <span className="block text-sm md:text-base">{c("summer_070")}</span>
                  <span className="block text-xl md:text-2xl">{c("summer_071")}</span>
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
                      alt={c("summer_072")}
                      aria-hidden="true"
                      className="w-full h-auto opacity-0 pointer-events-none"
                    />
                    {weddingPhotos.map((src, index) => (
                      <img loading="lazy" decoding="async"
                        key={src}
                        src={withBaseUrl(src)}
                        alt={c("summer_073")}
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
                        title: c("summer_074"),
                        details: [
                          c("summer_075"),
                          c("summer_076"),
                          c("summer_077"),
                          c("summer_078"),
                          c("summer_079"),
                          c("summer_080"),
                        ],
                        price: c("summer_139"),
                      },
                      {
                        title: c("summer_081"),
                        details: [
                          c("summer_082"),
                          c("summer_083"),
                          c("summer_084"),
                          c("summer_085"),
                          c("summer_086"),
                          c("summer_087"),
                        ],
                        price: c("summer_140"),
                      },
                      {
                        title: c("summer_088"),
                        details: [
                          c("summer_089"),
                          c("summer_090"),
                          c("summer_091"),
                          c("summer_092"),
                          c("summer_093"),
                          c("summer_094"),
                        ],
                        price: c("summer_141"),
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
                      <p className="font-semibold text-[#1f2937]">{c("summer_095")}</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>{c("summer_096")}</p>
                        <p>{c("summer_097")}</p>
                        <p>{c("summer_098")}</p>
                      </div>
                    </div>
                    <div>
                      <p className="font-semibold text-[#1f2937]">{c("summer_099")}</p>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>{c("summer_100")}</p>
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
                {c("summer_101")}</h2>
              <div className="mt-6 text-base md:text-lg text-[#475569] space-y-2">
                {[
                  c("summer_102"),
                  c("summer_103"),
                  c("summer_104"),
                  c("summer_105"),
                  c("summer_106"),
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
                  <SiteLink to="/booking?service=photo"
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
                    {c("summer_107")}</SiteLink>
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
                    {c("summer_108")}</a>
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
                    {c("summer_109")}</a>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section id="booking-flow" className="mt-12 md:mt-16 bg-[#e9eef3] w-screen relative left-1/2 -translate-x-1/2 scroll-mt-28 md:scroll-mt-32">
          <div className="max-w-5xl mx-auto px-6 md:px-12 py-12 md:py-16">
            <div className="text-center">
              <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                {c("summer_110")}</h2>
            </div>
            <div className="mt-12">
              <div className="relative">
                <div className="absolute left-[10%] right-[10%] top-7 hidden md:block h-px bg-[#1f2937]/40" />
                <div className="grid gap-10 md:grid-cols-4">
                  {[
                    {
                      number: "01",
                      title: c("summer_111"),
                      body: c("summer_112"),
                    },
                    {
                      number: "02",
                      title: c("summer_113"),
                      body:
                        c("summer_114"),
                    },
                    {
                      number: "03",
                      title: c("summer_115"),
                      body: c("summer_116"),
                    },
                    {
                      number: "04",
                      title: c("summer_117"),
                      body:
                        c("summer_118"),
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
                to="/booking?service=photo"
                className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
              >
                {c("summer_119")}</SiteLink>
            </div>
          </div>
        </section>
        <section id="faq" className="mt-12 md:mt-16 scroll-mt-28 md:scroll-mt-32">
          <div className="max-w-6xl mx-auto px-6 md:px-12 py-12 md:py-16">
            <div className="grid gap-10 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.6fr)]">
              <div>
                <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                  {c("summer_120")}</h2>
              </div>
              <div className="space-y-6 text-[#475569]">
                {[
                  {
                    question: c("summer_121"),
                    answer: (
                      <p className="text-sm md:text-base leading-relaxed">
                        {c("summer_122")}</p>
                    ),
                  },
                  {
                    question: c("summer_123"),
                    answer: (
                      <p className="text-sm md:text-base leading-relaxed">
                        {c("summer_124")}</p>
                    ),
                  },
                  {
                    question: c("summer_125"),
                    answer: (
                      <p className="text-sm md:text-base leading-relaxed">
                        {c("summer_126")}</p>
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
                    to="/faq"
                    className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
                  >
                    {c("summer_127")}</SiteLink>
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
                    c("summer_128")
                  )}
                  alt={c("summer_129")}
                  className="absolute inset-0 h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-black/10 to-transparent transition-opacity duration-300 group-hover:opacity-90" />
                <div className="absolute bottom-0 left-0 p-6">
                  <h3 className="text-lg md:text-xl font-semibold tracking-wide text-white drop-shadow">
                    {c("summer_130")}</h3>
                </div>
              </SiteLink>
              <SiteLink
                to="/photography/winter"
                className="group relative overflow-hidden aspect-[4/3] bg-[#d1d5db] text-[#1f2937] md:w-[calc((100%-4rem)/3)]"
              >
                <img loading="lazy" decoding="async"
                  src={withBaseUrl(c("summer_131"))}
                  alt={c("summer_132")}
                  className="absolute inset-0 h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-black/10 to-transparent transition-opacity duration-300 group-hover:opacity-90" />
                <div className="absolute bottom-0 left-0 p-6">
                  <h3 className="text-lg md:text-xl font-semibold tracking-wide text-white drop-shadow">
                    {c("summer_133")}</h3>
                </div>
              </SiteLink>
            </div>
          </div>
        </section>
      </main>
      <div className="max-w-6xl mx-auto px-6 md:px-12 pb-12 -mt-6 text-xs md:text-sm text-[#94a3b8] leading-relaxed">
        <p className="font-semibold text-[#64748b]">{c("summer_134")}</p>
        <p>
          {c("summer_135")}</p>
      </div>
      <SiteFooter />
    </div>
  );
}

function SummerPhotographyPage() {
  return <PhotographyContentGate season="summer">{content => <SummerPhotographyLayout content={content} />}</PhotographyContentGate>;
}

export default SummerPhotographyPage;
