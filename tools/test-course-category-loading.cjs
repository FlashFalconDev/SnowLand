const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const compile=source=>ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
const states=[],requests=[];let cursor=0,effect,previousDeps,cleanup
const ctx=vm.createContext({exports:{},require:name=>{
  if(name==='react')return{useState:v=>{const i=cursor++;if(!(i in states))states[i]=v;return[states[i],next=>states[i]=typeof next==='function'?next(states[i]):next]},useEffect:(fn,deps)=>{if(!previousDeps||deps.some((d,i)=>d!==previousDeps[i])){cleanup?.();effect=fn;previousDeps=deps}}}
  if(name==='@/api/booking')return{fetchCourseCategories:service=>new Promise((resolve,reject)=>requests.push({service,resolve,reject}))}
  throw Error(name)
}})
vm.runInContext(compile(fs.readFileSync(path.join(root,'src/hooks/useCourseCategories.ts'),'utf8')),ctx)
function render(service){cursor=0;const result=ctx.exports.default(service);if(effect){const run=effect;effect=null;cleanup=run()}return result}
const settle=()=>new Promise(resolve=>setImmediate(resolve))
;(async()=>{
  assert.equal(render('photo').status,'loading');assert.equal(requests[0].service,'photo')
  requests[0].resolve([]);await settle();assert.equal(render('photo').status,'ready');assert.equal(render('photo').categories.length,0)
  render('ski');assert.equal(requests[1].service,'ski');render('photo');assert.equal(requests[2].service,'photo')
  requests[2].resolve([{id:2,name:'攝影'}]);await settle();requests[1].resolve([{id:1,name:'滑雪'}]);await settle()
  assert.equal(render('photo').categories[0].id,2,'較晚回來的舊服務請求不得蓋掉新服務')
  render('photo').retry();render('photo');requests[3].reject(Error('QA offline'));await settle();assert.equal(render('photo').status,'error')
  render('photo').retry();render('photo');requests[4].resolve([{id:3,name:'新攝影'}]);await settle();assert.equal(render('photo').categories[0].id,3)
  assert.equal(render('').categories.length,0);assert.equal(render('').status,'ready')
  const locale=require('./helpers/site-locale-harness.cjs')(React)
  const ui=vm.createContext({React,exports:{},require:name=>name.includes('SiteLocale')?locale:req(name)});vm.runInContext(compile(fs.readFileSync(path.join(root,'src/components/booking/CourseCategoryOptions.tsx'),'utf8')),ui)
  const props={categories:[],selected:null,onSelect(){},onRetry(){}}
  const html=status=>renderToStaticMarkup(ui.exports.default({...props,status}))
  assert.ok(html('loading').includes('載入課程大類中'))
  assert.ok(html('ready').includes('目前尚未開放'));assert.ok(!html('ready').includes('載入課程大類中'))
  assert.ok(html('error').includes('重新載入課程'));assert.ok(html('error').includes('role="alert"'))
  let retried=false;ui.exports.default({...props,status:'error',onRetry:()=>retried=true}).props.children[1].props.onClick();assert.ok(retried)
  let selected;const chosen=ui.exports.default({...props,status:'ready',categories:[{id:3,name:'QA攝影'}],selected:3,onSelect:(...args)=>selected=args})
  chosen.props.children[0].props.onClick();assert.deepEqual(selected,[3,'QA攝影']);assert.equal(chosen.props.children[0].props['aria-pressed'],true)
  console.log('PASS actual course-category hook/UI: loading vs empty, error/retry, service-race guard, clear state and selection')
})().catch(e=>{console.error(e);process.exit(1)})
