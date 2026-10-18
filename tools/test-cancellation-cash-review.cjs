const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),localRequire=Module.createRequire(path.join(root,'package.json')),React=localRequire('react'),ts=localRequire('typescript')
const compiled=ts.transpileModule(fs.readFileSync(path.join(root,'src/admin/components/CancellationStatusPanel.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText
function harness(states){
  let index=0;const calls=[]
  const context=vm.createContext({React,exports:{},require:name=>name==='react'?{useEffect(){},useState(){const i=index++;return[states[i],value=>states[i]=value]}}:name==='@tanstack/react-query'?{useQueryClient:()=>({invalidateQueries(){}}),useMutation:config=>({isPending:false,mutate:value=>config.mutationFn(value)})}:name==='../context'?{useNotification:()=>({success(){},error(){}})}:{processOrderCancellation:async(...args)=>calls.push(args)}})
  vm.runInContext(compiled,context)
  const render=()=>{index=0;return context.exports.default({cancellation:{id:5,status:'requested',refund_amount:null,requires_cash_review:true,actual_received_amount:null},readOnly:false})}
  function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,predicate);if(result)return result}return null}
  return {calls,render,button:name=>find(render(),node=>node.type==='button'&&node.props.children===name)}
}
async function main(){
  for(const [ack,received,refund,note] of [[false,'9500','7000','QA'],[true,'9500','11500','QA'],[true,'','0','QA'],[true,'9500','1.5','QA'],[true,'9500','7000','']]){
    const ui=harness(['approved',ack,'',received,refund,note]);assert.equal(ui.button('確定核准取消').props.disabled,true)
  }
  const ui=harness(['approved',true,'','9500','7000','QA核對'])
  assert.equal(ui.button('確定核准取消').props.disabled,false)
  await ui.button('確定核准取消').props.onClick()
  assert.equal(ui.calls[0][0],5);assert.equal(ui.calls[0][1],'approved')
  assert.equal(JSON.stringify(ui.calls[0][2]),JSON.stringify({actual_received_amount:9500,refund_amount:7000,cash_review_note:'QA核對',confirmed_received:true}))
  const rejected=harness(['rejected',false,'','','',''])
  await rejected.button('確定駁回申請').props.onClick();assert.equal(rejected.calls[0][2],undefined)
  console.log('PASS actual cancellation review: required actual receipt/note/ack, refund cap, integer checks, explicit restricted payload, rejection without financial override')
}
main().catch(error=>{console.error(error);process.exitCode=1})
