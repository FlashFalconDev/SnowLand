const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const compile=source=>ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
const source=fs.readFileSync(path.join(root,'src/admin/components/ReviewPlacementFields.tsx'),'utf8')
function findAll(node,predicate,result=[]){if(!node||typeof node!=='object')return result;if(predicate(node))result.push(node);for(const child of React.Children.toArray(node.props?.children))findAll(child,predicate,result);return result}
function harness({loading=false,error=false,coaches=[{id:1,name:'A教練',website_enabled:true},{id:2,name:'B教練',website_enabled:false}]}={}){
  let retries=0
  const ctx=vm.createContext({React,exports:{},require:name=>{
    if(name==='react')return React
    if(name==='@tanstack/react-query')return{useQuery:()=>({data:coaches,isLoading:loading,error:error?new Error('QA'):null,refetch(){retries++}})}
    if(name==='../api/siteContent')return{fetchReviewCoachChoices(){}}
    throw new Error(name)
  }})
  vm.runInContext(compile(source),ctx)
  return{render:(metadata,onChange)=>ctx.exports.default({metadata,onChange}),retries:()=>retries}
}
const ui=harness();let metadata={coach_ids:[1],show_on_homepage:false,keep:'QA原設定'}
const render=()=>ui.render(metadata,next=>metadata=next)
let inputs=findAll(render(),node=>node.type==='input')
assert.equal(inputs.length,3);assert.equal(inputs[0].props.checked,false);assert.equal(inputs[1].props.checked,true)
inputs[2].props.onChange({target:{checked:true}});assert.deepEqual(Array.from(metadata.coach_ids),[1,2]);assert.equal(metadata.show_on_homepage,false)
findAll(render(),node=>node.type==='input')[0].props.onChange({target:{checked:true}});assert.equal(metadata.show_on_homepage,true);assert.equal(metadata.keep,'QA原設定')
findAll(render(),node=>node.type==='input')[1].props.onChange({target:{checked:false}});assert.deepEqual(Array.from(metadata.coach_ids),[2])
assert.ok(renderToStaticMarkup(render()).includes('官網已下架，仍可保留歸檔'))
metadata={coach_ids:[1,99],keep:'keep'}
findAll(render(),node=>node.type==='button'&&node.props.children==='移除已不存在的教練歸檔')[0].props.onClick();assert.deepEqual(Array.from(metadata.coach_ids),[1]);assert.equal(metadata.keep,'keep')
assert.ok(renderToStaticMarkup(harness({loading:true}).render({},()=>{})).includes('正在載入'))
assert.ok(renderToStaticMarkup(harness({coaches:[]}).render({},()=>{})).includes('尚無教練資料'))
const failed=harness({error:true}),retry=findAll(failed.render({},()=>{}),node=>node.type==='button'&&node.props.children==='重試教練清單')[0]
retry.props.onClick();assert.equal(failed.retries(),1)
const home=fs.readFileSync(path.join(root,'src/pages/site/HomePage.jsx'),'utf8')
assert.ok(!home.includes('staticReviews'));assert.ok(!home.includes('5.0 ⭐⭐⭐⭐⭐ 176'))
assert.ok(home.includes('重試學員評價'));assert.ok(home.includes('目前尚無公開評價'))
function homepage(status,rows=[]){
  const states=[false,null,rows,status,0],effects=[];let cursor=0
  const hooks={...React,useMemo:fn=>fn(),useEffect:(fn,deps)=>effects.push({fn,deps}),useRef:()=>({current:null}),useState:initial=>{const i=cursor++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial;return[states[i],value=>states[i]=typeof value==='function'?value(states[i]):value]}}
  const ctx=vm.createContext({exports:{},require:name=>{
    if(name==='react')return hooks
    if(name==='react-router-dom')return{Link:()=>null}
    if(name==='framer-motion')return{useScroll:()=>({scrollYProgress:0}),useTransform:()=>0,motion:new Proxy({},{get:()=>props=>React.createElement('div',null,props.children)})}
    if(name==='../../api/websiteCoaches')return{useWebsiteCoachCards:()=>({coaches:[],isLoading:false,error:false,retry(){}})}
    if(name==='../../api/booking')return{fetchSiteContent:async()=>[]}
    if(name==='../../hooks/useSiteContent')return{useSiteContent:()=>({items:[],isLoading:false,error:null})}
    if(name==='../../components/site/HomepagePresentation')return{__esModule:true,default:()=>null,ContentState:()=>null,HomepageCoachHeading:()=>null,HomepageContactBanner:()=>null}
    if(name.startsWith('../../components/'))return()=>null
    if(name.startsWith('../../assets/'))return'/qa-asset.jpg'
    throw new Error(name)
  }})
  vm.runInContext(compile(home),ctx)
  return{states,effects,render:()=>{cursor=0;effects.length=0;return ctx.exports.default()}}
}
;(async()=>{
  assert.ok(renderToStaticMarkup(homepage('loading').render()).includes('正在載入學員評價'))
  assert.ok(renderToStaticMarkup(homepage('ready').render()).includes('目前尚無公開評價'))
  const selected=renderToStaticMarkup(homepage('ready',[{title:'QA唯一評價',summary:'QA摘要',metadata:{}}]).render())
  assert.ok(selected.includes('QA唯一評價'));assert.ok(!selected.includes('Chingyee Lee'))
  assert.ok(!selected.includes('Image Holder'),'沒有照片的真實評論不可顯示設計佔位圖')
  assert.ok(!selected.includes('has-media'),'純文字評論不可留下空的媒體區')
  const withPhoto=renderToStaticMarkup(homepage('ready',[{title:'QA照片評價',summary:'QA摘要',image_url:'/qa-review.jpg',metadata:{}}]).render())
  assert.ok(withPhoto.includes('src="/qa-review.jpg"'));assert.ok(withPhoto.includes('has-media'))
  const broken=homepage('error'),tree=broken.render()
  const retry=findAll(tree,node=>node.type==='button'&&node.props.children==='重試學員評價')[0]
  assert.ok(retry);retry.props.onClick();assert.equal(broken.states[4],1)
  broken.render()
  const fetchEffect=broken.effects.find(effect=>effect.fn.toString().includes('fetchSiteContent'))
  assert.equal(fetchEffect.deps[0],1);fetchEffect.fn();await new Promise(setImmediate)
  assert.equal(broken.states[3],'ready');assert.equal(broken.states[2].length,0)
  console.log('PASS actual review placement controls and homepage: independent switch/multi-coach, stale/disabled labels, retained metadata, real loading/error/empty/render/retry effect, no static fallback')
})().catch(error=>{console.error(error);process.exit(1)})
