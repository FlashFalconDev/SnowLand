import React from 'react';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import footerPagesContent from '../../data/site/footerPagesContent';

function PolicyPage({ contentKey, eyebrow = "POLICY" }) {
  const page = footerPagesContent[contentKey];

  if (!page) {
    return (
      <div className="min-h-screen bg-white text-[#1f2937] flex flex-col">
        <SiteHeader forceTransparent forceDarkText forceLogoColor />
        <main className="flex-1 flex items-center justify-center px-6 pt-32 pb-24">
          <p className="text-sm text-[#64748b]">內容載入中。</p>
        </main>
        <SiteFooter />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent />
      <main className="flex-1 pb-24">
        <section className="relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-[#1c3b5f] via-[#2b5f8f] to-[#7bbbe7]" />
          <div
            className="absolute inset-0 opacity-40"
            style={{
              backgroundImage:
                "radial-gradient(circle at 20% 20%, rgba(255,255,255,0.35), transparent 45%), radial-gradient(circle at 70% 30%, rgba(255,255,255,0.25), transparent 50%), radial-gradient(circle at 40% 80%, rgba(255,255,255,0.2), transparent 55%)",
            }}
          />
          <div className="relative max-w-6xl mx-auto px-6 pt-32 pb-20 md:pt-36 md:pb-24 text-white text-center">
            <p className="text-xs font-semibold tracking-[0.3em] uppercase text-white/70 font-display">
              {eyebrow}
            </p>
            <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
              {page.title}
            </h1>
          </div>
        </section>

        <section className="max-w-5xl mx-auto px-6 mt-12">
          <div
            className="policy-content text-sm md:text-base text-[#475569] leading-relaxed"
            dangerouslySetInnerHTML={{ __html: page.html }}
          />
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export default PolicyPage;
