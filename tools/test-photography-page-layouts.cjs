const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),frontend=path.join(root,'snowland-frontend'),req=Module.createRequire(path.join(frontend,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const definitions=JSON.parse(fs.readFileSync(path.join(root,'snowland/Client/fixtures/photography_page_defaults.json'),'utf8'))
const crypto=require('node:crypto')
// Rendered from the original layouts at 65a90808, with only the approved
// booking/FAQ destination fixes normalized. These also run without tmp files.
const layoutHashes={winter:'8c0733269ceb941261aaa8b8862374cc729d13de53cd244a8335f8326045c874',summer:'26f13c63366bb4269729c773bd7b3da5b1867d23df120be9c3a7c38c3b5571b0'}
const canonical=html=>html.replace(/<([a-z0-9]+)((?:\s+[^\s=>]+(?:="[^"]*")?)*)>/gi,(_tag,name,attrs)=>'<'+name+(attrs?' '+(attrs.match(/[^\s=]+="[^"]*"|[^\s=]+/g)||[]).sort().join(' '):'')+'>')
function render(source,content){
  const link=({to,...props})=>React.createElement('a',{...props,href:to})
  const motion=tag=>({initial,animate,variants,transition,whileInView,viewport,...props})=>React.createElement(tag,props)
  const ctx=vm.createContext({exports:{},require:name=>{
    if(name==='react')return React
    if(name==='framer-motion')return{motion:{div:motion('div'),img:motion('img')},useReducedMotion:()=>true,useScroll:()=>({}),useTransform(){}}
    if(name==='react-router-dom')return{Link:link}
    if(name.endsWith('SiteLink'))return link
    if(name.endsWith('PhotographyContentGate'))return props=>props.children(content)
    if(name.includes('/components/'))return()=>null
    if(name.includes('/assets/'))return'/qa-about.jpg'
    throw Error(name)
  }})
  vm.runInContext(ts.transpileModule(source.replace('import.meta.env.BASE_URL','"/"'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText,ctx)
  return renderToStaticMarkup(React.createElement(ctx.exports.default))
}
for(const definition of definitions){
  const {season}=definition,name=season==='winter'?'Winter':'Summer'
  const source=fs.readFileSync(path.join(frontend,`src/pages/site/${name}PhotographyPage.jsx`),'utf8')
  const values=Object.fromEntries(definition.sections.flatMap(s=>s.fields.map(f=>[f.key,f.value])))
  const keys=[...source.matchAll(/c\("([^"]+)"\)/g)].map(m=>m[1])
  assert.equal(new Set(keys).size,Object.keys(values).length,'每個版型欄位必須有對應後台資料')
  assert.ok(keys.every(key=>key in values))
  const content={season,version:1,values},html=render(source,content)
  assert.equal(crypto.createHash('sha256').update(canonical(html)).digest('hex'),layoutHashes[season],'原版型、文案或樣式發生未核對的變更')
  const before=path.join(root,`tmp/${season}-photography-before-cms.jsx`)
  if(fs.existsSync(before)){
    const original=canonical(render(fs.readFileSync(before,'utf8')).replace(/href="#(?:booking-flow)?"/g,'href="/booking?service=photo"').replace(/href="\/course\/tomamu"/g,'href="/booking?service=ski"').replace(/<a([^>]*)>查看更多常見問題<\/a>/g,(_all,attrs)=>'<a'+attrs.replace('href="/booking?service=photo"','href="/faq"')+'>查看更多常見問題</a>')),actual=canonical(html)
    if(actual!==original){let i=0;while(actual[i]===original[i]&&i<Math.min(actual.length,original.length))i++;throw Error(`${season} layout changed at ${i}: original=${original.slice(i,i+100)} new=${actual.slice(i,i+100)}`)}
  }
  const image=definition.sections.flatMap(s=>s.fields).find(f=>f.kind==='image')
  const text=definition.sections.flatMap(s=>s.fields).find(f=>f.kind==='text'&&f.value.includes('NT$'))
  const updated=render(source,{...content,values:{...values,[image.key]:'https://example.test/qa-photo.jpg',[text.key]:'QA官網展示價格'}})
  assert.ok(updated.includes('src="https://example.test/qa-photo.jpg"'));assert.ok(!updated.includes('/https://'))
  assert.ok(updated.includes('QA官網展示價格'));assert.ok(!source.includes('href="#"'))
  console.log(`PASS ${season}: ${keys.length} backend bindings, original layout/copy parity, dynamic image/price and real booking CTA`)
}
