import {useSiteLocale} from '../../contexts/SiteLocale';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import SiteLink from '../../components/site/SiteLink';
import { useSiteContent } from '../../hooks/useSiteContent';

function OverseasPhotographyWorksPage() {
  const {t} = useSiteLocale();
  const baseUrl = import.meta.env.BASE_URL ?? "/";
  const withBaseUrl = (path) => {
    if (typeof path !== 'string' || /[\\\x00-\x1f]/.test(path) || path.startsWith('//')) return '';
    if (/^https?:\/\//i.test(path)) return path;
    return path.startsWith('/') ? `${baseUrl}${path.slice(1)}` : '';
  };
  const { items, isLoading, error } = useSiteContent('photography.gallery');
  const galleryItems = items.filter((item) => item && typeof item === 'object');
  const categories = ["All", "影片", "地點", "拍攝類型"];
  const photoItems = galleryItems.filter((item) => (item.metadata?.media_type ?? 'photo') === 'photo' && withBaseUrl(item.image_url));
  const locationCategories = [...new Set(photoItems.map((item) => item.metadata?.location).filter(value => typeof value === 'string' && value))];
  const typesFor = item => Array.isArray(item.metadata?.shoot_types) ? item.metadata.shoot_types.filter(value => typeof value === 'string' && value) : [];
  const shootTypeCategories = [...new Set(photoItems.flatMap(typesFor))];
  const videos = galleryItems
    .filter((item) => item.metadata?.media_type === 'video')
    .map((item) => ({ id: item.metadata.video_id, title: item.title }))
    .filter(video => typeof video.id === 'string' && /^[A-Za-z0-9_-]{11}$/.test(video.id));
  const [activeCategory, setActiveCategory] = useState("All");
  const [activeLocationCategory, setActiveLocationCategory] = useState(
    ""
  );
  const [activeShootTypeCategory, setActiveShootTypeCategory] = useState(
    ""
  );
  const [isLocationExpanded, setIsLocationExpanded] = useState(false);
  const [isShootTypeExpanded, setIsShootTypeExpanded] = useState(false);
  const [isHoshinoExpanded, setIsHoshinoExpanded] = useState(false);
  const [activeHoshinoCategory, setActiveHoshinoCategory] = useState(
    ""
  );
  const [activeVideoId, setActiveVideoId] = useState(null);
  const [lightboxIndex, setLightboxIndex] = useState(null);
  const lightboxRef = useRef(null);
  const closeRef = useRef(null);
  const selectedLocation = locationCategories.includes(activeLocationCategory) ? activeLocationCategory : locationCategories[0] || '';
  const selectedType = shootTypeCategories.includes(activeShootTypeCategory) ? activeShootTypeCategory : shootTypeCategories[0] || '';
  const locationPhotos = photoItems.filter(item => item.metadata?.location === selectedLocation);
  const hoshinoCategories = [...new Set(locationPhotos.map(item => item.metadata?.section).filter(value => typeof value === 'string' && value))];
  const selectedSection = hoshinoCategories.includes(activeHoshinoCategory) ? activeHoshinoCategory : hoshinoCategories[0] || '';
  const selectedVideoId = videos.some(video => video.id === activeVideoId) ? activeVideoId : videos[0]?.id;

  useEffect(() => {
    if (!activeVideoId && videos[0]?.id) setActiveVideoId(videos[0].id);
  }, [activeVideoId, videos]);

  const allPhotos = photoItems.map((item) => item.image_url);
  const activePhotos = useMemo(() => {
    if (activeCategory === "地點") {
      return locationPhotos.filter(item => !isHoshinoExpanded || !selectedSection || item.metadata?.section === selectedSection).map(item => item.image_url);
    }
    if (activeCategory === "拍攝類型") {
      return photoItems
        .filter((item) => typesFor(item).includes(selectedType))
        .map((item) => item.image_url);
    }
    if (activeCategory === "All") {
      return allPhotos;
    }
    return [];
  }, [
    activeCategory,
    activeHoshinoCategory,
    activeLocationCategory,
    locationPhotos,
    selectedSection,
    selectedType,
    isHoshinoExpanded,
    allPhotos,
    activeShootTypeCategory,
    photoItems,
  ]);
  const isFullBleedGallery = activeCategory !== "影片";

  useEffect(() => {
    if (lightboxIndex === null || !activePhotos.length) {
      return undefined;
    }
    const previousFocus = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === 'Tab') {
        const controls = lightboxRef.current?.querySelectorAll('button');
        const first = controls?.[0], last = controls?.[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
      if (event.key === "Escape") {
        setLightboxIndex(null);
      }
      if (event.key === "ArrowRight") {
        setLightboxIndex((prev) =>
          prev === null ? prev : (prev + 1) % activePhotos.length
        );
      }
      if (event.key === "ArrowLeft") {
        setLightboxIndex((prev) =>
          prev === null
            ? prev
            : (prev - 1 + activePhotos.length) % activePhotos.length
        );
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [lightboxIndex, activePhotos.length]);

  return (
    <div className="min-h-screen overflow-x-clip bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main className="max-w-5xl mx-auto px-6 pt-32 pb-24 flex-1 w-full">
        <div className="text-center">
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            Gallery
          </p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">{t("攝影作品")}</h1>
        </div>
        {isLoading && <p className="py-16 text-center text-sm text-[#64748b]">{t("正在載入攝影作品…")}</p>}
        {!isLoading && error && <p className="py-16 text-center text-sm text-red-600">{t("攝影作品暫時無法載入，請稍後再試。")}</p>}
        {!isLoading && !error && galleryItems.length === 0 && (
          <p className="py-16 text-center text-sm text-[#64748b]">{t("目前沒有已發布的攝影作品。")}</p>
        )}
        {galleryItems.length > 0 && (
          <>
        <div className="mt-10 flex flex-wrap justify-center gap-y-2 text-sm font-semibold text-[#1f2937] font-display">
          {categories.map((category, index) => (
            <span key={category} className="flex items-center">
              <button
                type="button"
                onClick={() => {
                  if (category === "地點") {
                    setIsLocationExpanded((prev) =>
                      activeCategory === "地點" ? !prev : true
                    );
                    setIsShootTypeExpanded(false);
                    setActiveCategory("地點");
                    return;
                  }
                  if (category === "拍攝類型") {
                    setIsShootTypeExpanded((prev) =>
                      activeCategory === "拍攝類型" ? !prev : true
                    );
                    setIsLocationExpanded(false);
                    setIsHoshinoExpanded(false);
                    setActiveCategory("拍攝類型");
                    return;
                  }
                  setIsLocationExpanded(false);
                  setIsShootTypeExpanded(false);
                  setIsHoshinoExpanded(false);
                  setActiveCategory(category);
                }}
                className={`min-h-11 min-w-11 transition-colors hover:text-[#2b5f8f] ${
                  activeCategory === category ? "text-[#2b5f8f]" : ""
                }`}
              >
                {t(category === 'All' ? '全部分類' : category)}
              </button>
              {index < categories.length - 1 && (
                <span className="mx-2 text-[#cbd5e1]">/</span>
              )}
            </span>
          ))}
        </div>
        {activeCategory === "地點" && isLocationExpanded && (
          <motion.div
            className="mt-6 flex flex-wrap justify-center gap-y-2 text-sm font-semibold text-[#1f2937] font-display"
            initial="hidden"
            animate="visible"
            variants={{
              hidden: { opacity: 0 },
              visible: { opacity: 1, transition: { staggerChildren: 0.06 } },
            }}
          >
            {locationCategories.map((category, index) => (
              <motion.span
                key={category}
                className="flex items-center"
                variants={{
                  hidden: { opacity: 0, x: -16 },
                  visible: { opacity: 1, x: 0 },
                }}
                transition={{ duration: 0.35, ease: "easeOut" }}
              >
                <button
                  type="button"
                  onClick={() => {
                    if (photoItems.some(item => item.metadata?.location === category && item.metadata?.section)) {
                      setIsHoshinoExpanded((prev) =>
                        selectedLocation === category ? !prev : true
                      );
                    } else {
                      setIsHoshinoExpanded(false);
                    }
                    setActiveLocationCategory(category);
                  }}
                  className={`min-h-11 min-w-11 transition-colors hover:text-[#2b5f8f] ${
                    selectedLocation === category ? "text-[#2b5f8f]" : ""
                  }`}
                >
                  {category}
                </button>
                {index < locationCategories.length - 1 && (
                  <span className="mx-2 text-[#cbd5e1]">/</span>
                )}
              </motion.span>
            ))}
          </motion.div>
        )}

        {activeCategory === "地點" &&
          isLocationExpanded &&
          hoshinoCategories.length > 0 &&
          isHoshinoExpanded && (
          <motion.div
            className="mt-6 flex flex-wrap justify-center gap-y-2 text-sm font-semibold text-[#1f2937] font-display"
            initial="hidden"
            animate="visible"
            variants={{
              hidden: { opacity: 0 },
              visible: { opacity: 1, transition: { staggerChildren: 0.06 } },
            }}
          >
            {hoshinoCategories.map((category, index) => (
              <motion.span
                key={category}
                className="flex items-center"
                variants={{
                  hidden: { opacity: 0, x: -16 },
                  visible: { opacity: 1, x: 0 },
                }}
                transition={{ duration: 0.35, ease: "easeOut" }}
              >
                <button
                  type="button"
                  onClick={() => setActiveHoshinoCategory(category)}
                  className={`min-h-11 min-w-11 transition-colors hover:text-[#2b5f8f] ${
                    selectedSection === category ? "text-[#2b5f8f]" : ""
                  }`}
                >
                  {category}
                </button>
                {index < hoshinoCategories.length - 1 && (
                  <span className="mx-2 text-[#cbd5e1]">/</span>
                )}
              </motion.span>
            ))}
          </motion.div>
        )}

        {activeCategory === "拍攝類型" && isShootTypeExpanded && (
          <motion.div
            className="mt-6 flex flex-wrap justify-center gap-y-2 text-sm font-semibold text-[#1f2937] font-display"
            initial="hidden"
            animate="visible"
            variants={{
              hidden: { opacity: 0 },
              visible: { opacity: 1, transition: { staggerChildren: 0.06 } },
            }}
          >
            {shootTypeCategories.map((category, index) => (
              <motion.span
                key={category}
                className="flex items-center"
                variants={{
                  hidden: { opacity: 0, x: -16 },
                  visible: { opacity: 1, x: 0 },
                }}
                transition={{ duration: 0.35, ease: "easeOut" }}
              >
                <button
                  type="button"
                  onClick={() => setActiveShootTypeCategory(category)}
                  className={`min-h-11 min-w-11 transition-colors hover:text-[#2b5f8f] ${
                    selectedType === category ? "text-[#2b5f8f]" : ""
                  }`}
                >
                  {category}
                </button>
                {index < shootTypeCategories.length - 1 && (
                  <span className="mx-2 text-[#cbd5e1]">/</span>
                )}
              </motion.span>
            ))}
          </motion.div>
        )}

        {activeCategory === "影片" && (
          <div className="mt-12">
            {!selectedVideoId ? <p className="py-12 text-center text-sm text-[#64748b]">{t("目前沒有已發布的影片。")}</p> : <>
            <div className="w-full aspect-video bg-black">
              <iframe
                className="w-full h-full"
                src={`https://www.youtube.com/embed/${selectedVideoId}`}
                title={t('作品影片播放器')}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              ></iframe>
            </div>
            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
              {videos.map((video) => (
                <button
                  key={video.id}
                  type="button"
                  onClick={() => setActiveVideoId(video.id)}
                  className={`relative overflow-hidden ${
                    selectedVideoId === video.id ? "ring-2 ring-[#2b5f8f]" : ""
                  }`}
                >
                  <img loading="lazy" decoding="async"
                    src={`https://img.youtube.com/vi/${video.id}/hqdefault.jpg`}
                    alt={video.title}
                    className="w-full h-full object-cover"
                  />
                  {selectedVideoId === video.id && (
                    <span className="absolute inset-0 bg-black/35 flex items-center justify-center text-xs font-semibold text-white">
                      {t('目前選取影片')}
                    </span>
                  )}
                </button>
              ))}
            </div>
            </>}
          </div>
        )}

        {activeCategory !== "影片" && (
          <div className="mt-12">
            {!activePhotos.length && <p className="py-12 text-center text-sm text-[#64748b]">{t("這個分類目前沒有已發布的照片。")}</p>}
            <div
              className={`grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 ${
                isFullBleedGallery
                  ? "gap-0 w-screen relative left-1/2 right-1/2 -translate-x-1/2 overflow-hidden"
                  : "gap-4"
              }`}
            >
              {activePhotos.map((src, index) => (
                <button
                  key={`${src}-${index}`}
                  aria-label={t('查看攝影作品：{title}',{title:photoItems.find(item => item.image_url === src)?.title || t('攝影作品')})}
                  type="button"
                  onClick={() => setLightboxIndex(index)}
                  className="group relative overflow-hidden bg-[#e2e8f0] aspect-[4/3]"
                >
                  <img loading="lazy" decoding="async"
                    src={withBaseUrl(src)}
                    alt={photoItems.find(item => item.image_url === src)?.title || t('攝影作品')}
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                </button>
              ))}
            </div>
          </div>
        )}
            <div className="mt-12 flex justify-center">
              <SiteLink
                to="/booking?service=photo"
                className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
              >{t("預約攝影")}</SiteLink>
            </div>
          </>
        )}
      </main>
      <SiteFooter />

      {lightboxIndex !== null && activePhotos[lightboxIndex] && (
        <div ref={lightboxRef} role="dialog" aria-modal="true" aria-label={t("攝影作品預覽")} className="fixed inset-0 z-[80] bg-black/80 flex items-center justify-center px-4">
          <button
            ref={closeRef}
            type="button"
            onClick={() => setLightboxIndex(null)}
            className="absolute top-6 right-6 min-h-11 min-w-11 text-white text-2xl"
            aria-label={t('關閉')}
          >
            ✕
          </button>
          <button
            type="button"
            onClick={() =>
              setLightboxIndex(
                (lightboxIndex - 1 + activePhotos.length) % activePhotos.length
              )
            }
            className="absolute left-4 md:left-8 min-h-11 min-w-11 text-white text-3xl"
            aria-label={t('上一張作品')}
          >
            ‹
          </button>
          <img loading="lazy" decoding="async"
            src={withBaseUrl(activePhotos[lightboxIndex])}
            alt={t('攝影作品預覽')}
            className="max-h-[80vh] max-w-[90vw] object-contain"
          />
          <button
            type="button"
            onClick={() =>
              setLightboxIndex((lightboxIndex + 1) % activePhotos.length)
            }
            className="absolute right-4 md:right-8 min-h-11 min-w-11 text-white text-3xl"
            aria-label={t('下一張作品')}
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}

export default OverseasPhotographyWorksPage;
