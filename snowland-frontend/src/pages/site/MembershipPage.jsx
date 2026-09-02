import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';

const dashboardTabs = [
  { key: "overview", label: "會員總覽", path: "/membership" },
  { key: "orders", label: "我的訂單", path: "/membership/orders" },
  { key: "order-history", label: "歷史訂單", path: "/membership/order-history" },
  { key: "offers", label: "專屬優惠", path: "/membership/offers" },
  { key: "account-detail", label: "基本資料", path: "/membership/account-detial" },
];

const orderHistorySubtabs = ["訂單資訊", "訂單成員", "課程紀錄", "上課評量表"];

const dashboardCopy = {
  overview: {
    eyebrow: "MEMBERSHIP",
    title: "會員總覽",
    description: "",
  },
  orders: {
    eyebrow: "ORDERS",
    title: "我的訂單",
    description: "這裡會放進行中的訂單與預約明細。",
  },
  "order-history": {
    eyebrow: "ORDER HISTORY",
    title: "歷史訂單",
    description: "",
  },
  offers: {
    eyebrow: "SPECIAL OFFER",
    title: "專屬優惠",
    description: "",
  },
  "account-detail": {
    eyebrow: "ACCOUNT DETAIL",
    title: "基本資料",
    description: "",
  },
};

const mockOrders = [
  {
    id: "order-20260312",
    startDate: "2026-03-12",
    resort: "星野 Tomamu",
    coach: "Cash",
    skiType: "單板",
    people: "2 人",
    days: "3 天",
    status: "預約尚未完成",
  },
  {
    id: "order-20260216",
    startDate: "2026-02-16",
    resort: "新雪谷 Niseko",
    coach: "Lily",
    skiType: "雙板",
    people: "1 人",
    days: "2 天",
    status: "即將到來",
  },
  {
    id: "order-20260108",
    startDate: "2026-01-08",
    resort: "富良野 Furano",
    coach: "Dylan",
    skiType: "單板",
    people: "4 人",
    days: "1 天",
    status: "即將到來",
  },
];

function resolveDashboardTab(pathname) {
  if (pathname === "/membership" || pathname === "/membership/") {
    return "overview";
  }
  if (pathname.startsWith("/membership/orders")) {
    return "orders";
  }
  if (pathname.startsWith("/membership/order-history")) {
    return "order-history";
  }
  if (pathname.startsWith("/membership/offers")) {
    return "offers";
  }
  if (pathname.startsWith("/membership/account-detial") || pathname.startsWith("/membership/account-detail")) {
    return "account-detail";
  }
  return "overview";
}

function MembershipAvatar({ src, alt, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group relative mx-auto flex h-28 w-28 items-center justify-center overflow-hidden rounded-full border border-[#d8e1ea] bg-[#edf2f7] shadow-[0_12px_24px_rgba(15,23,42,0.08)] transition-transform duration-200 hover:scale-[1.02]"
      aria-label="編輯頭像"
    >
      {src ? (
        <img loading="lazy" decoding="async" src={src} alt={alt} className="h-full w-full object-cover" />
      ) : (
        <svg
          viewBox="0 0 96 96"
          fill="none"
          className="h-14 w-14 text-[#94a3b8]"
          aria-hidden="true"
        >
          <circle cx="48" cy="36" r="16" stroke="currentColor" strokeWidth="4" />
          <path
            d="M20 78c4.8-11.2 14.4-18 28-18s23.2 6.8 28 18"
            stroke="currentColor"
            strokeWidth="4"
            strokeLinecap="round"
          />
        </svg>
      )}
      <span className="pointer-events-none absolute inset-0 flex items-center justify-center bg-[#0f172a]/0 opacity-0 transition-all duration-200 group-hover:bg-[#0f172a]/18 group-hover:opacity-100">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          className="h-9 w-9 text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.3)]"
          aria-hidden="true"
        >
          <path
            d="M9 5l1.2-2h3.6L15 5h3a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3Z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
          <circle cx="12" cy="13" r="3.25" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      </span>
    </button>
  );
}

function formatOrderDate(dateString) {
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(dateString));
}

