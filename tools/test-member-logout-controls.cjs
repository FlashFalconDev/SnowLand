const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/pages/site/MembershipPage.jsx'),'utf8'),ast=ts.createSourceFile('MembershipPage.jsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JSX)
const component=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='MembershipPage')
const logout=component.body.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(ast)==='logout'))
const load=component.body.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(ast)==='loadMemberCenter'))
const rebook=component.body.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(ast)==='quickRebook'))
const requestJson=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='requestJson')
assert.ok(logout)
function harness(response={code:200},failure){
  const state={data:'original-member',status:'ready',notice:'',loggingOut:false},calls=[],navigation=[],removed=[],carts=[];let cleared=0
  const ctx=vm.createContext({Headers,JSON,document:{cookie:'csrftoken=QA-local-only'},URLSearchParams,useCallback:fn=>fn,memberLoadRevision:{current:0},location:{search:'?invite=QA%2Bonly'},basePath:'/snowland',logoutPending:{current:false},
    fetch:async(...args)=>{calls.push(args);if(failure)throw Error('QA network failure');return{ok:!response.httpStatus,status:response.httpStatus||200,json:async()=>response}},
    useBookingStore:{getState:()=>({replaceCart:cart=>carts.push(cart)})},qc:{clear:()=>cleared++},setData:v=>state.data=v,setStatus:v=>state.status=v,setNotice:v=>state.notice=v,setLoggingOut:v=>state.loggingOut=v,
    localStorage:{removeItem:key=>removed.push(key),setItem:(key,value)=>state.stored=value},navigate:url=>navigation.push(url)})
  vm.runInContext(requestJson.getText(ast)+'\n'+load.getText(ast)+'\n'+rebook.getText(ast)+'\n'+logout.getText(ast)+';this.logout=logout;this.load=loadMemberCenter;this.rebook=quickRebook',ctx)
  return{state,calls,navigation,removed,carts,get cleared(){return cleared},run:()=>ctx.logout(),ctx}
}
;(async()=>{
  for(const [response,failure] of [[{code:500},false],[{},false],[{code:403,httpStatus:403},false],[{code:200},true]]){
    const ui=harness(response,failure);await ui.run()
    assert.equal(ui.state.status,'ready','failed logout must not pretend the server session ended')
    assert.equal(ui.state.data,'original-member');assert.equal(ui.removed.length,0);assert.equal(ui.navigation.length,0);assert.equal(ui.cleared,0)
    assert.match(ui.state.notice,/登出|重試/);assert.equal(ui.state.loggingOut,false)
  }
  const ok=harness();await ok.run();assert.equal(ok.state.data,null);assert.equal(ok.state.status,'guest');assert.equal(ok.cleared,1)
  assert.deepEqual(ok.removed,['user']);assert.equal(ok.navigation[0],'/snowland/membership?invite=QA%2Bonly');assert.equal(ok.calls[0][0],'/control/api/logout/');assert.equal(ok.calls[0][1].method,'POST');assert.equal(ok.calls[0][1].headers.get('X-CSRFToken'),'QA-local-only');assert.equal(ok.calls[0][1].credentials,'include')
  const busy=harness();let finish;busy.ctx.requestJson=()=>new Promise(resolve=>finish=resolve)
  const first=busy.run();await busy.run();assert.equal(busy.state.loggingOut,true);finish({code:200});await first;assert.equal(busy.cleared,1);assert.equal(busy.state.loggingOut,false)
  for(const rejected of [false,true]){
    const race=harness();let resolve,reject
    race.ctx.requestJson=url=>url.includes('member-center')?new Promise((yes,no)=>{resolve=yes;reject=no}):Promise.resolve({code:200})
    const loading=race.ctx.load({silent:true});await race.run()
    if(rejected)reject(Object.assign(Error('old401'),{status:401}));else resolve({member:{name:'old member',email:'old@example.test'}})
    await loading
    assert.equal(race.state.status,'guest','old member response must not restore logged-out state')
    assert.equal(race.state.data,null);assert.equal(race.state.stored,undefined);assert.equal(race.state.notice,'')
  }
  for(const staleError of [false,true]){
    const latest=harness(),pending=[]
    latest.ctx.requestJson=()=>new Promise((resolve,reject)=>pending.push({resolve,reject}))
    const old=latest.ctx.load({silent:true}),fresh=latest.ctx.load({silent:true})
    pending[1].resolve({member:{name:'new',email:'new@example.test'}});await fresh
    if(staleError)pending[0].reject(Object.assign(Error('old401'),{status:401}));else pending[0].resolve({member:{name:'old'}})
    await old;assert.equal(latest.state.data.member.name,'new');assert.equal(latest.state.status,'ready');assert.match(latest.state.stored,/new@example/)
  }
  const unmounted=harness();let complete
  unmounted.ctx.requestJson=()=>new Promise(resolve=>complete=resolve)
  const loadEffect=component.body.statements.find(n=>ts.isExpressionStatement(n)&&n.getText(ast).startsWith('useEffect(')&&n.getText(ast).includes('loadMemberCenter'))
  unmounted.ctx.useEffect=fn=>unmounted.ctx.effect=fn
  vm.runInContext(loadEffect.getText(ast),unmounted.ctx)
  const cleanup=unmounted.ctx.effect();assert.equal(typeof cleanup,'function');cleanup()
  complete({member:{name:'old'}});await new Promise(setImmediate);assert.equal(unmounted.state.status,'loading');assert.equal(unmounted.state.stored,undefined)
  for(const failed of [false,true]){
    const race=harness();let resolve,reject
    race.ctx.requestJson=url=>url.includes('member-center')?new Promise((yes,no)=>{resolve=yes;reject=no}):Promise.resolve({code:200})
    const copying=race.ctx.rebook(42);await race.run()
    if(failed)reject(Error('old copy error'));else resolve({cart:[{students:[{name:'old private QA'}]}]})
    await copying;assert.equal(race.carts.length,0,'late rebook must not restore the previous member cart after logout');assert.equal(race.navigation.length,1);assert.equal(race.state.notice,'')
  }
  const rebookOk=harness({cart:[{id:'QA-current-cart'}]});await rebookOk.ctx.rebook(42);assert.equal(rebookOk.carts.length,1);assert.equal(rebookOk.navigation[0],'/snowland/booking?rebook=1')
  let button
  function walk(n){if(ts.isJsxElement(n)&&n.openingElement.tagName.getText(ast)==='button'&&n.openingElement.attributes.getText(ast).includes('onClick={logout}'))button=n;ts.forEachChild(n,walk)}
  walk(component);assert.ok(button)
  const React=req('react')
  for(const busy of [false,true]){
    const ctx=vm.createContext({React,LogOut:()=>null,logout(){},loggingOut:busy})
    vm.runInContext(ts.transpileModule('const button='+button.getText(ast),{compilerOptions:{jsx:ts.JsxEmit.React}}).outputText+';this.result=button',ctx)
    assert.equal(ctx.result.props.disabled,busy);assert.equal(ctx.result.props['aria-busy'],busy);assert.match(ctx.result.props.className,/min-h-11/)
    assert.ok(React.Children.toArray(ctx.result.props.children).includes(busy?'登出中…':'登出'))
  }
  console.log('PASS actual member logout: network/HTTP/application/malformed failure retained, confirmed cache clear, CSRF/credentials/invite, duplicate guard,44px feedback; stale success/error after logout/new load/unmount ignored')
})().catch(e=>{console.error(e);process.exitCode=1})
