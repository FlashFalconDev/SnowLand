const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/admin/pages/ContactInboxPage.tsx'),'utf8')
const row={id:7,name:'QA訪客',email:'qa@example.test',phone:'',subject:'QA詢問',message:'原文不可改',status:'new',admin_note:'',notification_status:'off',created_at:'2026-10-18T14:00:00Z'}
function find(n,p){if(!n||typeof n!=='object')return null;if(p(n))return n;for(const c of React.Children.toArray(n.props?.children)){const x=find(c,p);if(x)return x}return null}
function setup({fail=false,error=false,loading=false,rows=[row]}={}){
  const states=[1,'','','',row,'new','','',''],calls=[],invalidations=[];let i=0,retries=0
  const ctx=vm.createContext({React,exports:{},require(name){
    if(name==='react')return{...React,useState:initial=>{const x=i++;if(!(x in states))states[x]=initial;return[states[x],v=>states[x]=typeof v==='function'?v(states[x]):v]},useEffect(){},useRef:()=>({current:null})}
    if(name==='@tanstack/react-query')return{useQuery:()=>({data:{list:rows,total:rows.length},isLoading:loading,error:error?Error('QA'):null,refetch(){retries++}}),useQueryClient:()=>({invalidateQueries:v=>invalidations.push(v)}),useMutation:options=>({isPending:false,mutate:async vars=>{try{const result=await options.mutationFn(vars);options.onSuccess?.(result)}catch(e){options.onError?.(e)}}})}
    if(name==='../api/auth')return{fetchAdminMe(){}}
    if(name==='../../components/site/ContactForm')return{contactError:()=> 'QA儲存失敗，資料已保留'}
    if(name==='../api/contactInbox')return{fetchContactInbox(){},fetchContactSettings(){},updateContactSettings(){},retryContactNotification:async id=>calls.push({retry:id}),updateContactMessage:async(id,data)=>{calls.push({id,data});if(fail)throw Error('QA');return{...row,...data}}}
    throw Error(name)
  }})
  const compiled=ts.transpileModule(source,{reportDiagnostics:true,compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}})
  assert.equal(compiled.diagnostics.length,0);vm.runInContext(compiled.outputText,ctx)
  return{states,calls,invalidations,render:()=>{i=0;return ctx.exports.default()},retries:()=>retries}
}
;(async()=>{
  const app=setup();let tree=app.render()
  const searchForm=find(tree,n=>n.type==='form'&&String(n.props.className).includes('sm:flex-row'))
  searchForm.props.onSubmit({preventDefault(){}})
  assert.equal(app.retries(),1,'Searching unchanged filters must reload new incoming messages')
  app.states[2]='QA新條件'
  find(app.render(),n=>n.type==='form'&&String(n.props.className).includes('sm:flex-row')).props.onSubmit({preventDefault(){}})
  assert.equal(app.retries(),1,'Changed query key reloads without an extra request for the old filters')
  assert.equal(app.states[3],'QA新條件')
  app.states[4]=row
  assert.equal(find(tree,n=>n.type==='input'&&n.props['aria-label']==='搜尋聯絡留言').props.disabled,false)
  find(tree,n=>n.type==='textarea').props.onChange({target:{value:'QA未儲存'}})
  tree=app.render();assert.equal(find(tree,n=>n.type==='input'&&n.props['aria-label']==='搜尋聯絡留言').props.disabled,true)
  assert.ok(find(tree,n=>n.type==='button'&&n.props.children==='取消未儲存的修改'))
  const form=find(tree,n=>n.type==='form'&&n.props.className==='mt-5 space-y-4')
  form.props.onSubmit({preventDefault(){}});await new Promise(setImmediate)
  assert.equal(app.calls[0].id,7);assert.equal(app.calls[0].data.admin_note,'QA未儲存');assert.equal(app.states[4].admin_note,'QA未儲存');assert.equal(app.invalidations.length,1)
  assert.ok(find(app.render(),n=>n.props.role==='status'&&n.props.children==='處理狀態與備註已儲存'))
  const rejected=setup({fail:true});rejected.states[6]='QA錯誤保留'
  find(rejected.render(),n=>n.type==='form'&&n.props.className==='mt-5 space-y-4').props.onSubmit({preventDefault(){}});await new Promise(setImmediate)
  assert.equal(rejected.states[4].id,7);assert.equal(rejected.states[6],'QA錯誤保留');assert.ok(rejected.states[7].includes('儲存失敗'))
  const failed=setup({error:true});find(failed.render(),n=>n.type==='button'&&n.props.children==='重新載入留言').props.onClick();assert.equal(failed.retries(),1)
  const routes=fs.readFileSync(path.join(root,'src/admin/AdminRoutes.tsx'),'utf8');assert.ok(routes.includes('permission="contact_inbox"'))
  console.log('PASS actual inbox handlers: retained failed draft, typed update/refresh/success, unsaved guard/cancel, list retry and dedicated route permission')
})().catch(e=>{console.error(e);process.exit(1)})
