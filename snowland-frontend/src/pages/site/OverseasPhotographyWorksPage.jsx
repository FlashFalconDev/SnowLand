import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import SiteLink from '../../components/site/SiteLink';
import { useSiteContent } from '../../hooks/useSiteContent';

function OverseasPhotographyWorksPage() {
  const baseUrl = import.meta.env.BASE_URL ?? "/";
  const withBaseUrl = (path) =>
    `${baseUrl}${path.startsWith("/") ? path.slice(1) : path}`;
  const { items: galleryItems, isLoading, error } = useSiteContent('photography.gallery');
  const categories = ["All", "影片", "地點", "拍攝類型"];
  const photoItems = galleryItems.filter((item) => item.metadata?.media_type === 'photo');
  const locationCategories = [...new Set(photoItems.map((item) => item.metadata?.location).filter(Boolean))];
  const shootTypeCategories = [...new Set(photoItems.flatMap((item) => item.metadata?.shoot_types ?? []))];
  const hoshinoCategories = [...new Set(
    photoItems
      .filter((item) => item.metadata?.location === '星野')
      .map((item) => item.metadata?.section)
      .filter(Boolean)
  )];
  const hoshinoPhotos = photoItems.reduce((groups, item) => {
    if (item.metadata?.location !== '星野' || !item.metadata?.section) return groups;
    groups[item.metadata.section] ??= [];
    groups[item.metadata.section].push(item.image_url);
    return groups;
  }, {});
  const videos = galleryItems
    .filter((item) => item.metadata?.media_type === 'video')
    .map((item) => ({ id: item.metadata.video_id, title: item.title }));
  const [activeCategory, setActiveCategory] = useState("All");
  const [activeLocationCategory, setActiveLocationCategory] = useState(
    "星野"
  );
  const [activeShootTypeCategory, setActiveShootTypeCategory] = useState(
    "親子"
  );
  const [isLocationExpanded, setIsLocationExpanded] = useState(false);
  const [isShootTypeExpanded, setIsShootTypeExpanded] = useState(false);
  const [isHoshinoExpanded, setIsHoshinoExpanded] = useState(false);
  const [activeHoshinoCategory, setActiveHoshinoCategory] = useState(
    "霧冰平台"
  );
  const [activeVideoId, setActiveVideoId] = useState(null);
  const [lightboxIndex, setLightboxIndex] = useState(null);

  useEffect(() => {
    if (!activeVideoId && videos[0]?.id) setActiveVideoId(videos[0].id);
  }, [activeVideoId, videos]);

  const allPhotos = photoItems.map((item) => item.image_url);
  const activePhotos = useMemo(() => {
    if (activeCategory === "地點") {
      if (activeLocationCategory === "星野") {
        return hoshinoPhotos[activeHoshinoCategory] || [];
      }
      return [];
    }
    if (activeCategory === "拍攝類型") {
      return photoItems
        .filter((item) => item.metadata?.shoot_types?.includes(activeShootTypeCategory))
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
    hoshinoPhotos,
    allPhotos,
    activeShootTypeCategory,
    photoItems,
  ]);
  const isFullBleedGallery = activeCategory !== "影片";

  useEffect(() => {
    if (lightboxIndex === null) {
      return undefined;
    }

    const onKeyDown = (event) => {
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
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [lightboxIndex, activePhotos.length]);

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main className="max-w-5xl mx-auto px-6 pt-32 pb-24 flex-1 w-full">
        <div className="text-center">
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            Gallery
          </p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
            攝影作品
          </h1>
        </div>
        {isLoading && <p className="py-16 text-center text-sm text-[#64748b]">正在載入攝影作品…</p>}
        {!isLoading && error && <p className="py-16 text-center text-sm text-red-600">攝影作品暫時無法載入，請稍後再試。</p>}
        {!isLoading && !error && galleryItems.length === 0 && (
          <p className="py-16 text-center text-sm text-[#64748b]">目前沒有已發布的攝影作品。</p>
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
                className={`transition-colors hover:text-[#2b5f8f] ${
                  activeCategory === category ? "text-[#2b5f8f]" : ""
                }`}
              >
                {category}
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
                    if (category === "星野") {
                      setIsHoshinoExpanded((prev) =>
                        activeLocationCategory === "星野" ? !prev : true
                      );
                    } else {
                      setIsHoshinoExpanded(false);
                    }
                    setActiveLocationCategory(category);
                  }}
                  className={`transition-colors hover:text-[#2b5f8f] ${
                    activeLocationCategory === category ? "text-[#2b5f8f]" : ""
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
          activeLocationCategory === "星野" &&
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
                  className={`transition-colors hover:text-[#2b5f8f] ${
                    activeHoshinoCategory === category ? "text-[#2b5f8f]" : ""
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
                  className={`transition-colors hover:text-[#2b5f8f] ${
                    activeShootTypeCategory === category ? "text-[#2b5f8f]" : ""
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
            <div className="w-full aspect-video bg-black">
              <iframe
                className="w-full h-full"
                src={`https://www.youtube.com/embed/${activeVideoId}`}
                title="Gallery video player"
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
                    activeVideoId === video.id ? "ring-2 ring-[#2b5f8f]" : ""
                  }`}
                >
                  <img loading="lazy" decoding="async"
                    src={`https://img.youtube.com/vi/${video.id}/hqdefault.jpg`}
                    alt={video.title}
                    className="w-full h-full object-cover"
                  />
                  {activeVideoId === video.id && (
                    <span className="absolute inset-0 bg-black/35 flex items-center justify-center text-xs font-semibold text-white">
                      Now Playing
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {activeCategory !== "影片" && (
          <div className="mt-12">
            <div
              className={`grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 ${
                isFullBleedGallery
                  ? "gap-0 w-screen relative left-1/2 right-1/2 -translate-x-1/2 overflow-hidden"
                  : "gap-4"
              }`}
            >
              {activePhotos.map((src, index) => (
                <button
                  key={src}
                  type="button"
                  onClick={() => setLightboxIndex(index)}
                  className="group relative overflow-hidden bg-[#e2e8f0] aspect-[4/3]"
                >
                  <img loading="lazy" decoding="async"
                    src={withBaseUrl(src)}
                    alt="Gallery"
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                </button>
              ))}
            </div>
            <div className="mt-12 flex justify-center">
              <SiteLink
                to="/booking?service=photo"
                className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
              >
                預約攝影
              </SiteLink>
            </div>
          </div>
        )}
          </>
        )}
      </main>
      <SiteFooter />

      {lightboxIndex !== null && activePhotos[lightboxIndex] && (
        <div className="fixed inset-0 z-[80] bg-black/80 flex items-center justify-center px-4">
          <button
            type="button"
            onClick={() => setLightboxIndex(null)}
            className="absolute top-6 right-6 text-white text-2xl"
            aria-label="Close"
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
            className="absolute left-4 md:left-8 text-white text-3xl"
            aria-label="Previous"
          >
            ‹
          </button>
          <img loading="lazy" decoding="async"
            src={withBaseUrl(activePhotos[lightboxIndex])}
            alt="Gallery preview"
            className="max-h-[80vh] max-w-[90vw] object-contain"
          />
          <button
            type="button"
            onClick={() =>
              setLightboxIndex((lightboxIndex + 1) % activePhotos.length)
            }
            className="absolute right-4 md:right-8 text-white text-3xl"
            aria-label="Next"
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}

export default OverseasPhotographyWorksPage;
