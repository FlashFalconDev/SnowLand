const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/admin/pages/OperationsHubPage.tsx'),'utf8')
const compile=code=>ts.transpileModule(code,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const found=find(child,p);if(found)return found}return null}
function harness(patch={}){
 const row={id:42,member_name:'QA學員',sn:'QA-SN',order_number:'QA-ORDER',campus_name:'QA校區',course_dates:[],
  insurance_completed_at:'2026-10-01',waiver_completed_at:'2026-10-01',waiver_requires_resign:true,
  can_remind:true,can_mark_complete:true,insurance_processing_status:'pending',insurance_premium_amount:null,insurance_premium_currency:'',...patch}
 const states=[];let cursor=0
 const Dialog=()=>null
 const context=vm.createContext({React,exports:{},cardClass:'',inputClass:'',
  useQueryClient:()=>({invalidateQueries(){}}),useNotification:()=>({success(){},error(){}}),
  useState:initial=>{const slot=cursor++;if(!(slot in states))states[slot]=initial;return[states[slot],value=>states[slot]=typeof value==='function'?value(states[slot]):value]},
  useMemo:callback=>callback(),useQuery:()=>({data:[row],isLoading:false,isError:false,refetch(){}}),
  useMutation:()=>({isPending:false,mutate(){}}),InsuranceCalendar:()=>null,InsuranceDetail:()=>null,
  InsuranceReminderDialog:Dialog,insuranceDayRecords:rows=>rows,Empty:()=>null,Loader2:()=>null,
 })
 vm.runInContext(compile(source.slice(source.indexOf('const insuranceStatuses ='),source.indexOf('function InsuranceDetail('))),context)
 const render=()=>{cursor=0;return context.InsurancePanel()}
 return{render,Dialog}
}
let app=harness(),tree=app.render(),html=renderToStaticMarkup(tree)
assert.ok(html.includes('需重新簽署（文件已更新）'))
assert.ok(!html.includes('標記聲明書完成'),'Old signed versions must not offer a misleading manual completion button')
const remind=find(tree,node=>node.type==='button'&&node.props.children==='提醒重新簽署')
assert.ok(remind);assert.ok(remind.props.className.includes('min-h-11'));remind.props.onClick()
const dialog=find(app.render(),node=>node.type===app.Dialog);assert.equal(dialog.props.id,42);assert.equal(dialog.props.field,'waiver')
for(const record of [{waiver_requires_resign:false},{waiver_requires_resign:false,can_mark_complete:false}]){
 html=renderToStaticMarkup(harness(record).render());assert.ok(html.includes('已完成／已確認'));assert.ok(!html.includes('提醒重新簽署'));assert.ok(!html.includes('提醒補聲明書'))
}
html=renderToStaticMarkup(harness({waiver_requires_resign:false,waiver_completed_at:null}).render())
assert.ok(html.includes('提醒補聲明書'));assert.ok(html.includes('標記聲明書完成'),'Keep the existing explicit paper acknowledgement workflow')
html=renderToStaticMarkup(harness({can_remind:false,can_mark_complete:false}).render())
assert.ok(html.includes('需重新簽署'));assert.ok(!html.includes('提醒重新簽署'));assert.ok(!html.includes('標記聲明書完成'))
async function testDialogRejections(){
 const dialogSource=fs.readFileSync(path.join(root,'src/admin/components/InsuranceReminderDialog.tsx'),'utf8')
 for(const status of [400,401,403,404,409,502,undefined]){
  let cursor=0,calls=0;const states=[]
  const context=vm.createContext({React,exports:{},crypto:{randomUUID:()=> '11111111-1111-4111-8111-111111111111'},require:name=>{
   if(name==='react')return{...React,useEffect(){},useRef:initial=>({current:initial}),useState:initial=>{const slot=cursor++;if(!(slot in states))states[slot]=typeof initial==='function'?initial():initial;return[states[slot],value=>states[slot]=value]}}
   if(name==='@tanstack/react-query')return{useQuery:()=>({data:{recipient_email:'qa@example.test',subject:'QA',message:'QA',local_test:true,action_url:status===409?'https://booking.example.test/snowland/membership/pre-course-forms?reservation=42':''},isLoading:false,isError:false})}
   if(name==='../api/operations')return{sendInsuranceReminder:async()=>{calls++;throw{response:status?{status,data:{detail:'QA已完成，不需要再提醒'}}:undefined}},fetchInsuranceReminder(){}}
   if(name==='../context')return{useNotification:()=>({success(){}})}
   throw Error(name)
  }})
  vm.runInContext(compile(dialogSource),context)
  const render=()=>{cursor=0;return context.exports.default({id:42,field:'waiver',onClose(){}})}
  const initial=renderToStaticMarkup(render())
  if(status===409){
   assert.ok(initial.includes('預覽會員課前資料入口'));assert.ok(initial.includes('rel="noopener noreferrer"'))
   assert.ok(initial.includes('https://booking.example.test/snowland/membership/pre-course-forms?reservation=42'))
  }else assert.ok(initial.includes('不附直達連結'))
  await find(render(),node=>node.type==='button'&&node.props.children==='確認寄出提醒信').props.onClick()
  const html=renderToStaticMarkup(render());assert.equal(calls,1)
  if([400,401,403,404,409].includes(status)){
   assert.ok(html.includes('關閉'));assert.ok(!html.includes('查詢寄送結果'));assert.ok(!html.includes('確認寄出提醒信'))
  }else assert.ok(html.includes('查詢寄送結果'),'Unknown delivery outcomes must keep the safe same-key result query')
 }
 console.log('PASS actual insurance panel and reminder dialog: old/current/paper/permission states; definite rejection closes without retry, unknown outcome keeps result query')
}
testDialogRejections().catch(error=>{console.error(error);process.exitCode=1})