function OrderField({ label, value }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold tracking-[0.24em] uppercase text-[#94a3b8] font-display">
        {label}
      </p>
      <p className="text-sm md:text-base font-semibold text-[#1f2937] font-display">
        {value}
      </p>
    </div>
  );
}

function AuthSection({ activeTab, setActiveTab, authErrors, setAuthErrors, loginEmail, setLoginEmail, loginPassword, setLoginPassword, registerEmail, setRegisterEmail, registerPassword, setRegisterPassword, showPassword, setShowPassword, onLogin, onRegister }) {
  const inputBase =
    "mt-2 w-full rounded-sm border border-transparent bg-[#f3f4f6] px-4 py-3 text-base md:text-sm text-[#1f2937] focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30";

  return (
    <section className="mt-12">
      <div className="mx-auto max-w-3xl px-6 md:px-12">
        <div className="border-b border-[#e2e8f0]">
          <div className="flex flex-wrap items-center justify-center gap-12 md:gap-16 text-base md:text-lg font-semibold text-[#6b7280] font-display">
            <button
              type="button"
              onClick={() => setActiveTab("login")}
              className={`group relative pb-4 transition-colors duration-200 ${
                activeTab === "login" ? "text-[#111827]" : "hover:text-[#2b5f8f]"
              }`}
              aria-current={activeTab === "login" ? "page" : undefined}
            >
              會員登入
              <span
                className={`absolute left-0 -bottom-[1px] h-0.5 transition-all duration-300 ${
                  activeTab === "login"
                    ? "w-full bg-[#111827]"
                    : "w-0 bg-[#2b5f8f] group-hover:w-full"
                }`}
              />
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("register")}
              className={`group relative pb-4 transition-colors duration-200 ${
                activeTab === "register" ? "text-[#111827]" : "hover:text-[#2b5f8f]"
              }`}
              aria-current={activeTab === "register" ? "page" : undefined}
            >
              註冊會員
              <span
                className={`absolute left-0 -bottom-[1px] h-0.5 transition-all duration-300 ${
                  activeTab === "register"
                    ? "w-full bg-[#111827]"
                    : "w-0 bg-[#2b5f8f] group-hover:w-full"
                }`}
              />
            </button>
          </div>
        </div>

        {activeTab === "login" ? (
          <form
            className="mt-10 space-y-6"
            onSubmit={(event) => {
              event.preventDefault();
              onLogin();
            }}
          >
            <label className="block text-sm font-semibold text-[#1f2937]">
              電子郵件<span className="text-[#ef4444]">*</span>
              <input
                type="text"
                value={loginEmail}
                  onChange={(event) => {
                    setLoginEmail(event.target.value);
                    if (authErrors.loginEmail) {
                      setAuthErrors((prev) => ({ ...prev, loginEmail: "" }));
                    }
                  }}
                  autoComplete="username"
                  className={inputBase}
                />
              {authErrors.loginEmail && (
                <p className="mt-2 text-xs text-[#ef4444]">{authErrors.loginEmail}</p>
              )}
            </label>
            <label className="block text-sm font-semibold text-[#1f2937]">
              密碼<span className="text-[#ef4444]">*</span>
              <span className="relative mt-2 block">
                <input
                  type={showPassword ? "text" : "password"}
                  value={loginPassword}
                  onChange={(event) => {
                    setLoginPassword(event.target.value);
                    if (authErrors.loginPassword) {
                      setAuthErrors((prev) => ({ ...prev, loginPassword: "" }));
                    }
                  }}
                  autoComplete="current-password"
                  className="w-full rounded-sm border border-transparent bg-[#f3f4f6] px-4 py-3 pr-12 text-base md:text-sm text-[#1f2937] focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6b7280]"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M3 12s3.6-6 9-6 9 6 9 6-3.6 6-9 6-9-6-9-6z"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      />
                      <circle cx="12" cy="12" r="3.5" stroke="currentColor" strokeWidth="1.5" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M3 12s3.6-6 9-6 9 6 9 6-3.6 6-9 6-9-6-9-6z"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      />
                      <path d="M4 4l16 16" stroke="currentColor" strokeWidth="1.5" />
                    </svg>
                  )}
                </button>
              </span>
              {authErrors.loginPassword && (
                <p className="mt-2 text-xs text-[#ef4444]">{authErrors.loginPassword}</p>
              )}
            </label>
            <div className="flex items-center justify-center gap-6 text-sm">
              <label className="flex items-center gap-2 text-[#475569]">
                <input type="checkbox" className="h-4 w-4" />
                記住此帳號
              </label>
              <a
                href="https://www.powderlife.com/my-account/lost-password/"
                className="text-[#7b93a7] hover:text-[#2b5f8f]"
                target="_blank"
                rel="noopener noreferrer"
              >
                忘記密碼
              </a>
            </div>
            <div className="flex justify-center">
              <button
                type="submit"
                className="group relative inline-flex items-center justify-center px-10 py-4 text-sm font-bold text-white transition-all duration-300 bg-[#8ec8f0] rounded-full hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden"
              >
                <div className="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent" />
                <span className="relative z-10">會員登入</span>
              </button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <a
                href="https://www.powderlife.com/?wc-api=auth&start=google&return=https%3A%2F%2Fwww.powderlife.com%2Fmy-account%2F"
                className="flex items-center justify-center gap-3 rounded-lg bg-black px-4 py-2.5 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded bg-white text-black font-bold">
                  G
                </span>
                以Google帳號登入
              </a>
              <a
                href="https://www.powderlife.com/?wc-api=auth&start=line&return=https%3A%2F%2Fwww.powderlife.com%2Fmy-account%2F"
                className="flex items-center justify-center gap-3 rounded-lg bg-[#06c755] px-4 py-2.5 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded bg-white text-[#06c755] font-bold">
                  L
                </span>
                以Line帳號登入
              </a>
            </div>
          </form>
        ) : (
          <form
            className="mt-10 space-y-6"
            onSubmit={(event) => {
              event.preventDefault();
              onRegister();
            }}
          >
            <label className="block text-sm font-semibold text-[#1f2937]">
              電子郵件<span className="text-[#ef4444]">*</span>
              <input
                type="email"
                value={registerEmail}
                  onChange={(event) => {
                    setRegisterEmail(event.target.value);
                    if (authErrors.registerEmail) {
                      setAuthErrors((prev) => ({ ...prev, registerEmail: "" }));
                    }
                  }}
                  autoComplete="email"
                  className={inputBase}
                />
              {authErrors.registerEmail && (
                <p className="mt-2 text-xs text-[#ef4444]">{authErrors.registerEmail}</p>
              )}
            </label>
            <label className="block text-sm font-semibold text-[#1f2937]">
              密碼<span className="text-[#ef4444]">*</span>
              <span className="relative mt-2 block">
                <input
                  type={showPassword ? "text" : "password"}
                  value={registerPassword}
                  onChange={(event) => {
                    setRegisterPassword(event.target.value);
                    if (authErrors.registerPassword) {
                      setAuthErrors((prev) => ({ ...prev, registerPassword: "" }));
                    }
                  }}
                  autoComplete="new-password"
                  className="w-full rounded-sm border border-transparent bg-[#f3f4f6] px-4 py-3 pr-12 text-base md:text-sm text-[#1f2937] focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6b7280]"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M3 12s3.6-6 9-6 9 6 9 6-3.6 6-9 6-9-6-9-6z"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      />
                      <circle cx="12" cy="12" r="3.5" stroke="currentColor" strokeWidth="1.5" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M3 12s3.6-6 9-6 9 6 9 6-3.6 6-9 6-9-6-9-6z"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      />
                      <path d="M4 4l16 16" stroke="currentColor" strokeWidth="1.5" />
                    </svg>
                  )}
                </button>
              </span>
              {authErrors.registerPassword && (
                <p className="mt-2 text-xs text-[#ef4444]">{authErrors.registerPassword}</p>
              )}
            </label>
            <p className="text-sm text-[#475569]">
              您的個人資料將用於提供您在本站的體驗、管理帳號存取，以及我們{" "}
              <SiteLink to="/privacy-policy" className="text-[#2b5f8f] underline underline-offset-2">
                隱私權政策
              </SiteLink>
              {" "}中所述之用途。
            </p>
            <div className="flex justify-center">
              <button
                type="submit"
                className="group relative inline-flex items-center justify-center px-10 py-4 text-sm font-bold text-white transition-all duration-300 bg-[#8ec8f0] rounded-full hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden"
              >
                <div className="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent" />
                <span className="relative z-10">註冊</span>
              </button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <a
                href="https://www.powderlife.com/?wc-api=auth&start=google&return=https%3A%2F%2Fwww.powderlife.com%2Fmy-account%2F"
                className="flex items-center justify-center gap-3 rounded-lg bg-black px-4 py-2.5 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded bg-white text-black font-bold">
                  G
                </span>
                以Google帳號註冊
              </a>
              <a
                href="https://www.powderlife.com/?wc-api=auth&start=line&return=https%3A%2F%2Fwww.powderlife.com%2Fmy-account%2F"
                className="flex items-center justify-center gap-3 rounded-lg bg-[#06c755] px-4 py-2.5 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded bg-white text-[#06c755] font-bold">
                  L
                </span>
                以Line帳號註冊
              </a>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

