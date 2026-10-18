import React, { useMemo, useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import { motion, useScroll, useTransform } from 'framer-motion';
import SpecialOffers from '../../components/site/SpecialOffers';
import PopularCourses from '../../components/site/PopularCourses';
import CoachLoadNotice from '../../components/site/CoachLoadNotice';
import { useWebsiteCoachCards } from '../../api/websiteCoaches';
import { fetchSiteContent } from '../../api/booking';
import SiteFooter from '../../components/site/SiteFooter';
import HomepagePresentation from '../../components/site/HomepagePresentation';

function HomePage() {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"]
  });

  const y = useTransform(scrollYProgress, [0, 1], ["0%", "50%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);
  const [isReviewsPaused, setIsReviewsPaused] = useState(false);
  const [expandedReviewIndex, setExpandedReviewIndex] = useState(null);
  const [cmsReviews, setCmsReviews] = useState([]);
  const [reviewsStatus, setReviewsStatus] = useState('loading');
  const [reviewRetry, setReviewRetry] = useState(0);
  const reviewTextRefs = useRef([]);
  const [clampedReviewIndices, setClampedReviewIndices] = useState([]);
  const { coaches: coachCards, isLoading: coachesLoading, error: coachesError, retry: retryCoaches } = useWebsiteCoachCards();
  const coachScrollerRef = useRef(null);
  const coachItemRefs = useRef([]);
  const [activeCoachIndex, setActiveCoachIndex] = useState(0);
  const totalCoachCards = coachCards.length;
  React.useEffect(() => {
    let mounted = true;
    setReviewsStatus('loading');
    fetchSiteContent({ content_type: 'review', location_key: 'homepage.reviews', limit: 12 })
      .then((items) => {
        if (mounted) { setCmsReviews(Array.isArray(items) ? items : []); setReviewsStatus('ready'); }
      })
      .catch(() => {
        if (mounted) { setCmsReviews([]); setReviewsStatus('error'); }
      });
    return () => {
      mounted = false;
    };
  }, [reviewRetry]);

  const reviews = useMemo(() => {
    return cmsReviews.map((item) => ({
      name: item.title || 'SnowLand 學員',
      initials: item.metadata?.initials || (item.title || 'SL').slice(0, 2).toUpperCase(),
      media: item.image_url ? 'image' : '',
      image: item.image_url || '',
      textPrimary: item.summary || item.body || item.subtitle || '',
      textSecondary: item.summary && item.body ? item.body : '',
    }));
  }, [cmsReviews]);
  const reviewsLoop = useMemo(() => [...reviews, ...reviews], [reviews]);

  React.useEffect(() => {
    const updateClamped = () => {
      const nextClamped = reviewsLoop.map((_, index) => {
        const node = reviewTextRefs.current[index];
        if (!node) return false;
        return node.scrollHeight > node.clientHeight + 1;
      });
      setClampedReviewIndices((current) => {
        if (
          current.length === nextClamped.length &&
          current.every((value, index) => value === nextClamped[index])
        ) {
          return current;
        }
        return nextClamped;
      });
    };

    updateClamped();
    window.addEventListener("resize", updateClamped);
    return () => window.removeEventListener("resize", updateClamped);
  }, [reviewsLoop, expandedReviewIndex]);

  const scrollToCoachIndex = (index) => {
    if (!totalCoachCards) return;
    const clampedIndex = Math.min(
      Math.max(index, 0),
      totalCoachCards - 1
    );
    const scroller = coachScrollerRef.current;
    const target = coachItemRefs.current[clampedIndex];
    if (!scroller || !target) return;
    const offset =
      target.offsetLeft - (scroller.clientWidth - target.clientWidth) / 2;
    scroller.scrollTo({ left: offset, behavior: "smooth" });
    setActiveCoachIndex(clampedIndex);
  };

  const renderCoachCardContent = (coach) => (
    <>
      <div className="w-full aspect-[5/4] bg-[#f8fafc]">
        {coach.image ? (
          <img loading="lazy" decoding="async"
            src={coach.image}
            alt={coach.name}
            className="w-full h-full object-cover object-top"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-[#eef3f8] text-3xl font-semibold text-[#94a3b8] font-display">
            {coach.name?.slice(0, 1)}
          </div>
        )}
      </div>

      <div className="px-8 py-10">
        <h3 className="text-lg font-semibold text-[#1f2937] font-lora">
          {coach.name}
        </h3>
        {coach.coachType && (
          <p className="mt-4 text-sm font-semibold text-[#4b5563]">
            {coach.coachType}
          </p>
        )}
        {coach.cardBio && (
          <p className="mt-4 text-sm text-[#6b7280] leading-relaxed">
            {coach.cardBio}
          </p>
        )}
        {coach.languages && (
          <p className="mt-4 text-sm font-semibold text-[#64748b]">
            {coach.languages}
          </p>
        )}
      </div>
    </>
  );

  return (
    <div className="w-full font-sans">
      <HomepagePresentation containerRef={containerRef} y={y} opacity={opacity} />

      <PopularCourses />

      <section id="homepage-reviews" className="bg-[#f3f6f9] scroll-mt-24">
        <div className="max-w-6xl mx-auto px-6 md:px-10 pt-16 md:pt-24">
          <div className="text-center mb-12 md:mb-16">
            <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
              Reviews
            </p>
            <h2 className="text-2xl font-semibold text-[#1f2937] mt-4 font-display">
              學員好評
            </h2>
            <p className="mt-4 text-sm text-[#6b7280]">
              <a
                href="https://share.google/jDAaMDoQQX6g8LUs9"
                className="relative group inline-flex items-center text-[#6b7280] hover:text-[#2b5f8f] transition-colors"
                target="_blank"
                rel="noopener noreferrer"
              >
                查看 Google 商家評價
                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-[#2b5f8f] transition-all duration-300 group-hover:w-full"></span>
              </a>
            </p>
            {reviewsStatus === 'loading' && <p role="status" className="mt-6 text-sm text-[#475569]">正在載入學員評價…</p>}
            {reviewsStatus === 'error' && <p role="alert" className="mt-6 text-sm text-red-700">學員評價載入失敗。<button type="button" className="ml-2 min-h-11 px-3 underline" onClick={() => setReviewRetry(value => value + 1)}>重試學員評價</button></p>}
            {reviewsStatus === 'ready' && !reviews.length && <p className="mt-6 text-sm text-[#475569]">目前尚無公開評價。</p>}
          </div>
        </div>

        <div
          className="group relative w-full overflow-x-hidden"
          onTouchStart={() => setIsReviewsPaused(true)}
          onTouchEnd={() => setIsReviewsPaused(false)}
          onTouchCancel={() => setIsReviewsPaused(false)}
        >
          <div className="py-6">
            <div
              className={`review-marquee-track flex gap-6 ${isReviewsPaused ? "is-paused" : ""}`}
            >
              {reviewsLoop.map((review, index) => (
                <article
                  key={`${review.name}-${index}`}
                  className={`review-card group w-[280px] sm:w-[320px] md:w-[360px] shrink-0 bg-[#f9fafb] border border-[#eef2f7] rounded-lg p-6 md:p-7 shadow-[0_10px_24px_rgba(15,23,42,0.06)] ${review.media ? "has-media" : "no-media"
                    } ${expandedReviewIndex === index ? "is-expanded" : ""}`}
                  onClick={() =>
                    setExpandedReviewIndex((prev) => (prev === index ? null : index))
                  }
                >
                  {review.media === "image" && review.image && (
                    <img
                      loading="lazy"
                      decoding="async"
                      src={review.image}
                      alt={review.name}
                      className="review-image mb-5 w-full rounded-lg object-cover"
                    />
                  )}
                  <div className="review-body">
                    <div className="flex flex-col gap-2">
                      <p className="text-base font-semibold text-[#2b5f8f] whitespace-nowrap">
                        {review.name}
                      </p>
                      <div className="flex gap-1">
                        {[...Array(5)].map((_, starIndex) => (
                          <svg
                            key={starIndex}
                            className="w-4 h-4 text-[#f5c542]"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            aria-hidden="true"
                          >
                            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.286 3.965a1 1 0 00.95.69h4.173c.969 0 1.371 1.24.588 1.81l-3.377 2.455a1 1 0 00-.364 1.118l1.286 3.965c.3.921-.755 1.688-1.54 1.118l-3.377-2.455a1 1 0 00-1.176 0l-3.377 2.455c-.784.57-1.838-.197-1.539-1.118l1.286-3.965a1 1 0 00-.364-1.118L2.02 9.392c-.783-.57-.38-1.81.588-1.81h4.174a1 1 0 00.95-.69l1.317-3.965z" />
                          </svg>
                        ))}
                      </div>
                    </div>
                    <p
                      ref={(node) => {
                        reviewTextRefs.current[index] = node;
                      }}
                      className={`review-text text-sm text-[#4b5563] leading-relaxed whitespace-pre-line ${expandedReviewIndex === index ? "" : "review-clamp"
                        } ${clampedReviewIndices[index] ? "is-clamped" : ""}`}
                    >
                      {review.textSecondary
                        ? `${review.textPrimary}\n${review.textSecondary}`
                        : review.textPrimary}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
        <div className="pb-16 md:pb-24"></div>
      </section>

      <section id="homepage-coaches" className="bg-white scroll-mt-24">
        <div className="max-w-6xl mx-auto px-6 md:px-10 py-16 md:py-24">
          <div className="text-center mb-12 md:mb-16">
            <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
              COACH
            </p>
            <h2 className="text-2xl font-semibold text-[#1f2937] mt-4 font-display">
              <SiteLink
                to="/coach"
                className="no-underline text-[#1f2937] hover:text-[#1f2937]"
              >
                教練團隊
              </SiteLink>
            </h2>
          </div>

          <CoachLoadNotice isLoading={coachesLoading} error={coachesError} count={coachCards.length} retry={retryCoaches} />
          <div className="md:hidden">
            <div
              ref={coachScrollerRef}
              className="flex gap-6 overflow-x-auto snap-x snap-mandatory scroll-smooth -mx-6 px-6 pb-4 hide-scrollbar"
              onScroll={(event) => {
                const scroller = event.currentTarget;
                const center = scroller.scrollLeft + scroller.clientWidth / 2;
                let closestIndex = 0;
                let closestDistance = Number.POSITIVE_INFINITY;
                coachItemRefs.current.forEach((item, index) => {
                  if (!item) return;
                  const itemCenter = item.offsetLeft + item.clientWidth / 2;
                  const distance = Math.abs(center - itemCenter);
                  if (distance < closestDistance) {
                    closestDistance = distance;
                    closestIndex = index;
                  }
                });
                setActiveCoachIndex(closestIndex);
              }}
            >
              {coachCards.map((coach, index) => {
                const className = "snap-center min-w-[80%] bg-white border border-[#e5e9f2] rounded-sm overflow-hidden text-center shadow-[0_20px_40px_rgba(15,23,42,0.08)]";
                const setCardRef = (node) => {
                  coachItemRefs.current[index] = node;
                };

                if (coach.slug) {
                  return (
                    <SiteLink
                      key={coach.name}
                      ref={setCardRef}
                      to={`/coach/${coach.slug}`}
                      className={className}
                    >
                      {renderCoachCardContent(coach)}
                    </SiteLink>
                  );
                }

                return (
                  <article key={coach.name} ref={setCardRef} className={className}>
                    {renderCoachCardContent(coach)}
                  </article>
                );
              })}
            </div>
            <div className="mt-4 flex items-center justify-center gap-2">
              {coachCards.map((coach, index) => (
                <button
                  key={`coach-dot-${coach.name}`}
                  type="button"
                  onClick={() => scrollToCoachIndex(index)}
                  aria-label={`View ${coach.name}`}
                  className={`h-2 w-2 rounded-full transition-colors ${activeCoachIndex === index ? "bg-[#2b5f8f]" : "bg-[#cbd5e1]"
                    }`}
                />
              ))}
            </div>
          </div>

          <div className="hidden md:grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 md:gap-10">
            {coachCards.map((coach) => {
              const className = "bg-white border border-[#e5e9f2] rounded-sm overflow-hidden text-center shadow-[0_20px_40px_rgba(15,23,42,0.08)] transition-transform duration-300 hover:-translate-y-1";

              if (coach.slug) {
                return (
                  <SiteLink key={coach.name} to={`/coach/${coach.slug}`} className={className}>
                    {renderCoachCardContent(coach)}
                  </SiteLink>
                );
              }

              return (
                <article key={coach.name} className={className}>
                  {renderCoachCardContent(coach)}
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <SpecialOffers />

      <section className="bg-white">
        <div className="max-w-4xl mx-auto px-6 md:px-10 py-16 md:py-20 text-center">
          <div
            className="relative mx-auto w-full max-w-[724px] overflow-hidden rounded-sm border border-[#e2e8f0] px-6 py-8 md:h-[190px] md:px-10 md:py-0 flex flex-col items-center justify-center bg-cover"
            style={{
              backgroundImage: "url(/Course/off-piste-guide/off-piste-guide-006.jpg)",
              backgroundPosition: "center 60%",
            }}
          >
            <div className="absolute inset-0 bg-black/20" />
            <div className="relative z-10">
              <h2 className="text-2xl font-semibold text-white font-display">
                <span className="block md:inline">不知道該選哪個雪場</span>
                <span className="block md:inline">或課程天數？</span>
              </h2>
              <p className="mt-4 text-sm md:text-base text-white/90 leading-relaxed">
                <span className="block md:inline">歡迎與我們聯繫，協助你規劃</span>
                <span className="block md:inline">最適合你的滑雪旅程。</span>
              </p>
              <div className="mt-8">
                <SiteLink
                  to="/contact"
                  className="inline-flex items-center justify-center rounded-full bg-[#8ec8f0] px-6 py-3 text-sm font-semibold text-white hover:bg-[#7bbbe7] transition-colors"
                >
                  立即諮詢
                </SiteLink>
              </div>
            </div>
          </div>
        </div>
      </section>

      <SiteFooter />

    </div>
  );
}

export default HomePage;
