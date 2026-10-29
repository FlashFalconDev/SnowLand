const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const compiled=ts.transpileModule(fs.readFileSync(path.join(root,'src/admin/pages/my/ApplyLeavePage.tsx'),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
const rules={today:'2026-10-18',minimum_start_date:'2026-10-21',leave_advance_days:3,leave_max_consecutive_days:2,leave_daily_coach_limit:2}
function find(node,pred){if(!node||typeof node!=='object')return null;if(pred(node))return node;for(const child of React.Children.toArray(node.props?.children)){const found=find(child,pred);if(found)return found}return null}
function harness(states,query={data:rules,isPending:false,isError:false},pending=false){
  let index=0;const calls=[],warnings=[]
  const ctx=vm.createContext({React,Date,Math,exports:{},require:name=>name==='react'?{useState:()=>{const i=index++;return[states[i],v=>states[i]=typeof v==='function'?v(states[i]):v]},useEffect(){}}
    :name==='@tanstack/react-query'?{useQuery:()=>query,useQueryClient:()=>({invalidateQueries(){}}),useMutation:cfg=>({isPending:pending,mutate:()=>cfg.mutationFn()})}
    :name==='react-router-dom'?{useNavigate:()=>()=>{}}
    :name==='../../context'?{useNotification:()=>({warning:msg=>warnings.push(msg),error(){},success(){}})}
    :name==='../../api/extras'?{applyLeave:payload=>calls.push(payload),fetchCoachLeaveRules(){}}
    :new Proxy({},{get:()=>()=>null})})
  vm.runInContext(compiled,ctx)
  const render=()=>{index=0;return ctx.exports.default()}
  return{calls,warnings,states,render,submit:()=>find(render(),n=>n.type==='form').props.onSubmit({preventDefault(){}})}
}
const good=harness(['2026-10-21','2026-10-21','QA'])
assert.equal(find(good.render(),n=>n.props?.id==='coach-leave-start').props.min,'2026-10-21')
good.submit();assert.equal(good.calls.length,1);assert.equal(good.calls[0].start_date,'2026-10-21')
find(good.render(),n=>n.props?.id==='coach-leave-start').props.onChange({target:{value:'2026-10-24'}})
assert.equal(good.states[0],'2026-10-24');assert.equal(good.states[1],'2026-10-24')
for(const states of [['2026-10-20','2026-10-20','QA'],['2026-10-21','2026-10-25','QA'],['2026-10-21','2026-10-20','QA'],['2026-10-21','2026-10-21','   ']]){
  const ui=harness(states);ui.submit();assert.equal(ui.calls.length,0);assert.equal(ui.warnings.length,1)
}
for(const query of [{data:undefined,isPending:true,isError:false},{data:rules,isPending:false,isError:true}]){
  const ui=harness(['2026-10-21','2026-10-21','QA'],query);assert.equal(find(ui.render(),n=>n.type==='fieldset').props.disabled,true);ui.submit();assert.equal(ui.calls.length,0)
}
const busy=harness(['2026-10-21','2026-10-21','QA'],undefined,true);busy.submit();assert.equal(busy.calls.length,0)
console.log('PASS coach leave: server school date/rules, minimum date, end-date alignment, reason/advance/length guards, loading/error/pending guard')
