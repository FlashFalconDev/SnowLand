import React, { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import PhotographyContentGate from '../../components/site/PhotographyContentGate';
import SiteHeader from '../../components/site/SiteHeader';
import aboutSnowland from '../../assets/site/About snowland.jpg';
import { useSiteLocale } from '../../contexts/SiteLocale';

function WinterPhotographyLayout({ content }) {
  const { t } = useSiteLocale();
  const c = (key) => content.values[key] ?? '';
  const scrollerRef = useRef(null);
  const itemRefs = useRef([]);
  const introRef = useRef(null);
  const stageSectionRef = useRef(null);
  const stageTextRef = useRef(null);
  const whyRef = useRef(null);
  const addOnUnderlineRef = useRef(null);
  const discountUnderlineRef = useRef(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [introVisible, setIntroVisible] = useState(false);
  const [stageTextVisible, setStageTextVisible] = useState(false);
  const [whyVisible, setWhyVisible] = useState(false);
  const [addOnUnderlineVisible, setAddOnUnderlineVisible] = useState(false);
  const [discountUnderlineVisible, setDiscountUnderlineVisible] = useState(false);
  const [openFaqIndex, setOpenFaqIndex] = useState(0);
  const hasAutoScrolledRef = useRef(false);
  const prefersReducedMotion = useReducedMotion();
  const photos = [
    c("winter_001"),
    c("winter_002"),
    c("winter_003"),
  ];
  const baseUrl = import.meta.env.BASE_URL ?? "/";
  const withBaseUrl = (path) =>
    /^https?:\/\//i.test(path) ? path : `${baseUrl}${path.startsWith("/") ? path.slice(1) : path}`;
  const totalPhotos = photos.length;
  const { scrollYProgress: stageScrollYProgress } = useScroll({
    target: stageSectionRef,
    offset: ["start end", "end start"],
  });
  const stageImageY = useTransform(stageScrollYProgress, [0, 1], ["0%", "16%"]);
  const stageCardY = useTransform(stageScrollYProgress, [0, 1], ["0%", "10%"]);

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
    const target = addOnUnderlineRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setAddOnUnderlineVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.6 }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const target = discountUnderlineRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setDiscountUnderlineVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.6 }
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

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceCompact forceDarkText forceLogoColor />
      <main className="max-w-5xl mx-auto px-6 pt-32 pb-24 flex-1 w-full">
        <div className="text-center">
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            {c("winter_004")}</p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
            {c("winter_005")}</h1>
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
                  className="relative min-w-[85%] aspect-[3/2] md:aspect-auto md:min-w-[70%] md:h-[70vh] snap-center overflow-hidden bg-[#f8fafc]"
                >
                  <img loading="lazy" decoding="async"
                    src={withBaseUrl(src)}
                    alt={c("winter_006")}
                    className="h-full w-full object-cover"
                  />
                </figure>
              ))}
            </div>
            <button
              type="button"
              onClick={() => scrollToIndex(activeIndex - 1)}
              className="absolute left-4 top-1/2 -translate-y-1/2 h-11 w-11 rounded-full bg-white/80 text-[#1f2937] shadow-md hover:bg-white transition-colors"
              aria-label={t('上一張照片')}
            >
              ←
            </button>
            <button
              type="button"
              onClick={() => scrollToIndex(activeIndex + 1)}
              className="absolute right-4 top-1/2 -translate-y-1/2 h-11 w-11 rounded-full bg-white/80 text-[#1f2937] shadow-md hover:bg-white transition-colors"
              aria-label={t('下一張照片')}
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
              {c("winter_007")}</h2>
            <p className="mt-4 max-w-xl mx-auto text-base md:text-lg leading-relaxed text-[#475569]">
              <span className="block">
                {c("winter_008")}</span>
              <span className="block">
                {c("winter_009")}</span>
            </p>
            <div className="mt-8 flex justify-center">
              <SiteLink to="/booking?service=photo"
                className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
              >
                {t(c("winter_010"))}</SiteLink>
            </div>
          </div>
        </section>
        <section
          ref={stageSectionRef}
          className="mt-12 md:mt-16 w-screen relative left-1/2 -translate-x-1/2"
        >
          <div className="relative aspect-[3/4] w-full overflow-hidden md:aspect-auto md:h-screen">
            <motion.img
              src={withBaseUrl(
                c("winter_011")
              )}
              alt={c("winter_012")}
              className="absolute inset-0 h-full w-full object-cover scale-[1.06] md:scale-[1.1] object-center"
              style={
                prefersReducedMotion ? undefined : { y: stageImageY }
              }
            />
            <div className="absolute inset-0 bg-black/5" />
            <div className="absolute inset-x-0 top-[12%] px-6 md:top-[18%] md:px-16">
              <motion.div
                ref={stageTextRef}
                className="relative z-10 mx-auto w-full max-w-3xl space-y-4 bg-white/50 px-8 py-10 text-center text-[#1f2937] md:px-12 md:py-12"
                style={
                  prefersReducedMotion ? undefined : { y: stageCardY }
                }
              >
                <p className="text-base md:text-lg leading-relaxed">
                  {c("winter_013")}</p>
              </motion.div>
            </div>
          </div>
        </section>
        <section className="mt-12 md:mt-16 w-screen relative left-1/2 -translate-x-1/2">
          <div className="grid gap-8 md:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] md:items-center">
            <div className="aspect-[3/4] w-full overflow-hidden bg-[#e2e8f0]">
              <img loading="lazy" decoding="async"
                src={withBaseUrl(
                  c("winter_014")
                )}
                alt={c("winter_015")}
                className="h-full w-full object-cover"
              />
            </div>
            <div className="space-y-6 px-6 text-[#475569] md:pr-12">
              <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                {c("winter_016")}</h2>
              <p className="text-base md:text-lg leading-relaxed">
                {c("winter_017")}</p>
              <div className="grid gap-2 text-base md:text-lg text-[#1f2937]">
                <span>{c("winter_018")}</span>
                <span>{c("winter_019")}</span>
                <span>{c("winter_020")}</span>
                <span>{c("winter_021")}</span>
                <span>{c("winter_022")}</span>
              </div>
            </div>
          </div>
        </section>
        <section className="mt-16 md:mt-20 bg-[#e9eef3] w-screen relative left-1/2 -translate-x-1/2">
          <div className="max-w-6xl mx-auto px-6 md:px-10 py-16 md:py-24">
            <div className="text-center">
            <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
              {c("winter_023")}</h2>
            <p className="mt-3 text-sm md:text-base text-[#64748b]">
              {c("winter_024")}</p>
          </div>
          <div className="mt-12 grid gap-10 md:grid-cols-3">
            <div className="overflow-hidden bg-white shadow-[0_12px_30px_rgba(15,23,42,0.08)]">
              <div className="group aspect-square w-full overflow-hidden bg-[#e2e8f0]">
                <img loading="lazy" decoding="async"
                  src={withBaseUrl(
                    c("winter_025")
                  )}
                  alt={c("winter_026")}
                  className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
              </div>
              <div className="flex gap-5 px-6 py-8 text-left">
                <div className="flex flex-col items-center gap-4">
                  <span className="h-10 w-10 opacity-0" aria-hidden="true" />
                  <span className="w-px flex-1 bg-[#e2e8f0]" aria-hidden="true" />
                </div>
                <div className="space-y-3">
                  <h3 className="text-lg font-semibold text-[#1f2937] font-display">
                    {c("winter_027")}</h3>
                  <p className="text-lg font-semibold text-[#1f2937] font-display">
                    {c("winter_028")}</p>
                  <div className="space-y-2 text-sm text-[#475569] max-w-[16rem]">
                    <p>{c("winter_029")}</p>
                    <p>{c("winter_030")}</p>
                    <p>{c("winter_031")}</p>
                  </div>
                  <SiteLink
                    to="/booking?service=photo"
                    className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
                  >
                    {t(c("winter_032"))}</SiteLink>
                </div>
              </div>
            </div>
            <div className="overflow-hidden bg-white shadow-[0_12px_30px_rgba(15,23,42,0.08)]">
              <div className="group aspect-square w-full overflow-hidden bg-[#e2e8f0]">
                <img loading="lazy" decoding="async"
                  src={withBaseUrl(
                    c("winter_033")
                  )}
                  alt={c("winter_034")}
                  className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
              </div>
              <div className="relative flex gap-5 px-6 py-8 text-left">
                <div className="absolute right-4 top-4 h-10 w-10 bg-[#f59e0b] text-[10px] font-semibold text-white flex items-center justify-center text-center leading-tight px-1">
                  {c("winter_035")}</div>
                <div className="flex flex-col items-center gap-4">
                  <span className="h-10 w-10 opacity-0" aria-hidden="true" />
                  <span className="w-px flex-1 bg-[#e2e8f0]" aria-hidden="true" />
                </div>
                <div className="space-y-3">
                  <h3 className="text-lg font-semibold text-[#1f2937] font-display">
                    {c("winter_036")}</h3>
                  <p className="text-lg font-semibold text-[#1f2937] font-display">
                    {c("winter_037")}</p>
                  <div className="space-y-2 text-sm text-[#475569] max-w-[16rem]">
                    <p>{c("winter_038")}</p>
                    <p>{c("winter_039")}</p>
                    <p>{c("winter_040")}</p>
                  </div>
                  <SiteLink
                    to="/booking?service=photo"
                    className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
                  >
                    {t(c("winter_041"))}</SiteLink>
                </div>
              </div>
            </div>
            <div className="overflow-hidden bg-white shadow-[0_12px_30px_rgba(15,23,42,0.08)]">
              <div className="group aspect-square w-full overflow-hidden bg-[#e2e8f0]">
                <img loading="lazy" decoding="async"
                  src={withBaseUrl(c("winter_042"))}
                  alt={c("winter_043")}
                  className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
              </div>
              <div className="flex gap-5 px-6 py-8 text-left">
                <div className="flex flex-col items-center gap-4">
                  <span className="h-10 w-10 opacity-0" aria-hidden="true" />
                  <span className="w-px flex-1 bg-[#e2e8f0]" aria-hidden="true" />
                </div>
                <div className="space-y-3">
                  <h3 className="text-lg font-semibold text-[#1f2937] font-display">
                    {c("winter_044")}</h3>
                  <p className="text-lg font-semibold text-[#1f2937] font-display">
                    {c("winter_045")}</p>
                  <div className="space-y-2 text-sm text-[#475569] max-w-[16rem]">
                    <p>{c("winter_046")}</p>
                    <p>{c("winter_047")}</p>
                    <p>{c("winter_048")}</p>
                  </div>
                  <SiteLink
                    to="/booking?service=photo"
                    className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
                  >
                    {t(c("winter_049"))}</SiteLink>
                </div>
              </div>
            </div>
          </div>
          <div className="mt-12 text-center text-sm md:text-base text-[#475569]">
            <p className="font-semibold text-[#1f2937]">{c("winter_050")}</p>
            <p>
              <span
                ref={addOnUnderlineRef}
                className="relative inline-flex items-center"
              >
                {c("winter_051")}<span
                  className={`absolute -bottom-1 left-0 h-0.5 bg-[#f59e0b] transition-all duration-500 ${
                    addOnUnderlineVisible ? "w-full" : "w-0"
                  }`}
                />
              </span>
            </p>
          </div>
          </div>
        </section>
        <section className="bg-[#e9eef3] w-screen relative left-1/2 -translate-x-1/2 pb-16 md:pb-0 md:min-h-screen md:flex md:items-center">
          <div className="grid w-full gap-8 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] md:items-center">
            <div className="order-2 space-y-4 px-6 text-center text-[#475569] md:order-1 md:text-left md:pr-6 md:pl-[calc(2rem+10rem)] lg:pl-[calc(2rem+12rem)]">
              <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                {c("winter_052")}</h2>
              <p className="text-base md:text-lg leading-relaxed">
                {c("winter_053")}</p>
              <p className="text-base md:text-lg leading-relaxed">
                <span
                  ref={discountUnderlineRef}
                  className="relative inline-flex items-center"
                >
                  {c("winter_054")}<span
                    className={`absolute -bottom-1 left-0 h-0.5 bg-[#f59e0b] transition-all duration-500 ${
                      discountUnderlineVisible ? "w-full" : "w-0"
                    }`}
                  />
                </span>
              </p>
            </div>
            <div className="order-1 aspect-[4/3] w-full overflow-hidden bg-[#e2e8f0] md:order-2 md:aspect-auto md:h-screen">
              <img loading="lazy" decoding="async"
                src={withBaseUrl(
                  c("winter_055")
                )}
                alt={c("winter_056")}
                className="h-full w-full object-cover"
              />
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
                {c("winter_057")}</h2>
              <div className="mt-6 text-base md:text-lg text-[#475569] space-y-2">
                {[
                  c("winter_058"),
                  c("winter_059"),
                  c("winter_060"),
                  c("winter_061"),
                  c("winter_062"),
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
                    {t(c("winter_063"))}</SiteLink>
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
                    {c("winter_064")}</a>
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
                    {c("winter_065")}</a>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section id="booking-flow" className="mt-12 md:mt-16 bg-[#e9eef3] w-screen relative left-1/2 -translate-x-1/2 scroll-mt-28 md:scroll-mt-32">
          <div className="max-w-5xl mx-auto px-6 md:px-12 py-12 md:py-16">
            <div className="text-center">
              <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                {c("winter_066")}</h2>
            </div>
            <div className="mt-12">
              <div className="relative">
                <div className="absolute left-[10%] right-[10%] top-7 hidden md:block h-px bg-[#1f2937]/40" />
                <div className="grid gap-10 md:grid-cols-4">
                  {[
                    {
                      number: "01",
                      title: c("winter_067"),
                      body:
                        c("winter_068"),
                    },
                    {
                      number: "02",
                      title: c("winter_069"),
                      body: c("winter_070"),
                    },
                    {
                      number: "03",
                      title: c("winter_071"),
                      body: c("winter_072"),
                    },
                    {
                      number: "04",
                      title: c("winter_073"),
                      body: c("winter_074"),
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
                {t(c("winter_075"))}</SiteLink>
            </div>
          </div>
        </section>
        <section id="faq" className="mt-12 md:mt-16 scroll-mt-28 md:scroll-mt-32">
          <div className="max-w-6xl mx-auto px-6 md:px-12 py-12 md:py-16">
            <div className="grid gap-10 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.6fr)]">
              <div>
                <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                  {c("winter_076")}</h2>
              </div>
              <div className="space-y-6 text-[#475569]">
                {[
                  {
                    question: c("winter_077"),
                    answer: (
                      <p className="text-sm md:text-base leading-relaxed">
                        {c("winter_078")}</p>
                    ),
                  },
                  {
                    question: c("winter_079"),
                    answer: (
                      <p className="text-sm md:text-base leading-relaxed">
                        {c("winter_080")}</p>
                    ),
                  },
                  {
                    question: c("winter_081"),
                    answer: (
                      <div className="space-y-4 text-sm md:text-base leading-relaxed">
                        <p>
                          {c("winter_082")}</p>
                        <div>
                          <p className="font-semibold text-[#1f2937]">{c("winter_083")}</p>
                          <a
                            href={c("winter_084")}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[#1f2937] underline underline-offset-4"
                          >
                            {c("winter_085")}</a>
                        </div>
                        <div>
                          <p className="font-semibold text-[#1f2937]">{c("winter_086")}</p>
                          <a
                            href={c("winter_087")}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[#1f2937] underline underline-offset-4"
                          >
                            {c("winter_088")}</a>
                        </div>
                      </div>
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
                    {t(c("winter_089"))}</SiteLink>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section id="related-content" className="scroll-mt-28 md:scroll-mt-32">
          <div className="max-w-6xl mx-auto px-6 md:px-12 py-6 md:py-8">
            <div className="grid gap-8 md:grid-cols-3">
              <SiteLink
                to="/Gallery"
                className="group relative overflow-hidden aspect-[4/3] bg-[#1d4ed8] text-white"
              >
                <img loading="lazy" decoding="async"
                  src={withBaseUrl(
                    c("winter_090")
                  )}
                  alt={c("winter_091")}
                  className="absolute inset-0 h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent transition-opacity duration-300 group-hover:opacity-90" />
                <div className="absolute bottom-0 left-0 p-6">
                  <h3 className="text-lg md:text-xl font-semibold tracking-wide drop-shadow">
                    {c("winter_092")}</h3>
                </div>
              </SiteLink>
              <SiteLink
                to="/booking?service=ski"
                className="group relative overflow-hidden aspect-[4/3] bg-[#1d4ed8] text-white"
              >
                <img loading="lazy" decoding="async"
                  src={aboutSnowland}
                  alt={c("winter_093")}
                  className="absolute inset-0 h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent transition-opacity duration-300 group-hover:opacity-90" />
                <div className="absolute bottom-0 left-0 p-6">
                  <h3 className="text-lg md:text-xl font-semibold tracking-wide drop-shadow">
                    {c("winter_094")}</h3>
                </div>
              </SiteLink>
              <SiteLink
                to="/photography/summer"
                className="group relative overflow-hidden aspect-[4/3] bg-[#1d4ed8] text-white"
              >
                <img loading="lazy" decoding="async"
                  src={withBaseUrl(c("winter_095"))}
                  alt={c("winter_096")}
                  className="absolute inset-0 h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent transition-opacity duration-300 group-hover:opacity-90" />
                <div className="absolute bottom-0 left-0 p-6">
                  <h3 className="text-lg md:text-xl font-semibold tracking-wide drop-shadow">
                    {c("winter_097")}</h3>
                </div>
              </SiteLink>
            </div>
          </div>
        </section>
      </main>
      <div className="max-w-6xl mx-auto px-6 md:px-12 pb-12 -mt-6 text-xs md:text-sm text-[#94a3b8] leading-relaxed">
        <p className="font-semibold text-[#64748b]">{c("winter_098")}</p>
        <p>
          {c("winter_099")}</p>
      </div>
      <SiteFooter />
    </div>
  );
}

function WinterPhotographyPage() {
  return <PhotographyContentGate season="winter">{content => <WinterPhotographyLayout content={content} />}</PhotographyContentGate>;
}

export default WinterPhotographyPage;
