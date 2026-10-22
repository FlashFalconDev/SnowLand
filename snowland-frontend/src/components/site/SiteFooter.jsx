import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import SiteLink from './SiteLink';
import logo from '../../assets/site/logo-white.png';
import { homepageAssetBase } from '../../data/site/assetPaths';
import { faqLink } from '../../data/site/navigationLinks';
import { useSiteContent } from '../../hooks/useSiteContent';
import { footerSettings } from '../../data/site/footerSettings';
import { useSiteLocale } from '../../contexts/SiteLocale';

function SiteFooter() {
  const {t} = useSiteLocale();
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const {items, isLoading, error, refetch} = useSiteContent('site.footer', {limit:1});
  const settings = footerSettings(items[0]);
  const chatLinks = settings.links.filter(link => ['line','whatsapp'].includes(link.key));

  useEffect(() => {
    const onScroll = () => {
      setShowScrollTop(window.scrollY > 400);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <footer id="site-footer" className="scroll-mt-24 bg-gradient-to-br from-[#2b5f8f] via-[#3c78b6] to-[#5aa6c9] border-t border-[#275680] text-white">
      <div className="max-w-6xl mx-auto px-6 md:px-10 py-14 md:py-20">
        {isLoading && <p role="status" className="mb-4 text-sm">{t('載入聯絡資訊…')}</p>}
        {error && <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 text-sm"><span>{t('聯絡資訊暫時無法載入')}</span><button type="button" onClick={refetch} className="min-h-11 rounded border border-white/60 px-3">{t('重新載入聯絡資訊')}</button></div>}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 md:gap-16 text-sm text-white/85 text-left">
          <div className="space-y-6 flex flex-col items-start">
            <div className="w-36">
              <img loading="lazy" decoding="async"
                src={logo}
                alt="SNOWLAND Logo"
                className="w-full h-auto"
              />
            </div>
            <div className="text-sm leading-relaxed text-white/85 space-y-2">
              {settings.companyName && <p className="break-words">{settings.companyName}</p>}
              {settings.secondaryName && <p className="break-words">{settings.secondaryName}</p>}
              {settings.email && <a className="inline-flex min-h-11 items-center break-all" href={`mailto:${settings.email}`}>{settings.email}</a>}
            </div>
          </div>

          <div className="space-y-2 flex flex-col items-start border-t border-white/20 pt-6 md:border-t-0 md:pt-0">
              {[
              { label: "常見問題", href: faqLink },
              { label: "會員條款", href: "/membership-terms" },
              { label: "隱私權政策", href: "/privacy-policy" },
              { label: "取消更改規定", href: "/cancellation-policy" },
            ].map((item) => (
              <SiteLink
                key={item.label}
                to={item.href}
                className="group relative flex items-center text-sm text-white/85"
              >
                <span className="absolute -left-4 top-1/2 -translate-y-1/2 text-white/60 opacity-0 -translate-x-2 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0">
                  &gt;
                </span>
                <span className="transition-colors duration-200 group-hover:text-white">
                  {t(item.label)}
                </span>
              </SiteLink>
            ))}
          </div>

          <div className="space-y-2 flex flex-col items-start border-t border-white/20 pt-6 md:border-t-0 md:pt-0">
              {[
              { label: "關於SnowLand", href: "/about" },
              { label: "教練團隊", href: "/coach" },
              { label: "聯絡我們", href: "/contact" },
            ].map((item) => (
              <SiteLink
                key={item.label}
                to={item.href}
                className="group relative flex items-center text-sm text-white/85"
              >
                <span className="absolute -left-4 top-1/2 -translate-y-1/2 text-white/60 opacity-0 -translate-x-2 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0">
                  &gt;
                </span>
                <span className="transition-colors duration-200 group-hover:text-white">
                  {t(item.label)}
                </span>
              </SiteLink>
            ))}
          </div>
        </div>

        <div className="mt-12 border-t border-white/20 pt-10 grid grid-cols-1 md:grid-cols-2 gap-8 text-left">
          <div aria-label={t('官方社群')} className="flex flex-wrap items-center gap-2">
            {settings.links.map(({key,label,icon,href}) => <a key={key} href={href} target="_blank" rel="noopener noreferrer" aria-label={label} className="inline-flex h-11 w-11 items-center justify-center rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">
              <img loading="lazy" decoding="async" src={`${homepageAssetBase}/${icon}`} alt="" className="h-7 w-7" />
            </a>)}
          </div>
          <div className="flex justify-start md:justify-end md:items-end text-left md:text-right">
            <p className="text-xs text-white/70">
              {settings.copyright}
            </p>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {showScrollTop && (
          <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
            {chatLinks.length > 0 && <div className="relative">
              <motion.button
                type="button"
                onClick={() => setIsChatOpen((prev) => !prev)}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 16 }}
                transition={{ duration: 0.2 }}
                className="flex h-11 w-11 items-center justify-center rounded-full bg-white/60 text-[#1f2937] shadow-lg transition hover:-translate-y-0.5 hover:bg-white"
                aria-label={t('開啟客服連結')}
                aria-expanded={isChatOpen}
              >
                <svg
                  className="h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 15a4 4 0 0 1-4 4H7l-4 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
                </svg>
              </motion.button>
              <AnimatePresence>
                {isChatOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.2 }}
                    className="absolute bottom-14 right-0 flex flex-col gap-2 bg-[#2b5f8f] p-3 shadow-lg"
                  >
                    {chatLinks.map(({key,label,icon,href}) => <a key={key} href={href} target="_blank" rel="noopener noreferrer" aria-label={t('客服 {channel}', {channel:label})} className="inline-flex h-11 w-11 items-center justify-center rounded text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">
                      <img loading="lazy" decoding="async" src={`${homepageAssetBase}/${icon}`} alt="" className="h-5 w-5" />
                    </a>)}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>}
            <motion.button
              type="button"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 16 }}
              transition={{ duration: 0.2 }}
              className="flex h-11 w-11 items-center justify-center rounded-full bg-white/60 text-[#1f2937] shadow-lg transition hover:-translate-y-0.5 hover:bg-white"
              aria-label={t('回到頂部')}
            >
              <svg
                className="h-5 w-5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 15l7-7 7 7" />
              </svg>
            </motion.button>
          </div>
        )}
      </AnimatePresence>
    </footer>
  );
}

export default SiteFooter;
