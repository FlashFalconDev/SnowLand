const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm'),crypto=require('node:crypto').webcrypto
const root=path.resolve(__dirname,'../snowland-frontend'),localRequire=Module.createRequire(path.join(root,'package.json'))
const React=localRequire('react'),ts=localRequire('typescript')
const compiled=ts.transpileModule(fs.readFileSync(path.join(root,'src/admin/components/OrderAmendmentDialog.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText
const item={reservation_id:1,resort:'QA',course_type:'QA課程',number_of_people:1,members:[{id:4,name:'原學員'}],templates:[],coaches:[],equipment_slots:[]}
const quote={quote_token:'signed',previous_total:9500,new_total:11500,difference_amount:2000,items:[{waiver_resign_count:2,insurance_recheck_count:1}]}
const draft={reservation_id:1,number_of_people:2,ability_level_counts:{no_exp:2},retained_member_ids:[4],courses:[]}
function harness(initial,items=[item]){
  const state=[...initial],refs=[],calls=[];let si=0,ri=0,fail
  const api={fetchOrderAmendmentOptions:async()=>({items:[item]}),previewOrderAmendment:async(...args)=>{calls.push(['preview',...args]);return quote},confirmOrderAmendment:async(...args)=>{calls.push(['confirm',...args]);if(fail)throw fail;return {version:2,new_total:11500,balance_amount:2000,notice:'尚未收退款'}}}
  const hooks={useEffect(){},useState(initialValue){const i=si++;if(!(i in state))state[i]=typeof initialValue==='function'?initialValue():initialValue;return [state[i],value=>state[i]=typeof value==='function'?value(state[i]):value]},useRef(value){const i=ri++;return refs[i]||(refs[i]={current:value})}}
  const context=vm.createContext({React,crypto,exports:{},require:name=>name==='react'?hooks:name==='@tanstack/react-query'?{useQuery:()=>({data:{items},isLoading:false}),useQueryClient:()=>({invalidateQueries(){}})}:api})
  vm.runInContext(compiled,context)
  function render(){si=0;ri=0;return context.exports.default({orderId:42,onClose(){}})}
  function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of React.Children.toArray(node.props?.children)){const found=find(child,predicate);if(found)return found}return null}
  const button=name=>find(render(),node=>node.type==='button'&&node.props.children===name)
  return {state,calls,refs,render,find,button,setFailure(value){fail=value}}
}
async function main(){
  const blocked=harness([],[{...item,blocked_reason:'此課程已結束或取消，不能直接修改'}])
  assert.match(localRequire('react-dom/server').renderToStaticMarkup(blocked.render()),/目前沒有可直接修改的課程/,'Explain the blocked reason visibly, not only inside an unselectable option')
  assert.equal(blocked.find(blocked.render(),node=>node.type==='select').props.disabled,true)
  const states=[1,draft,quote,null,'QA原因',true,false,false,'',false]
  let ui=harness(states)
  const previewHtml=localRequire('react-dom/server').renderToStaticMarkup(ui.render())
  assert.match(previewHtml,/舊簽署留底/)
  assert.match(previewHtml,/本次須重新簽署：2 位；投保重新核對：1 位/)
  const nativeQuote={...quote,settlement:{currency:'JPY',rate:'4.50000000',previous_total:42750,new_total:51750,difference_amount:9000,balance_amount:9000}}
  const nativeUi=harness([1,draft,nativeQuote,null,'QA原因',true,false,false,'',false])
  const nativeHtml=localRequire('react-dom/server').renderToStaticMarkup(nativeUi.render())
  assert.match(nativeHtml,/JPY ¥ 51,750/)
  assert.match(nativeHtml,/JPY ¥ 9,000/)
  assert.match(nativeHtml,/台幣計價基準/)
  assert.equal(ui.button('確認保存修改').props.disabled,false)
  await ui.button('確認保存修改').props.onClick()
  assert.equal(ui.calls[0][1],42);assert.equal(ui.calls[0][2].changes[0],draft)
  assert.equal(ui.calls[0][2].confirmed,true);assert.equal(ui.state[3].version,2)
  for(const [reason,reviewed] of [['',true],['QA',false]]){ui=harness([1,draft,quote,null,reason,reviewed,false,false,'',false]);assert.equal(ui.button('確認保存修改').props.disabled,true)}
  ui=harness([1,{...draft,ability_level_counts:{no_exp:1}},null,null,'QA',false,false,false,'',false])
  await ui.button('預覽差額').props.onClick();assert.match(ui.state[8],/加總/);assert.equal(ui.calls.length,0)
  ui=harness(states);ui.setFailure({response:{status:503,data:{msg:'暫時無法確認'}}})
  await ui.button('確認保存修改').props.onClick()
  assert.equal(ui.state[9],true);assert.equal(ui.state[2],quote)
  assert.equal(ui.button('取消').props.disabled,true)
  const originalKey=ui.calls[0][2].request_key
  ui.setFailure(null);await ui.button('以相同識別碼查詢／重試').props.onClick()
  assert.equal(ui.calls[1][2].request_key,originalKey)
  ui=harness(states);ui.setFailure({response:{status:409,data:{msg:'價格已變更'}}})
  await ui.button('確認保存修改').props.onClick()
  assert.equal(ui.state[9],false);assert.equal(ui.state[2],null);assert.equal(ui.state[5],false)
  assert.equal(ui.button('確認保存修改').props.disabled,true)
  console.log('PASS actual amendment dialog: confirmation gates, counts validation, immutable payload, 503 keeps retry key, 409 requires new preview')
}
main().catch(error=>{console.error(error);process.exitCode=1})
