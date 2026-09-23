import { useEffect, useState } from 'react';
import { fetchSiteContent } from '../api/booking';

export function useSiteContent(locationKey, options = {}) {
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(Boolean(locationKey));
  const [error, setError] = useState(null);

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
  }, [locationKey, options.contentType, options.includeEnded, options.limit]);

  return { items, isLoading, error };
}

export function useCoursePricing(resortSlug) {
  const result = useSiteContent('course.pricing');
  const item = result.items.find((candidate) => candidate.external_id === resortSlug);
  return {
    ...result,
    pricing: item?.metadata?.pricing ?? null,
  };
}

export const siteContentToArticle = (item) => ({
  title: item.title,
  date: item.metadata?.date ?? '',
  excerpt: item.summary ?? item.metadata?.excerpt ?? '',
  category: item.metadata?.category ?? item.tags?.[0] ?? '',
  image: item.image_url ?? item.metadata?.image ?? '',
  url: item.link_url ?? item.metadata?.url ?? '',
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
