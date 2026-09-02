import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from './SiteLink';
import resortLegacyData from '../../data/site/resortLegacyData';

function ResortCard({ resort }) {
  const resortRoute = resort.route || `/course/${resort.slug}`;
  const heroImage = resort.heroImage || resortLegacyData[resort.slug]?.heroImage || resort.imagePlaceholder;

  return (
    <SiteLink
      to={resortRoute}
      className="group flex h-full flex-col overflow-hidden transition-transform duration-300 hover:-translate-y-1"
    >
      <div className="aspect-square bg-[#e2e8f0]">
        <img
          src={heroImage}
          alt={resort.nameEnglish}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          loading="lazy"
        />
      </div>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="text-[10px] font-semibold tracking-[0.3em] uppercase text-[#94a3b8]">
          {resort.region}
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[#1f2937]">{resort.nameChinese}</h3>
          <p className="text-xs text-[#64748b]">{resort.nameEnglish}</p>
        </div>
        <div className="mt-auto flex flex-wrap gap-2">
          {resort.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-[#e2e8f0] px-2.5 py-0.5 text-[11px] font-semibold text-[#475569]"
            >
              {tag}
            </span>
          ))}
        </div>
        <span className="mt-3 inline-flex items-center justify-center rounded-full border border-[#1f2937] px-3 py-1.5 text-xs font-semibold text-[#1f2937] transition-colors duration-200 group-hover:bg-[#1f2937] group-hover:text-white">
          查看雪場資訊
        </span>
      </div>
    </SiteLink>
  );
}

export default ResortCard;
