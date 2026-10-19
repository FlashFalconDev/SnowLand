const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/utils/siteTracking.js'),'utf8')
const ctx=vm.createContext({exports:{},URL,Date});vm.runInContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,ctx)
const {trackingConfig,publicTrackingPage,trackingButton,createTrackingRuntime}=ctx.exports
const item={status:'active',metadata:{enabled:true,auto_events_disabled:true,ga4_id:'G-QA12345678',meta_pixel_id:'1234567890'}}
const config=trackingConfig(item)
let checks=0
function test(name,run){run();checks++;console.log('PASS '+name)}
function browser(url='https://qa.example/snowland/'){
  const stored=new Map(),scripts=[],events={},actions=[],messages=[]
  const win={navigator:{},location:new URL(url),document:{referrer:'',head:{appendChild:n=>scripts.push(n)},createElement:()=>({})},
    history:{pushState(s,u,target){win.location=new URL(target,win.location.href)},replaceState(s,u,target){win.location=new URL(target,win.location.href)}},
    localStorage:{getItem:key=>stored.get(key)||null,setItem:(key,value)=>stored.set(key,value)},
    addEventListener:(type,fn)=>{events[type]=fn},removeEventListener:type=>{delete events[type]}}
  for(const method of ['assign','replace','reload'])win.location[method]=target=>actions.push([method,target])
  const runtime=createTrackingRuntime(win)
  return {win,stored,scripts,events,actions,messages,runtime,setup:()=>runtime.configure(config,'/snowland',message=>messages.push(message))}
}
const queued=fn=>Array.from(fn?.queue||[],args=>Array.from(args))
const gaEvents=win=>Array.from(win.dataLayer||[],args=>Array.from(args))
test('default off, invalid IDs and explicit activation gate',()=>{
  for(const bad of [null,{}, {...item,status:'draft'},{...item,metadata:{...item.metadata,enabled:false}}, {...item,metadata:{...item.metadata,auto_events_disabled:false}}, {...item,metadata:{enabled:true,auto_events_disabled:true,ga4_id:'<script>',meta_pixel_id:'１２３４５'}}])assert.equal(trackingConfig(bad),null)
  const b=browser();assert.equal(b.setup(),null);assert.equal(b.scripts.length,0)
  b.runtime.button('booking_start');assert.equal(b.win.dataLayer,undefined)
})
test('only public tenant paths, no query, hash, encoded URLs, forms or other origin',()=>{
  for(const suffix of ['', 'course/tomamu','coach','Gallery','specialoffers/earlybird','privacy-policy'])assert.ok(publicTrackingPage('https://qa.example/snowland/'+suffix,'/snowland','https://qa.example'))
  for(const suffix of ['membership','console/orders','booking','payment','history','contact','booking-legacy','?email=private','#token','course/%61bc'])assert.equal(publicTrackingPage('https://qa.example/snowland/'+suffix,'/snowland','https://qa.example'),'')
  assert.equal(publicTrackingPage('https://other.example/snowland/','/snowland','https://qa.example'),'')
  assert.equal(publicTrackingPage('https://qa.example/snowland-other/course','/snowland','https://qa.example'),'')
})
test('reject persists and reload never loads an SDK',()=>{
  const b=browser();b.setup();assert.equal(b.runtime.save({analytics:false,marketing:false}),true)
  assert.equal(b.scripts.length,0);assert.equal(b.setup().analytics,false);assert.equal(b.scripts.length,0)
})
test('separate GA consent loads Google only and fixed payloads',()=>{
  const b=browser();b.setup();b.runtime.save({analytics:true,marketing:false})
  assert.equal(b.scripts.length,1);assert.match(b.scripts[0].src,/googletagmanager/);assert.equal(b.scripts[0].referrerPolicy,'no-referrer')
  assert.equal(b.win.fbq,undefined)
  const commands=gaEvents(b.win),cfg=commands.find(c=>c[0]==='config')[2]
  assert.equal(cfg.send_page_view,false);assert.equal(cfg.allow_google_signals,false);assert.equal(cfg.page_referrer,'')
  assert.equal(commands.filter(c=>c[1]==='page_view').length,1)
  b.runtime.page();assert.equal(gaEvents(b.win).filter(c=>c[1]==='page_view').length,1)
  b.runtime.button('member@example.test');b.runtime.button('booking_start')
  assert.equal(gaEvents(b.win).filter(c=>c[1]==='navigation_click').length,1)
  assert.equal(JSON.stringify(gaEvents(b.win)).includes('member@example.test'),false)
})
test('Meta manual events, auto configuration disabled BEFORE init, no advanced matching',()=>{
  const b=browser();b.setup();b.runtime.save({analytics:false,marketing:true})
  assert.equal(b.scripts.length,1);assert.match(b.scripts[0].src,/connect.facebook.net/);assert.equal(b.win.gtag,undefined)
  const commands=queued(b.win.fbq),set=commands.findIndex(c=>c[0]==='set'),init=commands.findIndex(c=>c[0]==='init')
  assert.ok(set<init);assert.deepEqual(commands[set],['set','autoConfig',false,config.meta]);assert.equal(commands[init].length,2)
  assert.equal(b.win.fbq.disablePushState,true)
  b.runtime.button('view_courses');assert.ok(queued(b.win.fbq).some(c=>c[0]==='trackSingleCustom'&&c[3].button_name==='view_courses'))
})
test('private navigation reloads BEFORE router mutation with tracking revoked',()=>{
  const b=browser();b.setup();b.runtime.save({analytics:true,marketing:true})
  b.win.history.pushState({},'','/snowland/membership?return_to=booking')
  assert.equal(b.win.location.pathname,'/snowland/');assert.equal(b.actions[0][0],'assign')
  assert.equal(b.win['ga-disable-'+config.ga4],true)
  assert.ok(queued(b.win.fbq).some(c=>c[0]==='consent'&&c[1]==='revoke'))
  const before=gaEvents(b.win).length;b.runtime.button('booking_start');assert.equal(gaEvents(b.win).length,before)
})
test('public navigation keeps router and records category, not slug',()=>{
  const b=browser();b.setup();b.runtime.save({analytics:true,marketing:true})
  b.win.history.pushState({},'','/snowland/course/tomamu');b.runtime.page()
  b.win.history.pushState({},'','/snowland/course/furano');b.runtime.page()
  assert.equal(b.actions.length,0);const pages=gaEvents(b.win).filter(c=>c[1]==='page_view')
  assert.equal(pages.length,3);assert.equal(pages[2][2].page_location,'https://qa.example/snowland/course')
})
test('withdraw persists before revoke and full reload',()=>{
  const b=browser();b.setup();b.runtime.save({analytics:true,marketing:true});b.runtime.save({analytics:false,marketing:false})
  assert.equal(JSON.parse(b.stored.values().next().value).analytics,false);assert.equal(b.actions[0][0],'reload')
})
test('storage failure, corrupt or expired preferences are fail closed',()=>{
  const b=browser();b.setup();b.win.localStorage.setItem=()=>{throw Error('blocked')}
  assert.equal(b.runtime.save({analytics:true,marketing:true}),false);assert.equal(b.scripts.length,0);assert.ok(b.messages.length)
  for(const value of ['not json',JSON.stringify({fingerprint:config.fingerprint,expires:1,analytics:true,marketing:true}),JSON.stringify({fingerprint:'old',expires:Date.now()+1000,analytics:true,marketing:true})]){
    const c=browser();c.stored.set('snowland:tracking:/snowland',value);assert.equal(c.setup(),null);assert.equal(c.scripts.length,0)
  }
})
test('browser privacy, local HTTP and all sensitive initial locations never load scripts',()=>{
  for(const url of ['http://localhost:3000/snowland/','http://127.0.0.1:3000/snowland/','https://qa.example/snowland/contact','https://qa.example/snowland/booking','https://qa.example/snowland/?access_token=secret']){
    const b=browser(url);b.setup();b.runtime.save({analytics:true,marketing:true});assert.equal(b.scripts.length,0,url)
  }
  const b=browser();b.win.navigator.globalPrivacyControl=true;b.setup();b.runtime.save({analytics:true,marketing:true});assert.equal(b.scripts.length,0)
})
test('unsafe referrer and competing integrations fail closed',()=>{
  for(const ref of ['https://qa.example/snowland/membership','https://qa.example/?email=secret']){
    const b=browser();b.win.document.referrer=ref;b.setup();b.runtime.save({analytics:true,marketing:true});assert.equal(b.scripts.length,0)
  }
  const b=browser();const existing=()=>{};b.win.gtag=existing;b.setup();b.runtime.save({analytics:true,marketing:true});assert.equal(b.scripts.length,0);assert.equal(b.win.gtag,existing);assert.ok(b.messages.length)
  const c=browser();c.win.dataLayer=[{email:'must-not-send@example.test'}];c.setup();c.runtime.save({analytics:true,marketing:true});assert.equal(c.scripts.length,0)
})
test('SDK failure stops future manual events without breaking navigation',()=>{
  const b=browser();b.setup();b.runtime.save({analytics:true,marketing:true});b.scripts[0].onerror()
  const before=gaEvents(b.win).length;b.runtime.page();b.runtime.button('booking_start');assert.equal(gaEvents(b.win).length,before);assert.ok(b.messages.length)
  b.win.history.pushState({},'','/snowland/contact');assert.equal(b.actions[0][0],'assign')
})
test('fixed navigation button names only',()=>{
  assert.equal(trackingButton('/booking'),'booking_start');assert.equal(trackingButton('/course/tomamu'),'view_courses')
  for(const value of ['/booking?email=private','/contact#private','https://other.test/',{},null])assert.equal(trackingButton(value),'')
})
test('config changes require fresh consent and revoke an already loaded SDK',()=>{
  const b=browser();b.setup();b.runtime.save({analytics:true,marketing:true})
  b.runtime.configure({...config,ga4:'G-NEW1234567',fingerprint:'new'},'/snowland')
  assert.equal(b.actions[0][0],'reload');assert.equal(b.win['ga-disable-'+config.ga4],true)
  const c=browser();c.stored.set('snowland:tracking:/snowland',JSON.stringify({fingerprint:'other-account',expires:Date.now()+1000,analytics:true,marketing:true}));assert.equal(c.setup(),null);assert.equal(c.scripts.length,0)
})
test('back navigation into a sensitive page revokes and reloads',()=>{
  const b=browser();b.setup();b.runtime.save({analytics:true,marketing:true})
  b.win.location.pathname='/snowland/membership';b.events.popstate()
  assert.equal(b.actions[0][0],'reload');assert.equal(b.win['ga-disable-'+config.ga4],true)
})
test('SDK initialization exceptions cannot break website controls',()=>{
  const b=browser();b.win.document.head.appendChild=()=>{throw Error('CSP blocks script')};b.setup()
  assert.doesNotThrow(()=>b.runtime.save({analytics:true,marketing:false}))
  assert.ok(b.messages.length);assert.equal(b.win['ga-disable-'+config.ga4],true)
})
console.log(`${checks} runtime contract checks passed (mock SDK, not proof of external platform receipt)`)
