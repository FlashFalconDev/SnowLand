const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/components/site/PopularCourses.jsx'),'utf8')
const defaults=JSON.parse(fs.readFileSync(path.join(__dirname,'../snowland/Client/fixtures/homepage_course_defaults.json'),'utf8'))
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const c of React.Children.toArray(node.props?.children)){const hit=find(c,p);if(hit)return hit}return null}
function setup(extra={}){
  let state={},retry=0
  const ctx=vm.createContext({exports:{},require(name){
    if(name==='react')return{...React,useState:()=>[state,v=>state=typeof v==='function'?v(state):v]}
    if(name==='./SiteLink')return p=>React.createElement('a',{href:'/snowland'+p.to,className:p.className},p.children)
    if(name.includes('useSiteContent'))return{useSiteContent:(key,options)=>{assert.equal(key,'homepage.courses');assert.equal(options.contentType,'page');return{items:defaults.map((r,i)=>({...r,id:i+1})),isLoading:false,error:null,refetch(){retry++},...extra}}}
    throw Error(name)
  }})
  const compiled=ts.transpileModule(source,{reportDiagnostics:true,compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}})
  assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0,'actual JSX must compile')
  vm.runInContext(compiled.outputText,ctx)
  return{render:()=>ctx.exports.default(),retry:()=>retry}
}
const app=setup(),html=renderToStaticMarkup(app.render())
assert.equal((html.match(/<article/g)||[]).length,4)
assert.ok(html.includes('lg:grid-cols-2'));assert.ok(html.indexOf('星野 TOMAMU')<html.indexOf('留壽都 RUSUTSU'))
assert.ok(html.includes('href="/snowland/course/rusutsu"'));assert.ok(html.includes('Rupow'))
assert.ok(html.includes('min-h-11'));assert.ok(!html.includes('undefined'))
const expand=find(app.render(),n=>n.type==='button'&&n.props['aria-expanded']===false)
expand.props.onClick();assert.ok(renderToStaticMarkup(app.render()).includes('aria-expanded="true"'))
assert.ok(renderToStaticMarkup(setup({items:[],isLoading:true}).render()).includes('正在載入熱門課程'))
assert.ok(renderToStaticMarkup(setup({items:[]}).render()).includes('目前尚無公開熱門課程'))
const failed=setup({items:[],error:Error('QA')});find(failed.render(),n=>n.type==='button'&&n.props.children==='重試熱門課程').props.onClick();assert.equal(failed.retry(),1)
const custom=renderToStaticMarkup(setup({items:[{id:99,title:'QA同名',summary:'QA更新',subtitle:'QA預約',image_url:'/vite.svg',link_url:'/booking'}]}).render())
assert.ok(custom.includes('QA更新'));assert.ok(custom.includes('QA預約'));assert.ok(custom.includes('href="/snowland/booking"'));assert.ok(!custom.includes('留壽都'))
const noImage=renderToStaticMarkup(setup({items:[{id:99,title:'QA無圖',summary:'QA文字',link_url:'/booking'}]}).render())
assert.ok(!noImage.includes('<img'))
console.log('PASS homepage CMS cards: customer four-card order/copy/links, two columns, mutable fields, expansion, 44px, loading/error/retry/empty/no-image')
