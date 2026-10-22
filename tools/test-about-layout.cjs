const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm'),crypto=require('node:crypto')
const root=path.resolve(__dirname,'..'),front=path.join(root,'snowland-frontend'),req=Module.createRequire(path.join(front,'package.json'))
const React=req('react'),ts=req('typescript'),renderToStaticMarkup=req('react-dom/server').renderToStaticMarkup
const row=JSON.parse(fs.readFileSync(path.join(root,'snowland/Client/fixtures/site_content_defaults.json'),'utf8')).find(r=>r.location_key==='about.snowland')
function render(source,page){
 const motion=tag=>({initial,animate,variants,transition,whileInView,viewport,...props})=>React.createElement(tag,props)
 const ctx=vm.createContext({exports:{},require:name=>{
  if(name==='react')return React
  if(name.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(React,'zh-Hant')
  if(name==='framer-motion')return{motion:new Proxy({},{get:(_t,tag)=>motion(tag)}),useReducedMotion:()=>true,useScroll:()=>({}),useTransform(){}}
  if(name.includes('useSiteContent'))return{}
  return{__esModule:true,default:()=>null}
 }})
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText+'\nexports.Layout=LegacyContentLayout;',ctx)
 return renderToStaticMarkup(React.createElement(ctx.exports.Layout,{pageKey:'about',page,guidesArticles:[]}))
}
const source=fs.readFileSync(path.join(front,'src/pages/site/LegacyContentPage.jsx'),'utf8')
const schemaFile=path.join(root,'snowland/Client/fixtures/about_page_defaults.json')
const schema=fs.existsSync(schemaFile)?JSON.parse(fs.readFileSync(schemaFile,'utf8')):{sections:[{fields:[{key:'about_001',kind:'text',value:'原固定文字'}]}]}
const values=Object.fromEntries(schema.sections.flatMap(s=>s.fields.map(f=>[f.key,f.value])))
if(fs.existsSync(schemaFile))assert.deepEqual([...new Set([...source.matchAll(/c\("(about_\d+)"\)/g)].map(match=>match[1]))].sort(),Object.keys(values).sort(),'每個原版型欄位都必須有實際顯示位置')
const page={...row.metadata.page,layout:{version:1,page_key:'about',values}}
const html=render(source,page),hash=crypto.createHash('sha256').update(html).digest('hex')
if(process.argv.includes('--baseline')){console.log(hash);process.exit(0)}
assert.equal(hash,'4dbeb557c35d1a72d546326e73446beff9ecd3d16bed35e2944787348798f17b','與改動前實際原頁的完整HTML、樣式及文案不符')
const text=schema.sections.flatMap(s=>s.fields).find(f=>f.kind==='text')
assert.ok(render(source,{...page,layout:{...page.layout,values:{...values,[text.key]:'QA後台學校介紹'}}}).includes('QA後台學校介紹'),'學校介紹的固定原稿必須讀後台，不能只接到不顯示的舊blocks')
const before=path.join(root,'tmp/about-before-cms.jsx')
if(fs.existsSync(before))assert.equal(html,render(fs.readFileSync(before,'utf8'),row.metadata.page),'原頁文字、照片、樣式與段落分隔必須完整保留')
const image=schema.sections.flatMap(s=>s.fields).find(f=>f.kind==='image')
assert.ok(image)
assert.ok(render(source,{...page,layout:{...page.layout,values:{...values,[image.key]:'/vite.svg'}}}).includes('src="/vite.svg"'))
console.log(`PASS original about layout parity, ${Object.keys(values).length} editable values and real text/image bindings; baseline ${hash}`)
