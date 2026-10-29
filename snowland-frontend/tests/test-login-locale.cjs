const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/LoginPage.tsx'),'utf8')
for(const language of ['en','ja'])for(const returnTo of ['booking','console']){
 const locale=require('./helpers/site-locale-harness.cjs')(React,language),effects=[],stored=[],document={title:'SnowLand booking'}
 const context=vm.createContext({exports:{},React,URLSearchParams,document,localStorage:{setItem:(...args)=>stored.push(args)},require:name=>{
  if(name==='react')return{...React,useEffect:effect=>effects.push(effect)}
  if(name==='react-router-dom')return{Link:({to,children,...props})=>React.createElement('a',{...props,href:to},children),useLocation:()=>({pathname:'/snowland/booking',search:'?staff_link=QA-not-real'})}
  if(name.includes('contexts/SiteLocale'))return locale
  if(name==='@/hooks/useClient')return{useClientInfo:()=>({clientName:'QA 客戶名稱'})}
  if(name==='@/hooks/useSiteBasePath')return{useSiteLink:route=>'/snowland'+route}
  if(name==='lucide-react')return{Mountain:()=>null,Award:()=>null,CalendarCheck:()=>null,Bot:()=>null}
  if(name.endsWith('GoogleLoginButton'))return()=>React.createElement('span',null,'SDK placeholder')
  throw Error(name)
 }})
 vm.runInContext(ts.transpileModule(source,{fileName:'login.tsx',compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,context)
 const html=renderToStaticMarkup(React.createElement(context.exports.default,{returnTo}))
 const cleanups=effects.map(effect=>effect())
 assert.ok(html.includes('QA 客戶名稱'),'Tenant name must not be translated')
 assert.ok(html.includes(language==='en'?'Sign in or register with email':'メールアドレスでログイン・登録'))
 assert.ok(!html.includes('預約系統')&&!html.includes('彈性預約'))
 assert.ok(document.title.endsWith(language==='en'?'Sign in':'ログイン'))
 assert.ok(html.includes(`return_to=${returnTo}&amp;staff_link=QA-not-real`),'Return destination and staff link preserved')
 assert.equal(stored.length,returnTo==='booking'?1:0)
 if(stored.length)assert.deepEqual(stored[0],['pre_login_url','/snowland/booking?staff_link=QA-not-real'])
 cleanups.forEach(cleanup=>{if(typeof cleanup==='function')cleanup()})
 assert.equal(document.title,'SnowLand booking','Leaving login must not leave a stale sign-in title on booking/member screens')
}
console.log('PASS actual login page en/ja, tenant name, title, booking/console return route and staff-link preservation; Google SDK not exercised')
