const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/components/site/SiteHeader.jsx'),'utf8')
const defaults=JSON.parse(fs.readFileSync(path.join(__dirname,'../../snowland/Client/fixtures/course_area_defaults.json'),'utf8'))
function findAll(node,p,result=[]){if(!node||typeof node!=='object')return result;if(p(node))result.push(node);for(const c of React.Children.toArray(node.props?.children))findAll(c,p,result);return result}
function setup(extra={}){
 const state=[];let index=0,retries=0
 const react={...React,createContext:defaultValue=>({defaultValue}),useContext:context=>context.defaultValue,useEffect(){},useRef:()=>({current:null}),useState:initial=>{const i=index++;if(!(i in state))state[i]=typeof initial==='function'?initial():initial;return[state[i],v=>state[i]=typeof v==='function'?v(state[i]):v]}}
 const actualModules={}
 function loadLocaleModule(name){
   if(actualModules[name])return actualModules[name]
   const moduleContext=vm.createContext({exports:{},require:dependency=>dependency==='react'?react:dependency==='react-router-dom'?req('react-router-dom'):loadLocaleModule(dependency.includes('SiteLocale')?'contexts/SiteLocale.jsx':'utils/siteLocale.ts')})
   vm.runInContext(ts.transpileModule(fs.readFileSync(path.join(root,'src',name),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,moduleContext)
   return actualModules[name]=moduleContext.exports
 }
 const motion=new Proxy({},{get:(_,tag)=>p=>React.createElement(tag,{},p.children)})
 const ctx=vm.createContext({exports:{},window:{scrollY:0},require(name){
   if(name==='react')return react
   if(name.includes('useClient'))return{useClientInfo:()=>({clientCode:'snowland',clientName:'SnowLand',clientInfo:null})}
   if(name.includes('contexts/SiteLocale'))return loadLocaleModule('contexts/SiteLocale.jsx')
   if(name==='./SiteLanguageSelect')return loadLocaleModule('components/site/SiteLanguageSelect.jsx')
   if(name==='react-router-dom')return{useLocation:()=>({pathname:'/snowland/contact'})}
   if(name==='./SiteLink')return p=>React.createElement('a',{href:'/snowland'+p.to,className:p.className,onClick:p.onClick},p.children)
   if(name==='framer-motion')return{motion,AnimatePresence:p=>React.createElement(React.Fragment,null,p.children)}
   if(name.includes('logo-white'))return'logo.png'
   if(name.includes('assetPaths'))return{homepageAssetBase:'/assets'}
   if(name.includes('navigationLinks'))return{faqLink:'/faq'}
   if(name.includes('useSiteContent'))return{useSiteContent:key=>{assert.equal(key,'course.areas');return{items:defaults,isLoading:false,error:null,refetch(){retries++},...extra}}}
   throw Error(name)
 }})
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,ctx)
 return{render:()=>{index=0;return ctx.exports.default({})},retries:()=>retries}
}
let app=setup(),tree=app.render(),html=renderToStaticMarkup(tree)
for(const row of defaults){assert.ok(html.includes('/snowland/course/'+row.external_id));assert.ok(html.includes(row.title.replaceAll('&','&amp;')))}
const trigger=findAll(tree,n=>n.type==='button'&&Array.isArray(n.props.children)&&n.props.children[0]==='滑雪課程')[0]
assert.ok(trigger);trigger.props.onClick();assert.equal(findAll(app.render(),n=>n.type==='button'&&n.props['aria-expanded']===true).length,1)
const open=findAll(app.render(),n=>n.type==='button'&&n.props['aria-label']==='開啟選單')[0];open.props.onClick()
tree=app.render();const mobileTrigger=findAll(tree,n=>n.type==='button'&&Array.isArray(n.props.children)&&n.props.children[0]==='滑雪課程').at(-1);mobileTrigger.props.onClick()
html=renderToStaticMarkup(app.render());for(const row of defaults)assert.equal(html.split('/snowland/course/'+row.external_id).length-1,2,'Desktop and expanded mobile share same data')
const mobileLink=findAll(app.render(),n=>n.type&&typeof n.type==='function'&&n.props.to==='/course/furano-area').at(-1);mobileLink.props.onClick();assert.ok(!renderToStaticMarkup(app.render()).includes('MENU'))
app=setup({items:[{external_id:'own-area',title:'自訂區'}]});html=renderToStaticMarkup(app.render());assert.ok(html.includes('自訂區'));assert.ok(!html.includes('星野校區'))
app=setup({items:[],error:Error('QA')});tree=app.render();findAll(tree,n=>n.type==='button'&&n.props.children==='校區載入失敗，點此重試')[0].props.onClick();assert.equal(app.retries(),1)
assert.ok(renderToStaticMarkup(setup({items:[],isLoading:true}).render()).includes('校區載入中'))
console.log('PASS actual desktop/mobile course menu: shared CMS groups, custom names/routes, open/close, retry/loading; no hardcoded area fallback')
