import { useEffect, useMemo, useState } from 'react';

const KNOWN_COACH_SLUGS = [
  { slug: 'cash', tokens: ['cash'] },
  { slug: 'lily', tokens: ['lily'] },
  { slug: 'qizhen', tokens: ['七針', 'qizhen'] },
  { slug: 'dylan', tokens: ['dylan'] },
  { slug: 'eric', tokens: ['eric'] },
  { slug: 'vicky', tokens: ['vicky'] },
  { slug: 'lin', tokens: ['小霖', 'lin'] },
  { slug: 'karen', tokens: ['karen'] },
  { slug: 'naomi', tokens: ['naomi'] },
  { slug: 'bernie', tokens: ['bernie'] },
];

function getClientCode() {
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  if (pathParts[0] && pathParts[0] !== 'auth') return pathParts[0];
  return localStorage.getItem('client_code') || 'snowland';
}

export async function fetchWebsiteCoaches() {
  const clientCode = getClientCode();
  const response = await fetch(`/booking/${encodeURIComponent(clientCode)}/api/website-coaches/`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to load website coaches: ${response.status}`);
  }

  const payload = await response.json();
  return payload?.data?.list || [];
}

function normalizeText(value) {
  return `${value || ''}`.trim().toLowerCase();
}

function normalizeImage(value) {
  const image = `${value || ''}`.trim();
  return image.toLowerCase() === 'none' ? '' : image;
}

function inferSlug(coach) {
  const name = normalizeText(coach?.name);
  const slug = normalizeText(coach?.slug);
  const match = KNOWN_COACH_SLUGS.find((item) =>
    item.slug === slug || item.tokens.some((token) => name.includes(normalizeText(token)))
  );

  return match?.slug || coach?.slug || '';
}

function getStaticCoach(coach, staticBySlug, staticByName) {
  const inferredSlug = inferSlug(coach);
  return staticBySlug.get(inferredSlug) || staticByName.get(coach?.name) || null;
}

function withLegacyImage(coach, legacyImageByName) {
  return {
    ...coach,
    image: legacyImageByName.get(coach.name) || coach.image,
  };
}

export function getFallbackCoachCards(staticCoaches, legacyImageByName = new Map()) {
  return staticCoaches.map((coach) => withLegacyImage(coach, legacyImageByName));
}

export function mergeWebsiteCoachesWithStatic(apiCoaches, staticCoaches, legacyImageByName = new Map()) {
  const staticBySlug = new Map(staticCoaches.map((coach) => [coach.slug, coach]));
  const staticByName = new Map(staticCoaches.map((coach) => [coach.name, coach]));

  return apiCoaches.map((coach) => {
    const staticCoach = getStaticCoach(coach, staticBySlug, staticByName);
    const languagesText = coach.languages_text || (coach.languages_display || []).join(' / ');
    const certifications = Array.isArray(coach.certifications) ? coach.certifications : [];
    const certificationText = coach.certification_text || certifications.map((item) => item.text).filter(Boolean).join(' / ');

    return {
      ...(staticCoach || {}),
      name: coach.name || staticCoach?.name || '',
      slug: staticCoach?.slug || coach.slug || '',
      image: normalizeImage(coach.image) || staticCoach?.image || '',
      alt: coach.name || staticCoach?.name || 'Coach portrait',
      coachType: coach.coach_type || staticCoach?.coachType || '',
      certifications,
      certificationText,
      cardBio: coach.card_bio || staticCoach?.cardBio || '',
      languages: languagesText || staticCoach?.languages || '',
      websiteCoachId: coach.id,
    };
  }).map((coach) => withLegacyImage(coach, legacyImageByName));
}

export function useWebsiteCoachCards(staticCoaches, legacyImageByName = new Map()) {
  const fallbackCards = useMemo(
    () => getFallbackCoachCards(staticCoaches, legacyImageByName),
    [staticCoaches, legacyImageByName],
  );
  const [coachCards, setCoachCards] = useState([]);

  useEffect(() => {
    let active = true;
    setCoachCards([]);

    fetchWebsiteCoaches()
      .then((apiCoaches) => {
        if (!active) return;
        setCoachCards(mergeWebsiteCoachesWithStatic(apiCoaches, staticCoaches, legacyImageByName));
      })
      .catch(() => {
        if (!active) return;
        setCoachCards(fallbackCards);
      });

    return () => {
      active = false;
    };
  }, [fallbackCards, staticCoaches, legacyImageByName]);

  return coachCards;
}
