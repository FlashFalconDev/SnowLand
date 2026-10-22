const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),frontend=path.join(root,'snowland-frontend'),req=Module.createRequire(path.join(frontend,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const definitions=JSON.parse(fs.readFileSync(path.join(root,'snowland/Client/fixtures/photography_page_defaults.json'),'utf8'))
const crypto=require('node:crypto')
// Reviewed layout snapshots include localized controls,44px targets, independent
// carousel dots and the opaque compact header. CMS prose and prices stay original.
const layoutHashes={winter:'ac7deb1ccc77522aa83fea5604353cec43407faea4e8e2bf1e1b5154f63ceeb3',summer:'4f8f2a4f1d5edba09aefc1d4a8649aefe053a995faf8c43dd443030151f2d558'}
const canonical=html=>html.replace(/<([a-z0-9]+)((?:\s+[^\s=>]+(?:="[^"]*")?)*)>/gi,(_tag,name,attrs)=>'<'+name+(attrs?' '+(attrs.match(/[^\s=]+="[^"]*"|[^\s=]+/g)||[]).sort().join(' '):'')+'>')
function render(source,content,faqIndex=0){
  let stateIndex=0
  const hooks={...React,useState(value){const [state,setState]=React.useState(value);return[stateIndex++===(content.season==='winter'?6:5)?faqIndex:state,setState]}}
  const link=({to,...props})=>React.createElement('a',{...props,href:to})
  const motion=tag=>({initial,animate,variants,transition,whileInView,viewport,...props})=>React.createElement(tag,props)
  const ctx=vm.createContext({exports:{},require:name=>{
    if(name==='react')return hooks
    if(name.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(React)
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
  const allFaqHtml=html+render(source,content,1)+render(source,content,2)
  for(const field of definition.sections.flatMap(section=>section.fields).filter(field=>field.kind==='text'&&field.value)){
    const encoded=renderToStaticMarkup(React.createElement('span',null,field.value)).slice(6,-7)
    assert.ok(allFaqHtml.includes(encoded),`CMS文字不可因操作介面修改而遺失：${field.key}`)
  }
  assert.equal(crypto.createHash('sha256').update(canonical(html)).digest('hex'),layoutHashes[season],'原版型、文案或樣式發生未核對的變更')
  const image=definition.sections.flatMap(s=>s.fields).find(f=>f.kind==='image')
  const text=definition.sections.flatMap(s=>s.fields).find(f=>f.kind==='text'&&f.value.includes('NT$'))
  const updated=render(source,{...content,values:{...values,[image.key]:'https://example.test/qa-photo.jpg',[text.key]:'QA官網展示價格'}})
  assert.ok(updated.includes('src="https://example.test/qa-photo.jpg"'));assert.ok(!updated.includes('/https://'))
  assert.ok(updated.includes('QA官網展示價格'));assert.ok(!source.includes('href="#"'))
  console.log(`PASS ${season}: ${keys.length} backend bindings, reviewed layout snapshot/all original CMS copy across3FAQstates, dynamic image/price and canonical booking CTA`)
}
