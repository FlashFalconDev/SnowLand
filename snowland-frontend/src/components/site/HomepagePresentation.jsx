import React, {useState} from 'react';
import {motion} from 'framer-motion';
import SiteHeader from './SiteHeader';
import SiteLink from './SiteLink';
import aboutSnowland from '../../assets/site/About snowland.jpg';
import {useSiteContent} from '../../hooks/useSiteContent';

function ContentState({result,label}) {
  if (result.isLoading) return <p role="status" className="px-6 py-32 text-center text-sm text-[#475569]">正在載入{label}…</p>;
  if (result.error) return <div role="alert" className="px-6 py-32 text-center text-sm text-red-700">{label}載入失敗。<button type="button" className="min-h-11 px-3 underline" onClick={result.refetch}>重新載入{label}</button></div>;
  return null;
}

export default function HomepagePresentation({containerRef,y,opacity}) {
  const heroResult=useSiteContent('homepage.hero'),introResult=useSiteContent('homepage.intro');
  const hero=heroResult.items[0],intro=introResult.items[0];
  const [showAboutMore,setShowAboutMore]=useState(false);
  const videoId=hero?.metadata?.youtube_id;
  const videoSrc=hero?.metadata?.media_type==='youtube' && /^[A-Za-z0-9_-]{11}$/.test(videoId || '') ? `https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1&controls=0&loop=1&playlist=${videoId}&playsinline=1&showinfo=0&rel=0&iv_load_policy=3&disablekb=1&modestbranding=1&autohide=1&enablejsapi=1` : '';
  const extraParagraphs=Array.isArray(intro?.metadata?.extra_paragraphs) ? intro.metadata.extra_paragraphs.filter(text=>typeof text==='string') : [];
  const introHasImage=Boolean(intro?.image_url || intro?.metadata?.image_asset === 'original-school-photo');
  return <>
    <SiteHeader forceDarkText={!hero} forceLogoColor={!hero} />
    <div ref={containerRef}>
    {hero ? <>
      <div className="relative w-full h-screen overflow-hidden bg-[#143a53]">

        {videoSrc && <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0"><div className="absolute top-1/2 left-1/2 min-w-full min-h-full w-[177.77vh] h-[56.25vw] -translate-x-1/2 -translate-y-1/2 pointer-events-none"><iframe className="w-full h-full scale-105" src={videoSrc} title="Background Video" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowFullScreen /></div></div>}
        {hero.metadata?.media_type === 'image' && hero.image_url && <img src={hero.image_url} alt="" className="absolute inset-0 h-full w-full object-cover" />}

        {/* Dark Overlay with Gradient */}
        <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-b from-black/60 via-black/40 to-black/70 z-10 pointer-events-none"></div>

        {/* Content Container */}
        <motion.div
          style={{ y, opacity }}
          className="relative z-20 w-full h-full flex flex-col items-center justify-center text-center px-4 md:px-8 text-white max-w-7xl mx-auto"
        >

          {/* Main Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
            className="whitespace-pre-line text-2xl md:text-4xl lg:text-5xl font-bold mb-6 tracking-wide drop-shadow-xl font-display leading-tight"
          >
            {hero.title}
          </motion.h1>

          {/* Subhead CN */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4, ease: "easeOut" }}
            className="text-base md:text-lg lg:text-xl font-medium mb-4 tracking-wider drop-shadow-md opacity-95 text-balance"
          >
            {hero.summary}
          </motion.p>

          {/* Subhead EN */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6, ease: "easeOut" }}
            className="text-xs md:text-sm lg:text-base font-light mb-16 tracking-wide font-inter italic opacity-80 max-w-3xl mx-auto"
          >
            {hero.subtitle}
          </motion.p>

          {/* CTA Button */}
          {hero.link_url && hero.metadata?.button_text && <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.8, ease: "easeOut" }}
          >
            <SiteLink
              to={hero.link_url}
              className="group relative inline-flex items-center justify-center px-10 py-5 text-sm md:text-base font-bold text-white transition-all duration-300 bg-[#8ec8f0] rounded-full hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden"
            >
              {/* Shimmer Effect */}
              <div className="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>

              <span className="relative z-10">{hero.metadata.button_text}</span>
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
          </motion.div>}
        </motion.div>

        <a
          href="#about-snowland"
          aria-label="Scroll down"
          className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20 text-white/80 hover:text-white transition-colors"
        >
          <div className="w-11 h-11 flex items-center justify-center">
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M6 9l6 6 6-6" />
            </svg>
          </div>
        </a>
      </div>
    </> : <ContentState result={heroResult} label="首頁主視覺" />}
    </div>
    {intro ? <>
      <section id="about-snowland" className="bg-white scroll-mt-24">
        <div className={`grid grid-cols-1 ${introHasImage ? 'lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]' : ''} gap-6 md:gap-12 lg:gap-16 items-center`}>
          {(intro.image_url || intro.metadata?.image_asset === 'original-school-photo') && <div className="w-full h-72 md:h-[420px] lg:h-full min-h-[420px]">
            <img loading="eager" decoding="async" fetchpriority="high"
              src={intro.image_url || (intro.metadata?.image_asset === 'original-school-photo' ? aboutSnowland : undefined)}
              alt="Snowland 滑雪學校"
              className="w-full h-full object-cover"
            />
          </div>}

          <div className="px-6 md:px-10 pt-10 pb-16 md:py-24">
            <div className="max-w-2xl text-[#2b2b2b] text-sm md:text-base leading-relaxed space-y-6">
              <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                {intro.title}
              </h2>
              <p>
                {intro.metadata?.opening_text}
                <span className="font-semibold">
                  {intro.metadata?.resort_names}
                </span>
                {intro.metadata?.opening_suffix}
              </p>
              <p>
                {intro.metadata?.language_prefix}
                <span className="font-semibold">{intro.metadata?.languages}</span>
                {intro.metadata?.language_suffix}
              </p>
              {showAboutMore &&
                extraParagraphs.map((text, index) => (
                  <p key={`about-more-${index}`}>{text}</p>
                ))}
              {extraParagraphs.length > 0 && <button
                type="button"
                onClick={() => setShowAboutMore((prev) => !prev)}
                aria-expanded={showAboutMore}
                className="min-h-11 inline-flex items-center text-sm font-semibold text-[#1f2937] hover:text-[#0f172a] transition-colors underline underline-offset-4"
              >
                {showAboutMore ? "收起" : "展開"}
              </button>}
              {intro.link_url && intro.metadata?.button_text && <div className="flex justify-center">
                <SiteLink
                  to={intro.link_url}
                  className="relative z-10 pointer-events-auto min-h-11 inline-flex items-center justify-center px-6 py-2 rounded-full border border-[#1f2937] text-sm font-semibold text-[#1f2937] hover:border-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white transition-colors"
                >
                  {intro.metadata.button_text}
                </SiteLink>
              </div>}
            </div>
          </div>
        </div>
      </section>
    </> : <ContentState result={introResult} label="首頁學校介紹" />}
  </>;
}
