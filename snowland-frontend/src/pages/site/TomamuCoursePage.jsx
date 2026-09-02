import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Link as RouterLink, useParams } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import HokkaidoMap from '../../components/site/HokkaidoMap';
import TomamuWeatherSection from '../../components/site/TomamuWeatherSection';
import tomamuSlopeMap from '../../assets/site/tomamu/course-map0102-cn.png';
import skiResorts from '../../data/site/skiResorts';
import resortNavigation from '../../data/site/resortNavigation';

function TomamuCoursePage() {
  const { section } = useParams();
  const [priceTab, setPriceTab] = useState("regular");
  const [activeTab, setActiveTab] = useState("滑雪課程");
  const [daycareFaqIndex, setDaycareFaqIndex] = useState(0);
  const priceSwipeStartX = useRef(null);
  const heroSectionRef = useRef(null);
  const [isHeroActive, setIsHeroActive] = useState(false);
  const bookingUrl = "/booking";
  const resortCount = resortNavigation.length;
  const resortIndex = resortNavigation.findIndex((resort) => resort.slug === "tomamu");
  const activeResortIndex = resortIndex >= 0 ? resortIndex : 0;
  const previousResort = resortCount ? resortNavigation[(activeResortIndex - 1 + resortCount) % resortCount] : null;
  const nextResort = resortCount ? resortNavigation[(activeResortIndex + 1) % resortCount] : null;
  const tomamuResort = useMemo(
    () => skiResorts.find((resort) => resort.slug === "tomamu"),
    []
  );
  const daycareServices = [
    {
      title: "室內托兒",
      rows: [
        ["服務內容", "最短 2 小時托兒，適合租雪具或滑雪課程時使用。"],
        ["適合年齡", "5 個月至 8 歲（學齡前）。"],
        ["營業時間", "10:00-17:00（16:00 停止接待）。"],
        ["費用", "2 小時 6,000 日元；每增加 30 分鐘 1,500 日元。"],
        ["名額", "10 人。"],
        ["備品", "尿布、濕巾、換洗衣物、零食與飲料（未開封）。"],
      ],
    },
    {
      title: "全日托兒",
      rows: [
        ["服務內容", "玩雪 + 午餐 + 工藝創作。"],
        ["特色", "雪地活動與手作體驗，完整體驗北海道冬季。"],
        ["適合年齡", "3 歲以上。"],
        ["營業時間", "10:00-16:00。"],
        ["費用", "25,000 日元；延長 30 分鐘 1,500 日元。"],
      ],
    },
    {
      title: "夜間托兒",
      rows: [
        ["營業時間", "18:00-21:00。"],
        ["最短時間", "2 小時以上。"],
        ["費用", "2 小時 8,000 日元；每增加 30 分鐘 2,000 日元。"],
        ["晚餐", "需提前預訂，費用 1,200 日元。"],
        ["名額", "5 人。"],
      ],
    },
  ];
  const tabItems = useMemo(() => ([
    { label: "滑雪課程", slug: "price" },
    { label: "雪道介紹", slug: "ski-slope" },
    { label: "租借雪具", slug: "rental" },
    { label: "雪票", slug: "lift" },
    { label: "住宿", slug: "accommodation" },
    { label: "交通", slug: "access" },
    { label: "雪場托兒", slug: "nursery" },
  ]), []);
  const slugToTab = useMemo(() => (
    tabItems.reduce((acc, item) => {
      acc[item.slug] = item.label;
      return acc;
    }, {})
  ), [tabItems]);

  useEffect(() => {
    if (!section) {
      setActiveTab("滑雪課程");
      return;
    }
    setActiveTab(slugToTab[section] || "滑雪課程");
  }, [section, slugToTab]);

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
  const accommodations = [
    {
      name: "Tomamu The Tower",
      title: "Tomamu The Tower",
      description:
        "位於度假村中心位置，非常便利的飯店。推薦給想享受機動性度假住宿的人。",
      image: "https://www.snowtomamu.jp/summer/reserve/images/tw_win_img.jpg",
      imageAlt: "Tomamu The Tower winter view",
      ctaUrl: "https://hoshinoresorts.com/CH/hotels/0000000006/search",
    },
    {
      name: "RISONARE Tomamu",
      title: "RISONARE Tomamu",
      description:
        "位於度假村高地，有針葉樹林環繞，所有客房面積均為100㎡以上、配備有展望按摩浴缸和三溫暖的套房式客房。",
      image: "https://www.snowtomamu.jp/summer/reserve/images/rn_win_img.jpg",
      imageAlt: "RISONARE Tomamu winter view",
      ctaUrl: "https://hoshinoresorts.com/CH/hotels/1000000006/search",
    },
    {
      name: "Petit Hotel Gracey",
      title: "苫鵡格雷西貝提酒店",
      description:
        "Petit Hotel Gracey酒店距離Alpha Tomamu滑雪勝地有10分鐘車程，提供帶私人浴室的簡單客房。酒店在大堂提供免費無線網絡連接，並提供從Tomamu Station站至酒店的免費班車。",
      image: "https://land110602.com/wp-content/uploads/2023/08/344145648.jpg",
      imageAlt: "Petit Hotel Gracey exterior",
      ctaUrl:
        "https://www.booking.com/hotel/jp/petit-gracey-tomamu.zh-tw.html",
    },
  ];
  const regularPriceTableRows = [
    { label: "1人", full: 19200, half: 14400 },
    { label: "2人", full: 22200, half: 17400 },
    { label: "3人", full: 25200, half: 20400 },
    { label: "4人", full: 28200, half: 23400 },
    { label: "5人", full: 31200, half: 26400 },
    { label: "6人", full: 34200, half: 29400 },
  ];
  const priceTableRows = regularPriceTableRows.map((row, index) => {
    const fullDiscount = priceTab === "discount" ? 4000 : 0;
    const halfDiscount =
      priceTab === "discount" ? (index < 2 ? 3000 : 2000) : 0;
    return {
      label: row.label,
      full: `NT$${(row.full - fullDiscount).toLocaleString("en-US")}`,
      half: `NT$${(row.half - halfDiscount).toLocaleString("en-US")}`,
    };
  });
  const priceAccent = priceTab === "discount" ? "#F7941D" : "#2b5f8f";
  const priceTextColor = "#1f2937";
  const priceAccentText = priceTab === "discount" ? "#F7941D" : "#2b5f8f";
  const priceDividerColor = priceTab === "discount" ? "#f0cfac" : "#dbe2f0";
  const slopeCourses = [
    { no: 1, level: "中級", name: "Dragon Ridge", length: 840, max: 32, avg: 20 },
    { no: 2, level: "進階", name: "The Glory", length: 520, max: 25, avg: 20 },
    { no: 3, level: "中級", name: "Short Story", length: 150, max: 20, avg: 15 },
    { no: 4, level: "進階", name: "No Gravity", length: 770, max: 35, avg: 26 },
    { no: 5, level: "進階", name: "North Star", length: 500, max: 30, avg: 22 },
    { no: 6, level: "中級", name: "Silky Way", length: 510, max: 28, avg: 15 },
    { no: 7, level: "中級", name: "Natural Terrain", length: 480, max: 21, avg: 15 },
    { no: 8, level: "中級", name: "Panorama Ridge", length: 790, max: 18, avg: 10 },
    { no: 9, level: "初級", name: "Platinum Bell", length: 650, max: 16, avg: 4 },
    { no: 10, level: "初級", name: "Silver Bell", length: 3300, max: 10, avg: 4 },
    { no: 11, level: "中級", name: "Aspen Bahn", length: 370, max: 25, avg: 15 },
    { no: 12, level: "中級", name: "Knaster", length: 850, max: 25, avg: 12 },
    { no: 13, level: "初級", name: "Twisting Forest", length: 1400, max: 13, avg: 8 },
    { no: 14, level: "中級", name: "Exhibition", length: 1500, max: 28, avg: 18 },
    { no: 15, level: "中級", name: "Highway Coaster", length: 1450, max: 28, avg: 18 },
    { no: 16, level: "初級", name: "Beginner's Choice", length: 900, max: 7, avg: 5 },
    { no: 17, level: "初級", name: "Forest Maze", length: 250, max: 9, avg: 4 },
    { no: 18, level: "進階", name: "Grand Prix Z", length: 450, max: 26, avg: 21 },
    { no: 19, level: "中級", name: "Gemini", length: 540, max: 23, avg: 15 },
    { no: 20, level: "中級", name: "Venus", length: 540, max: 23, avg: 15 },
    { no: 21, level: "初級", name: "Road to Gondola", length: 520, max: 10, avg: 8 },
    { no: 22, level: "中級", name: "Moonshine", length: 130, max: 26, avg: 18 },
    { no: 23, level: "初級", name: "Sunshine", length: 1600, max: 13, avg: 17 },
    { no: 24, level: "零基礎", name: "Hello Nipo", length: 710, max: 9, avg: 7 },
    {
      no: 25,
      level: "中級",
      name: "Freeway",
      length: 400,
      max: 20,
      avg: 16,
    },
    {
      no: 26,
      level: "中級",
      name: "Bird Watcher（Forest of great spoted woodpecker）",
      length: 160,
      max: 15,
      avg: 12,
    },
    { no: 27, level: "初級", name: "hotalu street", length: 250, max: 12, avg: 7 },
    { no: 28, level: "初級", name: "Fairy Woods", length: 710, max: 15, avg: 9 },
    { no: 29, level: "初級", name: "Pine Road", length: 220, max: 9, avg: 6 },
  ];
  const slopeLevelColors = {
    初級: "#3aa85a",
    中級: "#2b74c7",
    進階: "#111111",
    零基礎: "#e66fa6",
  };
  const tomamuOnlineTicketPrices = [
    {
      type: "新冬試滑一日券",
      adult: "5,000 日圓",
      child: "2,500 日圓",
      note: "2025年12月1日～12月20日期間內可使用",
    },
    {
      type: "1日券",
      adult: "7,700 日圓",
      child: "5,700 日圓",
      note: "",
    },
    {
      type: "春季單日票",
      adult: "5,000 日圓",
      child: "2,500 日圓",
      note: "可於2026年4月1日至4月5日期間使用",
    },
    {
      type: "4小時券",
      adult: "6,700 日圓",
      child: "5,200 日圓",
      note: "通過閘門初次感應後起算4小時",
    },
    {
      type: "購買2次以上 TOMATOMO 1日票（北海道道民限定雪票）",
      adult: "4,000 日圓",
      child: "2,000 日圓",
      note: "首次購買道民限定的雪票，需先在窗口購買IC卡",
    },
  ];
  const tomamuOnsiteTicketPrices = [
    {
      type: "新冬試滑一日券",
      adult: "5,000 日圓",
      child: "2,500 日圓",
      senior: "-",
      note: "2025年12月1日～12月20日期間內可使用",
    },
    {
      type: "1日券",
      adult: "8,000 日圓",
      child: "6,000 日圓",
      senior: "7,500 日圓",
      note: "如欲購買2日以上雪票請至窗口購買，費用為1日票乘以所需天數",
    },
    {
      type: "春季單日票",
      adult: "5,000 日圓",
      child: "2,500 日圓",
      senior: "-",
      note: "可於2026年4月1日至4月5日期間使用",
    },
    {
      type: "住宿者優惠雪票",
      adult: "7,500 日圓",
      child: "5,500 日圓",
      senior: "7,000 日圓",
      note: "入住Tomamu The Tower或RISONARE Tomamu可享纜車500日圓折扣（初滑期間成人4500日圓，小學生2000日圓）",
    },
    {
      type: "TOMATOMO 1日券（北海道道民限定）首次購買",
      adult: "5,000 日圓",
      child: "2,500 日圓",
      senior: "-",
      note: "需於櫃檯出示身分證明文件確認居住地",
    },
    {
      type: "4小時券",
      adult: "7,000 日圓",
      child: "5,500 日圓",
      senior: "6,500 日圓",
      note: "從購買時起4小時內有效",
    },
    {
      type: "After15",
      adult: "5,000 日圓",
      child: "3,500 日圓",
      senior: "4,500 日圓",
      note: "2025年12月26日～2026年3月31日 15:00～18:00可使用",
    },
    {
      type: "點數券（1點）",
      adult: "-",
      child: "1,000 日圓",
      senior: "-",
      note: "Nipo Chair・Romance Chair：1點 / Tower Express・Tomamu Express・Powder Express・雲海纜車：2點",
    },
    {
      type: "霧冰纜車來回券",
      adult: "2,500 日圓",
      child: "1,600 日圓",
      senior: "-",
      note: "",
    },
    {
      type: "北海道 Season Net 滑雪場 1日券",
      adult: "6,500 日圓",
      child: "4,800 日圓",
      senior: "-",
      note: "",
    },
  ];
  const transportOptions = [
    {
      id: "sapporo",
      label: "札幌市區",
      fields: {
        出發地: "札幌市區",
        建議交通方式: "JR / 自駕",
        預估時間: "自駕約 100 分鐘",
        是否需要轉乘: "JR 直達",
        小提醒: "適合住札幌市區後移動前往雪場",
      },
    },
    {
      id: "cts",
      label: "新千歲機場",
      fields: {
        出發地: "新千歲機場",
        建議交通方式: "JR 特急 / 自駕",
        預估時間: "自駕約 90 分鐘",
        是否需要轉乘: "JR 需於南千歲轉乘",
        小提醒: "適合國際航班抵達後直接前往 TOMAMU",
      },
    },
    {
      id: "asahikawa",
      label: "旭川機場",
      fields: {
        出發地: "旭川機場",
        建議交通方式: "自駕",
        預估時間: "約 3 小時",
        是否需要轉乘: "JR 需經由札幌，較不建議",
        小提醒: "適合搭配道北行程後前往",
      },
    },
    {
      id: "obihiro",
      label: "帶廣機場",
      fields: {
        出發地: "帶廣機場",
        建議交通方式: "自駕 / JR",
        預估時間: "自駕約 60 分鐘",
        是否需要轉乘: "JR 需轉乘（機場巴士 → 帶廣站）",
        小提醒: "適合搭配道東行程後前往",
      },
    },
    {
      id: "furano",
      label: "富良野",
      fields: {
        出發地: "富良野",
        建議交通方式: "自駕",
        預估時間: "約 90 分鐘",
        是否需要轉乘: "JR 需經由札幌，較不建議",
        小提醒: "適合安排富良野行程後銜接 TOMAMU",
      },
    },
  ];
  const [activeDeparture, setActiveDeparture] = useState("cts");
  const activeTransport = transportOptions.find((option) => option.id === activeDeparture);
  return (
    <div className="min-h-screen bg-[#0b1d2a] text-white flex flex-col">
      <SiteHeader forceTransparent />
      <main className="flex-1 w-full">
        <section ref={heroSectionRef} className="relative overflow-hidden bg-[#f3f0ea] text-[#1f2937]">
          <div className="absolute inset-0">
            <div
              className="h-full w-full bg-cover bg-center"
              style={{ backgroundImage: `url(${encodeURI("/Course/tomamu/240315-17 chris tomamu SB Vanessa-IMG_20240317_130744.jpg")})` }}
            />
            <div className="absolute inset-0 bg-gradient-to-br from-[#0b1d2a]/10 via-transparent to-[#0b1d2a]/35" />
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
          <div className="relative max-w-6xl mx-auto px-6 pt-28 pb-20">
            <div className="grid gap-10 lg:grid-cols-[1fr_1.1fr] items-stretch">
              <div className="relative flex flex-col justify-center text-center lg:text-left items-center lg:items-start">
                <p className="text-xs font-semibold tracking-[0.35em] uppercase text-white/80 font-display drop-shadow-sm">
                  Hoshino resort TOMAMU
                </p>
                <h1 className="text-3xl md:text-4xl font-semibold tracking-wide font-display leading-tight text-white drop-shadow-sm">
                  星野TOMAMU
                </h1>
                <p className="mt-6 text-base md:text-lg text-white/85 max-w-xl leading-relaxed drop-shadow-sm">
                  北海道的中心地帶，一站式度假村粉雪天堂。除了滑雪還提供多種雪地活動，讓您在雪地中盡情玩樂。
                </p>
                <a
                  href={bookingUrl}
                  className="group relative mt-6 hidden lg:inline-flex w-56 items-center justify-center rounded-full bg-[#8ec8f0] px-10 py-5 text-sm font-bold text-white transition-all duration-300 hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden"
                >
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
                </a>
              </div>

              <div className="relative min-h-[360px]">
                <div className="relative z-10 flex h-full items-center justify-center p-6 lg:justify-end">
                  <div className="w-full max-w-md rounded-sm bg-[#1b1f24]/30 backdrop-blur-md px-6 py-6 text-white shadow-[0_20px_45px_rgba(15,23,42,0.35)]">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.3em] text-[#f3a23a]">
                      <span className="h-2 w-2 rounded-full bg-[#f3a23a]" />
                      <span>北海道 | {tomamuResort?.region ?? "道東"}</span>
                    </div>
                    <div className="mt-4 text-4xl font-semibold tracking-wide font-display">星野TOMAMU</div>
                    <div className="mt-6 grid grid-cols-2 gap-4 text-xs text-white/80">
                      <div>
                        <p className="uppercase tracking-[0.3em] text-white/60">特色</p>
                        <ul className="mt-2 space-y-1 text-sm font-semibold text-white">
                          <li>Ski-in/Ski-out</li>
                          <li>親子樂園</li>
                          <li>初學友善</li>
                          <li>夜滑雪道</li>
                          <li>托兒服務</li>
                          <li>雪具租借</li>
                          <li>多元戶外活動</li>
                        </ul>
                      </div>
                      <div>
                        <p className="uppercase tracking-[0.3em] text-white/60">雪道分級</p>
                        <div className="mt-3 space-y-3 text-xs text-white/85">
                          {[
                            { label: "初級", value: 30, color: "bg-[#9cccf4]" },
                            { label: "中級", value: 40, color: "bg-[#f4d39c]" },
                            { label: "高級", value: 50, color: "bg-[#f2b8b8]" },
                            { label: "壓雪", value: 65, color: "bg-[#f3a23a]" },
                            { label: "非壓雪", value: 35, color: "bg-[#6fc3b8]" },
                          ].map((item) => (
                            <div key={item.label}>
                              <div className="flex items-center justify-between">
                                <span className="font-semibold">{item.label}</span>
                                <span className="text-white/70">{item.value}%</span>
                              </div>
                              <div className="mt-1 h-2 w-full overflow-hidden rounded-sm bg-white/20">
                                <div
                                  className={`h-full animate-[progress-fill_900ms_ease-out_forwards] ${item.color}`}
                                  style={{ "--target-width": `${item.value}%` }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex justify-center lg:hidden">
                <a
                  href={bookingUrl}
                  className="group relative mt-2 inline-flex w-56 items-center justify-center rounded-full bg-[#8ec8f0] px-10 py-5 text-sm font-bold text-white transition-all duration-300 hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden"
                >
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
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>
      <TomamuWeatherSection />
      <section className="bg-white text-[#1f2937] border-t border-[#e2e8f0]">
        <div className="max-w-6xl mx-auto px-6 py-10">
          <div className="border-b border-[#e2e8f0]">
            <div className="flex flex-wrap items-center justify-center gap-12 md:gap-16 text-base md:text-lg font-semibold text-[#6b7280] font-display">
              {tabItems.map((item) => {
                const isActive = item.label === activeTab;
                return (
                  <SiteLink
                    key={item.slug}
                    to={`/course/tomamu/${item.slug}`}
                    onClick={() => setActiveTab(item.label)}
                    className={`group relative pb-4 transition-colors duration-200 ${
                      isActive ? "text-[#111827]" : "hover:text-[#2b5f8f]"
                    }`}
                    aria-current={isActive ? "page" : undefined}
                  >
                    {item.label}
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
        </div>
      </section>
      {activeTab === "住宿" && (
        <section className="bg-white text-[#1f2937]">
          <div className="pt-14 pb-16 md:pt-14 md:pb-20 space-y-10 md:space-y-12">
            <div className="max-w-6xl mx-auto px-6 md:px-10">
              <motion.div
                className="text-center space-y-3"
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ amount: 0.4, once: true }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              >
                <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                  Accommodation
                </p>
                <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                  舒適的住宿選擇
                </h2>
                <p className="max-w-xl mx-auto text-sm md:text-base leading-relaxed text-[#475569]">
                  星野TOMAMU滑雪場提供多種住宿選擇，包括RISONARE Tomamu和The Tower等，房間寬敞舒適，部分客房配備私人桑拿和按摩浴池，讓您在滑雪後放鬆身心。
                </p>
              </motion.div>
            </div>

            {accommodations.map((hotel, index) => {
              const isReversed = index % 2 === 1;
              return (
                <div
                  key={hotel.name}
                  id={index === 0 ? "tomamu-hotels" : undefined}
                  className={`grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6 md:gap-12 lg:gap-16 items-center ${
                    isReversed ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]" : ""
                  }`}
                >
                  <div className={`w-full h-72 md:h-[420px] ${isReversed ? "lg:order-2" : ""}`}>
                    <img loading="lazy" decoding="async"
                      src={hotel.image}
                      alt={hotel.imageAlt}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <div className={`px-6 md:px-10 ${isReversed ? "lg:order-1" : ""}`}>
                    <div className="max-w-2xl text-[#2b2b2b] text-sm md:text-base leading-relaxed space-y-4">
                      <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
                        {hotel.title}
                      </h3>
                      <p className="text-sm md:text-base text-[#475569] leading-relaxed">
                        {hotel.description}
                      </p>
                      <div>
                        <a
                          href={hotel.ctaUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-6 py-2 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
                        >
                          查詢空房
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {activeTab === "滑雪課程" && (
        <section className="bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-14 space-y-12">
            <div className="text-center space-y-3">
              <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                TOMAMU COURSE PRICING
              </p>
              <h2 className="text-2xl font-semibold tracking-wide font-display">
                星野課程價目表
              </h2>
            </div>

            <div className="grid gap-8">
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
                    <span className="text-xl font-semibold">
                      25-26 SEASON ｜{" "}
                    </span>
                    <span className="text-lg font-semibold" style={{ color: priceAccentText }}>
                      {priceTab === "discount"
                        ? "季初 ~ 2025/12/15 & 2026/03/04 ~ 季末"
                        : "2025/12/16 ~ 2026/03/03"}
                    </span>
                  </p>
                </div>

                <div
                  className="mt-6 bg-white"
                  style={{ borderBottom: `1px solid ${priceDividerColor}` }}
                  onTouchStart={(event) => {
                    priceSwipeStartX.current = event.touches[0]?.clientX ?? null;
                  }}
                  onTouchEnd={(event) => {
                    const startX = priceSwipeStartX.current;
                    const endX = event.changedTouches[0]?.clientX ?? null;
                    priceSwipeStartX.current = null;
                    if (startX === null || endX === null) return;
                    const deltaX = endX - startX;
                    if (Math.abs(deltaX) < 40) return;
                    if (deltaX < 0) {
                      setPriceTab("discount");
                    } else {
                      setPriceTab("regular");
                    }
                  }}
                >
                  <div
                    className={`grid grid-cols-3 text-sm font-semibold font-display ${
                      priceTab === "discount" ? "text-[#475569]" : "text-[#2b5f8f]"
                    }`}
                    style={{
                      backgroundImage: "none",
                      backgroundColor: priceTab === "discount" ? "#f0cfac" : "#dbe2f0",
                    }}
                  >
                    <div className="px-4 py-3 text-center">
                      人數
                    </div>
                    <div className="px-4 py-3 text-center">
                      全天5hrs
                    </div>
                    <div className="px-4 py-3 text-center">
                      半天3hrs
                    </div>
                  </div>
                  <div className="text-sm text-[#475569]">
                    {priceTableRows.map((row, index) => (
                      <div
                        key={row.label}
                        className="grid grid-cols-3"
                        style={{
                          borderBottom:
                            index === priceTableRows.length - 1
                              ? "none"
                              : `1px solid ${priceDividerColor}`,
                        }}
                      >
                        <div
                          className="px-4 py-3 text-center text-sm font-medium font-display"
                          style={{ color: priceTab === "discount" ? "#475569" : priceAccentText }}
                        >
                          {row.label}
                        </div>
                        <div
                          className="px-4 py-3 text-center text-base"
                          style={{ color: priceTextColor }}
                        >
                          {row.full}
                        </div>
                        <div
                          className="px-4 py-3 text-center text-base"
                          style={{ color: priceTextColor }}
                        >
                          {row.half}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

            </div>

            <div className="grid gap-6 md:grid-cols-3">
              <div
                className="rounded-sm border bg-white shadow-sm flex h-full flex-col"
                style={{ borderColor: priceDividerColor }}
              >
                <div
                  className={`px-4 py-3 text-center text-sm font-semibold font-display ${
                    priceTab === "discount" ? "text-[#475569]" : "text-[#2b5f8f]"
                  }`}
                  style={{ backgroundColor: priceDividerColor }}
                >
                  協助租借裝備加購
                </div>
                <div className="relative flex-1 grid grid-cols-2 py-5 text-sm text-[#475569] items-stretch">
                  <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-[#e2e8f0]" />
                  <div className="flex flex-col items-center gap-4 px-4 py-6 text-center">
                    <p>1~3人</p>
                    <p>4~6人</p>
                  </div>
                  <div className="flex h-full flex-col items-center gap-4 px-4 py-6 text-center">
                    <p>+NT$1,000</p>
                    <p>+NT$2,000</p>
                  </div>
                </div>
              </div>

              <div
                className="rounded-sm border bg-white shadow-sm flex flex-col"
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
                  <div className="flex h-full flex-col justify-center space-y-4 px-4 py-5 text-center">
                    <p>中文</p>
                    <p>粵語</p>
                    <p>英語</p>
                  </div>
                  <div className="flex h-full items-center px-4 py-5 text-center">
                    <p>依照指定教練等級加指定費</p>
                  </div>
                </div>
              </div>

              <div
                className="rounded-sm border bg-white shadow-sm"
                style={{ borderColor: priceDividerColor }}
              >
                <div
                  className={`px-4 py-3 text-center text-sm font-semibold font-display ${
                    priceTab === "discount" ? "text-[#475569]" : "text-[#2b5f8f]"
                  }`}
                  style={{ backgroundColor: priceDividerColor }}
                >
                  教練指定費
                </div>
                <div className="grid grid-cols-2 divide-x divide-[#e2e8f0] text-sm text-[#475569]">
                  <div className="space-y-4 px-4 py-5 text-center">
                    <p>一般教練</p>
                    <p>Lv 2教練</p>
                    <p>Lv 3教練</p>
                    <p>校長/總監</p>
                  </div>
                  <div className="space-y-4 px-4 py-5 text-center">
                    <p>+NT$1,000</p>
                    <p>+NT$1,800</p>
                    <p>+NT$3,000</p>
                    <p>+NT$3,000</p>
                  </div>
                </div>
              </div>
            </div>

          </div>

          <div className="bg-[#e9eef3]">
            <div className="max-w-6xl mx-auto px-6 py-12 space-y-12">
              <div className="divide-y divide-[#e2e2de]">
                <div className="grid gap-6 md:grid-cols-[200px_minmax(0,1fr)] pb-8">
                  <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">優惠</h3>
                  <ul className="space-y-3 text-sm text-[#475569] list-disc pl-5">
                    <li className="space-y-2">
                      <span>早早鳥即日起至2025/6/30</span>
                      <ul className="space-y-1 pl-0">
                        <li>全日折扣500/人</li>
                        <li>半天折扣300/人</li>
                      </ul>
                    </li>
                    <li className="space-y-2">
                      <span>早鳥2025/7/1~2025/9/30</span>
                      <ul className="space-y-1 pl-0">
                        <li>全日折扣300/人</li>
                        <li>半天折扣200/人</li>
                      </ul>
                    </li>
                  </ul>
                </div>

                <div className="grid gap-6 md:grid-cols-[200px_minmax(0,1fr)] py-8">
                  <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">課程費用</h3>
                  <ul className="space-y-2 text-sm text-[#475569] list-disc pl-5">
                    <li>包含教學費</li>
                    <li>不含纜車費，雪具租賃等費用</li>
                    <li>贈送課程時段特殊活動意外險</li>
                  </ul>
                </div>

                <div className="pt-8">
                  <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">課程時間</h3>
                  <div className="mt-6 space-y-8 divide-y divide-[#e2e2de]">
                    <div className="grid gap-6 md:grid-cols-[200px_minmax(0,1fr)] pb-8">
                      <p className="text-sm font-semibold text-[#1f2937]">全天5hr課程</p>
                      <div className="grid gap-6 md:grid-cols-2">
                        <div className="space-y-2 mt-4 md:mt-0">
                          <p className="text-sm font-semibold text-[#1f2937]">含協助租借裝備</p>
                          <ul className="space-y-2 text-sm text-[#475569]">
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>08:30</span>
                              <span>- 集合時間</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>08:30~09:00(30min)</span>
                              <span>- 當日協助租借裝備</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>09:00~11:30(2.5hr)</span>
                              <span>- 上課時間</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>11:30~12:30(1hr)</span>
                              <span>- 中午休息</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>12:30~14:30(2hrs)</span>
                              <span>- 上課時間</span>
                            </li>
                          </ul>
                        </div>
                        <div className="space-y-2 mt-4 md:mt-0">
                          <p className="text-sm font-semibold text-[#1f2937]">不含協助租借裝備</p>
                          <ul className="space-y-2 text-sm text-[#475569]">
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>09:00</span>
                              <span>- 集合時間，教練在集合時檢整裝備沒問題後開始課程</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>09:00~11:30(2.5hr)</span>
                              <span>- 上課時間</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>11:30~12:30(1hr)</span>
                              <span>- 中午休息</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>12:30~15:00(2.5hrs)</span>
                              <span>- 上課時間</span>
                            </li>
                          </ul>
                          <div className="space-y-2 text-sm text-[#475569]">
                            <ul className="list-disc pl-5">
                              <li className="pt-2 font-semibold text-[#1f2937]">
                                如需要協助租借又不希望壓縮上課時間須加購協助服務
                              </li>
                            </ul>
                            <ul className="list-disc pl-5">
                              <li className="font-semibold text-[#1f2937]">加購協助租借裝備時間</li>
                            </ul>
                            <ul className="space-y-1 pl-5">
                              <li>- 前一日 15:30~17:00</li>
                              <li>- 當  日 08:30~09:00</li>
                            </ul>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-6 md:grid-cols-[200px_minmax(0,1fr)]">
                      <p className="text-sm font-semibold text-[#1f2937]">半天3h課程</p>
                      <div className="grid gap-6 md:grid-cols-2">
                        <div className="space-y-2">
                          <p className="text-sm font-semibold text-[#1f2937]">含協助租借裝備</p>
                          <ul className="space-y-2 text-sm text-[#475569]">
                            <li className="flex items-center gap-3 text-xs font-semibold text-[#1f2937]">
                              <span className="h-px flex-1 bg-[#1f2937]" />
                              <span>早上課</span>
                              <span className="h-px flex-1 bg-[#1f2937]" />
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>08:30</span>
                              <span>- 集合時間</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>08:30~09:00(30min)</span>
                              <span>- 協助租借裝備</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>09:00~11:30(2.5hrs)</span>
                              <span>- 上課時間</span>
                            </li>
                            <li className="flex items-center gap-3 pt-2 text-xs font-semibold text-[#1f2937]">
                              <span className="h-px flex-1 bg-[#1f2937]" />
                              <span>下午課</span>
                              <span className="h-px flex-1 bg-[#1f2937]" />
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>12:30</span>
                              <span>- 集合時間</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>12:30~13:00(30min)</span>
                              <span>- 協助租借裝備</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>13:00~15:30(2.5hrs)</span>
                              <span>- 上課時間</span>
                            </li>
                          </ul>
                        </div>
                        <div className="space-y-2">
                          <p className="text-sm font-semibold text-[#1f2937]">不含協助租借裝備</p>
                          <ul className="space-y-2 text-sm text-[#475569]">
                            <li className="flex items-center gap-3 text-xs font-semibold text-[#1f2937]">
                              <span className="h-px flex-1 bg-[#1f2937]" />
                              <span>早上課</span>
                              <span className="h-px flex-1 bg-[#1f2937]" />
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>09:00</span>
                              <span>- 集合時間</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>09:00~12:00(3hrs)</span>
                              <span>- 上課時間</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3 invisible">
                              <span>00:00</span>
                              <span>-</span>
                            </li>
                            <li className="flex items-center gap-3 pt-2 text-xs font-semibold text-[#1f2937]">
                              <span className="h-px flex-1 bg-[#1f2937]" />
                              <span>下午課</span>
                              <span className="h-px flex-1 bg-[#1f2937]" />
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>12:30</span>
                              <span>- 集合時間</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>12:30~15:30(3hrs)</span>
                              <span>- 上課時間</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>前一日 15:30~17:00</span>
                              <span>- 租借裝備</span>
                            </li>
                            <li className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                              <span>當日 08:30~09:00</span>
                              <span>- 集合時間</span>
                            </li>
                          </ul>
                          <div className="space-y-2 text-sm text-[#475569]">
                            <ul className="list-disc pl-5">
                              <li className="pt-2 font-semibold text-[#1f2937]">
                                如需要協助租借又不希望壓縮上課時間須加購協助服務
                              </li>
                            </ul>
                            <ul className="list-disc pl-5">
                              <li className="font-semibold text-[#1f2937]">加購協助租借裝備時間</li>
                            </ul>
                            <ul className="space-y-1 pl-5">
                              <li>- 前一日 15:30~17:00</li>
                              <li>- 當  日 08:30~09:00</li>
                            </ul>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-center">
                <a
                  href={bookingUrl}
                  className="group relative inline-flex w-56 items-center justify-center rounded-full bg-[#8ec8f0] px-10 py-5 text-sm font-bold text-white transition-all duration-300 hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden"
                >
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
                </a>
              </div>
            </div>
          </div>
        </section>
      )}

      {activeTab === "雪道介紹" && (
        <section className="bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-14 space-y-10">
            <div className="text-center space-y-3">
              <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                TOMAMU SLOPE MAP
              </p>
              <h2 className="text-2xl font-semibold tracking-wide font-display">
                雪道介紹
              </h2>
            </div>
            <div className="mt-6">
              <img loading="lazy" decoding="async"
                src={tomamuSlopeMap}
                alt="星野Tomamu 雪道地圖"
                className="w-full h-auto"
                loading="lazy"
              />
            </div>
            <div className="mt-6 bg-white">
              <div className="mx-auto w-full max-w-5xl border-b border-[#e2e8f0] text-sm text-[#475569]">
                <div className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[180px_minmax(0,1fr)]">
                  <div className="font-semibold text-[#1f2937]">滑道數量</div>
                  <div>29 (進階4條、中級14條、初級10條、零基礎1條)</div>
                </div>
                <div className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[180px_minmax(0,1fr)]">
                  <div className="font-semibold text-[#1f2937]">總滑行距離</div>
                  <div>21.5 km</div>
                </div>
                <div className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[180px_minmax(0,1fr)]">
                  <div className="font-semibold text-[#1f2937]">滑雪場滑道面積</div>
                  <div>123.9ha</div>
                </div>
                <div className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[180px_minmax(0,1fr)]">
                  <div className="font-semibold text-[#1f2937]">最長滑行距離</div>
                  <div>4,200ｍ　(Silver Bell ～ Beginner's Choice)</div>
                </div>
                <div className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[180px_minmax(0,1fr)]">
                  <div className="font-semibold text-[#1f2937]">最大坡度</div>
                  <div>35°　(No Gravity)</div>
                </div>
                <div className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[180px_minmax(0,1fr)]">
                  <div className="font-semibold text-[#1f2937]">標高差</div>
                  <div>585m (1171m～586m)</div>
                </div>
                <div className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[180px_minmax(0,1fr)]">
                  <div className="font-semibold text-[#1f2937]">纜車數</div>
                  <div>吊椅5、纜車1</div>
                </div>
              </div>
            </div>
            <div className="mt-8">
              <div className="overflow-x-auto">
                <table className="mx-auto w-full max-w-5xl text-left text-[10px] md:text-sm">
                  <thead className="bg-[#dbe2f0] text-[#1f2937]">
                    <tr className="text-[10px] font-semibold uppercase font-display tracking-[0.08em] md:text-xs md:tracking-[0.2em]">
                      <th className="px-1.5 md:px-4 py-2.5 text-right whitespace-nowrap w-[36px] md:w-[80px]">編號</th>
                      <th className="px-1.5 md:px-4 py-2.5 whitespace-nowrap w-[54px] md:w-[110px]">Level</th>
                      <th className="pl-1.5 pr-0.5 md:px-4 py-2.5 w-[110px] md:w-[320px]">雪道名稱</th>
                      <th className="pl-0.5 pr-1 md:px-4 py-2.5 text-right whitespace-nowrap w-[62px] md:w-[130px]">長度 (m)</th>
                      <th className="px-1 md:px-4 py-2.5 text-right whitespace-nowrap w-[54px] md:w-[120px]">斜率 (°)</th>
                      <th className="px-1 md:px-4 py-2.5 text-right whitespace-nowrap w-[70px] md:w-[150px]">平均斜率 (°)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slopeCourses.map((course, index) => {
                      const levelColor = slopeLevelColors[course.level] || "#475569";
                      return (
                      <tr
                        key={`${course.no}-${course.name}`}
                        className={`border-t border-[#e2e8f0] ${
                          index % 2 === 0 ? "bg-white" : "bg-[#f8fafc]"
                        }`}
                      >
                        <td
                          className="px-1.5 md:px-4 py-2.5 text-right font-semibold"
                          style={{ color: levelColor }}
                        >
                          {course.no}
                        </td>
                        <td
                          className="px-1.5 md:px-4 py-2.5 font-semibold"
                          style={{ color: levelColor }}
                        >
                          {course.level}
                        </td>
                        <td className="pl-1.5 pr-0.5 md:px-4 py-2.5 font-semibold text-[#1f2937] break-words">
                          {course.name}
                        </td>
                        <td className="pl-0.5 pr-1 md:px-4 py-2.5 text-right text-[#475569]">
                          {course.length.toLocaleString("en-US")}
                        </td>
                        <td className="px-1 md:px-4 py-2.5 text-right text-[#475569]">{course.max}</td>
                        <td className="px-1 md:px-4 py-2.5 text-right text-[#475569]">{course.avg}</td>
                      </tr>
                    );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      )}

      {activeTab === "雪票" && (
        <section className="bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-14 space-y-10">
            <motion.div
              className="text-center space-y-3"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ amount: 0.4, once: true }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            >
              <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                LIFT TICKETS
              </p>
              <h2 className="text-2xl font-semibold tracking-wide font-display">
                雪票價格
              </h2>
              <p className="text-sm md:text-base leading-relaxed text-[#475569]">
                星野住宿客人享有住宿者優惠，請於現場購買雪票。
              </p>
            </motion.div>
            <div className="space-y-8">
              <div className="relative w-full aspect-[5/2] overflow-hidden rounded-sm border border-[#e2e8f0]">
                <img loading="lazy" decoding="async"
                  src="/Course/tomamu/course-tomamu-005-lift.jpg"
                  alt="Tomamu lift"
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              </div>
              <div className="text-center">
                <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
                  網路販售價格
                </h3>
              </div>
              <div className="overflow-x-auto thin-scrollbar">
                <table className="w-full min-w-[720px] text-left text-sm text-[#475569]">
                  <thead className="bg-[#dbe2f0] text-xs font-semibold tracking-[0.2em] uppercase text-[#1f2937] font-display">
                    <tr>
                      <th className="px-4 py-3 font-semibold">票券類型</th>
                      <th className="px-4 py-3 text-center font-semibold">成人（12歲以上）</th>
                      <th className="px-4 py-3 text-center font-semibold">兒童（7～11歲）</th>
                      <th className="px-4 py-3 font-semibold w-[220px] md:w-[280px]">備註</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tomamuOnlineTicketPrices.map((ticket, index) => (
                      <tr
                        key={ticket.type}
                        className={`border-t border-[#e2e8f0] ${
                          index % 2 === 0 ? "bg-white" : "bg-[#f8fafc]"
                        }`}
                      >
                        <td className="px-4 py-3 font-semibold text-[#1f2937]">{ticket.type}</td>
                        <td className="px-4 py-3 text-center font-semibold text-[#1f2937] whitespace-nowrap">
                          {ticket.adult}
                        </td>
                        <td className="px-4 py-3 text-center font-semibold text-[#1f2937] whitespace-nowrap">
                          {ticket.child}
                        </td>
                        <td className="px-4 py-3 w-[220px] md:w-[280px]">{ticket.note || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="text-sm text-[#475569]">
                <ul className="space-y-2 list-disc pl-5">
                  <li>購入後不可退款，取消及變更。</li>
                  <li>Web販售價格不會變動，建議於使用當日再行購入。</li>
                  <li>IC卡片無抵壓保証金，可以將卡片帶回。</li>
                  <li>6歲以下免費。請攜同符合資格的兒童至售票處。</li>
                  <li>4/1～4/5期間內，僅有限纜車運行。</li>
                  <li>
                    詳細資訊請參閱
                    <a
                      href="https://www.snowtomamu.jp/winter/cn/ski/ticket/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-1 text-[#2b5f8f] underline underline-offset-2"
                    >
                      官方網站
                    </a>
                    詳情。
                  </li>
                </ul>
              </div>
            </div>
            <div className="space-y-8">
              <div className="text-center">
                <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
                  現場購買價格
                </h3>
              </div>
              <div className="overflow-x-auto thin-scrollbar">
                <table className="w-full min-w-[720px] text-left text-sm text-[#475569]">
                  <thead className="bg-[#dbe2f0] text-xs font-semibold tracking-[0.2em] uppercase text-[#1f2937] font-display">
                    <tr>
                      <th className="px-4 py-3 font-semibold">票券類型</th>
                      <th className="px-4 py-3 text-center font-semibold">成人（12歲以上）</th>
                      <th className="px-4 py-3 text-center font-semibold">兒童（7～11歲）</th>
                      <th className="px-4 py-3 text-center font-semibold">敬老（60歲以上）</th>
                      <th className="px-4 py-3 font-semibold w-[220px] md:w-[280px]">備註</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tomamuOnsiteTicketPrices.map((ticket, index) => (
                      <tr
                        key={ticket.type}
                        className={`border-t border-[#e2e8f0] ${
                          index % 2 === 0 ? "bg-white" : "bg-[#f8fafc]"
                        }`}
                      >
                        <td className="px-4 py-3 font-semibold text-[#1f2937]">{ticket.type}</td>
                        <td className="px-4 py-3 text-center font-semibold text-[#1f2937] whitespace-nowrap">
                          {ticket.adult}
                        </td>
                        <td className="px-4 py-3 text-center font-semibold text-[#1f2937] whitespace-nowrap">
                          {ticket.child}
                        </td>
                        <td className="px-4 py-3 text-center font-semibold text-[#1f2937] whitespace-nowrap">
                          {ticket.senior}
                        </td>
                        <td className="px-4 py-3 w-[220px] md:w-[280px]">{ticket.note || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="text-sm text-[#475569]">
                <ul className="space-y-2 list-disc pl-5">
                  <li>敬老價格適用於60歲及以上人士，購買纜車票時請出示能確認年齡的身分證明。</li>
                  <li>如需購買2日票以上的雪票，請至窗口購買。費用計算為1日票乘以所需天數。</li>
                </ul>
              </div>
            </div>
            <div className="text-sm text-[#475569]">
              <div className="px-1 pb-3 text-lg font-semibold text-[#1f2937] font-display">
                販售地點
              </div>
              <ul className="space-y-1 px-1">
                <li>Tomamu The Tower Ⅰ 售票處（雪場側）</li>
                <li>Resort Center售票處</li>
              </ul>
            </div>
          </div>
        </section>
      )}

      {activeTab === "租借雪具" && (
        <section className="bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-14 space-y-10">
            <div className="text-center space-y-3">
              <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                RENTAL
              </p>
              <h2 className="text-2xl font-semibold tracking-wide font-display">
                租借雪具
              </h2>
            </div>

            <div className="space-y-5">
              <div className="rounded-sm overflow-hidden border border-[#e2e8f0] bg-white shadow-sm">
                <img loading="lazy" decoding="async"
                  src="https://www.snowtomamu.jp/assets/ski/images/rental/map-cn.png"
                  alt="Tomamu rental area map"
                  className="w-full h-auto object-contain"
                  loading="lazy"
                />
              </div>
              <div className="text-sm text-[#475569]">
                <div className="px-1 pb-3 text-lg font-semibold text-[#1f2937] font-display">
                  租借地點：
                </div>
                <ul className="space-y-1 px-1">
                  <li>The Tower 1F 租賃區</li>
                  <li>RISONARE Tomamu 租借區</li>
                  <li>Resort Center Rental / VECTOR GLIDE Demo Center</li>
                </ul>
              </div>
              <ul className="space-y-2 text-sm text-[#475569] list-disc pl-5">
                <li>
                  費用及營業時間，請至{" "}
                  <a
                    href="https://www.snowtomamu.jp/winter/cn/ski/rental/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#2b5f8f] underline underline-offset-2"
                  >
                    星野TOMAMU官方網站
                  </a>{" "}
                  查詢。
                </li>
                <li>可使用網路預約，可以記房帳，租借超方便。</li>
              </ul>
            </div>

            <div className="space-y-6">
              <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display text-center">
                裝備尺寸
              </h3>
              <div className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-sm bg-white overflow-hidden">
                  <div className="px-4 py-3 text-center text-lg font-semibold text-[#1f2937] font-display">
                    成人
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-[#475569]">
                      <thead className="bg-[#dbe2f0] text-xs font-semibold tracking-[0.2em] uppercase text-[#1f2937] font-display">
                        <tr>
                          <th className="px-4 py-3 font-semibold">物品</th>
                          <th className="px-4 py-3 font-semibold w-[180px]">尺寸</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-t border-[#e2e8f0] bg-white">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">
                            滑雪板
                            <span className="mt-1 block text-xs font-normal text-[#94a3b8]">
                              ※不提供短滑雪板和Funski（一般長度滑雪板）<br />
                              ※不提供短板、Fun skis短板（130cm以下短版）、Fat skis寬板雙板、粉雪用雪板
                            </span>
                          </th>
                          <td className="px-4 py-3 w-[180px]">125cm～165cm</td>
                        </tr>
                        <tr className="border-t border-[#e2e8f0] bg-[#f8fafc]">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">滑雪靴</th>
                          <td className="px-4 py-3 w-[180px]">22.5cm～31.5cm（1cm刻度）</td>
                        </tr>
                        <tr className="border-t border-[#e2e8f0] bg-white">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">單板滑雪板</th>
                          <td className="px-4 py-3 w-[180px]">140cm～165cm</td>
                        </tr>
                        <tr className="border-t border-[#e2e8f0] bg-[#f8fafc]">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">單板滑雪靴</th>
                          <td className="px-4 py-3 w-[180px]">22.5cm～31.5cm（1cm刻度）</td>
                        </tr>
                        <tr className="border-t border-[#e2e8f0] bg-white">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">雪鞋</th>
                          <td className="px-4 py-3 w-[180px]">22.5cm～28.0cm</td>
                        </tr>
                        <tr className="border-t border-[#e2e8f0] bg-[#f8fafc]">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">雪衣</th>
                          <td className="px-4 py-3 w-[180px]">SS～XXO *男女通用款</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <ul className="px-4 py-3 text-sm text-[#475569] list-disc pl-5">
                    <li>高階裝備的尺寸請洽詢工作人員。</li>
                  </ul>
                </div>

                <div className="rounded-sm bg-white overflow-hidden">
                  <div className="px-4 py-3 text-center text-lg font-semibold text-[#1f2937] font-display">
                    兒童
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-[#475569]">
                      <thead className="bg-[#dbe2f0] text-xs font-semibold tracking-[0.2em] uppercase text-[#1f2937] font-display">
                        <tr>
                          <th className="px-4 py-3 font-semibold">物品</th>
                          <th className="px-4 py-3 font-semibold w-[180px]">尺寸</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-t border-[#e2e8f0] bg-white">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">
                            滑雪板
                            <span className="mt-1 block text-xs font-normal text-[#94a3b8]">
                              ※不提供短滑雪板和Funski（一般長度滑雪板）<br />
                              ※不提供短板、Fun skis短板（130cm以下短版）、Fat skis寬板雙板、粉雪用雪板
                            </span>
                          </th>
                          <td className="px-4 py-3 w-[180px]">70cm～140cm</td>
                        </tr>
                        <tr className="border-t border-[#e2e8f0] bg-[#f8fafc]">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">滑雪靴</th>
                          <td className="px-4 py-3 w-[180px]">15.5cm～24.5cm</td>
                        </tr>
                        <tr className="border-t border-[#e2e8f0] bg-white">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">單板滑雪板</th>
                          <td className="px-4 py-3 w-[180px]">90cm～140cm</td>
                        </tr>
                        <tr className="border-t border-[#e2e8f0] bg-[#f8fafc]">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">單板滑雪靴</th>
                          <td className="px-4 py-3 w-[180px]">17.0cm～21.0cm（1cm刻度）</td>
                        </tr>
                        <tr className="border-t border-[#e2e8f0] bg-white">
                          <th className="px-4 py-3 font-semibold text-[#1f2937]">雪衣</th>
                          <td className="px-4 py-3 w-[180px]">90cm～140cm *男女通用款</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>

          </div>
          <div className="mt-10 mb-10 w-full max-w-3xl mx-auto px-6">
            <div className="relative w-full aspect-[5/3] md:aspect-auto md:min-h-0 overflow-hidden rounded-sm border border-[#e2e8f0] shadow-[0_18px_40px_rgba(15,23,42,0.12)]">
              <img loading="lazy" decoding="async"
                src="/Course/tomamu/course-tomamu-004-equipment.jpg"
                alt="SnowLand星野滑雪課程租借裝備"
                className="absolute inset-0 h-full w-full object-cover object-[center_40%]"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-[#0b1d2a]/55" />
              <div className="relative z-10 flex h-full w-full flex-col items-center justify-center px-6 py-8 md:px-10 md:py-10 text-center text-white">
                <p className="max-w-[16rem] text-base md:max-w-[24rem] md:text-lg font-semibold leading-relaxed">
                  凡訂購SnowLand星野滑雪課程，皆可加購教練協助租借服務，租對裝備學滑雪更有效率。
                </p>
                <SiteLink
                  to="/guides/packing-checklist"
                  className="mt-6 inline-flex items-center justify-center rounded-full border border-white/70 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white hover:text-[#0b1d2a]"
                >
                  查看滑雪裝備準備清單
                </SiteLink>
              </div>
            </div>
          </div>
        </section>
      )}

      {activeTab === "雪場托兒" && (
        <section className="bg-white text-[#1f2937]">
          <div className="max-w-6xl mx-auto px-6 py-14 space-y-12">
            <div className="max-w-6xl mx-auto">
              <motion.div
                className="text-center space-y-3"
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ amount: 0.4, once: true }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              >
                <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                  Nursery
                </p>
                <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                  GAO育兒&玩雪
                </h2>
                <p className="max-w-2xl mx-auto text-sm md:text-base leading-relaxed text-[#475569]">
                  從 5 個月大的嬰兒開始提供保育，3 歲起提供保育和玩雪相結合的項目。 請根據您的住宿方式使用 2 小時至 1 天的托兒服務。
                </p>
              </motion.div>
            </div>

            <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] items-start">
              <div className="relative w-full aspect-[3/2] overflow-hidden rounded-sm border border-[#e2e8f0]">
                <img loading="lazy" decoding="async"
                  src="/Course/tomamu/course-tomamu-007-nursery.jpeg"
                  alt="GAO育兒與玩雪托兒服務"
                  className="absolute inset-0 h-full w-full object-cover"
                  loading="lazy"
                />
              </div>
              <div className="space-y-6">
                {daycareServices.map((service) => (
                  <div key={service.title} className="border-b border-[#e2e8f0] pb-6 last:border-b-0 last:pb-0">
                    <div className="px-1 pb-3 text-lg font-semibold text-[#1f2937] font-display">
                      {service.title}
                    </div>
                    <div className="divide-y divide-[#e2e8f0] text-sm text-[#475569]">
                      {service.rows.map((row) => (
                        <div key={row[0]} className="grid grid-cols-[120px_minmax(0,1fr)] gap-4 px-1 py-3">
                          <div className="font-semibold text-[#1f2937]">{row[0]}</div>
                          <div className="leading-relaxed">{row[1]}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-6">
              <ul className="mx-auto max-w-2xl space-y-2 list-disc pl-5 text-sm text-[#475569] leading-relaxed">
                <li>提供網路預約，當日現場不接受報名採完全預約制。</li>
                <li>詳細價格及開放時間請參考官網資訊。</li>
                <li>
                  請參考星野TOMAMU官方網站預約資訊：
                  <a
                    href="https://www.snowtomamu.jp/winter/cn/hotel/nursery/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 text-[#2b5f8f] underline underline-offset-2"
                  >
                    https://www.snowtomamu.jp/winter/cn/hotel/nursery/
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </section>
      )}

      {activeTab === "交通" && (
        <section className="bg-white text-[#1f2937]">
          <div className="pt-14 pb-16 md:pt-14 md:pb-20 space-y-10 md:space-y-12">
            <div className="max-w-6xl mx-auto px-6 md:px-10">
              <div className="text-center space-y-3">
                <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                  Access
                </p>
                <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                  交通方式
                </h2>
              </div>
            </div>

            <div className="max-w-6xl mx-auto px-6 md:px-10">
              <motion.div
                className="text-center"
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ amount: 0.4, once: true }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              >
                <p className="max-w-xl mx-auto text-sm md:text-base text-[#475569] leading-relaxed">
                  位於北海道中央位置的星野Tomamu，是離新千歲機場最近的度假村，便利的交通方式，不一定要自駕也能輕鬆抵達。
                </p>
              </motion.div>
            </div>
            <div className="mt-10 divide-y divide-[#e2e8f0]">
              <section className="py-12">
                <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6 md:gap-12 lg:gap-16 items-start">
                  <div className="w-full">
                    <img loading="lazy" decoding="async"
                      src="/Course/tomamu/course-tomamu-access1.png"
                      alt="JR access map"
                      className="w-full h-auto"
                      loading="lazy"
                    />
                  </div>
                  <div className="px-6 md:px-10 lg:pr-16">
                    <div className="max-w-2xl text-[#2b2b2b] text-sm md:text-base leading-relaxed space-y-4">
                      <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
                        搭乘國鐵 (JR)
                      </h3>
                      <p className="text-sm md:text-base text-[#475569] leading-relaxed">
                        一日 10 班以上特急列車運行，Tomamu 站下車後約 5 分鐘可到度假村。
                      </p>
                      <div className="text-sm text-[#64748b] space-y-1">
                        <div>路線：特急 Super 十勝 / Super 大空</div>
                        <div>札幌 ⇔ 南千歲 ⇔ 占冠 ⇔ Tomamu ⇔ 帶廣</div>
                        <div>札幌 ⇔ 南千歲 ⇔ 占冠 ⇔ Tomamu ⇔ 帶廣 ⇔ 釧路</div>
                      </div>
                      <div className="space-y-2 text-xs text-[#94a3b8] leading-relaxed">
                        <p>2024/03/16 起，停靠 TOMAMU 的列車改為全車指定席。</p>
                        <p>JR TOMAMU 車站無售票處，建議事先購買回程車票。</p>
                        <p>※2024/04/01 起根室本線（富良野-新得）停止列車服務。</p>
                      </div>
                      <div className="space-y-2 text-sm text-[#64748b]">
                        <p>購票方式：</p>
                        <ul className="space-y-1">
                          <li>・JR 東日本「<a href="https://www.eki-net.com/personal/top/index" target="_blank" rel="noopener noreferrer" className="text-[#2b5f8f] underline underline-offset-4">eki-net</a>」（日文）</li>
                          <li>・<a href="https://www.jrhokkaido.co.jp/global/chinese/ticket/reservation/index.html" target="_blank" rel="noopener noreferrer" className="text-[#2b5f8f] underline underline-offset-4">JR 東日本網路訂票系統</a>（海外旅客）</li>
                          <li>・機場或有站員車站購買</li>
                          <li>・The Tower 內指定席售票機</li>
                        </ul>
                      </div>
                      <a
                        href="http://www.jrhokkaido.co.jp/network/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center text-sm font-semibold text-[#2b5f8f] underline underline-offset-4"
                      >
                        JR 北海道時刻/票價
                      </a>
                      <div className="pt-2">
                        <p className="font-semibold text-[#1f2937]">抵達 Tomamu 站後</p>
                        <p className="mt-2 text-sm text-[#64748b]">
                          每班特快列車抵達後皆有免費接駁巴士送往飯店，無需預約。
                        </p>
                        <img
                          src="/Course/tomamu/course-tomamu-access2.jpg"
                          alt="Tomamu JR station platform"
                          className="mt-3 w-1/2 rounded-sm"
                          loading="lazy"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </section>
              <section className="py-12">
                <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6 md:gap-12 lg:gap-16 items-start">
                  <div className="w-full md:h-[420px]">
                    <img loading="lazy" decoding="async"
                      src="/Course/index_map_hokkaido_tomamu.png"
                      alt="Tomamu driving map"
                      className="w-full h-full object-contain"
                      loading="lazy"
                    />
                  </div>
                  <div className="px-6 md:px-10 lg:pr-16">
                    <div className="max-w-2xl text-[#2b2b2b] text-sm md:text-base leading-relaxed space-y-4">
                      <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
                        開車前往
                      </h3>
                      <p className="text-sm md:text-base text-[#475569] leading-relaxed">
                        從 TOMAMU I.C. 到度假村約 5 分鐘。
                      </p>
                      <ul className="space-y-2 text-sm text-[#64748b]">
                        <li>札幌出發：約 100 分鐘（札幌北 I.C. → TOMAMU I.C.）</li>
                        <li>新千歲機場出發：約 90 分鐘（千歲東 I.C. → TOMAMU I.C.）</li>
                        <li>旭川機場出發：約 3 小時</li>
                        <li>富良野出發：約 90 分鐘</li>
                        <li>帶廣機場出發：約 60 分鐘（音更帶廣 I.C. → TOMAMU I.C.）</li>
                      </ul>
                      <div className="space-y-2 text-sm">
                        <a
                          href="https://www.snowtomamu.jp/winter/cn/access/considerations.php"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center text-sm font-semibold text-[#2b5f8f] underline underline-offset-4"
                        >
                          汽車加油注意事項
                        </a>
                        <a
                          href="https://www.snowtomamu.jp/winter/cn/access/considerations.php#carnavi"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center text-sm font-semibold text-[#2b5f8f] underline underline-offset-4"
                        >
                          旭川/富良野方向行車建議
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
              <section className="py-12">
                <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6 md:gap-12 lg:gap-16 items-start">
                  <div className="w-full md:h-[420px]">
                    <img loading="lazy" decoding="async"
                      src="/Course/tomamu/course-tomamu-access3.jpg"
                      alt="Bus route map"
                      className="w-full h-full object-contain"
                      loading="lazy"
                    />
                  </div>
                  <div className="px-6 md:px-10 lg:pr-16">
                    <div className="max-w-2xl text-[#2b2b2b] text-sm md:text-base leading-relaxed space-y-4">
                      <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
                        乘坐巴士
                      </h3>
                      <p className="text-sm md:text-base text-[#475569] leading-relaxed">
                        巴士路線請向北海道交通網絡公司查詢，詳情請見下方連結。
                      </p>
                      <a
                        href="https://www.snowtomamu.jp/bus_25w/index_cn.html"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center text-sm font-semibold text-[#2b5f8f] underline underline-offset-4"
                      >
                        直達巴士詳情
                      </a>
                      <a
                        href="https://www.snowtomamu.jp/bus_25w/index_cn.html"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block"
                      >
                        <img
                          src="/Course/tomamu/course-tomamu-access4.svg"
                          alt="Busliner banner"
                          className="mt-3 h-12"
                          loading="lazy"
                        />
                      </a>
                    </div>
                  </div>
                </div>
              </section>
            </div>
            <div className="max-w-4xl mx-auto px-6 md:px-10">
              <div className="mt-8 border-y border-[#e2e8f0] py-6">
                <h4 className="text-base font-semibold text-[#1f2937]">地址資訊</h4>
                <p className="mt-3 text-sm text-[#64748b] leading-relaxed">
                  Naka-Tomamu Shimukappu Yufutsu Hokkaido JAPAN
                  <br />
                  TEL: +81 167-58-1111
                  <br />
                  MAPCODE: 608 511 304*40
                </p>
                <a
                  href="https://www.google.co.jp/maps/place/%E6%98%9F%E9%87%8E%E3%83%AA%E3%82%BE%E3%83%BC%E3%83%88+%E3%83%88%E3%83%9E%E3%83%A0/@43.055027,142.632877,14z/data=!3m1!5s0x5f7361459aaf07cd:0xf441a79de5f77730!4m12!1m6!3m5!1s0x5f7361458599b125:0xda5c88a662e141dc!2z5pif6YeO44Oq44K-44O844OIIOODiOODnuODoA!8m2!3d43.063565!4d142.631368!3m4!1s0x5f7361458599b125:0xda5c88a662e141dc!8m2!3d43.063565!4d142.631368?hl=en"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 inline-flex items-center text-sm font-semibold text-[#2b5f8f] underline underline-offset-4"
                >
                  查看 Google Map
                </a>
              </div>
              <div className="mt-10">
                <div className="aspect-video w-full overflow-hidden rounded-sm bg-[#e2e8f0]">
                  <iframe
                    className="h-full w-full"
                    src="https://www.youtube.com/embed/06Gv40nv6SM?si=9Rt10DNl0vIurriJ"
                    title="YouTube video player"
                    frameBorder="0"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    referrerPolicy="strict-origin-when-cross-origin"
                    allowFullScreen
                    loading="lazy"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {activeTab !== "滑雪課程" && activeTab !== "雪道介紹" && activeTab !== "雪票" && activeTab !== "住宿" && activeTab !== "租借雪具" && activeTab !== "雪場托兒" && activeTab !== "交通" && null}
      <section className="bg-[#f7f8fa] text-[#1f2937] border-t border-[#e2e8f0]">
        <div className="max-w-6xl mx-auto px-6 py-16">
          <h2 className="text-2xl font-semibold text-[#1f2937] font-display text-center">
            查看其他雪場
          </h2>
          <div className="mt-6">
            <HokkaidoMap resorts={skiResorts} />
          </div>
        </div>
      </section>
      <SiteFooter />
    </div>
  );
}

export default TomamuCoursePage;
