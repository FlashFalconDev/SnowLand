const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),localRequire=Module.createRequire(path.join(root,'package.json')),ts=localRequire('typescript')
const calls=[],quote={previous_total:9500,new_total:11500,difference_amount:2000,status:'preview_only',notice:'只預覽',quote_token:'QA'}
const context=vm.createContext({exports:{},require:()=>({default:{post:async(...args)=>{calls.push(args);return {code:200,data:quote}}}})})
vm.runInContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/admin/api/orders.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
async function main(){
  const changes=[{reservation_id:1,number_of_people:2,courses:[{booking_id:4,template_id:3,date:'2026-11-06',start_time:'09:00',end_time:'12:00'}]}]
  const before=JSON.stringify(changes)
  const result=await context.exports.previewOrderAmendment(42,changes)
  assert.equal(calls.length,1);assert.equal(calls[0][0],'/orders/42/amendment-quote/')
  assert.equal(calls[0][1].changes,changes);assert.equal(result,quote)
  assert.equal(JSON.stringify(changes),before)
  assert.equal(result.difference_amount,2000);assert.equal(result.status,'preview_only')
  const payload={changes,quote_token:'signed-QA-preview',request_key:'QA-stable-request-key',reason:'QA調整',confirmed:true,reschedule:false}
  const payloadBefore=JSON.stringify(payload)
  await context.exports.confirmOrderAmendment(42,payload)
  await context.exports.confirmOrderAmendment(42,payload)
  assert.equal(calls.length,3)
  assert.equal(calls[1][0],'/orders/42/amendment-confirm/')
  assert.equal(calls[1][1],payload);assert.equal(calls[2][1].request_key,payload.request_key)
  assert.equal(JSON.stringify(payload),payloadBefore)
  console.log('PASS actual order amendment client: separate preview/confirm endpoints, immutable draft, unchanged retry key and authoritative backend result')
}
main().catch(error=>{console.error(error);process.exitCode=1})
