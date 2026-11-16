import React, { createContext, useContext, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { clientCodeFromPath } from '../utils/tenant';
import { readSiteLanguagePreference, resolveSiteLocale, siteLanguages, siteLanguageStorageKey, translateSiteText } from '../utils/siteLocale';

const browserLanguages=()=>typeof navigator==='undefined'?[]:navigator.languages?.length?navigator.languages:[navigator.language];
const readPreference=()=>{try{return readSiteLanguagePreference(window.localStorage);}catch{return 'auto';}};
const SiteLocaleContext=createContext({locale:/** @type {import('../utils/siteLocale').SiteLocale} */ ('zh-Hant'),preference:'auto',storageError:false,setPreference:()=>{},siteText:(_scope,_key,source)=>source,navText:(source)=>translateSiteText('zh-Hant',source),t:(source,values={})=>translateSiteText('zh-Hant',source,values)});

export function SiteLocaleProvider({children}) {
  const {pathname}=useLocation();
  const tenant=clientCodeFromPath(pathname);
  const isConsole=/^(?:\/[^/]+)?\/console(?:\/|$)/.test(pathname);
  const [remote,setRemote]=useState(null);
  const [preference,setPreferenceState]=useState(readPreference);
  const [languages,setLanguages]=useState(browserLanguages);
  const [storageError,setStorageError]=useState(false);
  const locale=resolveSiteLocale(preference,languages);
  useEffect(()=>{
    if (!tenant || isConsole) return;
    const controller=new AbortController();
    fetch(`/booking/${encodeURIComponent(tenant)}/api/site-translations/`,{signal:controller.signal,cache:'no-store'})
      .then(response=>response.ok ? response.json() : null)
      .then(result=>{if (!controller.signal.aborted) setRemote({tenant,scopes:result?.scopes || {}});})
      .catch(()=>{if (!controller.signal.aborted) setRemote({tenant,scopes:{}});});
    return ()=>controller.abort();
  },[tenant,isConsole,locale]);
  useEffect(()=>{
    const languageChanged=()=>setLanguages(browserLanguages());
    const storageChanged=event=>{if(event.key===siteLanguageStorageKey||event.key===null){setPreferenceState(readPreference());setStorageError(false);}};
    window.addEventListener('languagechange',languageChanged);
    window.addEventListener('storage',storageChanged);
    return ()=>{window.removeEventListener('languagechange',languageChanged);window.removeEventListener('storage',storageChanged);};
  },[]);
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
  const scopes=remote?.tenant===tenant && !isConsole ? remote.scopes : {};
  const lookup=(scope,key,source)=>{
    const row=scopes?.[scope]?.[key];
    return row?.source===source ? row.values?.[locale] : undefined;
  };
  const siteText=(scope,key,source)=>lookup(scope,key,source) || source;
  return <SiteLocaleContext.Provider value={{locale,preference,setPreference,storageError,siteText,
    navText:(source)=>translateSiteText(locale,source,{},lookup('navigation',source,source)),
    t:(source,values={})=>translateSiteText(locale,source,values,lookup('ui',source,source))}}>{children}</SiteLocaleContext.Provider>;
}

export const useSiteLocale=()=>useContext(SiteLocaleContext);
