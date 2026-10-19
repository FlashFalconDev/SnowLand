import React, { createContext, useContext, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { readSiteLanguagePreference, resolveSiteLocale, siteLanguages, siteLanguageStorageKey, translateSiteText } from '../utils/siteLocale';

const browserLanguages=()=>typeof navigator==='undefined'?[]:navigator.languages?.length?navigator.languages:[navigator.language];
const readPreference=()=>{try{return readSiteLanguagePreference(window.localStorage);}catch{return 'auto';}};
const SiteLocaleContext=createContext({locale:/** @type {import('../utils/siteLocale').SiteLocale} */ ('zh-Hant'),preference:'auto',storageError:false,setPreference:()=>{},t:(source,values={})=>translateSiteText('zh-Hant',source,values)});

export function SiteLocaleProvider({children}) {
  const {pathname}=useLocation();
  const [preference,setPreferenceState]=useState(readPreference);
  const [languages,setLanguages]=useState(browserLanguages);
  const [storageError,setStorageError]=useState(false);
  useEffect(()=>{
    const languageChanged=()=>setLanguages(browserLanguages());
    const storageChanged=event=>{if(event.key===siteLanguageStorageKey||event.key===null){setPreferenceState(readPreference());setStorageError(false);}};
    window.addEventListener('languagechange',languageChanged);
    window.addEventListener('storage',storageChanged);
    return ()=>{window.removeEventListener('languagechange',languageChanged);window.removeEventListener('storage',storageChanged);};
  },[]);
  const locale=resolveSiteLocale(preference,languages);
  useEffect(()=>{
    const previous=document.documentElement.lang;
    document.documentElement.lang=/^(?:\/[^/]+)?\/console(?:\/|$)/.test(pathname)?'zh-Hant':locale;
    return ()=>{document.documentElement.lang=previous;};
  },[locale,pathname]);
  const setPreference=next=>{
    if(!siteLanguages.some(item=>item.value===next))return;
    setPreferenceState(next);
    try{window.localStorage.setItem(siteLanguageStorageKey,next);setStorageError(false);}
    catch{setStorageError(true);}
  };
  return <SiteLocaleContext.Provider value={{locale,preference,setPreference,storageError,t:(source,values={})=>translateSiteText(locale,source,values)}}>{children}</SiteLocaleContext.Provider>;
}

export const useSiteLocale=()=>useContext(SiteLocaleContext);
