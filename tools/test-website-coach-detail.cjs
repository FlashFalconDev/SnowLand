const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const compile=source=>ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
const calls=[],api=vm.createContext({exports:{},URLSearchParams,window:{location:{pathname:'/snowland/coach/qa'}},localStorage:{getItem:()=>null},fetch:async url=>{calls.push(url);return{ok:true,json:async()=>({data:{list:[]}})}},require:name=>{if(name==='react')return{};throw new Error(name)}})
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
function render(coach,status){
  const states=[coach,status,0];let index=0
  const hooks={...React,useEffect(){},useRef:()=>({current:null}),useState:initial=>{const i=index++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial;return[states[i],v=>states[i]=typeof v==='function'?v(states[i]):v]}}
  const noop=()=>null
  const ctx=vm.createContext({exports:{},window:{},require:name=>{
    if(name==='react')return hooks
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
assert.ok(fresh.includes('QA後端新教練'));assert.ok(fresh.includes('詳細介紹整理中'));assert.ok(fresh.includes('教練照片準備中'))
assert.ok(render(detail,'ready').includes('QA動態內容'))
;(async()=>{await api.exports.fetchWebsiteCoaches({includeProfile:true,slug:'qa/中文'});const url=new URL(calls[0],'http://localhost:3000');assert.equal(url.pathname,'/booking/snowland/api/website-coaches/');assert.equal(url.searchParams.get('slug'),'qa/中文');assert.equal(url.searchParams.get('include_profile'),'1');console.log('PASS actual coach detail: canonical backend fields, safe rich copy, new coach, loading/error/404, no static fallback and encoded request')})().catch(e=>{console.error(e);process.exit(1)})
