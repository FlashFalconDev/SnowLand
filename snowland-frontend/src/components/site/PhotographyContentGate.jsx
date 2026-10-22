import {useSiteLocale} from '../../contexts/SiteLocale';
import React from 'react';
import SiteHeader from './SiteHeader';
import SiteFooter from './SiteFooter';
import { useSiteContent } from '../../hooks/useSiteContent';

export default function PhotographyContentGate({ season, children }) {
  const {t} = useSiteLocale();
  const { items, isLoading, error } = useSiteContent(`photography.${season}`, { limit: 1 });
  const content = items[0]?.metadata?.photography;
  const valid = content?.version === 1 && content.season === season && content.values && typeof content.values === 'object' && !Array.isArray(content.values) && Object.keys(content.values).length > 0 && Object.values(content.values).every(value => typeof value === 'string');
  if (!isLoading && !error && valid) return children(content);
  return <div className="flex min-h-screen flex-col bg-[#f7f8fa] text-[#1f2937]">
    <SiteHeader forceTransparent forceDarkText forceLogoColor />
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6 pb-24 pt-32 text-center">
      <p role={error ? 'alert' : 'status'} className="text-sm leading-7 text-[#475569]">
        {isLoading ? t("正在載入攝影服務內容…") : error ? t("攝影服務內容暫時無法載入，請稍後再試。") : t("攝影服務內容更新中，請稍後再查看。")}
      </p>
      {error && <button type="button" className="mt-4 min-h-11 rounded-full border border-[#2b5f8f] px-6 text-sm text-[#2b5f8f]" onClick={() => window.location.reload()}>{t("重新載入")}</button>}
    </main>
    <SiteFooter />
  </div>;
}
