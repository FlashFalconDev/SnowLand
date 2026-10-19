const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),localRequire=Module.createRequire(path.join(root,'package.json')),React=localRequire('react'),ts=localRequire('typescript')
const compiled=ts.transpileModule(fs.readFileSync(path.join(root,'src/admin/components/CancellationStatusPanel.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText
function harness(states,cancellation={id:5,status:'requested',refund_amount:null,requires_cash_review:true,actual_received_amount:null}){
  let index=0;const calls=[]
  const context=vm.createContext({React,exports:{},require:name=>name==='react'?{useEffect(){},useState(){const i=index++;return[states[i],value=>states[i]=value]}}:name==='@tanstack/react-query'?{useQueryClient:()=>({invalidateQueries(){}}),useMutation:config=>({isPending:false,mutate:value=>config.mutationFn(value)})}:name==='../context'?{useNotification:()=>({success(){},error(){}})}:{processOrderCancellation:async(...args)=>calls.push(args)}})
  vm.runInContext(compiled,context)
  const render=()=>{index=0;return context.exports.default({cancellation,readOnly:false})}
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
  const native={id:5,status:'approved',refund_amount:7125,requires_cash_review:false,actual_received_amount:null,refund_bank_name:'QA銀行',refund_account_number:'QA-REFUND-NOT-REAL',refund_account_holder:'QA會員',currency_snapshot:{currency:'JPY',refund_amount:32063,rate:'4.50000000'}}
  const jpy=harness(['refunded',true,'','','',''],native)
  assert.match(JSON.stringify(jpy.render()),/32,063/)
  for(const bankValue of ['QA銀行','QA-REFUND-NOT-REAL','QA會員'])assert.ok(JSON.stringify(jpy.render()).includes(bankValue),'Refund reviewer must see the submitted destination account')
  await jpy.button('確定記錄退款完成').props.onClick()
  assert.equal(jpy.calls[0][2].currency,'JPY');assert.equal(jpy.calls[0][2].expected_refund_amount,32063);assert.equal(jpy.calls[0][2].confirmed_refund,true)
  const pendingNative={...native,status:'requested',requires_cash_review:true,refund_amount:null,currency_snapshot:{currency:'JPY',refund_amount:null,rate:'4.50000000'}}
  const manual=harness(['approved',true,'','9500','4001','QA人工帳務','42750','21000'],pendingNative)
  assert.equal(manual.button('確定核准取消').props.disabled,false)
  assert.ok(JSON.stringify(manual.render()).includes('本次日幣退款金額'))
  assert.ok(JSON.stringify(manual.render()).includes('台幣帳務金額'))
  await manual.button('確定核准取消').props.onClick()
  assert.equal(manual.calls[0][2].actual_received_currency_amount,42750)
  assert.equal(manual.calls[0][2].refund_currency_amount,21000)
  assert.equal(manual.calls[0][2].expected_refund_amount,21000)
  assert.equal(manual.calls[0][2].refund_amount,4667,'Calculate original receipt ratio, ignore stale manually entered refund')
  for(const [received,refund] of [['','21000'],['42750','42751'],['42750','1.5'],['9007199254740992','1']]){
    assert.equal(harness(['approved',true,'','9500','4001','QA人工帳務',received,refund],pendingNative).button('確定核准取消').props.disabled,true)
  }
  const memberSource=fs.readFileSync(path.join(root,'src/pages/site/MembershipPage.jsx'),'utf8')
  const memberCode=memberSource.slice(memberSource.indexOf('const formatDate ='),memberSource.indexOf('const ageOptions ='))+memberSource.slice(memberSource.indexOf('function CancellationForm('),memberSource.indexOf('function SharedClassSummary('))
  const preview={requires_bank_account:true,requires_cash_review:false,refund_amount:7500,settlement:{currency:'JPY',refund_amount:33750,original_amount:45000,rate:'4.50000000'}}
  const memberCalls=[]
  let memberStates=[preview,'schedule','QA取消',{bank_name:'QA銀行',account_number:'QA-NOT-REAL',account_holder:'QA會員',overseas_details:''},'',false],mi=0
  const memberContext=vm.createContext({React,useState(){const i=mi++;return[memberStates[i],value=>memberStates[i]=value]},requestJson:async(url,options)=>{memberCalls.push(JSON.parse(options.body));return{id:5,status:'requested'}}})
  vm.runInContext(ts.transpileModule(memberCode,{fileName:'member.jsx',compilerOptions:{jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText,memberContext)
  const renderMember=()=>{mi=0;return memberContext.CancellationForm({order:{id:42},onDone(){}})}
  const findMember=(node)=>{if(!node||typeof node!=='object')return null;if(node.type==='button'&&node.props.children==='確認送出')return node;for(const child of React.Children.toArray(node.props?.children)){const found=findMember(child);if(found)return found}return null}
  assert.match(localRequire('react-dom/server').renderToStaticMarkup(renderMember()),/JPY ¥ 33,750/)
  assert.equal(findMember(renderMember()).props.disabled,false,'Blank optional overseas details do not block three complete required bank fields')
  await findMember(renderMember()).props.onClick()
  assert.equal(memberCalls[0].currency,'JPY');assert.equal(memberCalls[0].expected_refund_amount,33750)
  assert.equal(memberCalls[0].refund_amount,undefined,'Member cannot set the refund basis')
  console.log('PASS actual cancellation review: required actual receipt/note/ack, refund cap, integer checks, explicit restricted payload, rejection without financial override')
}
main().catch(error=>{console.error(error);process.exitCode=1})
