import React from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import { homepageAssetBase } from '../../data/site/assetPaths';
import legacyPages from '../../data/site/legacyPages.json';
import aboutSnowland from '../../assets/site/About snowland.jpg';

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
  const page = legacyPages["contact"];
  const blocks = page?.blocks ?? [];
  const infoLines = Array.from(
    new Set(
      blocks
        .filter((block) => block.type === "paragraph")
        .map((block) => block.text)
        .filter(
          (text) =>
            text.includes("Email") ||
            (text.includes("https://") && !text.includes("land110602.com")) ||
            text.includes("Line")
        )
    )
  );
  const headingText = blocks.find((block) => block.type === "heading")?.text ?? "聯絡我們";
  const emailLabel = blocks.find((block) => block.text?.includes("E-mail"))?.text ?? "E-mail*";
  const subjectLabel = blocks.find((block) => block.text === "主旨")?.text ?? "主旨";
  const messageLabel = blocks.find((block) => block.text === "訊息")?.text ?? "訊息";
  const prefersReducedMotion = useReducedMotion();
  const { scrollY } = useScroll();
  const contactBgY = useTransform(scrollY, [0, 900], ["0%", "28%"]);

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
                聯絡我們
              </h1>
              <div className="space-y-3 text-sm md:text-base text-[#475569] leading-relaxed">
                {infoLines
                  .filter((line) => !line.includes("Line"))
                  .map((line, index) => {
                    if (line.includes("Email")) {
                      const emailText = line.replace(/Email[:：]\s*/i, "").trim();
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
                          <span>{emailText}</span>
                        </div>
                      );
                    }
                    return (
                      <p key={`contact-line-${index}`}>{renderTextWithLinks(line)}</p>
                    );
                  })}
                <div className="flex items-center justify-center gap-2 text-[#475569] md:justify-start">
                  <a
                    href="https://line.me/R/ti/p/@snowlandcz?from=page&searchId=snowlandcz"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group relative inline-flex h-8 w-8"
                  >
                    <img loading="lazy" decoding="async"
                      src={`${homepageAssetBase}/footer_icon_line.png`}
                      alt="Line"
                      className="h-8 w-8 transition-opacity duration-200 group-hover:opacity-0"
                      style={{ filter: "grayscale(1) brightness(0.35)" }}
                      loading="lazy"
                    />
                    <img loading="lazy" decoding="async"
                      src={`${homepageAssetBase}/Social media_line logo-green.png`}
                      alt="Line"
                      className="absolute inset-0 h-8 w-8 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
                      loading="lazy"
                    />
                  </a>
                  <span>@snowlandcz</span>
                </div>
              </div>
            </section>
            <form className="space-y-8">
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
                  className="inline-flex w-full items-center justify-center rounded-full border border-[#1f2937]/30 px-6 py-3 text-sm font-semibold tracking-wide font-display text-[#1f2937] transition-colors hover:bg-[#D5C6AF]"
                  onClick={() => window.alert("已送出")}
                >
                  送出
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

export default ContactPage;
