const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/PaymentPage.tsx'),'utf8')
function render(status,inspect=false){
 let cursor=0;const calls=[]
 const data={reservation_group_id:42,total_amount:1000,order_details:[],payment_status:status,payment_methods:['bank_transfer','newebpay'],bank_info:{bank_name:'QA',bank_branch:'QA',bank_account_number:'QA',bank_account_holder:'QA'}}
 const context=vm.createContext({React,exports:{},URLSearchParams,document:{cookie:'other=1; csrftoken=qa-csrf-only'},setTimeout(){},fetch:async(url,options)=>{calls.push({url,options});return{ok:true,json:async()=>({})}},require:name=>{
  if(name==='react')return{...React,useEffect(){},useState:initial=>{const slot=cursor++;return[slot===0?data:slot===1?false:slot===4?'12345':initial,()=>{}]}}
  if(name==='react-router-dom')return{useNavigate:()=>()=>{},useParams:()=>({clientCode:'snowland'}),useSearchParams:()=>[new URLSearchParams('reservation_group=42')]}
  if(name==='lucide-react')return new Proxy({},{get:()=>()=>null})
  if(name.startsWith('@/components/ui/'))return{default:()=>null}
  throw Error(name)
 }})
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
 const tree=context.exports.default()
 return inspect?{tree,calls}:renderToStaticMarkup(tree)
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
 console.log('PASS actual payment page: unpaid only; terminal states cannot resubmit; real transfer handler sends CSRF')
}
checkSubmission().catch(error=>{console.error(error);process.exitCode=1})
