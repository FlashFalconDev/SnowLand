import React from 'react';
import { useParams } from 'react-router-dom';
import SiteHeader from '../../components/site/SiteHeader';
import SiteFooter from '../../components/site/SiteFooter';
import SiteLink from '../../components/site/SiteLink';
import { useSiteContent, guideArticleMode } from '../../hooks/useSiteContent';

export default function GuideArticlePage() {
  const { articleId } = useParams();
  const validId = /^[1-9]\d*$/.test(articleId || '');
  const { items, isLoading, error, refetch } = useSiteContent(validId ? 'guides.articles' : null, {contentId:articleId,limit:1});
  const item = items.find(row => String(row.id) === articleId && guideArticleMode(row) === 'internal');
  const blocks = Array.isArray(item?.metadata?.blocks) ? item.metadata.blocks : item?.body ? [{type:'paragraph',text:item.body}] : [];
  const category = item?.metadata?.category || item?.tags?.[0] || '';
  return <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
    <SiteHeader forceTransparent forceDarkText forceLogoColor />
    <main className="mx-auto w-full max-w-3xl px-6 pt-32 pb-24 flex-1 break-words">
      <SiteLink to={category ? `/guides?category=${encodeURIComponent(category)}` : '/guides'} className="inline-flex min-h-11 items-center text-sm text-[#2b5f8f] underline underline-offset-4">← 返回文章列表</SiteLink>
      {isLoading ? <p role="status" className="py-16 text-center">文章載入中。</p> : error ? <div role="alert" className="py-16 text-center text-red-600"><p>文章暫時無法載入。</p><button type="button" onClick={refetch} className="mt-4 min-h-11 rounded-full border border-current px-6">重新載入</button></div> : !item ? <p role="status" className="py-16 text-center">文章不存在或已下架。</p> : <article>
        <header className="my-8 space-y-4">
          <p className="text-sm text-[#64748b]">{category}{category && item.metadata?.date ? ' ｜ ' : ''}{item.metadata?.date || ''}</p>
          <h1 className="text-3xl md:text-4xl font-semibold leading-relaxed font-display">{item.title}</h1>
          {item.summary && <p className="text-base leading-8 text-[#64748b]">{item.summary}</p>}
          {item.image_url && !blocks.some(block => block?.type === 'image' && block.src === item.image_url) && <img src={item.image_url} alt={item.title} className="w-full h-auto rounded-sm" />}
        </header>
        <div className="space-y-6 text-base leading-8 text-[#475569]">
          {blocks.map((block,index) => {
            if (!block || typeof block !== 'object') return null;
            if (block.type === 'paragraph') return <p key={index} className="whitespace-pre-line">{typeof block.text === 'string' ? block.text : ''}</p>;
            if (block.type === 'heading') { const Tag = block.level === 3 ? 'h3' : 'h2'; return <Tag key={index} className="text-xl font-semibold text-[#1f2937]">{typeof block.text === 'string' ? block.text : ''}</Tag>; }
            if (block.type === 'image' && typeof block.src === 'string' && block.src) { const alt = typeof block.alt === 'string' ? block.alt : ''; return <figure key={index}><img src={block.src} alt={alt} loading="lazy" className="w-full h-auto rounded-sm" />{alt && <figcaption className="mt-2 text-sm text-[#64748b]">{alt}</figcaption>}</figure>; }
            if (block.type === 'list' && Array.isArray(block.items)) { const Tag = block.ordered ? 'ol' : 'ul'; return <Tag key={index} className={`pl-6 space-y-2 ${block.ordered ? 'list-decimal' : 'list-disc'}`}>{block.items.filter(text=>typeof text==='string').map((text,i)=><li key={i}>{text}</li>)}</Tag>; }
            return null;
          })}
        </div>
      </article>}
    </main><SiteFooter />
  </div>;
}
