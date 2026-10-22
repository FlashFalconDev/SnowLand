import React, { useState } from 'react';
import SiteLink from './SiteLink';
import { useSiteContent } from '../../hooks/useSiteContent';
import { useSiteLocale } from '../../contexts/SiteLocale';

export default function PopularCourses() {
  const { t } = useSiteLocale();
  const [expandedCourses, setExpandedCourses] = useState({});
  const { items, isLoading, error, refetch } = useSiteContent('homepage.courses', { contentType: 'page' });
  const resortCards = items.map(item => ({id: item.id, title: item.title, description: item.summary || item.body || '', image: item.image_url, href: item.link_url, cta: item.subtitle || '立即查看課程'}));
  return (<section id="homepage-courses" className="bg-white scroll-mt-24">
        <div className="max-w-6xl mx-auto px-6 md:px-10 py-16 md:py-24">
          <div className="text-center mb-12 md:mb-16">
            <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
              Course
            </p>
            <h2 className="text-2xl font-semibold text-[#1f2937] mt-4 font-display">
              {t('熱門課程')}
            </h2>
          </div>

          {isLoading ? <p role="status" className="text-center text-sm text-[#475569]">{t('正在載入熱門課程…')}</p> : error ? <p role="alert" className="text-center text-sm text-red-700">{t('熱門課程載入失敗。')}<button type="button" className="ml-2 min-h-11 underline" onClick={refetch}>{t('重試熱門課程')}</button></p> : !resortCards.length ? <p className="text-center text-sm text-[#475569]">{t('目前尚無公開熱門課程。')}</p> : null}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 md:gap-16">
            {resortCards.map((resort) => (
              <article
                key={resort.id}
                className="group flex flex-col items-center w-full max-w-md mx-auto"
              >
                <h3 className="text-xl font-semibold text-[#2b2b2b] font-display tracking-wide text-center">
                  {resort.title}
                </h3>

                {resort.image && <div className="mt-6 w-full">
                  <div className="relative w-full h-56 md:h-60 shadow-[0_16px_28px_rgba(15,23,42,0.12)] overflow-hidden">
                    <img loading="lazy" decoding="async"
                      src={resort.image}
                      alt={`${resort.title} Course`}
                      className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/35 via-black/10 to-transparent opacity-70 transition-opacity duration-300 group-hover:opacity-90"></div>
                  </div>
                </div>}

                <div className="mt-6 text-[#3f3f3f] text-sm leading-relaxed w-full">
                  <p
                    style={
                      expandedCourses[resort.id]
                        ? undefined
                        : {
                          display: "-webkit-box",
                          WebkitLineClamp: 3,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }
                    }
                  >
                    {resort.description}
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedCourses((prev) => ({
                        ...prev,
                        [resort.id]: !prev[resort.id],
                      }))
                    }
                    aria-expanded={!!expandedCourses[resort.id]} className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-[#1f2937] hover:text-[#0f172a] transition-colors underline underline-offset-4"
                  >
                    {t(expandedCourses[resort.id] ? "收起" : "展開")}
                  </button>
                  <div className="w-12 h-px bg-[#c4c4c4] my-6 mx-auto"></div>
                  <div className="mt-6 text-center">
                    <SiteLink
                      to={resort.href}
                      className="inline-flex min-h-11 items-center justify-center px-8 py-2 rounded-full border border-[#1f2937] text-sm font-semibold text-[#1f2937] hover:border-[#4A6B8A] hover:bg-[#4A6B8A] hover:text-white transition-colors"
                    >
                      {t(resort.cta)}
                    </SiteLink>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>);
}
