const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm')
const html=fs.readFileSync(path.join(__dirname,'../snowland/templates/booking/payment.html'),'utf8')
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
assert.equal(scripts.length,1)
assert.ok(html.includes('payment_data|json_script:"payment-data"'))
assert.ok(!html.includes('/api/rebind_order/'))
function harness(status='unpaid',type='TT',sender='12345',ok=true){
  const calls=[],timers=[],lookups=[],nodes=new Map();let ready
  for(const id of ['loadingAnimation','notification','senderAccount'])nodes.set(id,{style:{},value:sender,classList:{remove(){}}})
  if(status==='unpaid')for(const id of ['bankTransferSection','newebpaySection'])nodes.set(id,{style:{display:'none'}})
  const config={paymentStatus:status,paymentType:type,reservation_group_pk:'42',access_token:'QA-signed-guest-token'}
  const ctx=vm.createContext({JSON,console:{error(){}},window:{location:{reload(){}}},setTimeout:(fn,ms)=>timers.push({fn,ms}),
    fetch:async(...args)=>{calls.push(args);return{ok,json:async()=>({message:'Payment confirmed'})}},
    document:{addEventListener:(name,fn)=>{assert.equal(name,'DOMContentLoaded');ready=fn},getElementById:id=>{lookups.push(id);return id==='payment-data'?{textContent:JSON.stringify(config)}:nodes.get(id)||null},querySelector:selector=>selector.startsWith('meta')?{getAttribute:()=> 'QA-csrf'}:null}})
  vm.runInContext(scripts[0][1],ctx)
  return{ctx,calls,nodes,lookups,timers,ready:()=>ready()}
}
;(async()=>{
  for(const status of ['paid','pending','refunded','expired','payment_records_review','collecting_class','pending_coach_approval']){
    const ui=harness(status);ui.ready();assert.ok(!ui.lookups.includes('bankTransferSection'));assert.equal(ui.calls.length,0)
  }
  for(const type of ['TT','newebpay']){
    const ui=harness('unpaid',type);ui.ready()
    assert.equal(ui.nodes.get(type==='TT'?'bankTransferSection':'newebpaySection').style.display,'block','authorized guest must initialize without a currentUser object or icon CDN')
  }
  for(const value of ['','1234','123456','abcde','１２３４５']){
    const ui=harness('unpaid','TT',value);ui.ctx.confirmBankTransfer();await new Promise(setImmediate);assert.equal(ui.calls.length,0,'invalid bank suffix must stop before request')
  }
  const report=harness();report.ready();report.ctx.confirmBankTransfer();await new Promise(setImmediate)
  assert.equal(report.calls[0][0],'/booking/api/process_payment/');assert.equal(report.calls[0][1].headers['X-CSRFToken'],'QA-csrf')
  const body=JSON.parse(report.calls[0][1].body);assert.equal(body.access_token,'QA-signed-guest-token');assert.equal(body.senderAccount,'12345');assert.ok(!('user' in body));assert.match(report.nodes.get('notification').textContent,/等待確認/)
  const failure=harness('unpaid','TT','12345',false);failure.ctx.confirmBankTransfer();await new Promise(setImmediate)
  assert.match(failure.nodes.get('notification').textContent,/錯誤/);assert.equal(failure.nodes.get('loadingAnimation').style.display,'none')
  console.log('PASS actual legacy payment JavaScript: valid JSON, terminal states no missing-form crash, signed-guest initialization without CDN/currentUser, ASCII suffix guards, CSRF/token-only report and server error feedback; no dead rebind flow')
})().catch(e=>{console.error(e);process.exitCode=1})
