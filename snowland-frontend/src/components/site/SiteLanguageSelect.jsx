import React, { useId } from 'react';
import { useSiteLocale } from '../../contexts/SiteLocale';
import { siteLanguages } from '../../utils/siteLocale';

export default function SiteLanguageSelect({darkText=true}) {
  const {preference,setPreference,storageError,t}=useSiteLocale();
  const id=useId();
  return <div className={darkText?'text-[#1f2937]':'text-white'}>
    <label htmlFor={id} className="sr-only">語言 / Language / 言語</label>
    <select id={id} value={preference} onChange={event=>setPreference(event.target.value)} className="min-h-11 max-w-full rounded border border-current bg-transparent px-2 text-xs font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">
      {siteLanguages.map(item=><option key={item.value} value={item.value} className="bg-white text-[#1f2937]">{item.label}</option>)}
    </select>
    {storageError&&<p role="status" className="mt-1 max-w-56 text-xs leading-5">{t('語言偏好無法儲存，本次仍可使用。')}</p>}
  </div>;
}
