const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm'),crypto=require('node:crypto').webcrypto
const root=path.resolve(__dirname,'../snowland-frontend'),localRequire=Module.createRequire(path.join(root,'package.json')),React=localRequire('react'),ts=localRequire('typescript')
function harness(file,extra,states,props,api){
  let si=0,ri=0;const refs=[],state=[...states]
  const hooks={...React,default:React,useEffect(){},useCallback:fn=>fn,useState(initial){const i=si++;if(!(i in state))state[i]=typeof initial==='function'?initial():initial;return[state[i],value=>state[i]=typeof value==='function'?value(state[i]):value]},useRef(value){const i=ri++;return refs[i]||(refs[i]={current:value})}}
  const source=fs.readFileSync(path.join(root,file),'utf8')+`\nexports.testComponent=${extra};`
  const context=vm.createContext({React,crypto,exports:{},require:name=>name==='react'?hooks:name==='@tanstack/react-query'?{useQueryClient:()=>({invalidateQueries(){}})}:name==='../context'?{useNotification:()=>({success(){}})}:api})
  vm.runInContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText,context)
  const render=()=>{si=0;ri=0;return context.exports.testComponent(props)}
  function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,predicate);if(result)return result}return null}
  return {state,render,find,button(name){return find(render(),node=>node.type==='button'&&node.props.children===name)}}
}
async function main(){
  const row={id:9,version:2,status:'topup_due',balance_amount:2000,updated_at:'2026-10-17T10:00:00Z',bank_snapshot:{},refund_bank:{}}
  const calls=[];let fail
  const props={row,url:'/member/9',requestJson:async(url,options)=>{calls.push(JSON.parse(options.body));if(fail)throw fail;return{data:{id:9},message:'已回報'}},onReload:async()=>{},onRefresh:async()=>{throw new Error('refresh failed after acknowledged save')}}
  let ui=harness('src/components/OrderAmendmentBalance.jsx','BalanceRow',['1234',{},false,'',false],props,{})
  assert.equal(ui.button('我已匯款，送出末五碼').props.disabled,true)
  ui=harness('src/components/OrderAmendmentBalance.jsx','BalanceRow',['12345',{},false,'',false],props,{})
  let form=ui.find(ui.render(),node=>node.type==='form');await form.props.onSubmit({preventDefault(){}})
  assert.equal(ui.state[4],false);assert.match(ui.state[3],/資料已回報/)
  assert.deepEqual(Object.keys(calls[0]).sort(),['action','amendment_id','expected_updated_at','reference','request_key'])
  fail={status:503,message:'結果未確認'};calls.length=0
  ui=harness('src/components/OrderAmendmentBalance.jsx','BalanceRow',['12345',{},false,'',false],props,{})
  await ui.find(ui.render(),node=>node.type==='form').props.onSubmit({preventDefault(){}})
  assert.equal(ui.state[4],true);assert.equal(ui.find(ui.render(),node=>node.type==='fieldset').props.disabled,true)
  const key=calls[0].request_key;fail=null
  await ui.find(ui.render(),node=>node.type==='form').props.onSubmit({preventDefault(){}})
  assert.equal(calls[1].request_key,key)
  const bank={bank_name:'QA銀行',account_number:'QA-ONLY',account_holder:'QA會員'}
  ui=harness('src/components/OrderAmendmentBalance.jsx','BalanceRow',['',bank,false,'',false],{...props,row:{...row,status:'refund_due',refund_bank:bank}}, {})
  assert.equal(ui.button('更新退款帳戶').props.disabled,true)
  for(const cancellationStatus of ['requested','approved','refunded']){
    ui=harness('src/components/OrderAmendmentBalance.jsx','OrderAmendmentBalance',[[row],'',true],{orderId:9,requestJson:async()=>({items:[row]}),cancellationStatus}, {})
    assert.equal(ui.find(ui.render(),node=>node.type==='form'),null)
    assert.match(JSON.stringify(ui.render()),/請勿再補款/)
  }
  ui=harness('src/components/OrderAmendmentBalance.jsx','OrderAmendmentBalance',[[],'',true],{orderId:9,requestJson:async()=>({items:[]}),cancellationStatus:'requested'}, {})
  assert.equal(ui.render(),null,'A cancelled order with no amendment history must not show an unrelated topup warning')
  const actionCalls=[];const api={processAmendmentBalance:async(id,payload)=>{actionCalls.push(payload);return{data:{id:row.id},msg:'已留底'}}}
  const reviewProps={orderId:42,row,action:'confirm_refund',onClose(){}}
  for(const states of [['',true,false,false,''],['QA',false,false,false,'']]){
    ui=harness('src/admin/components/AmendmentBalancesPanel.tsx','BalanceReviewDialog',states,reviewProps,api)
    assert.equal(ui.button('確認核對並留底').props.disabled,true)
  }
  ui=harness('src/admin/components/AmendmentBalancesPanel.tsx','BalanceReviewDialog',['QA依據',true,false,false,''],reviewProps,api)
  await ui.button('確認核對並留底').props.onClick()
  assert.equal(actionCalls[0].confirmed,true);assert.equal(actionCalls[0].action,'confirm_refund')
  assert.equal(actionCalls[0].expected_updated_at,row.updated_at)
  const native={...row,settlement:{currency:'JPY',rate:'4.50000000',balance_amount:9000}}
  calls.length=0
  ui=harness('src/components/OrderAmendmentBalance.jsx','BalanceRow',['12345',{},false,'',false],{...props,row:native},{})
  assert.match(JSON.stringify(ui.render()),/9,000/,'Member sees the native amount, not only TWD 2,000')
  await ui.find(ui.render(),node=>node.type==='form').props.onSubmit({preventDefault(){}})
  assert.equal(calls[0].currency,'JPY');assert.equal(calls[0].expected_amount,9000)
  ui=harness('src/admin/components/AmendmentBalancesPanel.tsx','BalanceReviewDialog',['QA日幣依據',true,false,false,''],{...reviewProps,row:native},api)
  assert.match(JSON.stringify(ui.render()),/9,000/,'Reviewer confirms the same native amount')
  await ui.button('確認核對並留底').props.onClick()
  assert.equal(actionCalls[1].currency,'JPY');assert.equal(actionCalls[1].expected_amount,9000)
  console.log('PASS actual member/staff balance controls: required fields, no paid claim on report, same retry key, acknowledged refresh error, explicit staff confirmation')
}
main().catch(error=>{console.error(error);process.exitCode=1})
