const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/components/site/ContactForm.jsx'),'utf8')
const compiled=ts.transpileModule(source,{reportDiagnostics:true,compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}})
assert.equal(compiled.diagnostics.length,0)
const payload={name:'QA訪客',email:'qa@example.test',phone:'',subject:'QA主旨',message:'QA留言'}
function find(n,p){if(!n||typeof n!=='object')return null;if(p(n))return n;for(const c of React.Children.toArray(n.props?.children)){const x=find(c,p);if(x)return x}return null}
function setup({enabled=true,configFail=false,failures=0,deferred=false}={}){
  const states=[],refs=[],effects=[],calls=[];let i=0,r=0,sequence=0,resolvePost
  const api={get:async()=>{if(configFail)throw Error('QA');return{enabled}},post:async(url,data)=>{calls.push({url,data});if(failures-->0)throw{response:{data:{message:['QA請稍後再試']}}};if(deferred)await new Promise(resolve=>resolvePost=resolve);return{ok:true,reference:data.submission_id}}}
  const ctx=vm.createContext({exports:{},crypto:{randomUUID:()=>`00000000-0000-4000-8000-${String(++sequence).padStart(12,'0')}`},require(name){
    if(name==='react')return{...React,useState:initial=>{const x=i++;if(!(x in states))states[x]=initial;return[states[x],v=>states[x]=typeof v==='function'?v(states[x]):v]},useRef:initial=>{const x=r++;return refs[x]||(refs[x]={current:initial})},useEffect:fn=>effects.push(fn)}
    if(name==='../../api/axios')return api
    throw Error(name)
  }})
  vm.runInContext(compiled.outputText,ctx)
  return{states,calls,ctx,refs,effects,render:()=>{i=r=0;return ctx.exports.default({})},mount:async()=>{effects.shift()();await new Promise(setImmediate)},fill:()=>states[3]={...payload},resolve:()=>resolvePost()}
}
const event={preventDefault(){}}
;(async()=>{
  const app=setup();assert.ok(renderToStaticMarkup(app.render()).includes('表單載入中'))
  await app.mount();app.fill();let tree=app.render()
  assert.equal(find(tree,n=>n.type==='fieldset').props.disabled,false)
  await find(tree,n=>n.type==='form').props.onSubmit(event)
  assert.equal(app.calls.length,1);assert.equal(app.calls[0].url,'/contact/');assert.equal(app.calls[0].data.name,payload.name)
  tree=app.render();assert.ok(renderToStaticMarkup(tree).includes('已收到您的訊息'));assert.equal(find(tree,n=>n.type==='fieldset').props.disabled,true)
  let focused=false,scrolled=false
  app.refs[2].current={focus(){focused=true},scrollIntoView(options){scrolled=options.block==='center'}}
  app.effects.filter(fn=>fn.toString().includes('scrollIntoView')).at(-1)()
  assert.ok(focused&&scrolled,'successful receipt must be focused and scrolled into view')
  find(tree,n=>n.type==='button'&&n.props.children==='再送一則').props.onClick();assert.equal(app.states[6],'');assert.equal(app.states[3].name,'')
  const stopped=setup({enabled:false});stopped.render();await stopped.mount();stopped.fill();tree=stopped.render();assert.equal(find(tree,n=>n.type==='fieldset').props.disabled,true)
  await find(tree,n=>n.type==='form').props.onSubmit(event);assert.equal(stopped.calls.length,0);assert.ok(renderToStaticMarkup(tree).includes('聯絡表單尚未啟用'))
  const invalid=setup();invalid.render();await invalid.mount();await find(invalid.render(),n=>n.type==='form').props.onSubmit(event);assert.equal(invalid.calls.length,0);assert.ok(invalid.states[5].includes('請填寫'))
  const retry=setup({failures:1});retry.render();await retry.mount();retry.fill();await find(retry.render(),n=>n.type==='form').props.onSubmit(event)
  assert.equal(retry.states[3].message,payload.message);assert.ok(retry.states[5].includes('QA請稍後再試'));assert.equal(retry.states[6],'')
  await find(retry.render(),n=>n.type==='form').props.onSubmit(event);assert.equal(retry.calls[0].data.submission_id,retry.calls[1].data.submission_id)
  const twice=setup({deferred:true});twice.render();await twice.mount();twice.fill();const submit=find(twice.render(),n=>n.type==='form').props.onSubmit
  const first=submit(event);await submit(event);assert.equal(twice.calls.length,1);twice.resolve();await first
  const failure=setup({configFail:true});failure.render();await failure.mount();tree=failure.render();assert.ok(renderToStaticMarkup(tree).includes('表單狀態載入失敗'))
  find(tree,n=>n.type==='button'&&n.props.children==='重新載入表單').props.onClick();assert.equal(failure.states[2],1)
  assert.ok(app.ctx.exports.contactError({response:{status:429}}).includes('一分鐘'))
  assert.equal(app.ctx.exports.contactError({response:{data:'<html>debug'}}),'目前無法送出，資料已保留，請稍後再試。')
  console.log('PASS contact form actual handlers: disabled/loading/retry, required data, real receipt only, retained errors, same id retry, double click guard, reset and 429')
})().catch(e=>{console.error(e);process.exit(1)})
