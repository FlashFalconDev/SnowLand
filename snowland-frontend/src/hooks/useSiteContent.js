import { useEffect, useState } from 'react';
import { fetchSiteContent } from '../api/booking';

export function useSiteContent(locationKey, options = {}) {
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(Boolean(locationKey));
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!locationKey) {
      setItems([]);
      setIsLoading(false);
      setError(null);
      return undefined;
    }

    let active = true;
    setIsLoading(true);
    setError(null);
    fetchSiteContent({
      location_key: locationKey,
      limit: options.limit ?? 500,
      ...(options.contentType ? { content_type: options.contentType } : {}),
      ...(options.includeEnded ? { include_ended: true } : {}),
      ...(options.contentId ? { content_id: options.contentId } : {}),
      ...(locationKey === 'guides.articles' && !options.contentId ? {view:'cards'} : {}),
    })
      .then((result) => {
        if (active) setItems(Array.isArray(result) ? result : []);
      })
      .catch((requestError) => {
        if (active) {
          setItems([]);
          setError(requestError);
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [locationKey, options.contentType, options.includeEnded, options.limit, options.contentId, reloadKey]);

  return { items, isLoading, error, refetch: () => setReloadKey(value => value + 1) };
}

export function useCoursePricing(resortSlug) {
  const result = useSiteContent('course.pricing');
  const item = result.items.find((candidate) => candidate.external_id === resortSlug);
  const storedPricing = item?.metadata?.pricing ?? null;
  const seasonYears = String(storedPricing?.season_label ?? '').match(/(\d{2})\s*[-–]\s*(\d{2})/);
  const isStale = Boolean(seasonYears && Date.now() >= new Date(2000 + Number(seasonYears[2]), 6, 1).getTime());
  return {
    ...result,
    pricing: isStale ? null : storedPricing,
    isStale,
  };
}

export const GUIDE_CATEGORIES = ['滑雪初心者', '北海道滑雪場', '行程規劃與實戰攻略', '裝備與技巧', '北海道生活', '限時活動'];
export const guideArticleMode = (item) => item.metadata?.article_mode || (item.link_url && !item.body ? 'external' : 'internal');
export const guideArticleTarget = (item) => {
  const url = item.link_url || item.metadata?.url || '';
  if (guideArticleMode(item) === 'internal' && Number.isInteger(item.id) && item.id > 0) return `/guides/articles/${item.id}`;
  const local = {
    'https://land110602.com/%e6%9e%97%e9%96%93%e9%9b%aa%e9%81%93/': '/guides/best-hokkaido-tree-runs',
    'https://land110602.com/packing-checklist/': '/guides/packing-checklist',
    'https://land110602.com/%e7%ac%ac%e4%b8%80%e6%ac%a1%e6%bb%91%e9%9b%aa%ef%bc%8c%e6%96%b0%e6%89%8b%e6%87%b6%e4%ba%ba%e5%8c%85/': '/guides/preparation',
  };
  if (Object.hasOwn(local, url)) return local[url];
  if (typeof url !== 'string' || /[\u0000-\u001f\\]/.test(url)) return '';
  if (url.startsWith('/') && !url.startsWith('//')) return url;
  try { const parsed = new URL(url); return ['http:', 'https:'].includes(parsed.protocol) ? url : ''; } catch { return ''; }
};

export const siteContentToArticle = (item) => ({
  id: item.id,
  title: item.title,
  date: item.metadata?.date ?? '',
  excerpt: item.summary ?? item.metadata?.excerpt ?? '',
  category: item.metadata?.category ?? item.tags?.[0] ?? '',
  image: item.image_url ?? item.metadata?.image ?? '',
  url: item.location_key === 'guides.articles' && guideArticleMode(item) === 'internal' ? guideArticleTarget(item) : item.link_url || item.metadata?.url || '',
});

export const siteContentToResort = (item) => ({
  ...(item.metadata ?? {}),
  slug: item.metadata?.slug ?? item.external_id,
  nameChinese: item.metadata?.nameChinese ?? item.title,
  nameEnglish: item.metadata?.nameEnglish ?? item.subtitle,
  tags: item.tags ?? item.metadata?.tags ?? [],
  heroImage: item.metadata?.heroImage ?? item.image_url,
  imagePlaceholder: item.metadata?.imagePlaceholder ?? item.image_url,
  route: item.metadata?.route ?? item.link_url ?? `/course/${item.external_id}`,
});

export const siteContentToPage = (item) => {
  if (!item) return null;
  const storedPage = item.metadata?.page;
  if (storedPage && typeof storedPage === 'object') {
    return {
      ...storedPage,
      title: item.title || storedPage.title,
      subtitle: item.subtitle || storedPage.subtitle,
      summary: item.summary || storedPage.summary,
      heroImage: item.image_url || storedPage.heroImage,
      blocks: Array.isArray(item.metadata?.blocks) ? item.metadata.blocks : storedPage.blocks,
    };
  }
  return {
    title: item.title,
    subtitle: item.subtitle,
    summary: item.summary,
    heroImage: item.image_url,
    blocks: Array.isArray(item.metadata?.blocks) ? item.metadata.blocks : [],
  };
};
