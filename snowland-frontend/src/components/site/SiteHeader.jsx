import React, { useEffect, useRef, useState } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import SiteLink from './SiteLink';
import { AnimatePresence, motion } from 'framer-motion';
import logo from '../../assets/site/logo-white.png';
import { homepageAssetBase } from '../../data/site/assetPaths';
import { faqLink } from '../../data/site/navigationLinks';

function CartIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
      <path
        d="M3 5h2l2.2 9.3a2 2 0 0 0 2 1.6h7.9a2 2 0 0 0 1.9-1.4L21 8H7.1"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="19" r="1.6" fill="currentColor" />
      <circle cx="17" cy="19" r="1.6" fill="currentColor" />
    </svg>
  );
}

function MemberAvatarIcon({ src }) {
  if (src) {
    return <img loading="lazy" decoding="async" src={src} alt="" className="h-full w-full object-cover" />;
  }

  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
      <circle cx="12" cy="8.5" r="3.3" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M5 19c1.1-3.2 3.8-5 7-5s5.9 1.8 7 5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SiteHeader({
  forceTransparent = false,
  forceDarkText = false,
  forceLogoColor = false,
  memberAuthenticated = false,
  memberAvatarSrc = "",
  hideBookingCta = false,
  forceCompact = false,
}) {
  const logoColor = `${homepageAssetBase}/LOGO_250903_color.png`;
  const bookingUrl = "/booking";
  const [isScrollCompact, setIsScrollCompact] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.scrollY > 80;
  });
  const [isLangOpen, setIsLangOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [openMobileSection, setOpenMobileSection] = useState(null);
  const [openDesktopSection, setOpenDesktopSection] = useState(null);
  const langMenuRef = useRef(null);
  const location = useLocation();
  const pathParts = location.pathname.replace(/\/+$/, '').split('/');
  const isHome = location.pathname === "/" || (pathParts.length === 2 && pathParts[0] === '');
  const trackCompactState = forceTransparent || isHome;
  const isNavCompact = forceCompact || (trackCompactState ? isScrollCompact : true);
  const useDarkText = isNavCompact || forceDarkText;
  const MotionHeader = motion.header;
  const MotionDiv = motion.div;
  const MotionAside = motion.aside;

  useEffect(() => {
    if (!trackCompactState) {
      return undefined;
    }

    const onScroll = () => {
      setIsScrollCompact(window.scrollY > 80);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [trackCompactState]);

  useEffect(() => {
    const onClickOutside = (event) => {
      if (langMenuRef.current && !langMenuRef.current.contains(event.target)) {
        setIsLangOpen(false);
      }
    };
    if (isLangOpen) {
      document.addEventListener("mousedown", onClickOutside);
    }
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [isLangOpen]);

  const navItems = [
    { label: "滑雪課程" },
    { label: "海外攝影" },
    { label: "滑雪攻略" },
    { label: "最新消息" },
    { label: "關於Snowland" },
    { label: "會員專區", variant: "outline", to: "/membership" }
  ];
  const memberItem = { label: "會員專區" };
  const visibleNavItems = memberAuthenticated
    ? navItems.filter((item) => item.label !== memberItem.label)
    : navItems;
  const mobileNavItems = visibleNavItems.filter((item) => item.label !== memberItem.label);
  const mobileSubItems = {
    滑雪課程: [
      { label: "星野滑雪課程", to: "/course/tomamu" },
      { label: "野雪嚮導", to: "/course/off-piste-guide" },
      { label: "北海道其他雪場課程", to: "/course/hokkaido" },
      { label: "預約流程", to: "/course/how-to-book" },
    ],
    海外攝影: [
      { label: "冬季雪地攝影", to: "/photography/winter" },
      { label: "夏季旅拍攝影", to: "/photography/summer" },
      { label: "攝影作品", to: "/Gallery" },
      { label: "預約攝影流程", to: "/photography/how-to-book" },
    ],
    滑雪攻略: [
      { label: "雪場攻略", to: "/guides/skiresorts" },
      { label: "行前須知", to: "/guides/preparation" },
      { label: "滑雪裝備", to: "/guides/packing-checklist" },
      { label: "常見問題", to: faqLink },
      { label: "滑雪精選文章", to: "/guides" },
    ],
    最新消息: [
      { label: "限定優惠", to: "/specialoffers" },
      { label: "最新消息", to: "/news" },
    ],
    關於Snowland: [
      { label: "滑雪學校介紹", to: "/about" },
      { label: "教練團隊", to: "/coach" },
      { label: "成為教練", to: "/join-us" },
      { label: "聯絡我們", to: "/contact" },
    ],
  };
  const headerControlClass = useDarkText ? "text-[#1f2937]" : "text-white";

  return (
    <>
      <MotionHeader
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className={`fixed top-0 left-0 w-full box-border z-50 flex justify-between items-center transition-all duration-300 ${
          isNavCompact
            ? "bg-white/95 text-[#1f2937] shadow-md backdrop-blur px-4 md:px-8 py-3"
            : useDarkText
              ? "bg-transparent text-[#1f2937] px-4 sm:px-6 md:px-8 py-6"
              : "bg-transparent text-white px-4 sm:px-6 md:px-8 py-6"
        }`}
      >
        <SiteLink
          to="/"
          className={`shrink-0 transition-all duration-300 ${isNavCompact ? "w-28 md:w-32" : "w-28 sm:w-32 md:w-40 lg:w-48"}`}
          aria-label="SnowLand Ski School home"
        >
          <img loading="eager" decoding="async"
            src={isNavCompact || forceLogoColor ? logoColor : logo}
            alt="SnowLand Ski School"
            className={`w-full h-auto ${isNavCompact || forceLogoColor ? "opacity-100" : "drop-shadow-md opacity-90"} transition-opacity duration-300`}
          />
        </SiteLink>

        <nav className="hidden md:flex flex-col items-end gap-3">
          {!isNavCompact && (
            <div className="relative flex items-center justify-end gap-3 self-end" ref={langMenuRef}>
              <button
                type="button"
                onClick={() => setIsLangOpen((prev) => !prev)}
                className={`text-[10px] tracking-widest font-medium transition-colors duration-300 font-display ${
                  useDarkText ? "text-[#1f2937]" : "text-white/90 drop-shadow-sm"
                }`}
                aria-expanded={isLangOpen}
                aria-label="Language menu"
              >
                Language
              </button>
              {isLangOpen && (
                <motion.div
                  className={`flex items-center gap-2 text-[10px] font-medium tracking-widest font-display ${
                    useDarkText ? "text-[#1f2937]" : "text-white/90"
                  }`}
                  initial="hidden"
                  animate="visible"
                  variants={{
                    hidden: { opacity: 0 },
                    visible: { opacity: 1, transition: { staggerChildren: 0.06 } },
                  }}
                >
                  {["中文", "日本語", "EN"].map((lang, index) => (
                    <motion.span
                      key={lang}
                      className="flex items-center gap-2"
                      variants={{
                        hidden: { opacity: 0, x: -16 },
                        visible: { opacity: 1, x: 0 },
                      }}
                      transition={{ duration: 0.35, ease: "easeOut" }}
                    >
                      <button
                        type="button"
                        className={`transition-colors duration-200 ${
                          useDarkText ? "hover:text-[#0f172a]" : "hover:text-white"
                        } ${lang === "中文" ? "underline underline-offset-4" : ""}`}
                      >
                        {lang}
                      </button>
                      {index < 2 && (
                        <span className={useDarkText ? "text-[#cbd5e1]" : "text-white/60"}>/</span>
                      )}
                    </motion.span>
                  ))}
                </motion.div>
              )}
              {memberAuthenticated && (
                <div className="flex items-center gap-3">
                  <SiteLink
                    to={bookingUrl}
                    className={`inline-flex items-center justify-center transition-opacity duration-300 hover:opacity-80 ${headerControlClass}`}
                    aria-label="購物車"
                  >
                    <CartIcon />
                  </SiteLink>
                  <SiteLink
                    to="/membership"
                    className={`inline-flex items-center justify-center overflow-hidden transition-opacity duration-300 hover:opacity-80 ${headerControlClass}`}
                    aria-label="會員頭像"
                  >
                    <span className="flex h-5 w-5 items-center justify-center overflow-hidden">
                      <MemberAvatarIcon src={memberAvatarSrc} />
                    </span>
                  </SiteLink>
                </div>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-4 lg:gap-6">
            {visibleNavItems.map((item) => {
              const isDesktopSectionOpen = openDesktopSection === item.label;

              return (
              <div
                key={item.label}
                className={`relative ${item.variant ? "" : "group"}`}
              >
                {item.to ? (
                  <SiteLink
                    to={item.to}
                    className={
                      item.variant === "outline"
                        ? useDarkText
                          ? "text-[#1f2937] text-xs md:text-sm font-semibold tracking-wide transition-colors duration-300 font-display border border-[#1f2937]/30 rounded-full px-4 py-2 hover:bg-[#1f2937]/10"
                          : "text-white text-xs md:text-sm font-semibold tracking-wide transition-colors duration-300 drop-shadow-sm font-display border border-white/80 rounded-full px-4 py-2 hover:bg-white/15"
                        : useDarkText
                          ? "text-[#1f2937] hover:text-[#0f172a] text-xs md:text-sm font-medium tracking-wide transition-colors duration-300 font-display relative group"
                          : "text-white/90 hover:text-white text-xs md:text-sm font-medium tracking-wide transition-colors duration-300 drop-shadow-sm font-display relative group"
                    }
                  >
                    {item.label}
                  </SiteLink>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      if (["海外攝影", "滑雪課程", "滑雪攻略", "最新消息", "關於Snowland"].includes(item.label)) {
                        setOpenDesktopSection((prev) => (prev === item.label ? null : item.label));
                      }
                    }}
                    onBlur={() => {
                      if (isDesktopSectionOpen) {
                        window.requestAnimationFrame(() => {
                          if (!document.activeElement || !document.activeElement.closest?.(`[data-desktop-nav="${item.label}"]`)) {
                            setOpenDesktopSection(null);
                          }
                        });
                      }
                    }}
                    className={
                      item.variant === "outline"
                        ? useDarkText
                          ? "text-[#1f2937] text-xs md:text-sm font-semibold tracking-wide transition-colors duration-300 font-display border border-[#1f2937]/30 rounded-full px-4 py-2 hover:bg-[#1f2937]/10"
                          : "text-white text-xs md:text-sm font-semibold tracking-wide transition-colors duration-300 drop-shadow-sm font-display border border-white/80 rounded-full px-4 py-2 hover:bg-white/15"
                        : useDarkText
                          ? "text-[#1f2937] hover:text-[#0f172a] text-xs md:text-sm font-medium tracking-wide transition-colors duration-300 font-display relative group"
                          : "text-white/90 hover:text-white text-xs md:text-sm font-medium tracking-wide transition-colors duration-300 drop-shadow-sm font-display relative group"
                    }
                    >
                      {item.label}
                      {!item.highlight && !item.variant && (
                        <span
                        className={`absolute -bottom-1 left-0 w-0 h-0.5 transition-all duration-300 group-hover:w-full ${isNavCompact ? "bg-[#1f2937]" : "bg-brand-orange"}`}
                      ></span>
                    )}
                  </button>
                )}
                {["海外攝影", "滑雪課程", "滑雪攻略", "最新消息", "關於Snowland"].includes(item.label) && (
                  <div
                    data-desktop-nav={item.label}
                    className={`absolute left-0 top-full pt-3 transition-all duration-200 ${
                      isDesktopSectionOpen
                        ? "opacity-100 translate-y-0 pointer-events-auto"
                        : "opacity-0 translate-y-2 pointer-events-none group-hover:opacity-100 group-hover:translate-y-0 group-hover:pointer-events-auto"
                    }`}
                    onMouseLeave={() => setOpenDesktopSection(null)}
                  >
                    <div className="w-48 bg-white text-[#1f2937] font-display">
                      {(item.label === "海外攝影"
                        ? [
                            { label: "冬季雪地攝影", to: "/photography/winter" },
                            { label: "夏季旅拍攝影", to: "/photography/summer" },
                            { label: "攝影作品", to: "/Gallery" },
                            { label: "預約攝影流程", to: "/photography/how-to-book" },
                          ]
                        : item.label === "滑雪課程"
                          ? [
                                { label: "星野滑雪課程", to: "/course/tomamu" },
                              { label: "野雪嚮導", to: "/course/off-piste-guide" },
                              { label: "北海道其他雪場課程", to: "/course/hokkaido" },
                              { label: "預約流程", to: "/course/how-to-book" },
                            ]
                          : item.label === "滑雪攻略"
                            ? [
                                { label: "雪場攻略", to: "/guides/skiresorts" },
                                { label: "行前須知", to: "/guides/preparation" },
                                { label: "滑雪裝備", to: "/guides/packing-checklist" },
      { label: "常見問題", to: faqLink },
                                { label: "滑雪精選文章", to: "/guides" },
                              ]
                          : item.label === "最新消息"
                            ? [{ label: "限定優惠", to: "/specialoffers" }, { label: "最新消息", to: "/news" }]
                              : [
                                  { label: "滑雪學校介紹", to: "/about" },
                                  { label: "教練團隊", to: "/coach" },
                                  { label: "成為教練", to: "/join-us" },
                                  { label: "聯絡我們", to: "/contact" },
                                ]
                      ).map((entry) => {
                        const label = typeof entry === "string" ? entry : entry.label;
                        const to = typeof entry === "string" ? null : entry.to;

                        if (to) {
                          return (
                            <SiteLink
                              key={label}
                              to={to}
                              onClick={() => setOpenDesktopSection(null)}
                              className="block px-4 py-2 text-sm font-medium font-display hover:bg-[#f3f4f6]"
                            >
                              {label}
                            </SiteLink>
                          );
                        }

                        return (
                          <a
                            key={label}
                            href="#"
                            className="block px-4 py-2 text-sm font-medium font-display hover:bg-[#f3f4f6]"
                          >
                            {label}
                          </a>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
            })}
            {!hideBookingCta && (
              <SiteLink
                to={bookingUrl}
                className={
                  isNavCompact
                    ? "text-white text-xs md:text-sm font-semibold tracking-wide transition-colors duration-300 font-display rounded-full px-4 py-2 bg-[#2b5f8f] hover:bg-[#8ec8f0]"
                    : "text-white text-xs md:text-sm font-semibold tracking-wide transition-colors duration-300 drop-shadow-sm font-display rounded-full px-4 py-2 bg-[#2b5f8f] hover:bg-[#8ec8f0]"
                }
              >
                預約課程
              </SiteLink>
            )}
          </div>
        </nav>

        <div className="md:hidden flex shrink-0 items-center gap-2 sm:gap-3">
          {memberAuthenticated && (
            <div className="flex items-center gap-2 sm:gap-3">
              <SiteLink
                to={bookingUrl}
                onClick={() => {
                  setIsMobileMenuOpen(false);
                  setOpenMobileSection(null);
                }}
                className={`inline-flex items-center justify-center transition-opacity duration-300 hover:opacity-80 ${headerControlClass}`}
                aria-label="購物車"
              >
                <CartIcon />
              </SiteLink>
              <SiteLink
                to="/membership"
                onClick={() => {
                  setIsMobileMenuOpen(false);
                  setOpenMobileSection(null);
                }}
                className={`inline-flex items-center justify-center overflow-hidden transition-opacity duration-300 hover:opacity-80 ${headerControlClass}`}
                aria-label="會員頭像"
              >
                <span className="flex h-5 w-5 items-center justify-center overflow-hidden">
                  <MemberAvatarIcon src={memberAvatarSrc} />
                </span>
              </SiteLink>
            </div>
          )}
          <button
            type="button"
            onClick={() => {
              setIsMobileMenuOpen(true);
              setOpenMobileSection(null);
            }}
            className={`cursor-pointer ${useDarkText ? "text-[#1f2937]" : "text-white"}`}
            aria-label="Open menu"
          >
            <svg className="h-7 w-7 sm:h-8 sm:w-8 drop-shadow-md" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16m-7 6h7"></path>
            </svg>
          </button>
        </div>
      </MotionHeader>
      <AnimatePresence>
        {isMobileMenuOpen && (
          <>
            <MotionDiv
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-[55] bg-black/40 backdrop-blur-sm"
              onClick={() => {
                setIsMobileMenuOpen(false);
                setOpenMobileSection(null);
              }}
            />
            <MotionAside
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", stiffness: 320, damping: 28 }}
              className="fixed right-0 top-0 z-[60] h-full w-[min(18rem,calc(100vw-1rem))] bg-white px-5 py-8 shadow-2xl font-display"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold tracking-[0.3em] text-[#94a3b8] font-display">
                  MENU
                </span>
                <button
                  type="button"
                  className="text-[#1f2937]"
                  onClick={() => {
                    setIsMobileMenuOpen(false);
                    setOpenMobileSection(null);
                  }}
                  aria-label="Close menu"
                >
                  ✕
                </button>
              </div>
              <div className="mt-8 flex flex-col gap-4">
                {mobileNavItems.map((item) => (
                  <div key={item.label} className="flex flex-col gap-2">
                    <button
                      type="button"
                      className="flex items-center justify-between text-base font-medium text-[#1f2937] font-display"
                      aria-expanded={openMobileSection === item.label}
                      onClick={() => {
                        setOpenMobileSection((prev) => (prev === item.label ? null : item.label));
                      }}
                    >
                      {item.label}
                      <span className="text-lg leading-none text-[#94a3b8]">
                        {openMobileSection === item.label ? "−" : "+"}
                      </span>
                    </button>
                    {openMobileSection === item.label &&
                      (mobileSubItems[item.label] ?? []).map((subItem) => (
                        <SiteLink
                          key={subItem.label}
                          to={subItem.to}
                          className="pl-3 text-sm font-medium text-[#475569] font-display"
                          onClick={() => {
                            setIsMobileMenuOpen(false);
                            setOpenMobileSection(null);
                          }}
                        >
                          {subItem.label}
                        </SiteLink>
                      ))}
                  </div>
                ))}
              </div>
              <div className="mt-8 border-t border-[#e5e7eb] pt-6">
                <p className="text-xs font-semibold tracking-[0.3em] text-[#94a3b8] font-display">
                  LANGUAGE
                </p>
                <div className="mt-4 flex flex-col gap-2 text-sm font-semibold text-[#1f2937]">
                  <div className="flex flex-col gap-2 text-sm text-[#475569]">
                    {["中文", "EN", "日本語"].map((lang) => (
                      <button
                        key={lang}
                        type="button"
                        className={lang === "中文" ? "text-left underline underline-offset-4 text-[#1f2937]" : "text-left"}
                      >
                        {lang}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="mt-8 flex flex-col items-start gap-3">
                {!memberAuthenticated && (
                  <SiteLink
                    to="/membership"
                    onClick={() => {
                      setIsMobileMenuOpen(false);
                      setOpenMobileSection(null);
                    }}
                    className="inline-flex items-center justify-start rounded-full border-[0.5px] border-[#111827] px-4 py-1.5 text-base font-semibold text-[#111827]"
                  >
                    {memberItem.label}
                  </SiteLink>
                )}
                {!hideBookingCta && (
                  <SiteLink
                    to={bookingUrl}
                    onClick={() => {
                      setIsMobileMenuOpen(false);
                      setOpenMobileSection(null);
                    }}
                    className="inline-flex items-center justify-start rounded-full bg-[#2b5f8f] px-4 py-1.5 text-base font-semibold text-white"
                  >
                    預約課程
                  </SiteLink>
                )}
              </div>
            </MotionAside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

export default SiteHeader;
