const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/PaymentPage.tsx'),'utf8')
const loadSiteLocale=require('./helpers/site-locale-harness.cjs')
function render(status,inspect=false,overrides={},language='zh-Hant'){
 let cursor=0;const calls=[],updates=[],clipboard={}
 const locale=loadSiteLocale(React,language),settlementExports={},selector={exports:{},require:name=>name==='react'?React:locale}
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/components/booking/SettlementSummary.tsx'),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,{React,exports:settlementExports,require:()=>locale})
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/components/site/SiteLanguageSelect.jsx'),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,selector)
 const data={reservation_group_id:42,total_amount:1000,order_details:[],payment_status:status,payment_methods:['bank_transfer','newebpay'],bank_info:{bank_name:'QA',bank_branch:'QA',bank_account_number:'QA',bank_account_holder:'QA'},...overrides}
 const context=vm.createContext({React,exports:{},URLSearchParams,navigator:{clipboard:{writeText:()=>new Promise((resolve,reject)=>{clipboard.resolve=resolve;clipboard.reject=reject})}},document:{cookie:'other=1; csrftoken=qa-csrf-only'},setTimeout(){},fetch:async(url,options)=>{calls.push({url,options});return{ok:true,json:async()=>({})}},require:name=>{
  if(name==='react')return{...React,useEffect(){},useState:initial=>{const slot=cursor++;return[slot===0?data:slot===1?false:slot===4?'12345':initial,value=>updates.push({slot,value})]}}
  if(name==='react-router-dom')return{useNavigate:()=>()=>{},useParams:()=>({clientCode:'snowland'}),useSearchParams:()=>[new URLSearchParams('reservation_group=42')]}
  if(name==='lucide-react')return new Proxy({},{get:()=>()=>null})
  if(name.startsWith('@/components/ui/'))return{default:()=>null}
  if(name==='@/components/booking/SettlementSummary')return settlementExports
  if(name.includes('contexts/SiteLocale'))return locale
  if(name.includes('site/SiteLanguageSelect'))return selector.exports
  throw Error(name)
 }})
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
 const tree=context.exports.default()
 return inspect?{tree,calls,updates,clipboard}:renderToStaticMarkup(tree)
}
for(const status of ['paid','pending','refunded','expired','unexpected']){
 const html=render(status)
 assert.ok(!html.includes('確認已匯款'),`${status} must not allow another transfer report`)
 assert.ok(!html.includes('前往付款'),`${status} must not allow card payment`)
 if(status==='refunded')assert.ok(html.includes('已記錄退款'))
}
assert.ok(render('unpaid').includes('確認已匯款'))
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,p);if(result)return result}return null}
async function checkSubmission(){
 const {tree,calls}=render('unpaid',true)
 await find(tree,n=>n.type==='button'&&n.props.children==='確認已匯款').props.onClick()
 assert.equal(calls.length,1);assert.equal(calls[0].options.headers['X-CSRFToken'],'qa-csrf-only')
 assert.equal(calls[0].options.credentials,'include');assert.equal(JSON.parse(calls[0].options.body).sender_account,'12345')
 const jpy={currency:'JPY',base_currency:'TWD',base_amount:10000,amount:45000,rate:'4.50000000',locked_at:'2026-10-19T03:00:00Z'}
 const jpyHtml=render('unpaid',false,{total_amount:10000,settlement:jpy,payment_methods:['bank_transfer']})
 assert.ok(jpyHtml.includes('日幣 JPY ¥ 45,000'))
 assert.ok(jpyHtml.includes('台幣計價基準 NT$ 10,000'))
 assert.ok(!jpyHtml.includes('NT$ 45,000'))
 const jpyApp=render('unpaid',true,{total_amount:10000,settlement:jpy,payment_methods:['bank_transfer']})
 await find(jpyApp.tree,n=>n.type==='button'&&n.props.children==='確認已匯款').props.onClick()
 assert.equal(JSON.parse(jpyApp.calls[0].options.body).currency,'JPY')
 assert.equal(JSON.parse(jpyApp.calls[0].options.body).expected_amount,45000)
 for(const [language,label] of [['en','Bank transfer details'],['ja','銀行振込先']]){
   const localized=render('unpaid',false,{total_amount:10000,settlement:jpy,payment_methods:['bank_transfer']},language)
   assert.ok(localized.includes(label),'Payment instructions follow the site language')
   assert.ok(localized.includes('45,000'));assert.ok(!localized.includes('NT$ 45,000'))
 }
 const copy=render('unpaid',true)
 const pendingCopy=find(copy.tree,n=>n.type==='button'&&n.props.title==='複製帳號').props.onClick()
 assert.ok(!copy.updates.some(update=>update.slot===5&&update.value===true),'Do not claim copied while clipboard permission is pending')
 copy.clipboard.reject(Error('QA clipboard denied'));await pendingCopy
 assert.ok(!copy.updates.some(update=>update.slot===5&&update.value===true))
 assert.ok(copy.updates.some(update=>update.value?.type==='error'),'Rejected copy must show failure instead of false success')
 const copied=render('unpaid',true)
 const successfulCopy=find(copied.tree,n=>n.type==='button'&&n.props.title==='複製帳號').props.onClick()
 copied.clipboard.resolve();await successfulCopy
 assert.ok(copied.updates.some(update=>update.slot===5&&update.value===true))
 assert.ok(copied.updates.some(update=>update.value?.type==='success'))
 console.log('PASS actual payment page: unpaid only; terminal states cannot resubmit; real transfer handler sends CSRF')
}
checkSubmission().catch(error=>{console.error(error);process.exitCode=1})
