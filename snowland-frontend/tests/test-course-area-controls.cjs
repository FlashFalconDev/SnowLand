const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const defaults=JSON.parse(fs.readFileSync(path.join(__dirname,'../../snowland/Client/fixtures/course_area_defaults.json'),'utf8'))
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const c of React.Children.toArray(node.props?.children)){const hit=find(c,p);if(hit)return hit}return null}
function load(file,imports){const ctx=vm.createContext({exports:{},require:imports});vm.runInContext(ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,ctx);return ctx.exports.default}
function setup(areas={},resorts={},slug='tomamu-area',language='zh-Hant'){
 let retries=0
 const Component=load('src/components/site/CourseAreaPage.jsx',name=>{
   if(name==='react')return React
   if(name.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(React,language)
   if(name==='react-router-dom')return{useParams:()=>({resort:slug})}
   if(name==='./SiteLink')return p=>React.createElement('a',{href:'/snowland'+p.to},p.children)
   if(name==='./ResortGrid')return p=>React.createElement('div',null,p.resorts.map(r=>React.createElement('a',{key:r.slug,href:'/snowland'+r.route},r.nameChinese)))
   if(name==='./HokkaidoMap')return p=>React.createElement('div',{'data-map-slugs':p.resorts.map(r=>r.slug).join(',')})
   if(name.includes('useSiteContent'))return{siteContentToResort:r=>({slug:r.external_id,nameChinese:r.title,route:'/course/'+r.external_id}),useSiteContent:key=>({items:key==='course.areas'?defaults:[{external_id:'tomamu',title:'星野'},{external_id:'sahoro',title:'佐幌'},{external_id:'teine',title:'手稻'}],isLoading:false,error:null,refetch(){retries++},...(key==='course.areas'?areas:resorts)})}
   if(name==='./SiteHeader'||name==='./SiteFooter')return()=>null
   throw Error(name)
 })
 return{render:()=>Component(),retries:()=>retries}
}
let app=setup(),html=renderToStaticMarkup(app.render())
for(const language of ['en','ja']){
 const local=setup({}, {}, 'tomamu-area',language),markup=renderToStaticMarkup(local.render())
 assert.ok(markup.includes(language==='en'?'Campus resort list':'校区のスキー場一覧'))
 assert.ok(markup.includes('星野校區')&&markup.includes('/snowland/course/tomamu'))
 const failed=setup({error:Error('QA')},{},'tomamu-area',language);find(failed.render(),n=>n.type==='button').props.onClick();assert.equal(failed.retries(),2)
 assert.ok(renderToStaticMarkup(setup({items:[]},{},'missing',language).render()).includes(language==='en'?'This campus is not open yet':'この校区はまだ公開されていません'))
}
assert.ok(html.includes('星野校區'));assert.ok(html.includes('/snowland/course/tomamu'));assert.ok(html.includes('佐幌'));assert.ok(!html.includes('手稻'));assert.ok(html.includes('data-map-slugs="tomamu,sahoro"'))
assert.ok(renderToStaticMarkup(setup({isLoading:true}).render()).includes('正在載入校區雪場'))
assert.ok(renderToStaticMarkup(setup({items:[]}).render()).includes('此校區尚未開放'))
assert.ok(renderToStaticMarkup(setup({}, {items:[]}).render()).includes('目前沒有已發布的雪場'))
app=setup({error:Error('QA')});find(app.render(),n=>n.type==='button'&&n.props.children==='重新載入').props.onClick();assert.equal(app.retries(),2)
app=setup({items:[{external_id:'custom-area',title:'新增自訂校區',metadata:{resort_slugs:['teine','tomamu']}}]}, {},'custom-area');html=renderToStaticMarkup(app.render());assert.ok(html.includes('新增自訂校區'));assert.ok(html.indexOf('手稻')<html.indexOf('星野'))
let metadata={resort_slugs:['tomamu'],preserve:'原資料'}
// TSX uses the project's automatic JSX transform in production; provide React for this standalone harness.
const fieldsSource=fs.readFileSync(path.join(root,'src/admin/components/CourseAreaFields.tsx'),'utf8')
const context=vm.createContext({React,exports:{}});vm.runInContext(ts.transpileModule(fieldsSource,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,context)
const render=()=>context.exports.default({metadata,options:[{value:'tomamu',label:'星野'},{value:'teine',label:'手稻'}],onChange:m=>metadata=m})
find(render(),n=>n.type==='input'&&n.props.checked===false).props.onChange({target:{checked:true}})
assert.deepEqual(Array.from(metadata.resort_slugs),['tomamu','teine']);assert.equal(metadata.preserve,'原資料')
find(render(),n=>n.type==='input'&&n.props.checked===true).props.onChange({target:{checked:false}})
assert.deepEqual(Array.from(metadata.resort_slugs),['teine']);assert.ok(renderToStaticMarkup(render()).includes('不會改動營運校區'))
const routes=fs.readFileSync(path.join(root,'src/pages/site/SiteRoutes.tsx'),'utf8')
const wrapper=routes.slice(routes.indexOf('function ResortOrAreaPage()'),routes.indexOf('export default function SiteRoutes'))
let routeSlug='custom-area';const routeContext=vm.createContext({React,useParams:()=>({resort:routeSlug}),CourseAreaPage:()=>null,ResortCoursePage:()=>null})
vm.runInContext(ts.transpileModule(wrapper,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,routeContext)
assert.equal(routeContext.ResortOrAreaPage().type,routeContext.CourseAreaPage);routeSlug='kamui';assert.equal(routeContext.ResortOrAreaPage().type,routeContext.ResortCoursePage)
console.log('PASS actual area page: source groups, original resort cards/map, dynamic custom route/order, missing/hidden/empty/loading/error retry; CMS checkbox edits preserve metadata and permissions')