function DashboardSection({ sectionKey }) {
  const content = dashboardCopy[sectionKey] ?? dashboardCopy.overview;
  const sortedOrders = [...mockOrders].sort(
    (left, right) => new Date(right.startDate) - new Date(left.startDate)
  );
  const renderOrderCards = (getStatusLabel) => (
    <div className="space-y-4">
      {sortedOrders.map((order) => (
        <article
          key={order.id}
          className="rounded-sm border border-[#dbe3ec] bg-white px-5 py-5 shadow-[0_10px_24px_rgba(15,23,42,0.04)] md:px-6 md:py-6"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold tracking-[0.24em] uppercase text-[#94a3b8] font-display">
                課程起始日
              </p>
              <p className="mt-2 text-lg font-semibold text-[#111827] font-display">
                {formatOrderDate(order.startDate)}
              </p>
            </div>
            <span className="inline-flex rounded-full bg-[#eef4fa] px-3 py-1 text-xs font-semibold text-[#2b5f8f]">
              {getStatusLabel(order)}
            </span>
          </div>

          <div className="mt-5 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            <OrderField label="雪場" value={order.resort} />
            <OrderField label="教練" value={order.coach} />
            <OrderField label="類型" value={order.skiType} />
            <OrderField label="上課人數" value={order.people} />
            <OrderField label="上課天數" value={order.days} />
          </div>

          <div className="mt-6 flex justify-end border-t border-[#eef2f7] pt-4">
            <button
              type="button"
              className="inline-flex items-center gap-2 text-sm font-semibold text-[#2b5f8f] transition-colors hover:text-[#1c4f7b]"
            >
              查看訂單詳情
              <span aria-hidden="true">&gt;</span>
            </button>
          </div>
        </article>
      ))}
    </div>
  );

  if (sectionKey === "orders" || sectionKey === "order-history") {
    return (
      <div className="space-y-6">
        <div>
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            {content.eyebrow}
          </p>
          <h2 className="mt-3 text-2xl md:text-3xl font-semibold text-[#1f2937] font-display">
            {content.title}
          </h2>
        </div>
        <div className="border-t border-[#dbe3ec] pt-6">
          {sortedOrders.length > 0 ? (
            renderOrderCards((order) => (sectionKey === "order-history" ? "課程已完成" : order.status))
          ) : (
            <div className="flex min-h-[320px] flex-col items-center justify-center rounded-sm border border-dashed border-[#dbe3ec] bg-white px-6 py-12 text-center">
              <p className="text-2xl font-semibold text-[#111827] font-display">
                您目前尚無課程預約排程
              </p>
              <SiteLink
                to="/booking"
                className="mt-6 inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#1c4f7b]"
              >
                預約課程
              </SiteLink>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            {content.eyebrow}
          </p>
          <h2 className="mt-3 text-2xl md:text-3xl font-semibold text-[#111827] font-display">
            {content.title}
          </h2>
        </div>
      </div>
      <div className="border-t border-[#dbe3ec] pt-6">
        {content.description && (
          <p className="max-w-2xl text-sm md:text-base leading-relaxed text-[#475569]">
            {content.description}
          </p>
        )}
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <div className="border border-dashed border-[#dbe3ec] p-5">
            <p className="text-xs font-semibold tracking-[0.25em] uppercase text-[#94a3b8]">
              Section
            </p>
            <p className="mt-3 text-sm text-[#1f2937]">{content.title}</p>
          </div>
          <div className="border border-dashed border-[#dbe3ec] p-5">
            <p className="text-xs font-semibold tracking-[0.25em] uppercase text-[#94a3b8]">
              Status
            </p>
            <p className="mt-3 text-sm text-[#1f2937]">內容待補充</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function MembershipPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("login");
  const [showPassword, setShowPassword] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [memberName] = useState("會員姓名");
  const [memberEmail, setMemberEmail] = useState("account@example.com");
  const [avatarSrc, setAvatarSrc] = useState("");
  const [avatarMenuOpen, setAvatarMenuOpen] = useState(false);
  const [orderHistoryExpanded, setOrderHistoryExpanded] = useState(false);
  const [authErrors, setAuthErrors] = useState({
    loginEmail: "",
    loginPassword: "",
    registerEmail: "",
    registerPassword: "",
  });
  const avatarMenuRef = useRef(null);
  const mobileAvatarMenuRef = useRef(null);
  const avatarInputRef = useRef(null);

  const activeSectionKey = useMemo(
    () => resolveDashboardTab(location.pathname),
    [location.pathname]
  );
  const activeSectionCopy = dashboardCopy[activeSectionKey] ?? dashboardCopy.overview;
  const hideMobileMemberPanel = ["orders", "order-history", "offers"].includes(activeSectionKey);

  const isOrderHistoryOpen = orderHistoryExpanded;

  const handleOrderHistoryClick = () => {
    setOrderHistoryExpanded((prev) => !prev);
    if (activeSectionKey !== "order-history") {
      navigate("/membership/order-history");
    }
  };

  useEffect(() => {
    if (!avatarMenuOpen) {
      return undefined;
    }

    const onClickOutside = (event) => {
      const clickedInsideDesktopMenu = avatarMenuRef.current && avatarMenuRef.current.contains(event.target);
      const clickedInsideMobileMenu = mobileAvatarMenuRef.current && mobileAvatarMenuRef.current.contains(event.target);
      if (!clickedInsideDesktopMenu && !clickedInsideMobileMenu) {
        setAvatarMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [avatarMenuOpen]);

  const validateLogin = () => {
    blurActiveField();
    const nextErrors = {
      loginEmail: loginEmail.trim() ? "" : "請輸入電子郵件",
      loginPassword: loginPassword.trim() ? "" : "請輸入密碼",
      registerEmail: "",
      registerPassword: "",
    };
    setAuthErrors(nextErrors);
    if (!nextErrors.loginEmail && !nextErrors.loginPassword) {
      setMemberEmail(loginEmail.trim());
      setIsAuthenticated(true);
    }
  };

  const validateRegister = () => {
    blurActiveField();
    const nextErrors = {
      loginEmail: "",
      loginPassword: "",
      registerEmail: registerEmail.trim() ? "" : "請輸入電子郵件",
      registerPassword: registerPassword.trim() ? "" : "請輸入密碼",
    };
    setAuthErrors(nextErrors);
    if (!nextErrors.registerEmail && !nextErrors.registerPassword) {
      setMemberEmail(registerEmail.trim());
      setIsAuthenticated(true);
    }
  };

  const handleAvatarUpload = (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setAvatarSrc(reader.result);
      }
    };
    reader.readAsDataURL(file);
    setAvatarMenuOpen(false);
  };

  const handleAvatarReset = () => {
    setAvatarSrc("");
    if (avatarInputRef.current) {
      avatarInputRef.current.value = "";
    }
    setAvatarMenuOpen(false);
  };

  const blurActiveField = () => {
    const activeElement = document.activeElement;
    if (activeElement instanceof HTMLElement) {
      activeElement.blur();
    }
  };

  const navDarkState = isAuthenticated;

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader
        forceTransparent
        forceDarkText={navDarkState}
        forceLogoColor={navDarkState}
        memberAuthenticated={isAuthenticated}
        memberAvatarSrc={avatarSrc}
      />
      <main className="flex-1 pb-24">
        {!isAuthenticated ? (
          <>
            <section className="relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-[#1c3b5f] via-[#2b5f8f] to-[#7bbbe7]" />
              <div
                className="absolute inset-0 opacity-40"
                style={{
                  backgroundImage:
                    "radial-gradient(circle at 20% 20%, rgba(255,255,255,0.35), transparent 45%), radial-gradient(circle at 70% 30%, rgba(255,255,255,0.25), transparent 50%), radial-gradient(circle at 40% 80%, rgba(255,255,255,0.2), transparent 55%)",
                }}
              />
              <div className="relative max-w-6xl mx-auto px-6 pt-32 pb-20 md:pt-36 md:pb-24 text-white text-center">
                <p className="text-xs font-semibold tracking-[0.3em] uppercase text-white/70 font-display">
                  Membership
                </p>
                <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
                  會員專區
                </h1>
              </div>
            </section>
            <AuthSection
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              authErrors={authErrors}
              setAuthErrors={setAuthErrors}
              loginEmail={loginEmail}
              setLoginEmail={setLoginEmail}
              loginPassword={loginPassword}
              setLoginPassword={setLoginPassword}
              registerEmail={registerEmail}
              setRegisterEmail={setRegisterEmail}
              registerPassword={registerPassword}
              setRegisterPassword={setRegisterPassword}
              showPassword={showPassword}
              setShowPassword={setShowPassword}
              onLogin={validateLogin}
              onRegister={validateRegister}
            />
          </>
        ) : (
          <section className="mx-auto max-w-7xl px-4 sm:px-6 md:px-10 pt-24 md:pt-28">
            <nav
              aria-label="breadcrumb"
              className="mb-6 flex flex-wrap items-center gap-2 text-xs sm:text-sm font-semibold tracking-wide text-[#64748b] font-display"
            >
              <SiteLink to="/" className="transition-colors hover:text-[#2b5f8f]">
                首頁
              </SiteLink>
              <span aria-hidden="true" className="text-[#cbd5e1]">
                /
              </span>
              <SiteLink to="/membership" className="transition-colors hover:text-[#2b5f8f]">
                會員專區
              </SiteLink>
              {activeSectionKey !== "overview" && (
                <>
                  <span aria-hidden="true" className="text-[#cbd5e1]">
                    /
                  </span>
                  <span className="text-[#111827]">{activeSectionCopy.title}</span>
                </>
              )}
            </nav>
            {!hideMobileMemberPanel && (
              <div
                ref={mobileAvatarMenuRef}
                className="lg:hidden mb-8 rounded-sm border border-[#dbe3ec] bg-white px-4 py-5 shadow-[0_12px_30px_rgba(15,23,42,0.05)]"
              >
              <div className="relative">
                <div className="flex flex-col items-center text-center">
                  <MembershipAvatar
                    src={avatarSrc}
                    alt={`${memberName} 頭像`}
                    onClick={() => setAvatarMenuOpen((prev) => !prev)}
                  />
                  <div className="mt-4 pb-2">
                    <p className="text-lg font-semibold text-[#111827] font-display">{memberName}</p>
                    <p className="mt-1 text-sm text-[#64748b] break-all">{memberEmail}</p>
                  </div>
                </div>

                {avatarMenuOpen && (
                  <div className="absolute left-1/2 top-full z-20 mt-4 w-56 -translate-x-1/2 rounded-sm border border-[#dbe3ec] bg-white p-3 shadow-[0_18px_40px_rgba(15,23,42,0.16)]">
                    <button
                      type="button"
                      onClick={() => avatarInputRef.current?.click()}
                      className="flex w-full items-center justify-center rounded-sm px-4 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:bg-[#f3f6fa]"
                    >
                      上傳照片
                    </button>
                    <button
                      type="button"
                      onClick={handleAvatarReset}
                      className="mt-2 flex w-full items-center justify-center rounded-sm px-4 py-3 text-sm font-semibold text-[#64748b] transition-colors hover:bg-[#f3f6fa]"
                    >
                      重置回預設
                    </button>
                  </div>
                )}

                <input
                  ref={avatarInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleAvatarUpload}
                />
              </div>

              <nav className="mt-5 border-t border-[#dbe3ec]">
                {dashboardTabs.map((tab) => {
                  const isActive = activeSectionKey === tab.key;
                  const isOrderHistory = tab.key === "order-history";
                  return (
                    <div key={tab.key} className="border-b border-[#dbe3ec]">
                      {isOrderHistory ? (
                        <button
                          type="button"
                          onClick={handleOrderHistoryClick}
                          className={`group flex w-full items-center justify-between gap-3 py-4 text-base font-semibold font-display transition-colors duration-200 ${
                            isActive || isOrderHistoryOpen
                              ? "text-[#2b5f8f]"
                              : "text-[#64748b] hover:text-[#2b5f8f]"
                          }`}
                        >
                          <span className="flex items-center gap-3">
                            <span
                              className={`h-2.5 w-2.5 shrink-0 rounded-full bg-[#f28b2f] transition-opacity duration-200 ${
                                isActive || isOrderHistoryOpen ? "opacity-100" : "opacity-0"
                              }`}
                            />
                            {tab.label}
                          </span>
                          <span className="text-xs">{isOrderHistoryOpen ? "−" : "+"}</span>
                        </button>
                      ) : (
                        <SiteLink
                          to={tab.path}
                          onClick={() => setOrderHistoryExpanded(false)}
                          className={`group flex items-center gap-3 py-4 text-base font-semibold font-display transition-colors duration-200 ${
                            isActive
                              ? "text-[#2b5f8f]"
                              : "text-[#64748b] hover:text-[#2b5f8f]"
                          }`}
                        >
                          <span
                            className={`h-2.5 w-2.5 shrink-0 rounded-full bg-[#f28b2f] transition-opacity duration-200 ${
                              isActive ? "opacity-100" : "opacity-0"
                            }`}
                          />
                          {tab.label}
                        </SiteLink>
                      )}
                      {isOrderHistory && isOrderHistoryOpen && (
                        <div className="pb-3 pl-6">
                          {orderHistorySubtabs.map((subtab) => (
                            <button
                              key={subtab}
                              type="button"
                              className="block w-full py-1 text-left text-sm font-medium text-[#64748b] transition-colors hover:text-[#2b5f8f]"
                            >
                              {subtab}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
                <button
                  type="button"
                  onClick={() => {
                    setOrderHistoryExpanded(false);
                    setIsAuthenticated(false);
                  }}
                  className="group flex w-full items-center gap-3 border-b border-[#dbe3ec] py-4 text-base font-semibold font-display text-[#64748b] transition-colors duration-200 hover:text-[#2b5f8f]"
                >
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-[#f28b2f] opacity-0 transition-opacity duration-200 group-hover:opacity-40" />
                  <span>登出</span>
                </button>
              </nav>
              </div>
            )}

            <div className="mt-10 grid gap-8 lg:grid-cols-[320px_minmax(0,1fr)]">
              <aside className="relative px-0 py-0 hidden lg:block">
                <div ref={avatarMenuRef} className="relative">
                  <MembershipAvatar
                    src={avatarSrc}
                    alt={`${memberName} 頭像`}
                    onClick={() => setAvatarMenuOpen((prev) => !prev)}
                  />
                  {avatarMenuOpen && (
                    <div className="absolute left-1/2 top-full z-20 mt-4 w-56 -translate-x-1/2 rounded-sm border border-[#dbe3ec] bg-white p-3 shadow-[0_18px_40px_rgba(15,23,42,0.16)]">
                      <button
                        type="button"
                        onClick={() => avatarInputRef.current?.click()}
                        className="flex w-full items-center justify-center rounded-sm px-4 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:bg-[#f3f6fa]"
                      >
                        上傳照片
                      </button>
                      <button
                        type="button"
                        onClick={handleAvatarReset}
                        className="mt-2 flex w-full items-center justify-center rounded-sm px-4 py-3 text-sm font-semibold text-[#64748b] transition-colors hover:bg-[#f3f6fa]"
                      >
                        重置回預設
                      </button>
                    </div>
                  )}
                  <input
                    ref={avatarInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleAvatarUpload}
                  />
                </div>

                <div className="mt-6 pb-6 text-center">
                  <p className="text-lg font-semibold text-[#111827] font-display">{memberName}</p>
                  <p className="mt-2 text-sm text-[#64748b]">{memberEmail}</p>
                </div>

                <nav className="border-t border-[#dbe3ec]">
                  {dashboardTabs.map((tab) => {
                    const isActive = activeSectionKey === tab.key;
                    const isOrderHistory = tab.key === "order-history";
                    return (
                      <div key={tab.key} className="border-b border-[#dbe3ec]">
                        {isOrderHistory ? (
                          <button
                            type="button"
                            onClick={handleOrderHistoryClick}
                            className={`group flex w-full items-center justify-between gap-3 py-4 text-base md:text-lg font-semibold font-display transition-colors duration-200 ${
                              isActive || isOrderHistoryOpen
                                ? "text-[#2b5f8f]"
                                : "text-[#64748b] hover:text-[#2b5f8f]"
                            }`}
                          >
                            <span className="flex items-center gap-3">
                              <span
                                className={`h-2.5 w-2.5 shrink-0 rounded-full bg-[#f28b2f] transition-opacity duration-200 ${
                                  isActive || isOrderHistoryOpen ? "opacity-100" : "opacity-0"
                                }`}
                              />
                              <span>{tab.label}</span>
                            </span>
                            <span className="text-xs">{isOrderHistoryOpen ? "−" : "+"}</span>
                          </button>
                        ) : (
                        <SiteLink
                          to={tab.path}
                          onClick={() => setOrderHistoryExpanded(false)}
                          className={`group flex items-center gap-3 py-4 text-base md:text-lg font-semibold font-display transition-colors duration-200 ${
                            isActive
                              ? "text-[#2b5f8f]"
                                : "text-[#64748b] hover:text-[#2b5f8f]"
                            }`}
                          >
                            <span
                              className={`h-2.5 w-2.5 shrink-0 rounded-full bg-[#f28b2f] transition-opacity duration-200 ${
                                isActive ? "opacity-100" : "opacity-0"
                              }`}
                            />
                            <span>{tab.label}</span>
                          </SiteLink>
                        )}
                        {isOrderHistory && isOrderHistoryOpen && (
                          <div className="pb-3 pl-6">
                            {orderHistorySubtabs.map((subtab) => (
                              <button
                                key={subtab}
                                type="button"
                                className="block w-full py-1 text-left text-sm md:text-base font-medium text-[#64748b] transition-colors hover:text-[#2b5f8f]"
                              >
                                {subtab}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  <button
                    type="button"
                    onClick={() => {
                      setOrderHistoryExpanded(false);
                      setIsAuthenticated(false);
                    }}
                    className="group flex w-full items-center gap-3 border-b border-[#dbe3ec] py-4 text-base md:text-lg font-semibold font-display text-[#64748b] transition-colors duration-200 hover:text-[#2b5f8f]"
                  >
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-[#f28b2f] opacity-0 transition-opacity duration-200 group-hover:opacity-40" />
                    <span>登出</span>
                  </button>
                </nav>
              </aside>

              <section className="min-w-0 pt-2">
                <DashboardSection sectionKey={activeSectionKey} />
              </section>
            </div>
          </section>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

export default MembershipPage;
