import {useSiteLocale} from '../../contexts/SiteLocale';
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import SiteHeader from '../../components/site/SiteHeader';
import SiteFooter from '../../components/site/SiteFooter';
import SiteLink from '../../components/site/SiteLink';
import { useSiteContent, guideArticleMode } from '../../hooks/useSiteContent';
import { prepareGuideArticleHtml } from '../../utils/guideArticleHtml';

export default function GuideArticlePage() {
  const {t} = useSiteLocale();
  const { articleId } = useParams();
  const [isTocOpen,setIsTocOpen] = useState(true);
  const validId = /^[1-9]\d*$/.test(articleId || '');
  const { items, isLoading, error, refetch } = useSiteContent(validId ? 'guides.articles' : null, {contentId:articleId,limit:1});
  const item = items.find(row => String(row.id) === articleId && guideArticleMode(row) === 'internal');
  const blocks = Array.isArray(item?.metadata?.blocks) ? item.metadata.blocks : item?.body ? [{type:'paragraph',text:item.body}] : [];
  const importedArticle = item?.metadata?.article;
  // Dynamically inserted lazy iframes stayed blank after scrolling in Chrome.
  // Load article videos immediately; leave ordinary image loading unchanged.
  const {html:importedHtml,toc} = prepareGuideArticleHtml(typeof importedArticle?.html === 'string' ? importedArticle.html : '');
  useEffect(()=>{
    if (!importedHtml || !window.location.hash) return;
    try { document.getElementById(decodeURIComponent(window.location.hash.slice(1)))?.scrollIntoView({block:'start'}); } catch { /* Ignore malformed incoming anchors. */ }
  },[importedHtml,articleId]);
  const coverInBody = !!item?.image_url && [...importedHtml.matchAll(/<img\b[^>]*\bsrc="([^"]*)"/gi)].some(match => match[1].replace(/&amp;/g,'&') === item.image_url);
  const category = item?.metadata?.category || item?.tags?.[0] || '';
  return <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
    <SiteHeader forceTransparent forceDarkText forceLogoColor />
    <main className={`mx-auto w-full ${toc.length ? 'max-w-5xl' : 'max-w-3xl'} px-6 pt-32 pb-24 flex-1 break-words`}>
      <SiteLink to={category ? `/guides?category=${encodeURIComponent(category)}` : '/guides'} className="inline-flex min-h-11 items-center text-sm text-[#2b5f8f] underline underline-offset-4">{t("← 返回文章列表")}</SiteLink>
      {isLoading ? <p role="status" className="py-16 text-center">{t("文章載入中。")}</p> : error ? <div role="alert" className="py-16 text-center text-red-600"><p>{t("文章暫時無法載入。")}</p><button type="button" onClick={refetch} className="mt-4 min-h-11 rounded-full border border-current px-6">{t("重新載入")}</button></div> : !item ? <p role="status" className="py-16 text-center">{t("文章不存在或已下架。")}</p> : <article>
        <header className="my-8 space-y-4">
          <p className="text-sm text-[#64748b]">{t(category)}{category && item.metadata?.date ? ' ｜ ' : ''}{item.metadata?.date || ''}</p>
          <h1 className="text-3xl md:text-4xl font-semibold leading-relaxed font-display">{item.title}</h1>
          {item.summary && <p className="text-base leading-8 text-[#64748b]">{item.summary}</p>}
          {item.image_url && !coverInBody && !blocks.some(block => block?.type === 'image' && block.src === item.image_url) && <img src={item.image_url} alt={item.title} className="w-full h-auto rounded-sm" />}
        </header>
        {importedHtml ? <div className={toc.length ? 'grid gap-8 lg:grid-cols-[230px_minmax(0,1fr)]' : ''}>
          {toc.length > 0 && <aside className="self-start rounded-sm border border-[#e2e8f0] bg-white p-4 lg:sticky lg:top-24">
            <button type="button" aria-expanded={isTocOpen} aria-controls="guide-article-toc" onClick={()=>setIsTocOpen(!isTocOpen)} className="flex min-h-11 w-full items-center justify-between text-left text-sm font-semibold text-[#475569]">{t("文章目錄")}<span aria-hidden="true">{isTocOpen ? '−' : '＋'}</span></button>
            {isTocOpen && <p className="mb-2 text-xs text-[#64748b] lg:hidden">{t("上下滑動目錄，點選章節快速跳轉。")}</p>}
            <nav id="guide-article-toc" aria-label={t("文章目錄")} hidden={!isTocOpen} className="mt-2 max-h-64 space-y-1 overflow-y-auto lg:max-h-[calc(100vh-12rem)]">{toc.map(section=><a key={section.id} href={`#${encodeURIComponent(section.id)}`} className={`flex min-h-11 items-center text-sm leading-6 text-[#64748b] hover:text-[#2b5f8f] ${section.level>2 ? 'pl-3' : ''}`}>{section.label}</a>)}</nav>
          </aside>}
          <div className="min-w-0">
          {/<table\b/i.test(importedHtml) && <p className="mb-4 text-sm text-[#64748b] md:hidden">{t("表格可左右滑動，查看完整比較內容。")}</p>}
          <div className="article-content imported-guide text-base leading-8 text-[#475569]" dangerouslySetInnerHTML={{__html:importedHtml}} />
          </div>
        </div> : <div className="space-y-6 text-base leading-8 text-[#475569]">
          {blocks.map((block,index) => {
            if (!block || typeof block !== 'object') return null;
            if (block.type === 'paragraph') return <p key={index} className="whitespace-pre-line">{typeof block.text === 'string' ? block.text : ''}</p>;
            if (block.type === 'heading') { const Tag = block.level === 3 ? 'h3' : 'h2'; return <Tag key={index} className="text-xl font-semibold text-[#1f2937]">{typeof block.text === 'string' ? block.text : ''}</Tag>; }
            if (block.type === 'image' && typeof block.src === 'string' && block.src) { const alt = typeof block.alt === 'string' ? block.alt : ''; return <figure key={index}><img src={block.src} alt={alt} loading="lazy" className="w-full h-auto rounded-sm" />{alt && <figcaption className="mt-2 text-sm text-[#64748b]">{alt}</figcaption>}</figure>; }
            if (block.type === 'list' && Array.isArray(block.items)) { const Tag = block.ordered ? 'ol' : 'ul'; return <Tag key={index} className={`pl-6 space-y-2 ${block.ordered ? 'list-decimal' : 'list-disc'}`}>{block.items.filter(text=>typeof text==='string').map((text,i)=><li key={i}>{text}</li>)}</Tag>; }
            return null;
          })}
        </div>}
      </article>}
    </main><SiteFooter />
  </div>;
}
