const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const compile=source=>ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
const calls=[],api=vm.createContext({exports:{},URLSearchParams,window:{location:{pathname:'/snowland/coach/qa'}},localStorage:{getItem:()=>null},fetch:async url=>{calls.push(url);return{ok:true,json:async()=>({data:{list:[]}})}},require:name=>{if(name.includes('utils/tenant'))return require('./helpers/tenant-harness.cjs')({location:{pathname:'/snowland/coach/qa'}},{getItem:()=>null});if(name==='react')return{};throw new Error(name)}})
vm.runInContext(compile(fs.readFileSync(path.join(root,'src/api/websiteCoaches.js'),'utf8')),api)
const map=api.exports.websiteCoachDetail
const row={id:7,name:'QA後端新教練',slug:'qa-new',image:'',coach_type:'單板',card_bio:'QA後端簡介',languages_text:'中文',certifications:[{text:'QA新證照'}],profile:{name:'不採用的舊姓名',image:'/old.jpg',cardBio:'舊簡介',sections:[{title:'教學理念',lines:['QA動態內容']},{title:'滑雪證照',lines:['舊證照']}],videos:[],reviews:[]}}
const detail=map(row)
assert.equal(detail.name,row.name);assert.equal(detail.image,'');assert.equal(detail.cardBio,row.card_bio)
assert.equal(detail.sections[0].lines[0],'QA動態內容');assert.equal(detail.sections[1].lines[0],'QA新證照')
assert.ok(!JSON.stringify(detail.sections).includes('舊證照'))
const cards=api.exports.websiteCoachCards([{...row,name:'Cash 更新姓名',slug:'cash-new',image:'',card_bio:''}])
assert.equal(cards[0].slug,'cash-new');assert.equal(cards[0].image,'');assert.equal(cards[0].cardBio,'')
const legacy=JSON.parse(fs.readFileSync(path.resolve(root,'../snowland/Client/fixtures/coach_profile_defaults.json'),'utf8'))
for(const profile of legacy){
  const preserved=map({...row,slug:profile.slug,profile})
  assert.equal(preserved.videos.length,(profile.videos||[]).length)
  assert.equal(preserved.reviews.length,(profile.reviews||[]).length)
  const originalImages=(profile.sections||[]).filter(s=>!['專業證照','滑雪證照'].includes(s.title)).reduce((n,s)=>n+(s.media||[]).length,0)
  assert.equal(preserved.sections.reduce((n,s)=>n+(s.media||[]).length,0),originalImages)
}
const malformed=map({...row,profile:{sections:[null,{title:'合法標題',lines:'bad',media:[null]}],videos:[null,{src:123}],reviews:[null,{paragraphs:{},photos:'bad'}],heroBadges:{},abilityTags:{snowboard:{}}}})
assert.equal(malformed.sections[0].lines.length,0);assert.equal(malformed.videos.length,0);assert.equal(malformed.reviews[0].photos.length,0)
const page=fs.readFileSync(path.join(root,'src/pages/site/CoachPage.jsx'),'utf8')
assert.ok(!page.includes("data/site/coaches"));assert.ok(!page.includes("data/site/cashReviews"))
function render(coach,status,language='zh-Hant'){
  const states=[coach,status,0];let index=0
  const hooks={...React,useEffect(){},useRef:()=>({current:null}),useState:initial=>{const i=index++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial;return[states[i],v=>states[i]=typeof v==='function'?v(states[i]):v]}}
  const noop=()=>null
  const ctx=vm.createContext({exports:{},window:{},require:name=>{
    if(name==='react')return hooks
    if(name.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(React,language)
    if(name==='react-router-dom')return{useParams:()=>({slug:'qa-new'}),Link:noop}
    if(name==='../../api/websiteCoaches')return{fetchWebsiteCoaches(){},websiteCoachDetail:map}
    if(name.startsWith('../../components/'))return noop
    throw new Error(name)
  }})
  vm.runInContext(compile(page),ctx)
  return renderToStaticMarkup(React.createElement(ctx.exports.default))
}
assert.ok(render(null,'loading').includes('正在載入教練介紹'))
assert.ok(render(null,'error').includes('重新載入'))
assert.ok(render(null,'ready').includes('找不到教練頁面'))
const fresh=render(map({...row,profile:{}}),'ready')
for(const language of ['en','ja']){
 const loaded=render(map({...row,profile:{sections:[{title:'教學理念',lines:['QA原始指導理念']},{title:'QA自訂段落',lines:['QA原始段落']}],videos:[],reviews:[]}}),'ready',language)
 assert.ok(loaded.includes(language==='en'?'Teaching philosophy':'指導方針'))
 assert.ok(loaded.includes('QA原始指導理念')&&loaded.includes('QA自訂段落')&&loaded.includes('QA原始段落'))
 assert.ok(loaded.includes(language==='en'?'Instructor photo coming soon':'インストラクターの写真を準備中'))
 assert.ok(render(null,'loading',language).includes(language==='en'?'Loading instructor profile':'インストラクター紹介を読み込み中'))
 assert.ok(render(null,'error',language).includes(language==='en'?'Outdated instructor information':'古いインストラクター情報'))
 assert.ok(render(null,'ready',language).includes(language==='en'?'Instructor page not found':'ページが見つかりません'))
 const locale=require('./helpers/site-locale-harness.cjs')(React,language)
 const text=(source,values)=>locale.translateSiteText(language,source,values)
 const rich=render(map({...row,profile:{sections:[{title:'自我介紹',lines:['QA原文保持'],media:[{src:'/qa-one.jpg',alt:'QA original alt'},{src:'/qa-two.jpg',alt:'QA original alt 2'}]}],videos:[{src:'https://www.youtube.com/embed/abcdefghijk',title:'QA original video'}],reviews:Array.from({length:6},(_,i)=>({name:`QA reviewer ${i+1}`,paragraphs:['QA original review'],photos:[{src:'/qa-review.jpg'}]}))}}),'ready',language)
 for(const key of ['上一部影片','下一部影片','上一頁評價','下一頁評價']){
  const button=rich.match(new RegExp(`<button[^>]*aria-label="${text(key)}"[^>]*>`))?.[0]
  assert.ok(button?.includes('min-h-11')&&button.includes('min-w-11'),`${language} ${key}: accessible touch target`)
 }
 assert.ok(rich.includes(text('評價第 {number} 頁',{number:2})))
 assert.ok(rich.includes(text('{title} 照片，按 Enter 或空白鍵切換',{title:text('自我介紹')})))
 assert.ok(rich.includes('QA original review')&&rich.includes('QA original video')&&rich.includes('QA original alt'))
 assert.ok(!rich.includes('VIEW MORE'))
}
assert.ok(fresh.includes('QA後端新教練'));assert.ok(fresh.includes('詳細介紹整理中'));assert.ok(fresh.includes('教練照片準備中'))
assert.ok(!fresh.includes('影音短片'), 'no videos must not render an empty carousel with a live next button')
const singleCopy=render(map({...row,profile:{sections:[{title:'教學理念',lines:['QA唯一理念20261018']},{title:'自訂段落',lines:['QA唯一自訂段落20261018']},{title:'自我介紹',lines:['QA沒有照片的介紹']}],videos:[]}}),'ready')
assert.equal((singleCopy.match(/QA唯一理念20261018/g)||[]).length,1,'one teaching paragraph must render once')
assert.equal((singleCopy.match(/QA唯一自訂段落20261018/g)||[]).length,1,'one custom paragraph must render once')
assert.ok(!singleCopy.includes('自我介紹-photos'),'no photos must not render the mobile empty carousel')
assert.ok(render(map({...row,profile:{videos:[{src:'https://www.youtube.com/embed/abcdefghijk',title:'QA影片'}]}}),'ready').includes('影音短片'))
assert.ok(render(detail,'ready').includes('QA動態內容'))
;(async()=>{await api.exports.fetchWebsiteCoaches({includeProfile:true,slug:'qa/中文'});const url=new URL(calls[0],'http://localhost:3000');assert.equal(url.pathname,'/booking/snowland/api/website-coaches/');assert.equal(url.searchParams.get('slug'),'qa/中文');assert.equal(url.searchParams.get('include_profile'),'1');console.log('PASS actual coach detail: canonical backend fields, safe rich copy, new coach, loading/error/404, no static fallback and encoded request')})().catch(e=>{console.error(e);process.exit(1)})
