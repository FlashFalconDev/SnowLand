const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript'),React=req('react')
const source=fs.readFileSync(path.join(root,'src/hooks/useAuth.ts'),'utf8'),ast=ts.createSourceFile('useAuth.ts',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TS)
const hook=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='useAuth')
const logout=hook.body.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(ast)==='logout'))
const checkAuth=hook.body.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(ast)==='checkAuth'))
function harness(response={ok:true,code:200},failure=false){
  const state={user:'original',error:'',busy:false},removed=[],stored=[],calls=[],location={href:'original-url',pathname:'/snowland/console/orders'}
  const ctx=vm.createContext({Headers,document:{cookie:'csrftoken=QA-local-only'},authRevision:{current:0},logoutPending:{current:false},window:{location},console:{error(){}},
    fetch:async(...args)=>{calls.push(args);if(failure)throw Error('QA unavailable');return{ok:response.ok,json:async()=>response}},
    localStorage:{getItem:key=>key==='client_code'?'snowland':null,removeItem:key=>removed.push(key),setItem:(...args)=>stored.push(args)},
    setUser:v=>state.user=v,setLoading:v=>state.loading=v,setLogoutError:v=>state.error=v,setLoggingOut:v=>state.busy=v})
  vm.runInContext(ts.transpileModule(checkAuth.getText(ast)+'\n'+logout.getText(ast)+';this.logout=logout;this.check=checkAuth',{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText,ctx)
  return{state,removed,stored,calls,location,ctx,run:target=>ctx.logout(target)}
}
;(async()=>{
  for(const [response,failure] of [[{ok:false,code:403},false],[{ok:true,code:500},false],[{ok:true},false],[{ok:true,code:200},true]]){
    const ui=harness(response,failure);await ui.run('/snowland/console')
    assert.equal(ui.state.user,'original','failed Console logout must retain state and expose retry, not claim success')
    assert.equal(ui.location.href,'original-url');assert.equal(ui.removed.length,0);assert.equal(ui.stored.length,0);assert.match(ui.state.error,/登出|重試/);assert.equal(ui.state.busy,false)
  }
  const good=harness();await good.run('/snowland/console');assert.equal(good.location.href,'/snowland/console');assert.equal(good.state.user,null);assert.deepEqual(good.removed,['user']);assert.equal(good.stored[0][0],'just_logged_out')
  assert.equal(good.calls[0][0],'/control/api/logout/');assert.equal(good.calls[0][1].method,'POST');assert.equal(good.calls[0][1].credentials,'include');assert.equal(good.calls[0][1].headers['X-CSRFToken'],'QA-local-only')
  const fallback=harness();await fallback.run();assert.equal(fallback.location.href,'/snowland')
  const busy=harness();let finish;busy.ctx.fetch=()=>new Promise(resolve=>finish=resolve)
  const first=busy.run();await busy.run();assert.equal(busy.state.busy,true);finish({ok:true,json:async()=>({code:200})});await first;assert.equal(busy.removed.length,1);assert.equal(busy.state.busy,false)
  const race=harness();let finishOld
  race.ctx.fetch=url=>url.includes('google-login')?new Promise(resolve=>finishOld=resolve):Promise.resolve({ok:true,json:async()=>({code:200})})
  const checking=race.ctx.check();await race.run('/snowland/console')
  finishOld({ok:true,json:async()=>({code:200,user:{email:'old@example.test'}})});await checking
  assert.equal(race.state.user,null,'old auth response must not restore a logged-out Console user')
  assert.equal(race.stored.filter(([key])=>key==='user').length,0)
  const fallbackRace=harness();let finishAdmin
  fallbackRace.ctx.fetch=url=>url.includes('google-login')?Promise.resolve({ok:false}):url.includes('/me/')?new Promise(resolve=>finishAdmin=resolve):Promise.resolve({ok:true,json:async()=>({code:200})})
  const fallbackChecking=fallbackRace.ctx.check();await new Promise(setImmediate);assert.equal(typeof finishAdmin,'function')
  await fallbackRace.run();finishAdmin({ok:true,json:async()=>({code:200,data:{email:'old-admin@example.test'}})});await fallbackChecking
  assert.equal(fallbackRace.state.user,null)
  const decoding=harness();let finishJson
  decoding.ctx.fetch=url=>Promise.resolve(url.includes('google-login')?{ok:true,json:()=>new Promise(resolve=>finishJson=resolve)}:{ok:true,json:async()=>({code:200})})
  const decoded=decoding.ctx.check();await new Promise(setImmediate);await decoding.run();finishJson({code:200,user:{email:'late-json@example.test'}});await decoded;assert.equal(decoding.state.user,null)
  const latest=harness(),responses=[]
  latest.ctx.fetch=()=>new Promise(resolve=>responses.push(resolve))
  const oldCheck=latest.ctx.check(),newCheck=latest.ctx.check()
  responses[1]({ok:true,json:async()=>({code:200,user:{email:'new@example.test'}})});await newCheck
  responses[0]({ok:true,json:async()=>({code:200,user:{email:'old@example.test'}})});await oldCheck
  assert.equal(latest.state.user.email,'new@example.test');assert.equal(latest.stored.filter(([key])=>key==='user').length,1)
  const unmounted=harness();let finishUnmounted
  unmounted.ctx.fetch=()=>new Promise(resolve=>finishUnmounted=resolve)
  const effect=hook.body.statements.find(n=>ts.isExpressionStatement(n)&&n.getText(ast).startsWith('useEffect('))
  unmounted.ctx.useEffect=fn=>unmounted.ctx.effect=fn
  vm.runInContext(ts.transpileModule(effect.getText(ast),{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText,unmounted.ctx)
  const cleanup=unmounted.ctx.effect();assert.equal(typeof cleanup,'function');cleanup()
  finishUnmounted({ok:true,json:async()=>({code:200,user:{email:'unmounted@example.test'}})});await new Promise(setImmediate)
  assert.equal(unmounted.state.user,'original');assert.equal(unmounted.stored.length,0)
  const layout=fs.readFileSync(path.join(root,'src/admin/layout/AdminLayout.tsx'),'utf8'),layoutAst=ts.createSourceFile('AdminLayout.tsx',layout,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
  const denied=layoutAst.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='NoManagerPermission')
  const ctx=vm.createContext({React,PRIMARY:'#8b5cf6',useEffect(){},window:{location:{hostname:'localhost'}}})
  vm.runInContext(ts.transpileModule(denied.getText(layoutAst),{compilerOptions:{jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText,ctx)
  const find=(n,p)=>{if(!n||typeof n!=='object')return null;if(p(n))return n;for(const child of React.Children.toArray(n.props?.children)){const found=find(child,p);if(found)return found}return null}
  const view=ctx.NoManagerPermission({user:{name:'QA'},onLogout(){},onRetry(){},basePath:'/snowland',errorCode:401,errorMsg:'QA',logoutError:'無法確認登出，請重試',loggingOut:false})
  assert.ok(find(view,n=>n.props?.role==='alert'),'failed automatic401 logout must show recovery instead of a permanent spinner')
  assert.ok(find(view,n=>n.type==='button'&&React.Children.toArray(n.props.children).includes('切換帳號')))
  const waiting=ctx.NoManagerPermission({user:{name:'QA'},onLogout(){},onRetry(){},basePath:'/snowland',errorCode:403,errorMsg:'QA',logoutError:'重試',loggingOut:true})
  const switchButton=find(waiting,n=>n.type==='button'&&React.Children.toArray(n.props.children).includes('登出中…'))
  assert.equal(switchButton.props.disabled,true);assert.equal(switchButton.props['aria-busy'],true);assert.match(switchButton.props.className,/min-h-11/)
  const buttons=[]
  function walk(n){if(ts.isJsxElement(n)&&n.openingElement.tagName.getText(layoutAst)==='button'&&n.openingElement.attributes.getText(layoutAst).includes('onClick={() => logout'))buttons.push(n);ts.forEachChild(n,walk)}
  walk(layoutAst);assert.equal(buttons.length,2)
  for(const button of buttons){
    const ui=vm.createContext({React,LogOut:()=>null,logout(){},basePath:'/snowland',loggingOut:true})
    vm.runInContext(ts.transpileModule('const button='+button.getText(layoutAst),{compilerOptions:{jsx:ts.JsxEmit.React}}).outputText+';this.result=button',ui)
    assert.equal(ui.result.props.disabled,true);assert.match(ui.result.props.className,/min-h-11/)
  }
  console.log('PASS actual Console logout: confirmed redirect only, failure/401 recovery, duplicate/busy; stale auth/admin fallback/JSON after logout, older checks and unmounted requests ignored')
})().catch(e=>{console.error(e);process.exitCode=1})
