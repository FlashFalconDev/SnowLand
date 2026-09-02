import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink, useLocation, useNavigate, useParams } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import HokkaidoMap from '../../components/site/HokkaidoMap';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import resortLegacyData from '../../data/site/resortLegacyData';
import skiResorts from '../../data/site/skiResorts';
import resortNavigation from '../../data/site/resortNavigation';

const slopeColors = {
  初級: "bg-[#9cccf4]",
  中級: "bg-[#f4d39c]",
  高級: "bg-[#f2b8b8]",
  壓雪: "bg-[#f3a23a]",
  非壓雪: "bg-[#6fc3b8]",
};

function ResortCoursePage() {
  const { resort, section } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const resortInfo = resortLegacyData[resort];
  const resortMeta = useMemo(
    () => skiResorts.find((item) => item.slug === resort),
    [resort]
  );
  const resortCount = resortNavigation.length;
  const resortIndex = resortNavigation.findIndex((item) => item.slug === resort);
  const activeResortIndex = resortIndex >= 0 ? resortIndex : 0;
  const previousResort = resortCount ? resortNavigation[(activeResortIndex - 1 + resortCount) % resortCount] : null;
  const nextResort = resortCount ? resortNavigation[(activeResortIndex + 1) % resortCount] : null;
  const [priceTab, setPriceTab] = useState("regular");
  const priceSwipeStartX = useRef(null);
  const heroSectionRef = useRef(null);
  const tabSectionRef = useRef(null);
  const [isHeroActive, setIsHeroActive] = useState(false);
  const liftScrollRef = useRef(null);
  const [liftScrollProgress, setLiftScrollProgress] = useState(0);
  const [liftThumbWidth, setLiftThumbWidth] = useState(30);
  const [showLiftScrollIndicator, setShowLiftScrollIndicator] = useState(false);
  const liftScrollTrackWidth = 160;
  const liftScrollThumbMinWidth = 24;
  const bookingUrl = "/booking";
  const fullDayOnlyPricing = {
    kamui: {
      discount: [15200, 18200, 21200, 24200, 27200, 30200],
      regular: [19200, 22200, 25200, 28200, 31200, 34200],
    },
    "mt-racey": {
      discount: [15200, 18200, 21200, 24200, 27200, 30200],
      regular: [19200, 22200, 25200, 28200, 31200, 34200],
    },
    rusutsu: {
      discount: [16000, 18500, 21000, 23500, 26000, 28500],
      regular: [19000, 21500, 24000, 26500, 29000, 31500],
    },
    teine: {
      discount: [13000, 15000, 17000, 19000, 21000, 23000],
      regular: [15000, 17000, 19000, 21000, 23000, 25000],
    },
    "sapporo-kokusai": {
      discount: [13000, 15000, 17000, 19000, 21000, 23000],
      regular: [15000, 17000, 19000, 21000, 23000, 25000],
    },
  };
  const isFullDayOnly = Boolean(fullDayOnlyPricing[resort]);
  const showHalfDay = resort !== "sahoro" && !isFullDayOnly;
  const regularPriceTableRows = [
    { label: "1人", full: 19200, half: 14400 },
    { label: "2人", full: 22200, half: 17400 },
    { label: "3人", full: 25200, half: 20400 },
    { label: "4人", full: 28200, half: 23400 },
    { label: "5人", full: 31200, half: 26400 },
    { label: "6人", full: 34200, half: 29400 },
  ];
  const sahoroPriceRows = {
    discount: [
      { label: "1人", full: 15200 },
      { label: "2人", full: 18200 },
      { label: "3人", full: 21200 },
      { label: "4人", full: 24200 },
      { label: "5人", full: 27200 },
      { label: "6人", full: 30200 },
    ],
    regular: [
      { label: "1人", full: 19200 },
      { label: "2人", full: 22200 },
      { label: "3人", full: 25200 },
      { label: "4人", full: 28200 },
      { label: "5人", full: 31200 },
      { label: "6人", full: 34200 },
    ],
  };
  const priceTableRows = resort === "sahoro"
    ? sahoroPriceRows[priceTab].map((row) => ({
      label: row.label,
      full: `NT$${row.full.toLocaleString("en-US")}`,
    }))
    : isFullDayOnly
      ? fullDayOnlyPricing[resort][priceTab].map((price, index) => ({
        label: `${index + 1}人`,
        full: `NT$${price.toLocaleString("en-US")}`,
      }))
      : regularPriceTableRows.map((row, index) => {
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
  const isPriceLanding = section === "price" && !location.state?.viaTabNav;
  const tabs = resortInfo?.tabs ?? [];
  const tabsBySlug = useMemo(
    () =>
      tabs.reduce((acc, tab) => {
        acc[tab.slug] = tab;
        return acc;
      }, {}),
    [tabs]
  );
  const tabOrder = ["price", "ski-slope", "rental", "lift", "accommodation", "access", "nursery"];
  const tabItems = useMemo(() => {
    const labelBySlug = tabs.reduce((acc, tab) => {
      acc[tab.slug] = tab.title;
      return acc;
    }, {});
    return tabOrder
      .filter((slug) => slug === "price" || labelBySlug[slug])
      .map((slug) => ({
        slug,
        label: slug === "price" ? "滑雪課程" : labelBySlug[slug],
      }));
  }, [tabs]);
  const slugToLabel = useMemo(
    () =>
      tabItems.reduce((acc, item) => {
        acc[item.slug] = item.label;
        return acc;
      }, {}),
    [tabItems]
  );
  const [activeTabSlug, setActiveTabSlug] = useState("price");

  useEffect(() => {
    if (tabItems.length === 0) return;
    if (!section) {
      setActiveTabSlug("price");
      return;
    }
    const matched = slugToLabel[section] ? section : "price";
    setActiveTabSlug(matched);
    if (slugToLabel[section] && tabSectionRef.current) {
      setTimeout(() => {
        tabSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }, [section, slugToLabel, tabItems]);

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

  useEffect(() => {
    if (activeTabSlug !== "lift") {
      return;
    }
    const target = liftScrollRef.current;
    if (!target) {
      return;
    }
    const updateScrollState = () => {
      const maxScrollLeft = target.scrollWidth - target.clientWidth;
      if (maxScrollLeft <= 1) {
        setShowLiftScrollIndicator(false);
        setLiftScrollProgress(0);
        setLiftThumbWidth(liftScrollTrackWidth);
        return;
      }
      setShowLiftScrollIndicator(true);
      setLiftScrollProgress(target.scrollLeft / maxScrollLeft);
      const idealWidth = (target.clientWidth / target.scrollWidth) * liftScrollTrackWidth;
      const nextWidth = Math.min(liftScrollTrackWidth, Math.max(liftScrollThumbMinWidth, idealWidth));
      setLiftThumbWidth(nextWidth);
    };
    updateScrollState();
    target.addEventListener("scroll", updateScrollState, { passive: true });
    window.addEventListener("resize", updateScrollState);
    return () => {
      target.removeEventListener("scroll", updateScrollState);
      window.removeEventListener("resize", updateScrollState);
    };
  }, [activeTabSlug]);

  if (!resortInfo) {
    return (
      <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
        <SiteHeader forceTransparent forceDarkText forceLogoColor />
        <main className="flex-1 flex items-center justify-center px-6 pt-32 pb-24">
          <p className="text-sm text-[#64748b]">內容載入中。</p>
        </main>
        <SiteFooter />
      </div>
    );
  }

  const heroImage = resortInfo.heroImage || resortMeta?.imagePlaceholder;
  const regionLabel = resortMeta?.region ? `北海道 | ${resortMeta.region}` : "北海道";
  const tags = resortInfo.tags.length > 0 ? resortInfo.tags : resortMeta?.tags ?? [];
  const activeTabContent = tabsBySlug[activeTabSlug];
  const tabHeaderMeta = {
    "ski-slope": { eyebrow: "SLOPE MAP", title: "雪道介紹" },
    rental: { eyebrow: "RENTAL", title: "租借雪具" },
    lift: { eyebrow: "LIFT TICKETS", title: "雪票價格" },
    accommodation: { eyebrow: "ACCOMMODATION", title: "住宿" },
    access: { eyebrow: "ACCESS", title: "交通" },
    nursery: { eyebrow: "NURSERY", title: "雪場托兒" },
  };
  const extractFirstMatch = (html, regex) => {
    if (!html) return null;
    const match = html.match(regex);
    return match ? match[1] : null;
  };
  const extractFirstImage = (html) =>
    extractFirstMatch(html, /<img loading="lazy" decoding="async"[^>]+src=["']([^"']+)["']/i);
  const extractAllMatches = (html, regex) => {
    if (!html) return [];
    const matches = [];
    let match;
    const re = new RegExp(regex.source, regex.flags.includes("g") ? regex.flags : `${regex.flags}g`);
    while ((match = re.exec(html))) {
      matches.push(match[1]);
    }
    return matches;
  };
  const extractFirstTable = (html) =>
    extractFirstMatch(html, /(<table[\s\S]*?<\/table>)/i);
  const extractFirstLink = (html) =>
    extractFirstMatch(html, /<a[^>]+href=["']([^"']+)["']/i);
  const extractTextSnippet = (html, maxLength = 160) => {
    if (!html) return "";
    const text = html
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (!text) return "";
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
  };
  const renderLegacyFallback = (html) =>
    html ? (
      <div className="mt-10">
        <div
          className="legacy-tab-content text-sm md:text-base text-[#475569] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </div>
    ) : null;
  const renderTabBody = () => {
    const legacyHtml = activeTabContent?.html ?? "";
    const firstImage = extractFirstImage(legacyHtml);
    const firstTable = extractFirstTable(legacyHtml);
    const firstLink = extractFirstLink(legacyHtml);
    const snippet = extractTextSnippet(legacyHtml, 220);
    const sentenceHints = snippet
      ? snippet.split("。").map((item) => item.trim()).filter(Boolean)
      : [];

    if (activeTabSlug === "ski-slope") {
      const resortStats = {
        kamui: [
          ["滑道數量", "25"],
          ["基地海拔", "150m"],
          ["最高點", "751m"],
          ["落差", "601m"],
          ["面積", "100 公頃"],
          ["年平均降雪", "8 公尺"],
          ["纜車數", "1 座 Gondola（纜車）、5 座固定雙人吊椅"],
        ],
      };
      const stats = resortStats[resort] || [
        ["滑道數量", "xxxx"],
        ["總滑行距離", "xxxx"],
        ["滑雪場滑道面積", "xxxx"],
        ["最長滑行距離", "xxxx"],
        ["最大坡度", "xxxx"],
        ["標高差", "xxxx"],
        ["纜車數", "xxxx"],
      ];
      const slopeCourses = [
        {
          no: "1",
          level: "初級",
          name: "Kids Garden",
          length: "100m",
          slope: "8°",
          intro: "小朋友與初學者專用的斜坡。可以開心地滑雪或玩雪橇。",
        },
        {
          no: "2",
          level: "初級",
          name: "First Timer",
          length: "900m",
          slope: "15°",
          intro:
            "位於山麓的寬廣初級雪道。從第4雙人吊椅（橘色纜車）左側下來後，沿著能感受纜車視野的路線一路滑到中心屋，是從平緩到稍陡都能練習的好路線。",
        },
        {
          no: "3",
          level: "初級",
          name: "Center",
          length: "800m",
          slope: "18°",
          intro:
            "位於山麓的寬廣初級雪道。從第4雙人吊椅（橘色纜車）右側下來後，最先展開的林間寬坡。雖然比「First Timer」稍陡，但很適合初學者進一步提升。",
        },
        {
          no: "4",
          level: "初級",
          name: "Family",
          length: "900m",
          slope: "18°",
          intro:
            "位於山麓的寬廣初級雪道。從第4雙人吊椅（橘色纜車）右側下來後稍微前進，就會一路連到中心屋。因為雪道寬闊，能安全滑行，也有助於提升滑雪或單板技巧。",
        },
        {
          no: "5",
          level: "初級",
          name: "Next Step",
          length: "4,000m",
          slope: "18°",
          intro:
            "全長4,000公尺，從山頂一路延伸到山麓的初級長距離雪道。可以欣賞山頂附近美麗的霧淞，經過林間路段、兩處中斜面，途中還會穿過纜車下方；下方區域也設有波浪地形，適合好好享受長線滑行。",
        },
        {
          no: "6",
          level: "初級",
          name: "The Rock",
          length: "300m",
          slope: "15°",
          intro:
            "可從「First Timer」或「Next Step」前往。這條路線會繞行 Kamui 最具代表性的巨石與鶴井橋。雪道較窄，滑行時請注意平衡。",
        },
        {
          no: "7",
          level: "初級",
          name: "Shirakaba 1",
          length: "800m",
          slope: "20°",
          intro:
            "這是為比賽設計、通過 FIS 與 SAJ 認證的雪道，也是從中腹「Shirakaba 2」延伸到山麓的下段路線。無論是比賽或旗門練習，都能感受到流暢的速度感。",
        },
        {
          no: "8",
          level: "中級",
          name: "Roller Coaster",
          length: "700m",
          slope: "18°",
          intro:
            "小朋友最喜歡的銀行彎道雪道，連續起伏的彎道刺激感十足，夏天也會作為登山車路線使用。滑行時要留意速度，不要衝出雪道或追撞前方滑行者。",
        },
        {
          no: "9",
          level: "初級",
          name: "Gold 1",
          length: "900m",
          slope: "18°",
          intro:
            "Kamui 主雪道「Gold」的山麓段，最大寬度可達150公尺。從第1雙人吊椅（紅色纜車）左側下來後，會展開林間路線。因為常有許多小朋友滑行，大人與中高級滑雪者請多留意周遭。",
        },
        {
          no: "10",
          level: "中級",
          name: "Gold 3",
          length: "900m",
          slope: "22°",
          intro:
            "Kamui 主雪道「Gold」的山頂段，可以欣賞美麗霧淞與壯闊景色。低溫下的緊實雪面很適合做出漂亮的切刃滑行。雪道末端會和左側的「Next Step」匯合，請注意。",
        },
        {
          no: "11",
          level: "中級",
          name: "Challenge Forest",
          length: "400m",
          slope: "20°",
          intro:
            "上手後的孩子可以第一次體驗的粉雪路線。從「Next Step」往右一點就能進入這片森林雪道，能感受深雪與起伏障礙，是體驗 Kamui 粉雪的入門挑戰。",
        },
        {
          no: "12",
          level: "中級",
          name: "Gold 2",
          length: "1,200m",
          slope: "30°",
          intro:
            "Kamui 主雪道「Gold」的中腹段，是相當受歡迎的路線。30 度的急斜面搭配最寬可達150公尺的開闊雪道，適合用動感的 carving turn 盡情享受滑行。",
        },
        {
          no: "13",
          level: "中級",
          name: "Shirakaba 2",
          length: "1,000m",
          slope: "28°",
          intro:
            "這是為比賽設計、通過 FIS 與 SAJ 認證的雪道，也是連接山麓「Shirakaba 1」的中腹段。連續急坡很適合競賽與旗門練習，但也容易在速度過快時跳起，請控制速度。",
        },
        {
          no: "14",
          level: "中級",
          name: "Royal Intermediate",
          length: "700m",
          slope: "28°",
          intro:
            "能奢侈享受山頂附近未壓雪的路線。滑在急斜面上的深雪非常過癮，是粉雪愛好者會喜歡的路線；但雪道末端會與初級道匯合，請注意控制速度。",
        },
        {
          no: "15",
          level: "中級",
          name: "Link",
          length: "1,100m",
          slope: "26°",
          intro:
            "連接山頂與第5雙人吊椅（海軍藍纜車）方向的路線，也是從第5雙人吊椅回到纜車區域的通道。請特別留意第5雙人吊椅的結束時間（15:00）；另外從吊椅乘車處無法回到纜車方向。",
        },
        {
          no: "16",
          level: "中級",
          name: "Slalom",
          length: "1,100m",
          slope: "28°",
          intro:
            "Kamui 最北側的壓雪雪道，雪質非常好。位在第5雙人吊椅山頂左側的坡面，雪道較窄但很有競速感。途中會與「Deep Powder」銜接，請留意第5雙人吊椅的結束時間（15:00）。",
        },
        {
          no: "17",
          level: "中級",
          name: "Logging Road",
          length: "1,300m",
          slope: "26°",
          intro:
            "把雪質極佳的北向林道直接做成了雪道。從第5雙人吊椅山頂往右延伸，是一條狹長路線，也常作為前往「Fresh Powder」、「Treerun」、「Bumps」等高級未壓雪路線的連接通道。請留意第5雙人吊椅的結束時間（15:00）。",
        },
        {
          no: "18",
          level: "進階",
          name: "Royal Advanced",
          length: "800m",
          slope: "28°",
          intro:
            "山頂附近的未壓雪路線，可以盡情享受深雪滑行的快感。這條路線非常適合粉雪愛好者，但末端會與初級道匯合，請務必控制速度。",
        },
        {
          no: "19",
          level: "進階",
          name: "Silky",
          length: "800m",
          slope: "30°",
          intro:
            "位於山頂附近的未壓雪雪包路線，是偏向 mogul 的高難度雪道。請依照自己的技術狀況滑行，務必注意安全。",
        },
        {
          no: "20",
          level: "進階",
          name: "Dynamic",
          length: "1,100m",
          slope: "35°",
          intro:
            "曾舉辦國體與全日本錦標賽的經典雪道，也是 Kamui 最陡的坡面。北向雪質緊實，適合做出豪快的大回轉；但斜度相當陡，請小心滑行。第5雙人吊椅結束時間為15:00。",
        },
        {
          no: "21",
          level: "進階",
          name: "Deep Powder",
          length: "800m",
          slope: "32°",
          intro:
            "可從第5雙人吊椅（海軍藍）旁的 gate 進入，是期間限定的林間深雪區。這裡能體驗到只有 Kamui 才有的優質粉雪，請盡情享受。第5雙人吊椅結束時間為15:00。",
        },
        {
          no: "22",
          level: "進階",
          name: "Fresh Powder",
          length: "600m",
          slope: "30°",
          intro:
            "可從「Logging Road」進入的期間限定林間深雪區。是能輕鬆享受 Kamui 粉雪魅力的路線。第5雙人吊椅結束時間為15:00。",
        },
        {
          no: "23",
          level: "進階",
          name: "Treerun",
          length: "1,200m",
          slope: "30°",
          intro:
            "從「Logging Road」旁的 gate 進入，往纜車山麓方向下降的未壓雪路線。路線中有樹木、倒木、大落差與凹凸，需要良好的深雪速度控制能力，請預留充足空間並安全滑行。",
        },
        {
          no: "24",
          level: "進階",
          name: "Bumps",
          length: "1,100m",
          slope: "30°",
          intro:
            "從「Logging Road」旁的 gate 進入，往纜車山麓方向下降的未壓雪路線。路線中有樹木、倒木、大落差與凹凸，需要良好的深雪速度控制能力，請預留充足空間並安全滑行。",
        },
        {
          no: "25",
          level: "進階",
          name: "Todomatsu",
          length: "800m",
          slope: "30°",
          intro:
            "從「Link」旁的 gate 進入，往纜車山麓方向下降的未壓雪路線。路線中有樹木、倒木、大落差與凹凸，需要良好的深雪速度控制能力，請預留充足空間並安全滑行。",
        },
        {
          no: "26",
          level: "進階",
          name: "Royal Powder",
          length: "400m",
          slope: "35°",
          intro:
            "能與纜車並行滑行、視野極佳的樹林路線，是為了紀念雪場 40 周年而開設的雪道。路線中有樹木、倒木、大落差與凹凸，請具備足夠的深雪速度控制能力並安全滑行。",
        },
      ];
      const slopeLevelColors = {
        初級: "#3aa85a",
        中級: "#2b74c7",
        進階: "#111111",
      };
      return (
        <div className="space-y-8">
          <div className="rounded-sm overflow-hidden border border-[#e2e8f0] bg-white shadow-sm">
            {firstImage ? (
              <img loading="lazy" decoding="async" src={firstImage} alt="雪道地圖" className="w-full h-auto object-contain" />
            ) : (
              <div className="aspect-[5/2] w-full bg-[#e2e8f0] flex items-center justify-center text-xs tracking-[0.4em] uppercase text-[#94a3b8]">
                Image Holder
              </div>
            )}
          </div>
          <div className="mt-6 bg-white">
            <div className="mx-auto w-full max-w-5xl border-b border-[#e2e8f0] text-sm text-[#475569]">
              {stats.map((row) => (
                <div
                  key={row[0]}
                  className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[180px_minmax(0,1fr)]"
                >
                  <div className="font-semibold text-[#1f2937]">{row[0]}</div>
                  <div>{row[1]}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-8">
            <div className="overflow-x-auto">
              <table className="mx-auto w-full max-w-5xl min-w-[980px] text-left text-[10px] md:text-sm">
                <thead className="bg-[#dbe2f0] text-[#1f2937]">
                  <tr className="text-[10px] font-semibold uppercase font-display tracking-[0.08em] md:text-xs md:tracking-[0.2em]">
                    <th className="px-1.5 md:px-4 py-2.5 text-right whitespace-nowrap w-[32px] md:w-[56px]">
                      編號
                    </th>
                    <th className="px-1.5 md:px-4 py-2.5 whitespace-nowrap w-[44px] md:w-[84px]">
                      Level
                    </th>
                    <th className="pl-1.5 pr-0.5 md:px-4 py-2.5 whitespace-nowrap">
                      雪道名稱
                    </th>
                    <th className="pl-0.5 pr-1 md:px-4 py-2.5 text-right whitespace-nowrap w-[54px] md:w-[100px]">
                      長度 (m)
                    </th>
                    <th className="px-1 md:px-4 py-2.5 text-right whitespace-nowrap w-[48px] md:w-[90px]">
                      斜率 (°)
                    </th>
                    <th className="px-1.5 md:px-4 py-2.5 w-[300px] md:w-[620px]">
                      雪道介紹
                    </th>
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
                      <td className="px-1.5 md:px-4 py-2.5 text-right font-semibold text-[#1f2937]">
                        <span style={{ color: levelColor }}>{course.no}</span>
                      </td>
                      <td className="px-1.5 md:px-4 py-2.5 font-semibold text-[#1f2937]">
                        <span style={{ color: levelColor }}>{course.level}</span>
                      </td>
                      <td className="pl-1.5 pr-0.5 md:px-4 py-2.5 font-semibold text-[#1f2937] whitespace-nowrap">
                        {course.name}
                      </td>
                      <td className="pl-0.5 pr-1 md:px-4 py-2.5 text-right whitespace-nowrap text-[#475569]">
                        {course.length}
                      </td>
                      <td className="px-1 md:px-4 py-2.5 text-right whitespace-nowrap text-[#475569]">
                        {course.slope}
                      </td>
                      <td className="px-1.5 md:px-4 py-2.5 text-[#475569] leading-relaxed whitespace-normal">
                        {course.intro}
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      );
    }

    if (activeTabSlug === "lift") {
      const ticketLocations = ["xxxx", "xxxx"];
      return (
        <div className="space-y-8">
          <div className="relative w-full aspect-[5/2] overflow-hidden rounded-sm border border-[#e2e8f0]">
            {firstImage ? (
              <img loading="lazy" decoding="async" src={firstImage} alt="雪票資訊" className="w-full h-full object-cover" />
            ) : (
              <>
                <div className="absolute inset-0 bg-gradient-to-br from-[#9fbad0] via-[#b7ccdc] to-[#dbe6ef]" />
                <div className="absolute inset-0 bg-[#0b1d2a]/30" />
                <div className="absolute inset-0 flex items-center justify-center text-xs tracking-[0.4em] uppercase text-white/40">
                  Image Holder
                </div>
              </>
            )}
          </div>
          <div className="text-center">
            <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
              網路販售價格
            </h3>
          </div>
          <div className="overflow-x-auto thin-scrollbar" ref={liftScrollRef}>
            {firstTable ? (
              <div
                className="legacy-tab-content text-sm md:text-base text-[#475569] leading-relaxed"
                dangerouslySetInnerHTML={{ __html: firstTable }}
              />
            ) : (
              <table className="w-full min-w-[720px] text-left text-sm text-[#475569]">
                <thead className="bg-[#dbe2f0] text-xs font-semibold tracking-[0.2em] uppercase text-[#1f2937] font-display">
                  <tr>
                    <th className="px-4 py-3 font-semibold">票券類型</th>
                    <th className="px-4 py-3 text-center font-semibold">成人</th>
                    <th className="px-4 py-3 text-center font-semibold">兒童</th>
                    <th className="px-4 py-3 font-semibold w-[220px] md:w-[280px]">備註</th>
                  </tr>
                </thead>
                <tbody>
                  {["xxxx", "xxxx", "xxxx"].map((item, index) => (
                    <tr
                      key={`${item}-${index}`}
                      className={`border-t border-[#e2e8f0] ${
                        index % 2 === 0 ? "bg-white" : "bg-[#f8fafc]"
                      }`}
                    >
                      <td className="px-4 py-3 font-semibold text-[#1f2937]">xxxx</td>
                      <td className="px-4 py-3 text-center">xxxx</td>
                      <td className="px-4 py-3 text-center">xxxx</td>
                      <td className="px-4 py-3">xxxx</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {showLiftScrollIndicator && (
            <div className="flex justify-center md:hidden">
              <div
                className="relative h-px bg-[#e2e8f0]"
                style={{ width: `${liftScrollTrackWidth}px` }}
              >
                <div
                  className="absolute left-0 -top-px h-0.5 bg-[#1f2937]"
                  style={{
                    width: `${liftThumbWidth}px`,
                    transform: `translateX(${liftScrollProgress * (liftScrollTrackWidth - liftThumbWidth)}px)`,
                  }}
                />
              </div>
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-[180px_minmax(0,1fr)] text-sm text-[#475569] border-t border-b border-[#e2e8f0] py-6">
            <div className="font-semibold text-[#1f2937]">販售地點</div>
            <ul className="space-y-1">
              {ticketLocations.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          </div>
          {resort === "kamui" ? null : renderLegacyFallback(legacyHtml)}
        </div>
      );
    }

    if (activeTabSlug === "rental") {
      const locationLines = sentenceHints.length > 0 ? sentenceHints.slice(0, 3) : ["xxxx", "xxxx"];
      return (
        <div className="space-y-8">
          <div className="rounded-sm overflow-hidden border border-[#e2e8f0] bg-white shadow-sm">
            {firstImage ? (
              <img loading="lazy" decoding="async" src={firstImage} alt="租借雪具" className="w-full h-auto object-contain" />
            ) : (
              <div className="aspect-[5/2] w-full bg-[#e2e8f0] flex items-center justify-center text-xs tracking-[0.4em] uppercase text-[#94a3b8]">
                Image Holder
              </div>
            )}
          </div>
          <div className="text-sm text-[#475569]">
            <div className="px-1 pb-3 text-lg font-semibold text-[#1f2937] font-display">
              租借地點：
            </div>
            <ul className="space-y-1 px-1">
              {locationLines.map((line, index) => (
                <li key={`${line}-${index}`}>{line || "xxxx"}</li>
              ))}
            </ul>
          </div>
          <ul className="space-y-2 text-sm text-[#475569] list-disc pl-5">
            <li>費用及營業時間：xxxx</li>
            <li>預約方式：xxxx</li>
          </ul>

          <div className="space-y-6">
            <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display text-center">
              裝備尺寸
            </h3>
            <div className="grid gap-6 lg:grid-cols-2">
              {["成人", "兒童"].map((title) => (
                <div key={title} className="rounded-sm bg-white overflow-hidden">
                  <div className="px-4 py-3 text-center text-lg font-semibold text-[#1f2937] font-display">
                    {title}
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
                        {["滑雪板", "滑雪靴", "雪衣"].map((item, index) => (
                          <tr
                            key={`${title}-${item}`}
                            className={`border-t border-[#e2e8f0] ${
                              index % 2 === 0 ? "bg-white" : "bg-[#f8fafc]"
                            }`}
                          >
                            <th className="px-4 py-3 font-semibold text-[#1f2937]">{item}</th>
                            <td className="px-4 py-3 w-[180px]">xxxx</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {firstTable && (
            <div className="overflow-x-auto">
              <div
                className="legacy-tab-content text-sm md:text-base text-[#475569] leading-relaxed"
                dangerouslySetInnerHTML={{ __html: firstTable }}
              />
            </div>
          )}
          <div className="mt-10 w-full">
            <div className="relative w-full min-h-[320px] overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-[#8fb9d6] via-[#a7c7dd] to-[#d7e3ed]" />
              <div className="absolute inset-0 bg-[#0b1d2a]/35" />
              <div className="absolute inset-0 flex items-center justify-center text-xs tracking-[0.4em] uppercase text-white/35">
                Image Holder
              </div>
              <div className="relative z-10 mx-auto flex min-h-[320px] max-w-3xl flex-col items-center justify-center px-6 text-center text-white">
                <p className="text-base md:text-lg font-semibold leading-relaxed">
                  訂購課程可加購教練協助租借服務，租對裝備學滑雪更有效率。
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
          {resort === "kamui" ? null : renderLegacyFallback(legacyHtml)}
          {resort === "teine" && (
            <div className="mt-10 mb-10 w-full max-w-3xl mx-auto px-6">
              <div className="relative w-full aspect-[5/3] md:aspect-auto md:min-h-0 overflow-hidden rounded-sm border border-[#e2e8f0] shadow-[0_18px_40px_rgba(15,23,42,0.12)]">
                <img loading="lazy" decoding="async"
                  src="/course/teine/course-teine-equipment.jpg"
                  alt="SnowLand手稻滑雪課程租借裝備"
                  className="absolute inset-0 h-full w-full object-cover object-[center_40%]"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-[#0b1d2a]/55" />
                <div className="relative z-10 flex h-full w-full flex-col items-center justify-center px-6 py-8 md:px-10 md:py-10 text-center text-white">
                  <p className="max-w-[16rem] text-base md:max-w-[24rem] md:text-lg font-semibold leading-relaxed">
                    凡訂購SnowLand手稻滑雪課程，皆可加購教練協助租借服務，租對裝備學滑雪更有效率。
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
          )}
        </div>
      );
    }

    if (activeTabSlug === "accommodation") {
      if (resort === "kamui") {
        const kamuiAccommodations = [
          {
            title: "旭川市區飯店旅社",
            description:
              "前往神居滑雪場的旅客，建議以旭川市區作為住宿據點。市區生活機能完整，滑雪後可直接回到飯店休息，也方便安排用餐與補給。",
            image: firstImage || "https://www.kamui-skilinks.com/wp/wp-content/uploads/2013/10/en_18.jpg",
            imageAlt: "旭川市區住宿示意",
            ctaUrl: firstLink || "http://www.asahikawa-tourism.com/",
            ctaLabel: "查看旭川住宿資訊",
          },
        ];

        return (
          <section className="bg-white text-[#1f2937]">
            <div className="pt-14 pb-16 md:pt-14 md:pb-20 space-y-10 md:space-y-12">
              <div className="max-w-6xl mx-auto px-6 md:px-10">
                <div className="text-center space-y-3">
                  <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                    Accommodation
                  </p>
                  <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                    旭川市區住宿選擇
                  </h2>
                  <p className="max-w-xl mx-auto text-sm md:text-base leading-relaxed text-[#475569]">
                    神居滑雪場建議以旭川市區作為住宿據點，車程便利、機能完整，適合把滑雪與市區用餐、採買一起安排。
                  </p>
                </div>
              </div>

              <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 md:px-8 space-y-10 md:space-y-12">
                {kamuiAccommodations.map((hotel, index) => {
                  const isReversed = index % 2 === 1;

                  return (
                    <div
                      key={hotel.title}
                      className={`grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6 md:gap-12 lg:gap-16 items-center ${
                        isReversed ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]" : ""
                      }`}
                    >
                      <div className={`w-full h-72 md:h-[420px] ${isReversed ? "lg:order-2" : ""}`}>
                        <img
                          src={hotel.image}
                          alt={hotel.imageAlt}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      </div>
                      <div className={`px-0 md:px-4 ${isReversed ? "lg:order-1" : ""}`}>
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
                              {hotel.ctaLabel}
                            </a>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        );
      }

      if (resort === "sapporo-kokusai") {
        const sapporoAccommodations = [
          {
            title: "OMO3 札幌薄野",
            description:
              "位於札幌中心繁華街薄野，適合把滑雪、逛街與美食行程排在同一趟。從市區出發前往札幌國際也更方便。",
            image:
              "https://land110602.com/wp-content/uploads/2023/07/db73aa7f76faff1f24165d786e308f5deddea633.47.9.26.3.jpg",
            imageAlt: "OMO3 札幌薄野外觀",
            ctaUrl: "https://hoshinoresorts.com/zh_tw/hotels/omo3sapporosusukino/",
            ctaLabel: "查詢空房",
          },
          {
            title: "定山溪溫泉",
            description:
              "適合把滑雪後行程延伸到溫泉放鬆，白天滑雪、晚上泡湯，行程節奏更完整。",
            image: "/Course/sapporo-kokusai/sapporo-kokusai-accommodation-002.jpg",
            imageAlt: "定山溪溫泉",
            ctaUrl: "https://jozankei.jp/tw/hotel/",
            ctaLabel: "查看溫泉區住宿",
          },
        ];

        return (
          <section className="bg-white text-[#1f2937]">
            <div className="pt-0 pb-12 md:pt-0 md:pb-16 space-y-4 md:space-y-6">
              <div className="max-w-5xl mx-auto px-6 md:px-8 text-center">
                <p className="max-w-2xl mx-auto text-sm md:text-base leading-relaxed text-[#475569]">
                  札幌國際滑雪場可選擇入住札幌市區或定山溪溫泉，交通便利、車程約 1 小時內。白天滑雪、晚上回市區或泡湯放鬆，是相當受歡迎的住宿安排。
                </p>
              </div>

              <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 md:px-8 space-y-10 md:space-y-12">
                {sapporoAccommodations.map((hotel, index) => {
                  const isReversed = index % 2 === 1;

                  return (
                    <div
                      key={hotel.title}
                      className={`grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6 md:gap-12 lg:gap-16 items-center ${
                        isReversed ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]" : ""
                      }`}
                    >
                      <div className={`w-full h-72 md:h-[420px] ${isReversed ? "lg:order-2" : ""}`}>
                        {hotel.image ? (
                          <img
                            src={hotel.image}
                            alt={hotel.imageAlt}
                            className="w-full h-full object-cover"
                            loading="lazy"
                          />
                        ) : (
                          <div className="relative h-full w-full overflow-hidden bg-gradient-to-br from-[#c7d4e4] via-[#dfe8f1] to-[#f3f7fb]">
                            <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(43,95,143,0.22),transparent_35%),radial-gradient(circle_at_80%_30%,rgba(11,29,42,0.08),transparent_30%),linear-gradient(135deg,rgba(255,255,255,0.45),rgba(255,255,255,0))]" />
                            <div className="absolute inset-0 flex flex-col items-center justify-center px-6 text-center">
                              <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#64748b] font-display">
                                HOT SPRING AREA
                              </p>
                              <h3 className="mt-3 text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
                                {hotel.title}
                              </h3>
                              <p className="mt-3 max-w-sm text-sm md:text-base text-[#475569] leading-relaxed">
                                {hotel.description}
                              </p>
                            </div>
                          </div>
                        )}
                      </div>
                      <div className={`px-0 md:px-4 ${isReversed ? "lg:order-1" : ""}`}>
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
                              {hotel.ctaLabel}
                            </a>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        );
      }

      const fallbackTitle = resortMeta?.nameChinese || "雪場";
      const cardDescription = snippet || "xxxx";
      const accommodationImages = extractAllMatches(legacyHtml, /<img loading="lazy" decoding="async"[^>]+src=["']([^"']+)["']/i);
      const accommodationLinks = extractAllMatches(legacyHtml, /<a[^>]+href=["']([^"']+)["']/i);
      const sentencePool = snippet
        ? snippet.split("。").map((item) => item.trim()).filter(Boolean)
        : [];
      const cardCount = Math.max(1, accommodationImages.length);
      return (
        <div className="space-y-10">
          {Array.from({ length: cardCount }).map((_, index) => (
            <div
              key={`stay-${index}`}
              className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] items-center rounded-sm border border-[#e2e8f0] bg-white shadow-sm overflow-hidden"
            >
              <div className="w-full h-full min-h-[240px] bg-[#e2e8f0]">
                {accommodationImages[index] ? (
                  <img loading="lazy" decoding="async"
                    src={accommodationImages[index]}
                    alt="住宿推薦"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="h-full w-full flex items-center justify-center text-xs tracking-[0.4em] uppercase text-[#94a3b8]">
                    Image Holder
                  </div>
                )}
              </div>
              <div className="px-6 py-6 space-y-4">
                <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
                  {fallbackTitle} 住宿推薦 {index === 0 ? "" : "xxxx"}
                </h3>
                <p className="text-sm md:text-base text-[#475569] leading-relaxed">
                  {sentencePool[index] || (index === 0 ? cardDescription : "xxxx")}
                </p>
                <div>
                  <a
                    href={accommodationLinks[index] || (index === 0 && firstLink ? firstLink : "#")}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-6 py-2 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
                  >
                    查詢空房
                  </a>
                </div>
              </div>
            </div>
          ))}
          {renderLegacyFallback(legacyHtml)}
        </div>
      );
    }

    if (activeTabSlug === "access") {
      const accessImages = extractAllMatches(legacyHtml, /<img loading="lazy" decoding="async"[^>]+src=["']([^"']+)["']/i);
      const accessTitles = ["搭乘國鐵 (JR)", "開車前往", "乘坐巴士"];
      const accessNotes = [
        snippet || "xxxx",
        "xxxx",
        "xxxx",
      ];
      return (
        <div className="space-y-10">
          <p className="max-w-2xl mx-auto text-sm md:text-base text-[#475569] leading-relaxed text-center">
            {snippet || "xxxx"}
          </p>
          <div className="divide-y divide-[#e2e8f0]">
            {accessTitles.map((title, index) => (
              <section key={title} className="py-10">
                <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6 md:gap-12 lg:gap-16 items-start">
                  <div className="w-full">
                    {accessImages[index] ? (
                      <img loading="lazy" decoding="async"
                        src={accessImages[index]}
                        alt={`${title} 交通示意`}
                        className="w-full h-auto object-contain"
                      />
                    ) : (
                      <div className="aspect-[5/2] w-full bg-[#e2e8f0] flex items-center justify-center text-xs tracking-[0.4em] uppercase text-[#94a3b8]">
                        Image Holder
                      </div>
                    )}
                  </div>
                  <div className="px-6 md:px-10 lg:pr-16">
                    <div className="max-w-2xl text-[#2b2b2b] text-sm md:text-base leading-relaxed space-y-4">
                      <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
                        {title}
                      </h3>
                      <p className="text-sm md:text-base text-[#475569] leading-relaxed">
                        {accessNotes[index] || "xxxx"}
                      </p>
                      <ul className="space-y-2 text-sm text-[#64748b]">
                        <li>xxxx</li>
                        <li>xxxx</li>
                        <li>xxxx</li>
                      </ul>
                      <a
                        href={firstLink || "#"}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center text-sm font-semibold text-[#2b5f8f] underline underline-offset-4"
                      >
                        交通資訊連結
                      </a>
                    </div>
                  </div>
                </div>
              </section>
            ))}
          </div>
          {renderLegacyFallback(legacyHtml)}
        </div>
      );
    }

    if (activeTabSlug === "nursery") {
      const serviceRows = [
        ["服務內容", "xxxx"],
        ["適合年齡", "xxxx"],
        ["營業時間", "xxxx"],
        ["費用", "xxxx"],
      ];
      return (
        <div className="space-y-10">
          <div className="text-center space-y-3">
            <h3 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
              xxxx
            </h3>
            <p className="max-w-2xl mx-auto text-sm md:text-base leading-relaxed text-[#475569]">
              xxxx
            </p>
          </div>
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] items-start">
            <div className="relative w-full aspect-[3/2] overflow-hidden rounded-sm border border-[#e2e8f0]">
              {firstImage ? (
                <img loading="lazy" decoding="async" src={firstImage} alt="雪場托兒" className="w-full h-full object-cover" />
              ) : (
                <>
                  <div className="absolute inset-0 bg-gradient-to-br from-[#9fbad0] via-[#b7ccdc] to-[#dbe6ef]" />
                  <div className="absolute inset-0 bg-[#0b1d2a]/30" />
                  <div className="absolute inset-0 flex items-center justify-center text-xs tracking-[0.4em] uppercase text-white/40">
                    Image Holder
                  </div>
                </>
              )}
            </div>
            <div className="space-y-6">
              {["方案一", "方案二"].map((title) => (
                <div key={title} className="border-b border-[#e2e8f0] pb-6 last:border-b-0 last:pb-0">
                  <div className="px-1 pb-3 text-lg font-semibold text-[#1f2937] font-display">
                    {title}
                  </div>
                  <div className="divide-y divide-[#e2e8f0] text-sm text-[#475569]">
                    {serviceRows.map((row) => (
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
            <div className="relative mx-auto w-full max-w-2xl overflow-hidden rounded-sm border border-[#e2e8f0]">
              <div className="relative aspect-[3/2] w-full">
                <div className="absolute inset-0 bg-gradient-to-br from-[#9fbad0] via-[#b7ccdc] to-[#dbe6ef]" />
                <div className="absolute inset-0 bg-[#0b1d2a]/25" />
                <div className="absolute inset-0 flex items-center justify-center text-xs tracking-[0.4em] uppercase text-white/40">
                  Image Holder
                </div>
              </div>
            </div>
            <p className="mt-4 text-center text-sm text-[#94a3b8] leading-relaxed">
              預約方式：xxxx
            </p>
          </div>
          {renderLegacyFallback(legacyHtml)}
        </div>
      );
    }

    return renderLegacyFallback(legacyHtml);
  };

  return (
    <div className="min-h-screen bg-[#0b1d2a] text-white flex flex-col">
      <SiteHeader forceTransparent />
      <main className="flex-1 w-full">
        {!isPriceLanding && (
          <section ref={heroSectionRef} className="relative overflow-hidden bg-[#f3f0ea] text-[#1f2937]">
          <div className="absolute inset-0">
            {heroImage && (
              <div
                className="h-full w-full bg-cover bg-center"
                style={{ backgroundImage: `url(${heroImage})` }}
              />
            )}
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
          <div className="relative max-w-6xl mx-auto px-4 pt-24 pb-28 sm:px-6 sm:pb-20 md:px-6 md:pt-28 md:pb-20">
            <div className="grid gap-10 lg:grid-cols-[1fr_1.1fr] items-stretch">
              <div className="flex flex-col justify-center text-center lg:text-left items-center lg:items-start">
                <p className="text-xs font-semibold tracking-[0.35em] uppercase text-white/80 font-display drop-shadow-sm">
                  {resortMeta?.nameEnglish ?? "SKI RESORT"}
                </p>
                <h1 className="text-3xl md:text-4xl font-semibold tracking-wide font-display leading-tight text-white drop-shadow-sm">
                  {resort === "sahoro" ? "佐幌滑雪場" : resortMeta?.nameChinese ?? resort}
                </h1>
                {resortInfo.description && (
                  <p className="mt-6 text-base md:text-lg text-white/85 max-w-xl leading-relaxed drop-shadow-sm">
                    {resortInfo.description}
                  </p>
                )}
                <SiteLink
                  to="/booking"
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
                </SiteLink>
              </div>

              <div className="relative min-h-[360px]">
                <div className="relative z-10 flex h-full items-center justify-center p-6 lg:justify-end">
                  <div className="w-full max-w-md rounded-sm bg-[#1b1f24]/30 backdrop-blur-md px-6 py-6 text-white shadow-[0_20px_45px_rgba(15,23,42,0.35)]">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.3em] text-[#f3a23a]">
                      <span className="h-2 w-2 rounded-full bg-[#f3a23a]" />
                      <span>{regionLabel}</span>
                    </div>
                    <div className="mt-4 text-3xl font-semibold tracking-wide font-display">
                      {resortMeta?.nameChinese ?? resort}
                    </div>
                    <div className="mt-6 grid grid-cols-2 gap-4 text-xs text-white/80">
                      <div>
                        <p className="uppercase tracking-[0.3em] text-white/60">特色</p>
                        <ul className="mt-2 space-y-1 text-sm font-semibold text-white">
                          {tags.map((tag) => (
                            <li key={tag}>{tag}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <p className="uppercase tracking-[0.3em] text-white/60">雪道分級</p>
                        <div className="mt-3 space-y-3 text-xs text-white/85">
                          {resortInfo.slopes.map((item) => (
                            <div key={item.label}>
                              <div className="flex items-center justify-between">
                                <span className="font-semibold">{item.label}</span>
                                <span className="text-white/70">{item.value}%</span>
                              </div>
                              <div className="mt-1 h-2 w-full overflow-hidden rounded-sm bg-white/20">
                                <div
                                  className={`h-full animate-[progress-fill_900ms_ease-out_forwards] ${
                                    slopeColors[item.label] || "bg-white"
                                  }`}
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
                <SiteLink
                  to="/booking"
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
                </SiteLink>
              </div>
            </div>
          </div>
          </section>
        )}

        <section
          ref={tabSectionRef}
          className={`bg-white text-[#1f2937] border-t border-[#e2e8f0] ${
            isPriceLanding ? "pt-24 md:pt-28" : ""
          }`}
        >
          <div className="max-w-6xl mx-auto px-6 py-10">
            <div className="border-b border-[#e2e8f0]">
              <div className="flex flex-wrap items-center justify-center gap-12 md:gap-16 text-base md:text-lg font-semibold text-[#6b7280] font-display">
                {tabItems.map((item) => {
                  const isActive = item.slug === activeTabSlug;
                  return (
                    <button
                      key={item.slug}
                      type="button"
                      onClick={() => {
                        setActiveTabSlug(item.slug);
                        navigate(`/course/${resort}/${item.slug}`, { state: { viaTabNav: true } });
                        if (tabSectionRef.current) {
                          setTimeout(() => {
                            tabSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
                          }, 50);
                        }
                      }}
                      className={`relative pb-4 transition-colors duration-200 group ${
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
                    </button>
                  );
                })}
              </div>
            </div>

            {activeTabSlug === "price" ? (
              <div className="mt-10 space-y-6">
                <section className="bg-white text-[#1f2937]">
                  <div className="max-w-6xl mx-auto px-6 py-14 space-y-12">
                    <div className="text-center space-y-3">
                      <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                        {resortMeta?.nameEnglish ? `${resortMeta.nameEnglish} COURSE PRICING` : "SKI COURSE PRICING"}
                      </p>
                      <h2 className="text-2xl font-semibold tracking-wide font-display">
                        {resortMeta?.nameChinese ? `${resortMeta.nameChinese}課程價目表` : "滑雪課程價目表"}
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
                          className={`grid ${showHalfDay ? "grid-cols-3" : "grid-cols-2"} text-sm font-semibold font-display ${
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
                          {showHalfDay && (
                            <div className="px-4 py-3 text-center">
                              半天3hrs
                            </div>
                          )}
                        </div>
                          <div className="text-sm text-[#475569]">
                            {priceTableRows.map((row, index) => (
                              <div
                                key={row.label}
                                className={`grid ${showHalfDay ? "grid-cols-3" : "grid-cols-2"}`}
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
                                {showHalfDay && (
                                  <div
                                    className="px-4 py-3 text-center text-base"
                                    style={{ color: priceTextColor }}
                                  >
                                    {row.half}
                                  </div>
                                )}
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
                          <div className="flex h-full flex-col justify-center space-y-4 px-4 py-5 text-left">
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

                  <div className="bg-[#e9eef3] w-screen relative left-1/2 right-1/2 -mx-[50vw]">
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
              </div>
            ) : activeTabContent ? (
              <div
                className={
                  resort === "kamui" && activeTabSlug === "accommodation"
                    ? "space-y-0"
                    : activeTabSlug === "accommodation"
                      ? "mt-4 space-y-4"
                      : "mt-10 space-y-10"
                }
              >
                {!(resort === "kamui" && activeTabSlug === "accommodation") && (
                  <div className="text-center space-y-3">
                    <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                      {tabHeaderMeta[activeTabSlug]?.eyebrow || "RESORT INFO"}
                    </p>
                    <h2 className="text-2xl font-semibold tracking-wide font-display">
                      {tabHeaderMeta[activeTabSlug]?.title || activeTabContent.title}
                    </h2>
                  </div>
                )}
                {renderTabBody()}
              </div>
            ) : null}
          </div>
        </section>
      </main>
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

export default ResortCoursePage;
