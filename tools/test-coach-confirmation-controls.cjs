const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/admin/pages/my/PendingConfirmationsPage.tsx'),'utf8')
const compiled=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
const item={id:246,course_type:'QA單板',resort:'QA雪場',user_name:'QA',number_of_people:1,ability_level:'level3',age_ranges:[],bookings:[{date:'2026-10-21',start_time:'09:00',end_time:'13:00'}]}
function find(node,pred){if(!node||typeof node!=='object')return null;if(pred(node))return node;for(const child of React.Children.toArray(node.props?.children)){const found=find(child,pred);if(found)return found}return null}
function text(node){if(typeof node==='string')return node;return React.Children.toArray(node?.props?.children).map(text).join('')}
function harness({pending=false,confirm=true,query={data:[item],isLoading:false,error:null}}={}){
  const calls=[],invalidations=[],messages=[];let mutation,retries=0,confirmations=0
  const ctx=vm.createContext({React,exports:{},confirm:()=>{confirmations++;return confirm},require:name=>
    name==='@tanstack/react-query'?{useQuery:()=>({...query,refetch:()=>retries++}),useQueryClient:()=>({invalidateQueries:({queryKey})=>invalidations.push(queryKey.join('/'))}),useMutation:cfg=>{mutation=cfg;return{isPending:pending,variables:{id:item.id},mutate:payload=>calls.push(payload)}}}
    :name==='../../context'?{useNotification:()=>({success:msg=>messages.push(['success',msg]),error:msg=>messages.push(['error',msg])})}
    :name==='../../api/extras'?{fetchCoachPending(){},coachConfirm:(...args)=>args}
    :name==='@/utils/learningProgress'?{formatAbilityLevel:v=>v}:new Proxy({},{get:()=>()=>null})})
  vm.runInContext(compiled,ctx);const render=()=>ctx.exports.default()
  return{render,calls,invalidations,messages,get mutation(){return mutation},get retries(){return retries},get confirmations(){return confirmations},button:label=>find(render(),n=>n.type==='button'&&text(n)===label)}
}
for(const label of ['接受課程','拒絕'])assert.match(harness().button(label).props.className,/min-h-11/,'coach actions need44px touch targets')
const accept=harness();accept.button('接受課程').props.onClick();assert.equal(accept.calls[0].action,'accept')
const cancel=harness({confirm:false});cancel.button('拒絕').props.onClick();assert.equal(cancel.confirmations,1);assert.equal(cancel.calls.length,0)
const reject=harness();reject.button('拒絕').props.onClick();assert.equal(reject.calls[0].action,'reject')
reject.mutation.onSuccess({code:200,msg:'已拒絕，請行政安排'},{action:'reject'})
assert.deepEqual(reject.invalidations.sort(),['admin/coach-pending','admin/my-calendar','admin/my-course-monthly-stats','admin/my-courses'].sort())
assert.equal(reject.messages[0][1],'已拒絕，請行政安排')
const failure=harness();failure.render();failure.mutation.onSuccess({code:400,msg:'狀態已變更'},{action:'accept'});assert.equal(failure.messages[0][0],'error');assert.equal(failure.invalidations.length,0)
failure.mutation.onError({response:{data:{msg:'無權操作'}}});assert.equal(failure.messages[1][1],'無權操作')
for(const label of ['接受課程','拒絕'])assert.equal(harness({pending:true}).button(label).props.disabled,true)
const error=harness({query:{data:[],error:new Error('QA'),isLoading:false}});const retry=error.button('重新載入');assert.ok(retry);retry.props.onClick();assert.equal(error.retries,1)
assert.ok(find(harness({query:{data:[],isLoading:false}}).render(),n=>text(n).includes('目前沒有待確認的課程')))
console.log('PASS actual coach confirmation:44px, accept/reject/cancel, busy, authoritative feedback, related calendar/courses/stats refresh, error retry and empty state')
