import React from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import aboutSnowland from '../../assets/site/About snowland.jpg';
import { siteContentToPage, useSiteContent } from '../../hooks/useSiteContent';

const renderTextWithLinks = (text) => {
  const linkRegex = /(https?:\/\/[^\s]+)/g;
  const linkTest = /^https?:\/\/[^\s]+$/;
  const parts = text.split(linkRegex);
  return parts.map((part, index) => {
    if (linkTest.test(part)) {
      return (
        <a
          key={`link-${index}`}
          href={part}
          className="text-[#2b5f8f] underline underline-offset-2 break-all"
          target="_blank"
          rel="noopener noreferrer"
        >
          {part}
        </a>
      );
    }
    return <span key={`text-${index}`}>{part}</span>;
  });
};

function ContactPage() {
  const { items, isLoading, error } = useSiteContent('about.contact', { limit: 1 });
  const page = siteContentToPage(items[0]);
  const blocks = Array.isArray(page?.blocks) ? page.blocks.filter(Boolean) : [];
  const infoLines = Array.from(
    new Set(
      blocks
        .filter((block) => block.type === "paragraph" && typeof block.text === 'string')
        .map((block) => block.text.trim())
        // Imported pages include the old form labels amongst their contact paragraphs.
        .filter((text) => text && !/^(e-?mail\*?|主旨|訊息)$/i.test(text))
    )
  );
  const emailLabel = blocks.find((block) => typeof block.text === 'string' && /^e-?mail\*?$/i.test(block.text.trim()))?.text ?? "E-mail*";
  const subjectLabel = blocks.find((block) => block.text === "主旨")?.text ?? "主旨";
  const messageLabel = blocks.find((block) => block.text === "訊息")?.text ?? "訊息";
  const prefersReducedMotion = useReducedMotion();
  const { scrollY } = useScroll();
  const contactBgY = useTransform(scrollY, [0, 900], ["0%", "28%"]);

  if (!page) {
    return (
      <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
        <SiteHeader forceTransparent forceDarkText forceLogoColor />
        <main className="flex-1 flex items-center justify-center px-6 pt-32 pb-24">
          <p className={`text-sm ${error ? "text-red-600" : "text-[#64748b]"}`}>
            {error ? "聯絡資訊暫時無法載入，請稍後再試。" : isLoading ? "聯絡資訊載入中。" : "目前沒有已發布的聯絡資訊。"}
          </p>
        </main>
        <SiteFooter />
      </div>
    );
  }

  return (
    <div className="min-h-screen text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main
        className="relative flex-1 w-full overflow-hidden px-6 pt-28 pb-24"
      >
        <motion.img
          src={aboutSnowland}
          alt="About snowland background"
          className="absolute inset-0 h-full w-full object-cover object-center scale-[1.08] md:scale-[1.12]"
          style={prefersReducedMotion ? undefined : { y: contactBgY }}
        />
        <div className="absolute inset-0 bg-black/10" />
        <div className="relative mx-auto w-full max-w-6xl rounded-sm bg-white/95 shadow-[0_20px_50px_rgba(15,23,42,0.15)]">
          <div className="grid gap-12 px-8 py-12 md:px-12 md:py-14 lg:grid-cols-[0.9fr_1.1fr]">
            <section className="space-y-6 text-center md:text-left">
              <p className="text-xs font-semibold tracking-[0.35em] uppercase text-[#64748b] font-display">
                Contact us
              </p>
              <h1 className="text-3xl md:text-4xl font-semibold tracking-wide text-[#111827] font-display">
                {page.title || "聯絡我們"}
              </h1>
              <div className="space-y-3 text-sm md:text-base text-[#475569] leading-relaxed">
                {infoLines
                  .map((line, index) => {
                    const emailText = line.replace(/^e-?mail\s*[:：]\s*/i, '').trim();
                    if (/^e-?mail\s*[:：]/i.test(line) && /^[^\s@<>?&#]+@[^\s@<>?&#]+\.[^\s@<>?&#]+$/.test(emailText)) {
                      return (
                        <div
                          key={`contact-line-${index}`}
                          className="flex items-center justify-center gap-2 md:justify-start"
                        >
                          <svg
                            viewBox="0 0 24 24"
                            className="h-5 w-5 text-[#475569]"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.6"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                          >
                            <path d="M4 6h16v12H4z" />
                            <path d="m4 7 8 6 8-6" />
                          </svg>
                          <a href={`mailto:${emailText}`} className="break-all text-[#2b5f8f] underline underline-offset-2">{emailText}</a>
                        </div>
                      );
                    }
                    return (
                      <p className="whitespace-pre-line break-words" key={`contact-line-${index}`}>{renderTextWithLinks(line)}</p>
                    );
                  })}
              </div>
            </section>
            <fieldset disabled aria-describedby="contact-form-unavailable" className="min-w-0 space-y-8">
              <p id="contact-form-unavailable" role="status" className="rounded-sm border border-[#cbd5e1] bg-[#f1f5f9] px-4 py-3 text-sm leading-6 text-[#475569]">
                聯絡表單尚未啟用，這裡不會送出或儲存訊息。請使用本頁列出的 Email 或官方 LINE 聯絡我們。
              </p>
              <div className="grid gap-6 md:grid-cols-2">
                <label className="block text-xs font-semibold tracking-[0.2em] uppercase text-[#475569]">
                  姓名*
                  <input
                    type="text"
                    className="mt-3 w-full border-b border-[#1f2937]/40 bg-transparent pb-2 text-sm text-[#1f2937] placeholder:text-[#94a3b8] focus:border-[#1f2937] focus:outline-none"
                    placeholder="請輸入姓名"
                  />
                </label>
                <label className="block text-xs font-semibold tracking-[0.2em] uppercase text-[#475569]">
                  電話
                  <input
                    type="tel"
                    className="mt-3 w-full border-b border-[#1f2937]/40 bg-transparent pb-2 text-sm text-[#1f2937] placeholder:text-[#94a3b8] focus:border-[#1f2937] focus:outline-none"
                    placeholder="請輸入電話"
                  />
                </label>
                <label className="block text-xs font-semibold tracking-[0.2em] uppercase text-[#475569]">
                  {emailLabel}
                  <input
                    type="email"
                    className="mt-3 w-full border-b border-[#1f2937]/40 bg-transparent pb-2 text-sm text-[#1f2937] placeholder:text-[#94a3b8] focus:border-[#1f2937] focus:outline-none"
                    placeholder="you@example.com"
                  />
                </label>
                <label className="block text-xs font-semibold tracking-[0.2em] uppercase text-[#475569]">
                  {subjectLabel}
                  <input
                    type="text"
                    className="mt-3 w-full border-b border-[#1f2937]/40 bg-transparent pb-2 text-sm text-[#1f2937] placeholder:text-[#94a3b8] focus:border-[#1f2937] focus:outline-none"
                    placeholder="請輸入主旨"
                  />
                </label>
              </div>
              <label className="block text-xs font-semibold tracking-[0.2em] uppercase text-[#475569]">
                {messageLabel}
                <textarea
                  rows={4}
                  className="mt-3 w-full resize-none border-b border-[#1f2937]/40 bg-transparent pb-2 text-sm text-[#1f2937] placeholder:text-[#94a3b8] focus:border-[#1f2937] focus:outline-none"
                  placeholder="請輸入訊息"
                />
              </label>
              <div className="flex justify-center">
                <button
                  type="button"
                  disabled
                  className="inline-flex w-full cursor-not-allowed items-center justify-center rounded-full border border-[#1f2937]/30 bg-[#f1f5f9] px-6 py-3 text-sm font-semibold tracking-wide font-display text-[#64748b]"
                >
                  表單尚未啟用
                </button>
              </div>
            </fieldset>
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

export default ContactPage;
