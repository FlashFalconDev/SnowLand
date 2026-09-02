import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';

function OverseasPhotographyWorksPage() {
  const baseUrl = import.meta.env.BASE_URL ?? "/";
  const withBaseUrl = (path) =>
    `${baseUrl}${path.startsWith("/") ? path.slice(1) : path}`;
  const categories = ["All", "影片", "地點", "拍攝類型"];
  const locationCategories = ["星野", "富良野", "旭岳"];
  const shootTypeCategories = ["親子", "滑雪側拍", "個人寫真"];
  const hoshinoCategories = [
    "霧冰平台",
    "CENTER",
    "高農場騎馬",
    "高農場冰滑梯",
    "溜滑梯公園",
    "螢火蟲餐廳街",
    "森林餐廳",
    "Club Med",
    "冰上釣魚",
  ];
  const hoshinoPhotos = useMemo(
    () => ({
      "霧冰平台": [
        "/photography-gallery/gallery-001.jpg",
        "/photography-gallery/gallery-002.jpg",
        "/photography-gallery/gallery-003.jpg",
        "/photography-gallery/gallery-004.jpg",
        "/photography-gallery/gallery-005.jpg",
        "/photography-gallery/gallery-006.jpg",
        "/photography-gallery/gallery-007.jpg",
        "/photography-gallery/gallery-008.jpg",
      ],
      CENTER: [
        "/photography-gallery/gallery-009.jpg",
        "/photography-gallery/gallery-010.jpg",
        "/photography-gallery/gallery-011.jpg",
        "/photography-gallery/gallery-012.jpg",
        "/photography-gallery/gallery-013.jpg",
        "/photography-gallery/gallery-014.jpg",
        "/photography-gallery/gallery-015.jpg",
        "/photography-gallery/gallery-016.jpg",
      ],
      "高農場騎馬": [
        "/photography-gallery/gallery-017.jpg",
        "/photography-gallery/gallery-018.jpg",
        "/photography-gallery/gallery-019.jpg",
        "/photography-gallery/gallery-020.jpg",
        "/photography-gallery/gallery-021.jpg",
        "/photography-gallery/gallery-022.jpg",
        "/photography-gallery/gallery-023.jpg",
        "/photography-gallery/gallery-024.jpg",
      ],
      "高農場冰滑梯": [
        "/photography-gallery/gallery-025.jpg",
        "/photography-gallery/gallery-026.jpg",
        "/photography-gallery/gallery-027.jpg",
        "/photography-gallery/gallery-028.jpg",
        "/photography-gallery/gallery-029.jpg",
        "/photography-gallery/gallery-030.jpg",
        "/photography-gallery/gallery-031.jpg",
        "/photography-gallery/gallery-032.jpg",
      ],
      "溜滑梯公園": [
        "/photography-gallery/gallery-033.jpg",
        "/photography-gallery/gallery-034.jpg",
        "/photography-gallery/gallery-035.jpg",
        "/photography-gallery/gallery-036.jpg",
        "/photography-gallery/gallery-037.jpg",
        "/photography-gallery/gallery-038.jpg",
        "/photography-gallery/gallery-039.jpg",
        "/photography-gallery/gallery-040.jpg",
      ],
      "螢火蟲餐廳街": [
        "/photography-gallery/gallery-041.jpg",
        "/photography-gallery/gallery-042.jpg",
        "/photography-gallery/gallery-043.jpg",
        "/photography-gallery/gallery-044.jpg",
        "/photography-gallery/gallery-045.jpg",
        "/photography-gallery/gallery-046.jpg",
        "/photography-gallery/gallery-047.jpg",
        "/photography-gallery/gallery-048.jpg",
      ],
      "森林餐廳": [
        "/photography-gallery/gallery-049.jpg",
        "/photography-gallery/gallery-050.jpg",
        "/photography-gallery/gallery-051.jpg",
        "/photography-gallery/gallery-052.jpg",
        "/photography-gallery/gallery-053.jpg",
        "/photography-gallery/gallery-054.jpg",
        "/photography-gallery/gallery-055.jpg",
        "/photography-gallery/gallery-056.jpg",
      ],
      "Club Med": [
        "/photography-gallery/gallery-057.jpg",
        "/photography-gallery/gallery-058.jpg",
        "/photography-gallery/gallery-059.jpg",
        "/photography-gallery/gallery-060.jpg",
        "/photography-gallery/gallery-061.jpg",
        "/photography-gallery/gallery-062.jpg",
        "/photography-gallery/gallery-063.jpg",
        "/photography-gallery/gallery-064.jpg",
      ],
      "冰上釣魚": [
        "/photography-gallery/gallery-065.jpg",
        "/photography-gallery/gallery-066.jpg",
        "/photography-gallery/gallery-067.jpg",
        "/photography-gallery/gallery-068.jpg",
        "/photography-gallery/gallery-069.jpg",
        "/photography-gallery/gallery-070.jpg",
        "/photography-gallery/gallery-071.jpg",
        "/photography-gallery/gallery-072.jpg",
      ],
    }),
    []
  );
  const expandIndices = (items) => {
    const result = [];
    items.forEach((item) => {
      if (Array.isArray(item)) {
        const [start, end] = item;
        for (let i = start; i <= end; i += 1) {
          result.push(i);
        }
        return;
      }
      result.push(item);
    });
    return result;
  };
  const shootTypeIndexMap = useMemo(
    () => ({
      親子: expandIndices([5, 6, 7, 8, [13, 24], [27, 43], 47, 48]),
      滑雪側拍: expandIndices([44, 45, 46]),
      個人寫真: expandIndices([1, 2, 3, 4, [9, 12], 25, 26, [49, 64]]),
    }),
    []
  );
  const videos = useMemo(
    () => [
      { id: "nPFLW9HsjdU", title: "Gallery Video 01" },
      { id: "s5OAiq3woco", title: "Gallery Video 02" },
      { id: "RM7SCH0oxAo", title: "Gallery Video 03" },
      { id: "nDpetYyg6M4", title: "Gallery Video 04" },
    ],
    []
  );
  const [activeCategory, setActiveCategory] = useState("All");
  const [activeLocationCategory, setActiveLocationCategory] = useState(
    locationCategories[0]
  );
  const [activeShootTypeCategory, setActiveShootTypeCategory] = useState(
    shootTypeCategories[0]
  );
  const [isLocationExpanded, setIsLocationExpanded] = useState(false);
  const [isShootTypeExpanded, setIsShootTypeExpanded] = useState(false);
  const [isHoshinoExpanded, setIsHoshinoExpanded] = useState(false);
  const [activeHoshinoCategory, setActiveHoshinoCategory] = useState(
    hoshinoCategories[0]
  );
  const [activeVideoId, setActiveVideoId] = useState(videos[0].id);
  const [lightboxIndex, setLightboxIndex] = useState(null);

  const allPhotos = useMemo(
    () => Object.values(hoshinoPhotos).flat(),
    [hoshinoPhotos]
  );
  const activePhotos = useMemo(() => {
    if (activeCategory === "地點") {
      if (activeLocationCategory === "星野") {
        return hoshinoPhotos[activeHoshinoCategory] || [];
      }
      return [];
    }
    if (activeCategory === "拍攝類型") {
      const indices = new Set(
        shootTypeIndexMap[activeShootTypeCategory] ?? []
      );
      return allPhotos.filter((_, index) => indices.has(index + 1));
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
    shootTypeIndexMap,
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
              <a
                href="#"
                className="inline-flex items-center justify-center rounded-full border border-[#1f2937] px-8 py-3 text-sm font-semibold text-[#1f2937] transition-colors hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white"
              >
                預約攝影
              </a>
            </div>
          </div>
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
