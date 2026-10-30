const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
let state,language='zh-Hant'
const context=vm.createContext({exports:{},require:name=>name==='@/hooks/useClient'?{useClientInfo:()=>state}:name==='@/contexts/SiteLocale'?require('./helpers/site-locale-harness.cjs')(React,language):name==='react-router-dom'?{Link:({to,children,...props})=>React.createElement('a',{href:to,...props},children)}:name.includes('SiteHeader')||name.includes('SiteFooter')?{default:()=>null}:req(name)})
const source=fs.readFileSync(path.join(root,'src/components/booking/SchoolBookingGate.tsx'),'utf8')
function render(){vm.runInContext('(function(){'+ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText+'})()',context);return renderToStaticMarkup(React.createElement(context.exports.default,{children:React.createElement('div',null,'BOOKING-QA')}))}
state={clientCode:'school-a',clientInfo:{booking_enabled:true},isLoading:false,error:''}
assert.ok(render().includes('BOOKING-QA'))
state={...state,isLoading:true};assert.ok(!render().includes('BOOKING-QA'))
state={...state,isLoading:false,clientCode:'school-b',clientInfo:{booking_enabled:false}}
let html=render();assert.ok(!html.includes('BOOKING-QA'));assert.ok(html.includes('暫停受理'));assert.ok(html.includes('href="/school-b/membership"'));assert.ok(!html.includes('/school-a/'))
for(language of ['en','ja']){html=render();assert.ok(!html.includes('目前暫停受理新預約'));assert.ok(html.includes('href="/school-b/membership"'))}
state={...state,clientInfo:null,error:'not found'};html=render();assert.ok(!html.includes('BOOKING-QA'));assert.ok(!html.includes('href="/school-b/membership"'))
const app=fs.readFileSync(path.join(root,'src/App.tsx'),'utf8')
assert.equal((app.match(/<SchoolBookingGate><BookingFlowPage \/><\/SchoolBookingGate>/g)||[]).length,2)
console.log('PASS booking school gate: enabled, loading, disabled, unavailable, school-scoped existing-member access and en/ja messages')
