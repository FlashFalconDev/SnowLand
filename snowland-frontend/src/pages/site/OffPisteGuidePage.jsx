import React, { useEffect, useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import resortNavigation from '../../data/site/resortNavigation';

const heroImage = encodeURI("/Course/off-piste-guide/off-piste-guide-007.jpg");

const galleryPhotos = [
  "/Course/off-piste-guide/off-piste-guide-002.jpg",
  "/Course/off-piste-guide/off-piste-guide-003.jpg",
  "/Course/off-piste-guide/off-piste-guide-005.jpg",
];

const safetyHighlights = [
  {
    title: "雪況說明與風險評估",
    description: "每日出發前說明地形、積雪狀況與可能風險。",
  },
  {
    title: "雪崩裝備使用教學",
    description: "提供 Beacon、Probe、Shovel 租借與現場教學。",
  },
  {
    title: "客製化滑行安排",
    description: "依技術程度、體力與當日雪況調整行程與路線。",
  },
];

const expertiseCards = [
  { title: "雪崩知識", description: "具備 Avalanche Safety 認知與現場應變能力。" },
  { title: "山岳經驗", description: "熟悉道北雪況、林間滑行與火山地形。" },
  { title: "急救證照", description: "具備山區活動基本急救知識與事故處理能力。" },
  { title: "即時調整", description: "依風雪、能見度與地形變化即時調整安排。" },
];

const locations = [
  {
    title: "星野 TOMAMU",
    description: "適合初入野雪世界的玩家，地形友善，雪質穩定。我們熟悉園區邊界外的秘境地形，可透過纜車搭乘後滑行至未經壓雪的樹林區，初嘗「越界粉雪」的樂趣。",
    image: "/Course/off-piste-guide/off-piste-guide-Tomamu.jpeg",
    imagePosition: "center 70%",
  },
  {
    title: "富良野山岳",
    description: "在富良野，不只有雪場，更有值得深入探訪的高山粉雪路線。這裡地形變化豐富，雪質乾爽，長距離林間滑行與登頂滑雪挑戰兼備。",
    image: "/Course/off-piste-guide/off-piste-guide-Furano.jpeg",
  },
  {
    title: "旭岳",
    description: "以高海拔、極細雪質聞名，旭岳適合想要挑戰滑雪極限者。需搭乘纜車後進行短距離滑登，滑行路線包含火山碗狀地形、開闊坡面與煙霧氤氳的地熱區。",
    image: "/Course/off-piste-guide/off-piste-guide-ASAHIDAKE.jpg",
  },
  {
    title: "十勝岳連峰",
    description: "原始、壯闊、具野性魅力。從深山登頂滑下的背山滑行（Ski Touring），這裡是許多資深滑雪玩家心中的夢幻之地。行程多為全日或多日形式，推薦搭配雪鞋、雪板與專業嚮導同行。",
    image: "/Course/off-piste-guide/off-piste-guide-Mount Tokachi.jpg",
  },
];

const criteria = [
  {
    title: "滑行能力",
    description: "能穩定滑行紅線以上雪道，具備基本粉雪環境控制能力。",
    colorClass: "text-[#2b5f8f]",
    icon: {
      type: "image",
      src: "/Course/skiing.png",
      alt: "Skiing",
    },
  },
  {
    title: "體能狀態",
    description: "需具備基本體能，部分地點需短距離滑登或較長時間滑行。",
    colorClass: "text-black",
    icon: {
      viewBox: "0 0 24 24",
      path: "M3 12h4l2-4 4 8 2-4h4",
    },
  },
  {
    title: "安全認知",
    description: "願意遵守嚮導指示與野雪安全規範，是所有行程的前提。",
    colorClass: "text-black",
    icon: {
      viewBox: "0 0 24 24",
      path: "M9 12l2 2 4-4M12 3l7 4v5c0 5-3.5 9-7 10-3.5-1-7-5-7-10V7l7-4z",
    },
  },
];

const faqItems = [
  {
    question: "初學者可以參加嗎？",
    answer: "野雪行程建議具備中級以上滑雪能力。若不確定程度是否適合，建議先聯絡 SnowLand 評估。",
  },
  {
    question: "是否提供雪崩安全裝備？",
    answer: "可提供雪崩裝備租借，並由嚮導在行程前進行基本使用說明。",
  },
  {
    question: "天氣或雪況不好會怎麼安排？",
    answer: "嚮導會依據天候、能見度、風向與地形條件調整路線，必要時協助改期或更換地點。",
  },
  {
    question: "可以客製化指定地點嗎？",
    answer: "若你已有特定想探索的地形，可先來信說明，我們會依條件與安全性提供建議。",
  },
];

const pricePeriods = [
  {
    title: "優惠時段",
    dates: ["2025/03/04~季末"],
    image: "https://land110602.com/wp-content/uploads/2025/04/D-2_offpiste_D-1.jpg",
  },
  {
    title: "一般時段",
    dates: ["2026/01/15", "~2026/03/03"],
    image: "https://land110602.com/wp-content/uploads/2025/04/D-2_offpiste_W.jpg",
  },
];

const discountItems = [
  {
    title: "早早鳥",
    date: "即日起至2025/6/30",
    full: "全日折扣500/人",
    half: "半天折扣300/人",
  },
  {
    title: "早鳥",
    date: "2025/7/1~2025/9/30",
    full: "全日折扣300/人",
    half: "半天折扣200/人",
  },
];

const courseFeeItems = [
  "包含嚮導",
  "不含纜車費，雪具租賃等費用",
  "贈送課程時段特殊活動意外險",
  "保險若如無法承保無相關退費",
];

const rentalItems = [
  ["發報器 beacon", "熊掌鞋 Snowshoes"],
  ["BC背包", "雪杖 poles"],
  ["雪鞋", "—"],
];

const languageItems = ["中文", "粵語", "英語"];

const requiredGear = [
  {
    title: "BC裝備",
    badge: "可提供租借",
    items: ["雪崩三寶：Beacon發信/收信器、雪鏟、探測棒", "雪杖", "BC用後背包"],
  },
  {
    title: "行走裝備",
    badge: "可提供租借",
    items: ["熊掌鞋 Snowshoes"],
  },
  {
    title: "滑雪板",
    items: ["Powderboard", "Alpine Touring Ski", "Splitboard"],
  },
  {
    title: "防護裝備",
    items: ["頭盔", "護目鏡", "防風保暖的衣物"],
  },
  {
    title: "應急裝備",
    items: ["行動口糧", "備用裝備"],
  },
];

function OffPisteGuidePage() {
  const scrollerRef = useRef(null);
  const itemRefs = useRef([]);
  const introRef = useRef(null);
  const includesRef = useRef(null);
  const heroSectionRef = useRef(null);
  const heroCardRef = useRef(null);
  const [isHeroActive, setIsHeroActive] = useState(false);
  const resortCount = resortNavigation.length;
  const resortIndex = resortNavigation.findIndex((item) => item.slug === "off-piste-guide");
  const activeResortIndex = resortIndex >= 0 ? resortIndex : 0;
  const previousResort = resortCount ? resortNavigation[(activeResortIndex - 1 + resortCount) % resortCount] : null;
  const nextResort = resortCount ? resortNavigation[(activeResortIndex + 1) % resortCount] : null;
  const [openFaqIndex, setOpenFaqIndex] = useState(0);
  const [activeIndex, setActiveIndex] = useState(0);
  const [priceTab, setPriceTab] = useState("regular");
  const [introVisible, setIntroVisible] = useState(false);
  const [includesVisible, setIncludesVisible] = useState(false);
  const totalPhotos = galleryPhotos.length;
  const baseUrl = import.meta.env.BASE_URL ?? "/";
  const withBaseUrl = (path) =>
    `${baseUrl}${path.startsWith("/") ? path.slice(1) : path}`;
  const priceAccent = priceTab === "discount" ? "#F7941D" : "#2b5f8f";
  const priceDividerColor = priceTab === "discount" ? "#f0cfac" : "#dbe2f0";
  const baseFullPrices = [17000, 20000, 23000, 26000];
  const fullPrices =
    priceTab === "discount"
      ? baseFullPrices
      : baseFullPrices.map((price) => price + 4000);
  const priceTableRows = fullPrices.map((price, index) => ({
    label: `${index + 1}人`,
    full: `NT$${price.toLocaleString("en-US")}`,
    half: "—",
  }));
  const pricePeriod = pricePeriods.find((period) =>
    priceTab === "discount" ? period.title === "優惠時段" : period.title === "一般時段"
  );
  const priceDateText = pricePeriod?.dates?.join(" ") ?? "";

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
    const target = includesRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIncludesVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let frameId = null;
    const updateHeroState = () => {
      if (frameId) {
        return;
      }
      frameId = window.requestAnimationFrame(() => {
        frameId = null;
        if (heroSectionRef.current) {
          const heroRect = heroSectionRef.current.getBoundingClientRect();
          setIsHeroActive(heroRect.bottom > 0 && heroRect.top < window.innerHeight);
        }
      });
    };
    updateHeroState();
    window.addEventListener("scroll", updateHeroState, { passive: true });
    window.addEventListener("resize", updateHeroState);
    return () => {
      window.removeEventListener("scroll", updateHeroState);
      window.removeEventListener("resize", updateHeroState);
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#0b1d2a] text-white flex flex-col">
      <SiteHeader forceTransparent />
      <main className="flex-1 w-full">
        <section
          id="top"
          ref={heroSectionRef}
          className="relative overflow-hidden bg-[#0b1d2a] md:min-h-[90vh] md:min-h-[90dvh]"
        >
          <div className="absolute inset-0">
            <div
              className="h-full w-full bg-cover bg-bottom"
              style={{ backgroundImage: `url(${heroImage})` }}
            />
            <div className="absolute inset-0 bg-gradient-to-br from-[#0b1d2a]/35 via-[#0b1d2a]/15 to-[#0b1d2a]/60" />
          </div>
          {previousResort && nextResort && (
            <>
              <SiteLink
                to={previousResort.route}
                className={`group absolute bottom-6 left-6 z-20 flex flex-col items-center gap-2 text-white/80 transition-all duration-300 ${
                  isHeroActive
                    ? "opacity-100 translate-x-0"
                    : "pointer-events-none opacity-0 -translate-x-4"
                }`}
                aria-label={`上一個雪場：${previousResort.nameChinese}`}
              >
                <span className="text-[10px] font-semibold tracking-[0.2em] text-white/80">
                  {previousResort.nameChinese}
                </span>
                <span className="flex h-10 w-10 items-center justify-center transition-all duration-200 group-hover:scale-105">
                  <svg
                    width="28"
                    height="12"
                    viewBox="0 0 28 12"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    className="text-white/90"
                  >
                    <path d="M6 1L1 6L6 11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M1 6H27" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                  </svg>
                </span>
              </SiteLink>
              <SiteLink
                to={nextResort.route}
                className={`group absolute bottom-6 right-6 z-20 flex flex-col items-center gap-2 text-white/80 transition-all duration-300 ${
                  isHeroActive
                    ? "opacity-100 translate-x-0"
                    : "pointer-events-none opacity-0 translate-x-4"
                }`}
                aria-label={`下一個雪場：${nextResort.nameChinese}`}
              >
                <span className="text-[10px] font-semibold tracking-[0.2em] text-white/80">
                  {nextResort.nameChinese}
                </span>
                <span className="flex h-10 w-10 items-center justify-center transition-all duration-200 group-hover:scale-105">
                  <svg
                    width="28"
                    height="12"
                    viewBox="0 0 28 12"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    className="text-white/90"
                  >
                    <path d="M22 1L27 6L22 11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M1 6H27" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                  </svg>
                </span>
              </SiteLink>
            </>
          )}
          <div className="relative max-w-6xl mx-auto px-4 pt-24 pb-28 sm:px-6 sm:pb-20 md:px-6 md:pt-28 md:pb-20">
            <div className="grid gap-10 justify-items-center lg:grid-cols-[1.15fr_0.85fr] lg:grid-rows-[auto_auto] lg:justify-items-stretch lg:items-stretch">
              <div className="order-1 flex w-full max-w-sm flex-col justify-center items-center text-center sm:max-w-md sm:text-left sm:items-start lg:order-none lg:col-start-1 lg:row-start-1 lg:max-w-none">
                <p className="text-xs font-semibold tracking-[0.35em] uppercase text-white/70 font-display drop-shadow-sm">
                  OFF-PISTE GUIDE
                </p>
                <h1 className="mt-4 text-3xl md:text-5xl font-semibold tracking-wide font-display leading-tight text-white drop-shadow-md">
                  野雪嚮導
                </h1>
                <p className="mt-4 text-sm md:mt-6 md:text-lg text-white/85 max-w-sm sm:max-w-md md:max-w-xl leading-relaxed drop-shadow-sm">
                  你已經征服雪道，現在是時候探索真正的粉雪天堂。
                </p>
              </div>

              <div
                className="order-2 relative w-full max-w-sm min-h-[320px] sm:max-w-md sm:min-h-[360px] lg:min-h-[360px] lg:order-none lg:col-start-2 lg:row-span-2 lg:max-w-none"
                ref={heroCardRef}
              >
                <div className="relative z-10 flex h-full w-full items-center justify-center p-4 sm:p-6 lg:justify-end">
                  <div className="w-full max-w-sm rounded-sm bg-[#1b1f24]/30 backdrop-blur-md px-5 py-5 text-white shadow-[0_20px_45px_rgba(15,23,42,0.35)] sm:max-w-md sm:px-6 sm:py-6">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.3em] text-[#f3a23a]">
                      <span className="h-2 w-2 rounded-full bg-[#f3a23a]" />
                      <span>北海道 | 道北</span>
                    </div>
                    <div className="mt-4 text-lg md:text-xl font-semibold tracking-wide font-display whitespace-nowrap">
                      星野・富良野・旭岳・十勝岳連峰
                    </div>
                    <div className="mt-6 grid grid-cols-2 gap-4 text-xs text-white/80">
                      {[
                        { label: "程度", value: "中高階" },
                        { label: "類型", value: "單板 / 雙板" },
                        {
                          label: "特色",
                          value: "無人探索的自然粉雪地形、山谷、林間、雪場界外",
                          className: "col-span-2",
                        },
                      ].map((item) => (
                        <div
                          key={item.label}
                          className={`rounded-full border border-white/15 bg-white/10 px-4 py-3 ${item.className ?? ""}`}
                        >
                          <p className="uppercase tracking-[0.25em] text-white/60 text-[10px]">{item.label}</p>
                          <p className="mt-2 text-sm font-semibold text-white">{item.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="order-3 flex w-full max-w-sm flex-col items-center gap-4 sm:max-w-md sm:flex-row sm:items-start lg:order-none lg:col-start-1 lg:row-start-2 lg:items-start lg:justify-start lg:max-w-none">
                <SiteLink
                  to="/booking"
                  className="group relative inline-flex w-48 items-center justify-center self-center rounded-full bg-[#8ec8f0] px-8 py-4 text-sm font-bold text-white transition-all duration-300 hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden sm:w-56 sm:self-start drop-shadow-sm"
                >
                  <div className="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>
                  <span className="relative z-10">預約野雪嚮導</span>
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
                <a
                  href="#pricing"
                  className="inline-flex w-48 items-center justify-center rounded-full border border-transparent bg-[#2f2f2f] px-8 py-4 text-sm font-semibold text-white transition-colors duration-300 hover:bg-[#7bbbe7] sm:w-56"
                >
                  查看課程價格
                </a>
              </div>
            </div>
          </div>
        </section>

        <section id="gallery" className="bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 pt-16 pb-8 md:pt-20 md:pb-10">
            <div
              ref={introRef}
              className={`mx-auto w-full max-w-md px-6 py-10 text-center transition-all duration-700 ease-out md:max-w-none md:px-12 md:py-14 ${
                introVisible ? "translate-y-0 opacity-100" : "translate-y-10 opacity-0"
              }`}
            >
              <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                離開壓雪雪道，探索真正的白色世界
              </h2>
              <p className="mt-4 max-w-xl mx-auto text-base md:text-lg leading-relaxed text-[#475569]">
                專為進階滑雪者與滑雪板玩家設計。由具備國際安全訓練與山岳經驗的專業嚮導帶領，依照每日雪況、天氣與地形條件，嚮導會規劃最適合的滑行路線，讓滑雪者在安全前提下探索北海道代表性的山岳地形，體驗真正自由滑行的快感。
              </p>
            </div>
          </div>
          <div className="w-screen relative left-1/2 -translate-x-1/2 pb-12 md:pb-16">
            <div className="relative">
              <div
                ref={scrollerRef}
                className="flex gap-3 overflow-x-auto snap-x snap-mandatory scroll-smooth px-0 hide-scrollbar"
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
                {galleryPhotos.map((src, index) => (
                  <figure
                    key={src}
                    ref={(node) => {
                      itemRefs.current[index] = node;
                    }}
                    className="relative min-w-[85%] md:min-w-[70%] snap-center overflow-hidden bg-[#f8fafc]"
                  >
                    <img loading="lazy" decoding="async"
                      src={withBaseUrl(src)}
                      alt="Off-piste guide"
                      className="h-[56vh] md:h-[70vh] w-full object-cover"
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
                <svg
                  viewBox="0 0 20 20"
                  className="h-5 w-5 mx-auto"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 4l-6 6 6 6" />
                </svg>
              </button>
              <button
                type="button"
                onClick={() => scrollToIndex(activeIndex + 1)}
                className="absolute right-4 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full bg-white/80 text-[#1f2937] shadow-md hover:bg-white transition-colors"
                aria-label="Next photo"
              >
                <svg
                  viewBox="0 0 20 20"
                  className="h-5 w-5 mx-auto"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M8 4l6 6-6 6" />
                </svg>
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
          </div>
        </section>

        <section className="bg-[#e9eef3] text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
            <div className="grid gap-10 lg:grid-cols-[1fr_1.1fr] items-center">
              <div className="relative">
                <div
                  className="h-80 md:h-[420px] rounded-sm bg-cover bg-center shadow-[0_20px_45px_rgba(15,23,42,0.18)]"
                  style={{
                    backgroundImage: `url(${withBaseUrl(
                      "/Course/off-piste-guide/off-piste-guide-001.jpg"
                    )})`,
                  }}
                />
                <div className="absolute -bottom-6 -left-4 hidden md:flex h-24 w-32 items-center justify-center border border-[#e2e8f0] bg-white/95 text-center shadow-[0_16px_30px_rgba(15,23,42,0.12)]">
                  <p className="text-sm font-semibold text-[#2b5f8f]">中高階課程</p>
                </div>
              </div>
              <div>
                <h2 className="mt-4 text-2xl font-semibold tracking-wide font-display text-center md:text-left">
                  嚮導專業｜安全至上
                </h2>
                <p className="mt-4 text-sm md:text-base text-[#475569] max-w-xl leading-relaxed">
                  所有嚮導皆具備雪崩安全知識、山岳滑行經驗與急救證照，並根據每日雪況與天氣即時調整行程，為你提供安全、流暢又富挑戰性的滑行路線。
                </p>
                <p className="mt-3 text-sm md:text-base text-[#475569] max-w-xl leading-relaxed">
                  每趟行程皆包含：
                </p>
                <div
                  ref={includesRef}
                  className="mt-4 text-sm md:text-base text-[#475569] space-y-2"
                >
                  {[
                    { text: "✓ 雪況說明與風險評估", muted: false },
                    { text: "每日出發前說明地形、積雪狀況與可能風險。", muted: true },
                    { text: "✓ 雪崩裝備使用教學", muted: false },
                    { text: "提供 Beacon、Probe、Shovel 租借與現場教學。", muted: true },
                    { text: "✓ 客製化滑行安排", muted: false },
                    { text: "依技術程度、體力與當日雪況調整行程與路線。", muted: true },
                  ].map((item, index) => (
                    <p
                      key={`${item.text}-${index}`}
                      className={`transition-all duration-700 ease-out ${
                        includesVisible ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
                      } ${item.muted ? "text-[#64748b] pl-[1.25em]" : ""}`}
                      style={{ transitionDelay: `${index * 120}ms` }}
                    >
                      {item.text}
                    </p>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>


        <section id="pricing" className="bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
            <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display text-center">
              Pricing
            </p>
            <h2 className="mt-4 text-2xl font-semibold tracking-wide font-display text-center">
              野雪嚮導價格
            </h2>
            <div className="mt-8 grid gap-8">
              <div className="flex items-center justify-center gap-4 text-base font-semibold text-[#64748b]">
                <button
                  type="button"
                  className={`transition-colors ${
                    priceTab === "discount" ? "text-[#F7941D]" : "hover:text-[#1f2937]"
                  }`}
                  onClick={() => setPriceTab("discount")}
                >
                  優惠時段
                </button>
                <button
                  type="button"
                  role="switch"
                  aria-checked={priceTab === "regular"}
                  aria-label="切換價目表"
                  className="relative h-10 w-20 rounded-full bg-[#d4d4d4] transition-colors"
                  onClick={() => setPriceTab((prev) => (prev === "discount" ? "regular" : "discount"))}
                >
                  <span
                    className={`absolute left-1 top-1 h-8 w-8 rounded-full shadow-md transition-transform duration-300 ${
                      priceTab === "discount" ? "translate-x-1" : "translate-x-11"
                    }`}
                    style={{ backgroundColor: priceAccent }}
                  />
                </button>
                <button
                  type="button"
                  className={`transition-colors ${
                    priceTab === "regular" ? "text-[#2b5f8f]" : "hover:text-[#1f2937]"
                  }`}
                  onClick={() => setPriceTab("regular")}
                >
                  一般時段
                </button>
              </div>

              <div className="w-full max-w-xl mx-auto">
                <div className="text-center">
                  <p className="text-[#1f2937]">
                    <span className="text-xl font-semibold">25-26 SEASON ｜ </span>
                    <span className="text-lg font-semibold" style={{ color: priceAccent }}>
                      {priceDateText}
                    </span>
                  </p>
                </div>
                <div
                  className="mt-6 bg-white"
                  style={{ borderBottom: `1px solid ${priceDividerColor}` }}
                >
                  <div
                    className={`grid grid-cols-2 text-sm font-semibold font-display ${
                      priceTab === "discount" ? "text-[#475569]" : "text-[#2b5f8f]"
                    }`}
                    style={{ backgroundColor: priceDividerColor }}
                  >
                    <div className="px-4 py-3 text-center">人數</div>
                    <div className="px-4 py-3 text-center">全天5hrs</div>
                  </div>
                  <div className="text-sm text-[#475569]">
                    {priceTableRows.map((row, index) => (
                      <div
                        key={row.label}
                        className="grid grid-cols-2"
                        style={{
                          borderBottom:
                            index === priceTableRows.length - 1
                              ? "none"
                              : `1px solid ${priceDividerColor}`,
                        }}
                      >
                        <div className="px-4 py-3 text-center text-sm font-medium font-display">
                          {row.label}
                        </div>
                        <div className="px-4 py-3 text-center text-base text-[#1f2937]">
                          {row.full}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <p
                  className={`mt-6 text-xl font-semibold font-display text-center ${
                    priceTab === "discount" ? "text-[#475569]" : "text-[#2b5f8f]"
                  }`}
                >
                  4人搭配一位嚮導
                </p>
              </div>
            </div>

            <div className="mt-10 grid gap-6 md:grid-cols-3">
              <div
                className="rounded-sm border bg-white shadow-sm overflow-hidden flex h-full flex-col"
                style={{ borderColor: priceDividerColor }}
              >
                <div
                  className={`px-4 py-3 text-center text-sm font-semibold font-display ${
                    priceTab === "discount" ? "text-[#475569]" : "text-[#2b5f8f]"
                  }`}
                  style={{ backgroundColor: priceDividerColor }}
                >
                  語言指定
                </div>
                <div className="relative grid h-full flex-1 grid-cols-2 text-sm text-[#475569] items-stretch">
                  <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-[#e2e8f0]" />
                  <div className="flex h-full flex-col justify-center space-y-4 px-4 py-5 text-left">
                    {languageItems.map((item) => (
                      <p key={item}>{item}</p>
                    ))}
                  </div>
                  <div className="flex h-full items-center px-4 py-5 text-center">
                    <p>依照指定教練等級加指定費</p>
                  </div>
                </div>
              </div>
              <div
                className="rounded-sm border bg-white shadow-sm overflow-hidden"
                style={{ borderColor: priceDividerColor }}
              >
                <div
                  className={`px-4 py-3 text-center text-sm font-semibold font-display ${
                    priceTab === "discount" ? "text-[#475569]" : "text-[#2b5f8f]"
                  }`}
                  style={{ backgroundColor: priceDividerColor }}
                >
                  課程費用
                </div>
                <div className="text-sm text-[#475569]">
                  <div className="space-y-2 px-4 py-5">
                    {courseFeeItems.map((item) => (
                      <p key={item}>▸ {item}</p>
                    ))}
                  </div>
                </div>
              </div>
              <div
                className="rounded-sm border bg-white shadow-sm overflow-hidden"
                style={{ borderColor: priceDividerColor }}
              >
                <div
                  className={`px-4 py-3 text-center text-sm font-semibold font-display ${
                    priceTab === "discount" ? "text-[#475569]" : "text-[#2b5f8f]"
                  }`}
                  style={{ backgroundColor: priceDividerColor }}
                >
                  優惠
                </div>
                <div className="text-sm text-[#475569]">
                  <div className="space-y-4 px-4 py-5">
                    {discountItems.map((item) => (
                      <div key={item.title}>
                        <p className="font-semibold text-[#1f2937]">{item.title}</p>
                        <p className="mt-1 text-[#64748b]">{item.date}</p>
                        <p className="mt-2 text-[#64748b]">{item.full}</p>
                        <p className="text-[#64748b]">{item.half}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-8 rounded-sm border border-[#d7e0ea] bg-white px-6 py-6 shadow-sm">
              <h3 className="text-lg font-semibold text-[#1f2937]">必備裝備</h3>
              <p className="mt-2 text-sm text-[#64748b]">
                請自備適合野雪環境的個人裝備，並須佩戴雪崩安全裝備。
              </p>
              <div className="mt-5 space-y-4 text-sm text-[#475569]">
                {requiredGear.map((section, index) => (
                  <div
                    key={section.title}
                    className={`grid gap-4 md:grid-cols-[160px_1fr] ${
                      index === 0 ? "" : "border-t border-[#e2e8f0] pt-4"
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2 text-[#1f2937]">
                        <span className="inline-flex items-center gap-2 text-sm font-semibold">
                          <span className="text-[#1f2937]">▸</span>
                          {section.title}
                        </span>
                      </div>
                      {section.badge && (
                        <span className="mt-2 inline-flex items-center rounded-full bg-[#dbe2f0] px-2 py-1 text-[11px] font-semibold text-[#2b5f8f]">
                          {section.badge}
                        </span>
                      )}
                    </div>
                    <ul className="grid gap-2 sm:grid-cols-2">
                      {section.items.map((item) => (
                        <li key={item} className="flex items-start gap-2">
                          <span
                            className={`mt-1 h-3 w-3 shrink-0 rounded-full ${
                              section.badge ? "bg-[#2b5f8f]" : "border border-[#94a3b8]"
                            }`}
                          />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="criteria" className="bg-[#e9eef3] text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
            <h2 className="mt-4 text-2xl font-semibold tracking-wide font-display text-center">
              參加條件
            </h2>
            <div className="mt-10 grid gap-10 text-center md:text-left md:grid-cols-3">
              {criteria.map((item) => (
                <div key={item.title} className="flex flex-col items-center gap-3 md:items-start">
                  <div className={`flex h-9 w-9 items-center justify-center ${item.colorClass ?? "text-[#2b5f8f]"}`}>
                    {item.icon.type === "image" ? (
                      <img loading="lazy" decoding="async"
                        src={withBaseUrl(item.icon.src)}
                        alt={item.icon.alt}
                        className="h-6 w-6"
                      />
                    ) : (
                      <svg
                        viewBox={item.icon.viewBox}
                        className="h-6 w-6"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d={item.icon.path} />
                      </svg>
                    )}
                  </div>
                  <h3 className="text-base font-semibold text-[#1f2937]">{item.title}</h3>
                  <p className="text-sm text-[#64748b] leading-relaxed">{item.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="locations" className="bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
            <h2 className="mt-4 text-2xl font-semibold tracking-wide font-display text-center">
              推薦地點介紹
            </h2>
            <div className="mt-10 grid gap-5 md:grid-cols-2">
              {locations.map((location) => (
                <article key={location.title} className="overflow-hidden rounded-sm border border-[#e2e8f0] bg-[#f8fafc] shadow-[0_18px_40px_rgba(15,23,42,0.1)]">
                  <div
                    className="h-48 bg-cover bg-center"
                    style={{
                      backgroundImage: `url(${withBaseUrl(
                        encodeURI(location.image || heroImage)
                      )})`,
                      backgroundPosition: location.imagePosition || "center",
                    }}
                  />
                  <div className="px-5 py-6">
                    <h3 className="text-lg font-semibold text-[#1f2937]">{location.title}</h3>
                    <p className="mt-3 text-sm text-[#64748b] leading-relaxed">{location.description}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="scroll-mt-28 md:scroll-mt-32 bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 md:px-12 pt-12 md:pt-16 pb-12 md:pb-16">
            <div className="grid gap-10 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.6fr)]">
              <div>
                <h2 className="text-2xl font-semibold tracking-wide text-[#1f2937] font-display">
                  野雪嚮導常見問題
                </h2>
              </div>
              <div className="space-y-6 text-[#475569]">
                {faqItems.map((item, index) => {
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
                      {isOpen && (
                        <div className="mt-3">
                          <p className="text-sm md:text-base leading-relaxed">
                            {item.answer}
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        <section className="bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-12 md:py-16">
            <div
              className="relative max-w-3xl mx-auto overflow-hidden rounded-sm border border-[#e2e8f0] bg-[#f8fafc] px-6 py-8 md:px-10 md:py-10 text-center shadow-[0_18px_40px_rgba(15,23,42,0.12)] bg-cover"
              style={{
                backgroundImage: "url(/Course/off-piste-guide/off-piste-guide-006.jpg)",
                backgroundPosition: "center 60%",
              }}
            >
              <div className="absolute inset-0 bg-black/20" />
              <div className="relative z-10">
                <h3 className="mt-3 text-2xl md:text-3xl font-semibold tracking-wide font-display text-white">
                  預約你的野雪嚮導課程
                </h3>
                <div className="mt-6 flex justify-center">
                  <SiteLink
                    to="/booking"
                    className="inline-flex items-center justify-center rounded-full bg-[#8ec8f0] px-6 py-3 text-sm font-semibold text-white hover:bg-[#7bbbe7] transition-colors"
                  >
                    立即預約
                  </SiteLink>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export default OffPisteGuidePage;
