const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm'),crypto=require('node:crypto')
const root=path.resolve(__dirname,'..'),front=path.join(root,'snowland-frontend'),req=Module.createRequire(path.join(front,'package.json')),React=req('react'),ts=req('typescript')
const original=JSON.parse(fs.readFileSync(path.join(root,'snowland/Client/fixtures/site_content_defaults.json'),'utf8')).find(r=>r.location_key==='about.join-us').metadata.page
function render(source,page){
 const motion=tag=>({initial,animate,variants,transition,whileInView,viewport,...props})=>React.createElement(tag,props)
 const ctx=vm.createContext({exports:{},require:name=>name==='react'?React:name==='framer-motion'?{motion:new Proxy({},{get:(_t,tag)=>motion(tag)}),useReducedMotion:()=>true,useScroll:()=>({}),useTransform(){}}:name.includes('useSiteContent')?{}:name.endsWith('SiteLink')?{__esModule:true,default:({to,...props})=>React.createElement('a',{...props,href:to})}:{__esModule:true,default:()=>null}})
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText+'\nexports.Layout=LegacyContentLayout;',ctx)
 return req('react-dom/server').renderToStaticMarkup(React.createElement(ctx.exports.Layout,{pageKey:'join-us',page,guidesArticles:[]}))
}
const source=fs.readFileSync(path.join(front,'src/pages/site/LegacyContentPage.jsx'),'utf8'),file=path.join(root,'snowland/Client/fixtures/join_page_defaults.json')
const schema=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{sections:[{fields:[{key:'join_001',kind:'text',value:'原稿'}]}]}
const values=Object.fromEntries(schema.sections.flatMap(s=>s.fields.map(f=>[f.key,f.value]))),page={...original,layout:{version:1,page_key:'join-us',values}}
const html=render(source,page),hash=crypto.createHash('sha256').update(html).digest('hex')
if(process.argv.includes('--baseline')){console.log(hash);process.exit(0)}
const text=schema.sections.flatMap(s=>s.fields).find(f=>f.kind==='text')
assert.ok(render(source,{...page,layout:{...page.layout,values:{...values,[text.key]:'QA招募原稿同步'}}}).includes('QA招募原稿同步'),'招募原稿不可繼續寫死，後台修改必須進入原頁')
// Deliberate fixes: CTA, carousel hit areas, and previously hidden mobile copy.
const normalize=html=>html.replace(/<(button|a)\b[^>]*>填寫履歷<\/\1>/g,'<apply-cta/>').replace(/<p data-recruit-notice="true"[^>]*>[\s\S]*?<\/p>/g,'').replace(/<button\b[^>]*aria-label="顯示第 [123] 張照片"[^>]*>[\s\S]*?<\/button>/g,'<carousel-control/>').replace('hidden lg:grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] items-start','grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] items-start').replace('hidden lg:block space-y-4 lg:sticky lg:top-28','space-y-4 lg:sticky lg:top-28')
assert.equal(crypto.createHash('sha256').update(normalize(html)).digest('hex'),'a03ab119d7a23dc8cd763c1ba6152006fbcf70ec7deb0e445e87ea9a6d6268f1','除已核對的互動與手機可見修正外，不可改原稿及排版')
assert.deepEqual([...new Set([...source.matchAll(/j\("([^"]+)"\)/g)].map(match=>match[1]))].sort(),Object.keys(values).sort())
assert.ok(render(source,{...page,layout:{...page.layout,values:{...values,join_034:'QA改語言標題',join_037:'QA改加分條件'}}}).includes('具備以上加分語言者優先錄取'),'修改可見標題或文字不可讓附註消失')
const before=path.join(root,'tmp/join-before-cms.jsx')
if(fs.existsSync(before)){
 const old=render(fs.readFileSync(before,'utf8'),original)
 assert.equal(crypto.createHash('sha256').update(old).digest('hex'),'2904d2e827c9bb907b862c5508d842836f321d293cbed66194ce5637d7c9d633')
 assert.equal(normalize(html),normalize(old),'除申請入口外，原版型、照片與原文案必須完整保留')
}
assert.ok(html.includes('href="https://www.surveycake.com/s/mYz4K"'))
assert.ok(html.includes('站內招募表單建置中'),'外部問卷不得假裝站內收件完成')
assert.ok(!html.includes('hidden lg:grid gap-12'),'不能再將招募條件與薪資福利全部藏在桌面專用容器中')
console.log(`PASS original recruitment layout parity and ${Object.keys(values).length} actual CMS bindings; normalized baseline ${crypto.createHash('sha256').update(normalize(html)).digest('hex')}`)
