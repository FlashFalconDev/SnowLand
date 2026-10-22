import { useEffect, useState } from 'react';


function getClientCode() {
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  if (pathParts[0] && pathParts[0] !== 'auth') return pathParts[0];
  return localStorage.getItem('client_code') || 'snowland';
}

export async function fetchWebsiteCoaches({ includeProfile = false, slug = '' } = {}) {
  const clientCode = getClientCode();
  const params = new URLSearchParams();
  if (includeProfile) params.set('include_profile', '1');
  if (slug) params.set('slug', slug);
  const response = await fetch(`/booking/${encodeURIComponent(clientCode)}/api/website-coaches/${params.size ? '?' + params.toString() : ''}`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to load website coaches: ${response.status}`);
  }

  const payload = await response.json();
  return payload?.data?.list || [];
}


function normalizeImage(value) {
  const image = `${value || ''}`.trim();
  return image.toLowerCase() === 'none' ? '' : image;
}

export function websiteCoachDetail(coach) {
  const profile = coach?.profile && typeof coach.profile === 'object' && !Array.isArray(coach.profile) ? coach.profile : {};
  const strings = value => Array.isArray(value) ? value.filter(item => typeof item === 'string') : [];
  const images = value => Array.isArray(value) ? value.filter(item => item && typeof item.src === 'string' && /^(https?:\/\/|\/(?!\/))/.test(item.src)).map(item => ({ ...item, alt: typeof item.alt === 'string' ? item.alt : '' })) : [];
  const sections = Array.isArray(profile.sections) ? profile.sections.filter(section => section && typeof section.title === 'string').map(section => ({ ...section, lines: strings(section.lines), media: images(section.media), lead: typeof section.lead === 'string' ? section.lead : '' })) : [];
  const certifications = Array.isArray(coach.certifications) ? coach.certifications.filter(item => item && typeof item.text === 'string') : [];
  const certificateLines = certifications.map(item => item.text).filter(Boolean);
  return {
    ...profile,
    name: coach.name || '',
    slug: coach.slug || '',
    image: normalizeImage(coach.image),
    detailImage: normalizeImage(coach.image) === normalizeImage(profile.image) ? normalizeImage(profile.detailImage) || normalizeImage(coach.image) : normalizeImage(coach.image),
    coachType: coach.coach_type || '',
    cardBio: coach.card_bio || '',
    languages: coach.languages_text || (coach.languages_display || []).join(' / '),
    sections: [...sections.filter(section => !['專業證照', '滑雪證照'].includes(section.title)), ...(certificateLines.length ? [{ title: '專業證照', lines: certificateLines }] : [])],
    videos: Array.isArray(profile.videos) ? profile.videos.filter(item => item && typeof item.src === 'string' && /^https?:\/\//.test(item.src)).map(item => ({ ...item, title: typeof item.title === 'string' ? item.title : '課程影片' })) : [],
    reviews: Array.isArray(profile.reviews) ? profile.reviews.filter(item => item && typeof item === 'object').map(item => ({ ...item, name: typeof item.name === 'string' ? item.name : '', time: typeof item.time === 'string' ? item.time : '', paragraphs: strings(item.paragraphs), photos: images(item.photos) })) : [],
    heroBadges: strings(profile.heroBadges),
    abilityTags: { snowboard: strings(profile.abilityTags?.snowboard), ski: strings(profile.abilityTags?.ski) },
    certifications,
  };
}

export function websiteCoachCards(apiCoaches) {
  return apiCoaches.map(coach => ({
    websiteCoachId: coach.id,
    name: coach.name || '',
    slug: coach.slug || '',
    image: normalizeImage(coach.image),
    alt: coach.name || 'Coach portrait',
    coachType: coach.coach_type || '',
    certifications: Array.isArray(coach.certifications) ? coach.certifications : [],
    certificationText: coach.certification_text || '',
    cardBio: coach.card_bio || '',
    languages: coach.languages_text || (coach.languages_display || []).join(' / '),
  }));
}

export function useWebsiteCoachCards() {
  const [state, setState] = useState({ coaches: [], isLoading: true, error: false });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setState({ coaches: [], isLoading: true, error: false });
    fetchWebsiteCoaches()
      .then(apiCoaches => {
        if (active) setState({ coaches: websiteCoachCards(apiCoaches), isLoading: false, error: false });
      })
      .catch(() => {
        if (active) setState({ coaches: [], isLoading: false, error: true });
      });
    return () => { active = false; };
  }, [attempt]);
  return { ...state, retry: () => setAttempt(value => value + 1) };
}
