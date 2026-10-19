// One-time mechanical extraction: preserve the existing section's visual markup.
const fs=require('node:fs'),path=require('node:path')
const base=path.resolve(__dirname,'../snowland-frontend/src'),file=path.join(base,'pages/site/HomePage.jsx')
let home=fs.readFileSync(file,'utf8').replace(/\r\n/g,'\n')
if(home.includes('<PopularCourses />'))throw Error('Already extracted; do not reapply')
const start=home.indexOf('      <section className="bg-white">'),end=home.indexOf('      <section id="homepage-reviews"',start)
if(start<0||end<0)throw Error('Expected original section missing')
let section=home.slice(start,end).trim()
section=section.replace('<section className="bg-white">','<section id="homepage-courses" className="bg-white scroll-mt-24">').replace('lg:grid-cols-3','lg:grid-cols-2').replace('key={resort.title}','key={resort.id}').replaceAll('expandedCourses[resort.title]','expandedCourses[resort.id]').replace('[resort.title]: !prev[resort.title]','[resort.id]: !prev[resort.id]').replace('className="mt-3 inline-flex items-center','aria-expanded={!!expandedCourses[resort.id]} className="mt-3 inline-flex min-h-11 items-center').replace('className="inline-flex items-center justify-center px-8 py-2','className="inline-flex min-h-11 items-center justify-center px-8 py-2')
section=section.replace('<div className="grid grid-cols-1 lg:grid-cols-2 gap-12 md:gap-16">',`{isLoading ? <p role="status" className="text-center text-sm text-[#475569]">正在載入熱門課程…</p> : error ? <p role="alert" className="text-center text-sm text-red-700">熱門課程載入失敗。<button type="button" className="ml-2 min-h-11 underline" onClick={refetch}>重試熱門課程</button></p> : !resortCards.length ? <p className="text-center text-sm text-[#475569]">目前尚無公開熱門課程。</p> : null}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 md:gap-16">`)
section=section.replace('<div className="mt-6 w-full">','{resort.image && <div className="mt-6 w-full">').replace('                </div>\n\n                <div className="mt-6 text-', '                </div>}\n\n                <div className="mt-6 text-')
const component=`import React, { useState } from 'react';
import SiteLink from './SiteLink';
import { useSiteContent } from '../../hooks/useSiteContent';

export default function PopularCourses() {
  const [expandedCourses, setExpandedCourses] = useState({});
  const { items, isLoading, error, refetch } = useSiteContent('homepage.courses', { contentType: 'page' });
  const resortCards = items.map(item => ({id: item.id, title: item.title, description: item.summary || item.body || '', image: item.image_url, href: item.link_url, cta: item.subtitle || '立即查看課程'}));
  return (${section});
}
`
fs.writeFileSync(path.join(base,'components/site/PopularCourses.jsx'),component)
home=home.slice(0,start)+'      <PopularCourses />\n\n'+home.slice(end)
home=home.replace("import SpecialOffers from '../../components/site/SpecialOffers';","import SpecialOffers from '../../components/site/SpecialOffers';\nimport PopularCourses from '../../components/site/PopularCourses';")
for(const name of ['tomamuResort','offPisteCourse','hokkaidoCourse'])home=home.replace(new RegExp('import '+name+' from [^;]+;\\r?\\n'),'')
home=home.replace(/  const \[expandedCourses, setExpandedCourses\] = useState\(\{\}\);\r?\n/,'')
const arrayStart=home.indexOf('  const resortCards = ['),arrayEnd=home.indexOf('  React.useEffect(',arrayStart)
if(arrayStart<0||arrayEnd<0)throw Error('Original hardcoded cards missing')
home=home.slice(0,arrayStart)+home.slice(arrayEnd)
fs.writeFileSync(file,home)
console.log('Extracted original popular course markup; removed hardcoded cards, kept existing site styling.')
