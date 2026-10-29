const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),render=req('react-dom/server').renderToStaticMarkup
const compiled=ts.transpileModule(fs.readFileSync(path.join(root,'src/components/site/SiteTracking.jsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true,target:ts.ScriptTarget.ES2020}}).outputText
function nodes(node,p,out=[]){if(!node||typeof node!=='object')return out;if(p(node))out.push(node);for(const child of React.Children.toArray(node.props?.children))nodes(child,p,out);return out}
function app(language,{signal=false,saveOk=true,notice='',config=true}={}){
 const states=[true,{analytics:false,marketing:false},notice],calls=[];let cursor=0
 const hooks={...React,useContext:()=>'/snowland',useMemo:fn=>fn(),useEffect:()=>{},useState:initial=>{const index=cursor++;return[states[index]??initial,value=>states[index]=typeof value==='function'?value(states[index]):value]}}
 const locale=require('./helpers/site-locale-harness.cjs')(React,language),context={exports:{},window:{location:{href:'http://127.0.0.1:3000/snowland/',origin:'http://127.0.0.1:3000'}},require:name=>{
  if(name==='react')return hooks
  if(name==='react-router-dom')return{useLocation:()=>({pathname:'/snowland/'})}
  if(name.includes('contexts/SiteLocale'))return locale
  if(name.includes('useSiteContent'))return{useSiteContent:()=>({items:[{}]})}
  if(name.includes('utils/siteTracking'))return{publicTrackingPage:()=>true,trackingConfig:()=>config?{ga4:'QA',meta:'QA'}:null,siteTracking:{isLocal:()=>true,privacySignal:()=>signal,save:choice=>{calls.push(choice);return saveOk}}}
  if(name==='./SiteLink')return{__esModule:true,SiteBasePathContext:React.createContext('/snowland'),default:({to,children})=>React.createElement('a',{href:'/snowland'+to},children)}
  throw Error(name)
 }};vm.runInNewContext(compiled,context);return{calls,states,render:()=>{cursor=0;return context.exports.default()}}
}
for(const language of ['en','ja']){
 const ui=app(language),tree=ui.render(),html=render(tree)
 assert.ok(html.includes(language==='en'?'Choose your analytics preferences':'アクセス解析の設定'))
 assert.ok(html.includes(language==='en'?'external tracking does not load':'外部トラッキングは読み込みません'))
 assert.ok(html.includes('href="/snowland/privacy-policy"'))
 nodes(tree,n=>n.type==='input')[0].props.onChange({target:{checked:true}})
 nodes(ui.render(),n=>n.type==='button'&&n.props.children===(language==='en'?'Save choices':'設定を保存'))[0].props.onClick()
 assert.equal(ui.calls[0].analytics,true);assert.equal(ui.calls[0].marketing,false);assert.equal(ui.states[0],false)
 nodes(ui.render(),n=>n.type==='button')[0].props.onClick();assert.equal(ui.states[0],true)
 nodes(ui.render(),n=>n.type==='button'&&n.props.children===(language==='en'?'Reject all':'すべて拒否'))[0].props.onClick()
 assert.equal(ui.calls[1].analytics,false);assert.equal(ui.calls[1].marketing,false)
 const failed=app(language,{saveOk:false,notice:'無法儲存隱私偏好，追蹤保持關閉。'});nodes(failed.render(),n=>n.type==='button'&&n.props.children===(language==='en'?'Save choices':'設定を保存'))[0].props.onClick();assert.equal(failed.states[0],true)
 assert.ok(render(failed.render()).includes(language==='en'?'Tracking remains off':'トラッキングは無効のまま'))
 assert.ok(nodes(app(language,{signal:true}).render(),n=>n.type==='input').every(input=>input.props.disabled))
 assert.equal(app(language,{config:false}).render(),null)
 console.log('PASS actual tracking preference UI locale',language,'defaultoff/save/reopen/reject/failure/privacy signal/no config; runtime mocked, no external tracking')
}
