// One-shot mechanical extraction of the current homepage sections, retaining original classes and motion.
const fs=require('node:fs'),path=require('node:path')
const root=path.resolve(__dirname,'../snowland-frontend/src'),file=path.join(root,'pages/site/HomePage.jsx')
let source=fs.readFileSync(file,'utf8').replace(/\r\n/g,'\n')
const start=source.indexOf('      <div ref={containerRef}'),end=source.indexOf('      <PopularCourses />')
if(start<0||end<start)throw Error('Original sections missing; refuse repeat or ambiguous extraction')
let block=source.slice(start,end),split=block.indexOf('      <section id="about-snowland"')
let hero=block.slice(0,split).trimEnd(),intro=block.slice(split).trimEnd()
const videoStart=hero.indexOf('        {/* Background Video'),videoEnd=hero.indexOf('        {/* Dark Overlay')
hero=hero.slice(0,videoStart)+`        {videoSrc && <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0"><div className="absolute top-1/2 left-1/2 min-w-full min-h-full w-[177.77vh] h-[56.25vw] -translate-x-1/2 -translate-y-1/2 pointer-events-none"><iframe className="w-full h-full scale-105" src={videoSrc} title="Background Video" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowFullScreen /></div></div>}
        {hero.metadata?.media_type === 'image' && hero.image_url && <img src={hero.image_url} alt="" className="absolute inset-0 h-full w-full object-cover" />}

`+hero.slice(videoEnd)
hero=hero.replace('className="relative w-full h-screen overflow-hidden"','className="relative w-full h-screen overflow-hidden bg-[#143a53]"')
 .replace('bg-linear-to-b','bg-gradient-to-b')
 .replace('            北海道星野TOMAMU<br />\n            官方許可滑雪學校','            {hero.title}')
 .replace('className="text-2xl md:text-4xl','className="whitespace-pre-line text-2xl md:text-4xl')
 .replace('            安心的親子共學旅程，一起創造難忘的滑雪回憶','            {hero.summary}')
 .replace('            Enjoy a joyful family ski experience — create unforgettable memories together.','            {hero.subtitle}')
 .replace('          <motion.div\n            initial={{ opacity: 0, scale: 0.9 }}','          {hero.link_url && hero.metadata?.button_text && <motion.div\n            initial={{ opacity: 0, scale: 0.9 }}')
 .replace('              to="/booking"','              to={hero.link_url}')
 .replace('<span className="relative z-10">預約課程</span>','<span className="relative z-10">{hero.metadata.button_text}</span>')
 .replace('          </motion.div>','          </motion.div>}')
 .replace('className="w-10 h-10 flex items-center justify-center"','className="w-11 h-11 flex items-center justify-center"')
intro=intro.replace('src={aboutSnowland}','src={intro.image_url || (intro.metadata?.image_asset === \'original-school-photo\' ? aboutSnowland : undefined)}')
 .replace('                Snowland 滑雪學校','                {intro.title}')
 .replace('                SnowLand滑雪學校為','                {intro.metadata?.opening_text}')
 .replace('                  星野Tomamu度假村／留壽都渡假村／手稻滑雪場 / 札幌國際雪場','                  {intro.metadata?.resort_names}')
 .replace('                官方許可，於日本合法登記的滑雪學校，擁有多年北海道雪場教學經歷。','                {intro.metadata?.opening_suffix}')
 .replace('                提供','                {intro.metadata?.language_prefix}')
 .replace('<span className="font-semibold">中文、粵語、英文</span>','<span className="font-semibold">{intro.metadata?.languages}</span>')
 .replace('                等多語言教學選擇，以確保每位學員都能在熟悉和舒適的語言環境中自在學習滑雪技巧。','                {intro.metadata?.language_suffix}')
 .replace('aboutParagraphs.slice(2)','extraParagraphs')
 .replace('              <button\n','              {extraParagraphs.length > 0 && <button\n')
 .replace('                className="inline-flex items-center text-sm','                aria-expanded={showAboutMore}\n                className="min-h-11 inline-flex items-center text-sm')
 .replace('              </button>','              </button>}')
 .replace('              <div className="flex justify-center">','              {intro.link_url && intro.metadata?.button_text && <div className="flex justify-center">')
 .replace('                  to="/about"','                  to={intro.link_url}')
 .replace('                  了解更多','                  {intro.metadata.button_text}')
 .replace('pointer-events-auto inline-flex','pointer-events-auto min-h-11 inline-flex')
 .replace('              </div>','              </div>}')
const output=`import React, {useState} from 'react';
import {motion} from 'framer-motion';
import SiteHeader from './SiteHeader';
import SiteLink from './SiteLink';
import aboutSnowland from '../../assets/site/About snowland.jpg';
import {useSiteContent} from '../../hooks/useSiteContent';

function ContentState({result,label}) {
  if (result.isLoading) return <p role="status" className="px-6 py-32 text-center text-sm text-[#475569]">正在載入{label}…</p>;
  if (result.error) return <div role="alert" className="px-6 py-32 text-center text-sm text-red-700">{label}載入失敗。<button type="button" className="min-h-11 px-3 underline" onClick={result.refetch}>重新載入{label}</button></div>;
  return null;
}

export default function HomepagePresentation({containerRef,y,opacity}) {
  const heroResult=useSiteContent('homepage.hero',{contentType:'setting'}),introResult=useSiteContent('homepage.intro',{contentType:'setting'});
  const hero=heroResult.items[0],intro=introResult.items[0];
  const [showAboutMore,setShowAboutMore]=useState(false);
  const videoId=hero?.metadata?.youtube_id;
  const videoSrc=hero?.metadata?.media_type==='youtube' && /^[A-Za-z0-9_-]{11}$/.test(videoId || '') ? \`https://www.youtube.com/embed/\${videoId}?autoplay=1&mute=1&controls=0&loop=1&playlist=\${videoId}&playsinline=1&showinfo=0&rel=0&iv_load_policy=3&disablekb=1&modestbranding=1&autohide=1&enablejsapi=1\` : '';
  const extraParagraphs=Array.isArray(intro?.metadata?.extra_paragraphs) ? intro.metadata.extra_paragraphs.filter(text=>typeof text==='string') : [];
  return <>
    <SiteHeader forceDarkText={!hero} forceLogoColor={!hero} />
    {hero ? <>
${hero}
    </> : <div ref={containerRef}><ContentState result={heroResult} label="首頁主視覺" /></div>}
    {intro ? <>
${intro}
    </> : <ContentState result={introResult} label="首頁學校介紹" />}
  </>;
}
`
const target=path.join(root,'components/site/HomepagePresentation.jsx')
if(fs.existsSync(target))throw Error('Target exists; refuse overwrite')
fs.writeFileSync(target,output)
source=source.slice(0,start)+'      <HomepagePresentation containerRef={containerRef} y={y} opacity={opacity} />\n\n'+source.slice(end)
source=source.replace("import aboutSnowland from '../../assets/site/About snowland.jpg';\n",'').replace("import SiteHeader from '../../components/site/SiteHeader';","import HomepagePresentation from '../../components/site/HomepagePresentation';")
 .replace('  const [showAboutMore, setShowAboutMore] = useState(false);\n','')
source=source.replace(/  const aboutParagraphs = \[[\s\S]*?\n  \];\n/,'').replace('      <SiteHeader />\n','')
fs.writeFileSync(file,source)
console.log('Extracted original hero and introduction without rebuilding page styles.')
