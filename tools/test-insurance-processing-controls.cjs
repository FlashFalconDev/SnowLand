const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const vm = require('node:vm')
const root = path.resolve(__dirname, '../snowland-frontend')
const localRequire = Module.createRequire(path.join(root, 'package.json'))
const React = localRequire('react'), ts = localRequire('typescript')
const { renderToStaticMarkup } = localRequire('react-dom/server')
const source = fs.readFileSync(path.join(root, 'src/admin/pages/OperationsHubPage.tsx'), 'utf8')
const compile = code => ts.transpileModule(code, { fileName:'insurance.tsx', compilerOptions:{ jsx:ts.JsxEmit.React, module:ts.ModuleKind.CommonJS, target:ts.ScriptTarget.ES2020 } }).outputText
const row = { id:95, can_mark_complete:true, insurance_processing_status:'pending', insurance_premium_amount:null,
  insurance_premium_currency:'', insurance_processing_updated_at:null, insurance_data:{full_name:'QA原學員'}, member_email:'', waiver_signature:'QA原簽名', waiver_requires_resign:true }
function render(states, editable=true) {
  let index=0, mutation
  const calls=[]
  const context=vm.createContext({ React, Date, Number, Object, inputClass:'',
    useQueryClient:()=>({invalidateQueries(){}}), useNotification:()=>({success(){},error(){}}),
    useQuery:()=>({data:{...row,can_mark_complete:editable},isLoading:false,isError:false}),
    useState:initial=>[states ? states[index++] : initial,()=>{}],
    useMutation:options=>{mutation=options;return {isPending:false,mutate(){}}},
    saveInsuranceProcessing:async (...args)=>calls.push(args),
    Field:({label,children})=>React.createElement('label',null,label,children),
  })
  vm.runInContext(compile(source.slice(source.indexOf('const insuranceStatuses ='),source.indexOf('function InsurancePanel'))),context)
  vm.runInContext(compile(source.slice(source.indexOf('function InsuranceDetail('),source.indexOf('function Empty('))),context)
  const tree=states ? context.InsuranceProcessingForm({row}) : React.createElement(context.InsuranceDetail,{id:95})
  const html=renderToStaticMarkup(tree)
  return {html,calls,save:()=>mutation.mutationFn()}
}
async function main(){
  const readonly=render(null,false)
  assert.doesNotMatch(readonly.html,/投保作業回報|儲存投保進度/)
  assert.match(readonly.html,/QA原學員/)
  assert.match(readonly.html,/聲明書已更新，請會員重新簽署/)
  assert.match(readonly.html,/不會覆寫成新版/)
  const valid=render(['processing','350.50','JPY',false])
  assert.doesNotMatch(valid.html,/<button[^>]* disabled=""/)
  await valid.save()
  assert.deepEqual(Object.keys(valid.calls[0][1]).sort(),['confirm_insured','currency','expected_updated_at','premium_amount','status'])
  assert.equal(valid.calls[0][1].premium_amount,'350.50')
  assert.equal(valid.calls[0][1].currency,'JPY')
  for(const states of [['insured','','',false],['checking','0','',false],['checking','','A',false],['checking','-1','TWD',false],['pending','','',false]]){
    assert.match(render(states).html,/<button[^>]* disabled=""/)
  }
  const confirmed=render(['insured','','',true])
  assert.doesNotMatch(confirmed.html,/<button[^>]* disabled=""/)
  assert.match(confirmed.html,/我已在保險公司完成投保/)
  await confirmed.save()
  assert.equal(confirmed.calls[0][1].premium_amount,null)
  assert.equal(confirmed.calls[0][1].confirm_insured,true)
  console.log('PASS actual insurance form: read-only role, amount/currency/unchanged guards, explicit confirmation, null vs zero and restricted payload')
}
main().catch(error=>{console.error(error);process.exitCode=1})
