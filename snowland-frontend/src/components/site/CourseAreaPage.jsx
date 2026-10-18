import React from 'react';
import { useParams } from 'react-router-dom';
import SiteHeader from './SiteHeader';
import SiteFooter from './SiteFooter';
import SiteLink from './SiteLink';
import ResortGrid from './ResortGrid';
import HokkaidoMap from './HokkaidoMap';
import { siteContentToResort, useSiteContent } from '../../hooks/useSiteContent';

export default function CourseAreaPage() {
  const { resort: slug } = useParams();
  const areas = useSiteContent('course.areas', {contentType:'page'});
  const resorts = useSiteContent('course.resorts', {contentType:'page'});
  const area = areas.items.find(item => item.external_id === slug);
  const bySlug = new Map(resorts.items.map(item => { const resort = siteContentToResort(item); return [resort.slug,resort]; }));
  const selected = (Array.isArray(area?.metadata?.resort_slugs) ? area.metadata.resort_slugs : []).map(key => bySlug.get(key)).filter(Boolean);
  const loading = areas.isLoading || resorts.isLoading;
  const failed = areas.error || resorts.error;
  return <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
    <SiteHeader forceDarkText forceLogoColor />
    <main className="max-w-6xl mx-auto px-6 pt-32 pb-24 flex-1 w-full">
      {loading ? <p role="status" className="py-16 text-center">正在載入校區雪場…</p> : failed ? <div role="alert" className="py-16 text-center space-y-4"><p>校區資料暫時無法載入，請再試一次。</p><button type="button" className="min-h-11 px-6 rounded-full border border-[#2b5f8f] text-[#2b5f8f]" onClick={() => {areas.refetch();resorts.refetch();}}>重新載入</button></div> : !area ? <div className="py-16 text-center space-y-4"><h1 className="text-2xl font-semibold">此校區尚未開放</h1><SiteLink to="/course/hokkaido" className="inline-flex min-h-11 items-center text-[#2b5f8f]">查看北海道所有雪場</SiteLink></div> : <>
        <section className="text-center"><p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">{area.subtitle}</p><h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">{area.title}</h1>{area.summary && <p className="mt-4 text-sm text-[#64748b] whitespace-pre-line">{area.summary}</p>}</section>
        <section className="mt-12" aria-label="校區雪場列表">{selected.length ? <ResortGrid resorts={selected} /> : <p className="py-12 text-center text-sm text-[#64748b]">此校區目前沒有已發布的雪場，請稍後再查看。</p>}</section>
        {selected.length > 0 && <section className="mt-12" aria-label="校區雪場地圖"><HokkaidoMap resorts={selected} /></section>}
      </>}
    </main><SiteFooter />
  </div>;
}
