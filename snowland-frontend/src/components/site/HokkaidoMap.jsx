import React, { useEffect, useMemo, useRef, useState } from 'react';
import SiteLink from './SiteLink';

const markerPositions = {
  kamui: { left: "42.83%", top: "47.37%" },
  tomamu: { left: "46.93%", top: "60.77%" },
  sahoro: { left: "48.49%", top: "58.34%" },
  "mt-racey": { left: "40.35%", top: "61.45%" },
  "sapporo-kokusai": { left: "34.68%", top: "60.29%" },
  teine: { left: "33.34%", top: "60.98%" },
  kiroro: { left: "31.94%", top: "60.98%" },
  rusutsu: { left: "31.77%", top: "67.61%" },
  "niseko-annupuri": { left: "29.27%", top: "65.35%" },
};

function HokkaidoMap({ resorts, initialActiveSlug }) {
  const preferredSlug = useMemo(() => (
    resorts.some((resort) => resort.slug === initialActiveSlug)
      ? initialActiveSlug
      : resorts[0]?.slug ?? null
  ), [resorts, initialActiveSlug]);
  const [activeSlug, setActiveSlug] = useState(() => preferredSlug);
  const [isCardVisible, setIsCardVisible] = useState(false);
  const [linePoints, setLinePoints] = useState(null);
  const [mapScale, setMapScale] = useState(1);
  const [mapTranslate, setMapTranslate] = useState({ x: 0, y: 0 });
  const mapRef = useRef(null);
  const cardRef = useRef(null);
  const markerRefs = useRef({});
  const pinchStateRef = useRef({
    initialDistance: 0,
    initialScale: 1,
    initialCenter: null,
    initialTranslate: { x: 0, y: 0 },
  });
  const activeResort = useMemo(
    () => resorts.find((resort) => resort.slug === activeSlug),
    [activeSlug, resorts]
  );
  const activeRoute = activeResort?.route || (activeResort ? `/course/${activeResort.slug}` : "");
  const mapOrigin = useMemo(() => {
    const points = resorts
      .map((resort) => markerPositions[resort.slug])
      .filter(Boolean)
      .map((position) => {
        const left = Number.parseFloat(position.left);
        const top = Number.parseFloat(position.top);
        if (Number.isNaN(left) || Number.isNaN(top)) {
          return null;
        }
        return { left, top };
      })
      .filter(Boolean);
    if (!points.length) {
      return "center";
    }
    const bounds = points.reduce(
      (acc, point) => ({
        minLeft: Math.min(acc.minLeft, point.left),
        maxLeft: Math.max(acc.maxLeft, point.left),
        minTop: Math.min(acc.minTop, point.top),
        maxTop: Math.max(acc.maxTop, point.top),
      }),
      { minLeft: Infinity, maxLeft: -Infinity, minTop: Infinity, maxTop: -Infinity }
    );
    const centerLeft = (bounds.minLeft + bounds.maxLeft) / 2;
    const centerTop = (bounds.minTop + bounds.maxTop) / 2;
    return `${centerLeft}% ${centerTop}%`;
  }, [resorts]);

  useEffect(() => {
    if (preferredSlug) {
      setActiveSlug(preferredSlug);
    }
  }, [preferredSlug]);

  useEffect(() => {
    if (!activeResort) {
      setIsCardVisible(false);
      return;
    }
    setIsCardVisible(false);
    const timer = setTimeout(() => setIsCardVisible(true), 160);
    return () => clearTimeout(timer);
  }, [activeResort]);

  useEffect(() => {
    const updateLine = () => {
      const container = mapRef.current;
      const marker = activeSlug ? markerRefs.current[activeSlug] : null;
      const card = cardRef.current;
      if (!container || !marker || !card || window.innerWidth < 768) {
        setLinePoints(null);
        return;
      }
      const containerRect = container.getBoundingClientRect();
      const markerRect = marker.getBoundingClientRect();
      const cardRect = card.getBoundingClientRect();
      const startX = markerRect.left - containerRect.left + markerRect.width / 2;
      const startY = markerRect.top - containerRect.top + markerRect.height / 2;
      const endX = cardRect.left - containerRect.left;
      const endY = cardRect.top - containerRect.top + cardRect.height / 2;
      setLinePoints({ startX, startY, endX, endY });
    };

    updateLine();
    if (!activeResort || !isCardVisible) {
      setLinePoints(null);
      return undefined;
    }
    window.addEventListener("resize", updateLine);
    window.addEventListener("scroll", updateLine, { passive: true });
    return () => {
      window.removeEventListener("resize", updateLine);
      window.removeEventListener("scroll", updateLine);
    };
  }, [activeResort, activeSlug, isCardVisible]);

  const handleTouchStart = (event) => {
    if (event.touches.length !== 2) {
      return;
    }
    event.preventDefault();
    const [touchA, touchB] = event.touches;
    const distance = Math.hypot(touchB.clientX - touchA.clientX, touchB.clientY - touchA.clientY);
    const centerX = (touchA.clientX + touchB.clientX) / 2;
    const centerY = (touchA.clientY + touchB.clientY) / 2;
    pinchStateRef.current = {
      initialDistance: distance,
      initialScale: mapScale,
      initialCenter: { x: centerX, y: centerY },
      initialTranslate: mapTranslate,
    };
  };

  const handleTouchMove = (event) => {
    if (event.touches.length !== 2) {
      return;
    }
    event.preventDefault();
    const [touchA, touchB] = event.touches;
    const distance = Math.hypot(touchB.clientX - touchA.clientX, touchB.clientY - touchA.clientY);
    const centerX = (touchA.clientX + touchB.clientX) / 2;
    const centerY = (touchA.clientY + touchB.clientY) / 2;
    const { initialDistance, initialScale, initialCenter, initialTranslate } = pinchStateRef.current;
    if (!initialDistance || !initialCenter) {
      return;
    }
    const nextScale = Math.max(1, initialScale * (distance / initialDistance));
    const deltaX = centerX - initialCenter.x;
    const deltaY = centerY - initialCenter.y;
    setMapScale(nextScale);
    setMapTranslate({
      x: initialTranslate.x + deltaX,
      y: initialTranslate.y + deltaY,
    });
  };

  const handleTouchEnd = () => {
    pinchStateRef.current = {
      initialDistance: 0,
      initialScale: mapScale,
      initialCenter: null,
      initialTranslate: mapTranslate,
    };
  };

  const adjustMapScale = (delta) => {
    setMapScale((current) => {
      const nextScale = Math.max(1, current + delta);
      return nextScale;
    });
  };

  return (
    <div
      ref={mapRef}
      className="relative w-full overflow-hidden rounded-sm border-0 bg-transparent"
    >
      <div
        className="relative aspect-[16/9] w-full bg-transparent"
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={handleTouchEnd}
        style={{ touchAction: "none" }}
      >
        <div className="absolute right-4 top-4 z-30 flex flex-col gap-3">
          <button
            type="button"
            onClick={() => adjustMapScale(0.2)}
            className="flex h-12 w-12 items-center justify-center bg-white/90 text-[#2b5f8f] transition-transform duration-200 hover:scale-105"
            aria-label="放大地圖"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-9 w-9"
              aria-hidden="true"
              focusable="false"
            >
              <path
                d="M12 5V19M5 12H19"
                fill="none"
                stroke="currentColor"
                strokeWidth="1"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => adjustMapScale(-0.2)}
            className="flex h-12 w-12 items-center justify-center bg-white/90 text-[#2b5f8f] transition-transform duration-200 hover:scale-105"
            aria-label="縮小地圖"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-9 w-9"
              aria-hidden="true"
              focusable="false"
            >
              <path
                d="M5 12H19"
                fill="none"
                stroke="currentColor"
                strokeWidth="1"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
        <div
          className="absolute inset-0"
          style={{
            transform: `translate(${mapTranslate.x}px, ${mapTranslate.y}px) scale(${mapScale})`,
            transformOrigin: mapOrigin,
            touchAction: "none",
          }}
        >
          <img loading="lazy" decoding="async"
            src={encodeURI("/Course/Hokkaido map-ski-resorts.svg")}
            alt="Hokkaido map"
            className="absolute inset-0 h-full w-full object-contain opacity-80"
          />
          <div className="pointer-events-none absolute inset-0 text-sm md:text-base font-semibold tracking-[0.2em] text-[#2b5f8f] font-display">
            <span className="absolute left-[22%] top-[14%] md:left-[18%] md:top-[18%] md:translate-x-[100px]">道北</span>
            <span className="absolute right-[20%] top-[30%] md:right-[18%] md:top-[32%] md:-translate-x-[200px]">道東</span>
            <span className="absolute left-[26%] bottom-[20%] translate-x-[40px] translate-y-[10px] md:left-[28%] md:bottom-[18%] md:translate-x-[100px] md:translate-y-0">道央</span>
            <span className="absolute left-[10%] bottom-[8%] md:left-[6%] md:bottom-[10%] md:translate-x-[100px]">道南</span>
          </div>
          <div className="absolute inset-0 bg-transparent" />
          {resorts.map((resort) => {
            const position = markerPositions[resort.slug] || { left: "50%", top: "50%" };
            const isActive = resort.slug === activeSlug;

            return (
              <button
                key={resort.slug}
                type="button"
                onClick={() => setActiveSlug((slug) => (slug === resort.slug ? null : resort.slug))}
                ref={(node) => {
                  if (node) {
                    markerRefs.current[resort.slug] = node;
                  }
                }}
                className={`absolute z-10 flex h-4 w-4 md:h-5 md:w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center border-0 transition-all duration-200 ${
                  isActive
                    ? "text-[#f06150] drop-shadow-[0_0_10px_rgba(240,97,80,0.45)]"
                    : "text-[#f06150] drop-shadow-[0_6px_12px_rgba(240,97,80,0.35)] hover:scale-105"
                }`}
                style={{ left: position.left, top: position.top }}
                aria-pressed={isActive}
                aria-label={`${resort.nameChinese} marker`}
              >
                {isActive && (
                  <span className="absolute inset-0 rounded-full bg-current opacity-25 animate-ping" />
                )}
                <svg
                  viewBox="0 0 24 24"
                  className={`h-full w-full transition-transform duration-200 ${isActive ? "scale-110" : ""}`}
                  aria-hidden="true"
                  focusable="false"
                >
                  <path
                    fill="currentColor"
                    d="M12 2.5a6.5 6.5 0 0 0-6.5 6.5c0 4.1 4.4 9.2 6.1 11a.5.5 0 0 0 .8 0c1.7-1.8 6.1-6.9 6.1-11A6.5 6.5 0 0 0 12 2.5Zm0 9.5a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z"
                  />
                </svg>
              </button>
            );
          })}
        </div>

        {linePoints && (
          <svg
            className="absolute inset-0 z-[5] hidden md:block pointer-events-none"
            aria-hidden="true"
          >
            <line
              x1={linePoints.startX}
              y1={linePoints.startY}
              x2={linePoints.endX}
              y2={linePoints.endY}
              stroke="#f06150"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        )}

        {activeResort && (
          <div
            className={`hidden md:block absolute bottom-6 right-6 z-20 w-72 rounded-sm border border-white/70 bg-white/90 p-4 text-[#1f2937] shadow-[0_16px_30px_rgba(15,23,42,0.18)] backdrop-blur transition-all duration-300 ease-out ${
              isCardVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
            }`}
            ref={cardRef}
          >
            <div className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8]">
              {activeResort.region}
            </div>
            <div className="mt-2 text-lg font-semibold font-display">
              {activeResort.nameChinese}
            </div>
            <div className="text-sm text-[#64748b]">{activeResort.nameEnglish}</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {activeResort.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-[#e2e8f0] px-3 py-1 text-xs font-semibold text-[#475569]"
                >
                  {tag}
                </span>
              ))}
            </div>
            <SiteLink
              to={activeRoute}
              className="mt-4 inline-flex w-full items-center justify-center rounded-full border border-[#1f2937] px-4 py-2 text-sm font-semibold text-[#1f2937] transition-colors duration-200 hover:bg-[#1f2937] hover:text-white"
            >
              查看雪場資訊
            </SiteLink>
          </div>
        )}
      </div>
      {activeResort && (
        <div
          className={`md:hidden w-full border-t border-[#e2e8f0] bg-white/90 p-4 text-[#1f2937] transition-all duration-300 ease-out ${
            isCardVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
          }`}
        >
          <div className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8]">
            {activeResort.region}
          </div>
          <div className="mt-2 text-lg font-semibold font-display">
            {activeResort.nameChinese}
          </div>
          <div className="text-sm text-[#64748b]">{activeResort.nameEnglish}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {activeResort.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-[#e2e8f0] px-3 py-1 text-xs font-semibold text-[#475569]"
              >
                {tag}
              </span>
            ))}
          </div>
          <SiteLink
            to={activeRoute}
            className="mt-4 inline-flex w-full items-center justify-center rounded-full border border-[#1f2937] px-4 py-2 text-sm font-semibold text-[#1f2937] transition-colors duration-200 hover:bg-[#1f2937] hover:text-white"
          >
            查看雪場資訊
          </SiteLink>
        </div>
      )}
    </div>
  );
}

export default HokkaidoMap;
