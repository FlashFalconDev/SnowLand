import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from './SiteLink';
import logo from '../../assets/site/logo-white.png';
import { homepageAssetBase } from '../../data/site/assetPaths';
import { faqLink } from '../../data/site/navigationLinks';

function SiteFooter() {
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => {
      setShowScrollTop(window.scrollY > 400);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <footer className="bg-gradient-to-br from-[#2b5f8f] via-[#3c78b6] to-[#5aa6c9] border-t border-[#275680] text-white">
      <div className="max-w-6xl mx-auto px-6 md:px-10 py-14 md:py-20">
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
              <p>SNOWLAND合同会社</p>
              <p>雪域創遊國際有限公司</p>
              <p>land110602@gmail.com</p>
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
                  {item.label}
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
                  {item.label}
                </span>
              </SiteLink>
            ))}
          </div>
        </div>

        <div className="mt-12 border-t border-white/20 pt-10 grid grid-cols-1 md:grid-cols-2 gap-8 text-left">
          <div className="flex flex-nowrap items-center gap-4 overflow-x-auto">
            <a
              href="https://www.facebook.com/snowlandcz/"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Facebook"
            >
              <img loading="lazy" decoding="async"
                src={`${homepageAssetBase}/footer_icon_fb.png`}
                alt="Facebook"
                className="h-7 w-7"
              />
            </a>
            <a
              href="https://www.instagram.com/snowlandcz/"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Instagram"
            >
              <img loading="lazy" decoding="async"
                src={`${homepageAssetBase}/instagram-logo.png`}
                alt="Instagram"
                className="h-7 w-7"
              />
            </a>
            <a
              href="https://www.threads.com/@snowlandcz"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Threads"
            >
              <img loading="lazy" decoding="async"
                src={`${homepageAssetBase}/footer_icon_threads.png`}
                alt="Threads"
                className="h-7 w-7"
              />
            </a>
            <a
              href="https://youtube.com/@snowlandcz?themeRefresh=1"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="YouTube"
            >
              <img loading="lazy" decoding="async"
                src={`${homepageAssetBase}/footer_icon_yt.png`}
                alt="YouTube"
                className="h-7 w-7"
              />
            </a>
            <a
              href="https://line.me/R/ti/p/@snowlandcz?from=page&accountId=snowlandcz"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Line"
            >
              <img loading="lazy" decoding="async"
                src={`${homepageAssetBase}/footer_icon_line.png`}
                alt="Line"
                className="h-7 w-7"
              />
            </a>
            <a
              href="https://api.whatsapp.com/message/FOWLAO5BHSNBE1?autoload=1&app_absent=0"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="WhatsApp"
            >
              <img loading="lazy" decoding="async"
                src={`${homepageAssetBase}/footer_icon_wa.png`}
                alt="WhatsApp"
                className="h-7 w-7"
              />
            </a>
            <a
              href="https://www.tiktok.com/@snowlandcz"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="TikTok"
            >
              <img loading="lazy" decoding="async"
                src={`${homepageAssetBase}/footer_icon_tikotok.png`}
                alt="TikTok"
                className="h-7 w-7"
              />
            </a>
            <a
              href="https://xhslink.com/m/A3otE4dwmAl"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="小紅書"
            >
              <img loading="lazy" decoding="async"
                src={`${homepageAssetBase}/footer_icon_red note.png`}
                alt="小紅書"
                className="h-7 w-7"
              />
            </a>
          </div>
          <div className="flex justify-start md:justify-end md:items-end text-left md:text-right">
            <p className="text-xs text-white/70">
              © Copyright - 雪域創遊 SnowLand
            </p>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {showScrollTop && (
          <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
            <div className="relative">
              <motion.button
                type="button"
                onClick={() => setIsChatOpen((prev) => !prev)}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 16 }}
                transition={{ duration: 0.2 }}
                className="flex h-11 w-11 items-center justify-center rounded-full bg-white/60 text-[#1f2937] shadow-lg transition hover:-translate-y-0.5 hover:bg-white"
                aria-label="Open chat options"
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
                    <a
                      href="https://line.me/R/ti/p/@snowlandcz?from=page&accountId=snowlandcz"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center justify-center text-xs font-semibold text-white"
                    >
                      <img loading="lazy" decoding="async"
                        src={`${homepageAssetBase}/footer_icon_line.png`}
                        alt="Line"
                        className="h-5 w-5"
                      />
                    </a>
                    <a
                      href="https://api.whatsapp.com/message/FOWLAO5BHSNBE1?autoload=1&app_absent=0"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center justify-center text-xs font-semibold text-white"
                    >
                      <img loading="lazy" decoding="async"
                        src={`${homepageAssetBase}/footer_icon_wa.png`}
                        alt="WhatsApp"
                        className="h-5 w-5"
                      />
                    </a>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <motion.button
              type="button"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 16 }}
              transition={{ duration: 0.2 }}
              className="flex h-11 w-11 items-center justify-center rounded-full bg-white/60 text-[#1f2937] shadow-lg transition hover:-translate-y-0.5 hover:bg-white"
              aria-label="Scroll to top"
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
