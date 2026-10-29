const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript'),React=req('react'),{renderToStaticMarkup}=req('react-dom/server')
const read=name=>{const source=fs.readFileSync(path.join(root,'src/admin/pages',name),'utf8');return ts.createSourceFile(name,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)}
const schedule=read('SchedulingPage.tsx'),orders=read('OrdersPage.tsx')
let statusGuard,dataGuard,query,dayOrderButton,documentReview
function walk(node){
 if(ts.isJsxExpression(node)&&node.expression?.getText(schedule).startsWith('rescheduleDate!==candidate.date'))documentReview=node.expression
 if(ts.isJsxExpression(node)&&node.expression?.getText(schedule).startsWith('selectedOrderId !== null && (isOrderLoading || orderError)'))statusGuard=node.expression
 if(ts.isJsxExpression(node)&&node.expression?.getText(schedule).startsWith('selectedOrderId !== null && selectedOrder &&'))dataGuard=node.expression
 if(ts.isVariableDeclaration(node)&&node.name.getText(schedule).includes('data: selectedOrder'))query=node.initializer
 if(ts.isJsxOpeningElement(node)&&node.tagName.getText(schedule)==='button'&&node.attributes.getText(schedule).includes('openBookingOrder(firstBooking)'))dayOrderButton=node
 ts.forEachChild(node,walk)
}
walk(schedule)
assert.ok(statusGuard,'A calendar order lookup failure must render a status drawer, not silently disappear')
assert.ok(documentReview,'Whole-class date changes must explain resigning and insurance recheck')
assert.ok(dataGuard,'Keep previously loaded editor state hidden while access is revalidated')
assert.ok(dayOrderButton.attributes.getText(schedule).includes('min-h-11'),'Mobile day-details order button must be at least 44px')
const component=orders.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='OrderDetailStatusDrawer')
const message=orders.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='getOrderDetailErrorMessage')
assert.ok(component);assert.ok(message)
let closed=0,retried=0
const ctx=vm.createContext({React,exports:{},useRef:()=>({current:null}),useEffect(){},PRIMARY:'#8b5cf6',Loader2:()=>null,AlertCircle:()=>null,X:()=>null,selectedOrderId:213,selectedOrder:null,isOrderLoading:false,orderError:null,setSelectedOrderId(){closed++},refetchOrder(){retried++},OrderDetailDrawer:()=>React.createElement('section',{'data-order':'private'})})
function run(source){return vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,ctx)}
run(message.getText(orders)+'\n'+component.getText(orders))
ctx.rescheduleDate='2026-10-30';ctx.candidate={date:'2026-10-29'};ctx.scheduleOptions={waiver_resign_count:2,insurance_recheck_count:1}
run('exports.documentReview=()=> <>{'+documentReview.getText(schedule)+'}</>')
assert.match(renderToStaticMarkup(ctx.exports.documentReview()),/改期須重新簽署：2 位；已投保重核：1 位/)
ctx.rescheduleDate='2026-10-29'
assert.equal(renderToStaticMarkup(ctx.exports.documentReview()),'','A time-only change must not claim date-based invalidation')
run('exports.preview=()=> <>{'+statusGuard.getText(schedule)+'}{'+dataGuard.getText(schedule)+'}</>')
for(const state of ['loading','error','cached-error','success','closed']){
 ctx.selectedOrderId=state==='closed'?null:213
 ctx.isOrderLoading=state==='loading'
 ctx.orderError=state.includes('error')?{response:{status:404}}:null
 ctx.selectedOrder=['success','cached-error','closed'].includes(state)?{id:213}:null
 const tree=ctx.exports.preview(),html=renderToStaticMarkup(tree)
 if(state==='loading'){assert.ok(html.includes('role="dialog"'));assert.ok(html.includes('載入訂單明細中'));assert.ok(html.includes('role="status"'))}
 if(state.includes('error')){assert.ok(html.includes('role="alert"'));assert.ok(html.includes('重新載入明細'));assert.ok(!html.includes('訂單 API 路徑不存在'))}
 if(state==='cached-error'){
   const wrapper=React.Children.toArray(tree.props.children).find(child=>child.type==='div')
   assert.equal(wrapper.props['aria-hidden'],true);assert.equal(wrapper.props.className,'invisible')
 }
 if(state==='success'){assert.ok(html.includes('data-order="private"'));assert.ok(!html.includes('role="dialog"'))}
 if(state==='closed')assert.equal(html,'')
}
for(const code of [401,403,404,500,undefined]){
 const error=code?{response:{status:code,data:{detail:'<html>TRACE SECRET</html>'}}}:Error('network failure')
 const tree=ctx.OrderDetailStatusDrawer({title:'明細載入失敗',error,onClose:()=>closed++,onRetry:()=>retried++,isRetrying:false})
 const html=renderToStaticMarkup(tree)
 assert.ok(html.includes('role="dialog"'));assert.ok(html.includes('aria-modal="true"'));assert.ok(!html.includes('TRACE SECRET'))
 const buttons=[];function collect(node){if(!node||typeof node!=='object')return;if(node.type==='button')buttons.push(node);React.Children.forEach(node.props?.children,collect)}collect(tree)
 const retry=buttons.find(button=>button.props.children==='重新載入明細');assert.ok(retry)
 assert.ok(retry.props.className.includes('min-h-11'));retry.props.onClick()
 const close=buttons.find(button=>button.props['aria-label']==='關閉訂單載入視窗');assert.ok(close);close.props.onClick()
 let prevented=false;tree.props.children[1].props.onKeyDown({key:'Escape',preventDefault(){prevented=true},stopPropagation(){}})
 assert.ok(prevented)
}
assert.equal(retried,5);assert.equal(closed,10)
const busyTree=ctx.OrderDetailStatusDrawer({title:'明細載入失敗',error:{response:{status:500}},onClose(){},onRetry(){},isRetrying:true})
const busyHtml=renderToStaticMarkup(busyTree)
assert.ok(busyHtml.includes('正在重新載入…'));assert.ok(busyHtml.includes('disabled=""'));assert.ok(busyHtml.includes('aria-busy="true"'))
let focus=''
const first={focus(){focus='first'}},last={focus(){focus='last'}}
ctx.document={activeElement:first}
const onKeyDown=busyTree.props.children[1].props.onKeyDown
onKeyDown({key:'Tab',shiftKey:true,currentTarget:{querySelectorAll:()=>[first,last]},preventDefault(){}})
assert.equal(focus,'last');ctx.document.activeElement=last
onKeyDown({key:'Tab',shiftKey:false,currentTarget:{querySelectorAll:()=>[first,last]},preventDefault(){}})
assert.equal(focus,'first')
ctx.useQuery=options=>options;ctx.fetchOrder=id=>id;ctx.selectedOrderId=213
run('exports.options='+query.getText(schedule))
assert.equal(ctx.exports.options.retry,false);assert.equal(ctx.exports.options.gcTime,0);assert.equal(ctx.exports.options.staleTime,0)
assert.equal(ctx.exports.options.queryFn(),213)
let viewingGuard,viewingData,viewingQuery,mainPanel
function walkOrders(node){
 if(ts.isJsxExpression(node)&&node.expression?.getText(orders).startsWith('viewingId !== null && (isViewingLoading || viewingError)'))viewingGuard=node.expression
 if(ts.isJsxExpression(node)&&node.expression?.getText(orders).startsWith('viewingId !== null && viewing &&'))viewingData=node.expression
 if(ts.isVariableDeclaration(node)&&node.name.getText(orders).includes('data: viewing,'))viewingQuery=node.initializer
 if(ts.isJsxOpeningElement(node)&&node.attributes.properties.some(prop=>ts.isJsxAttribute(prop)&&prop.name.text==='ref'&&prop.initializer?.expression?.getText(orders)==='orderPanel'))mainPanel=node
 ts.forEachChild(node,walkOrders)
}
walkOrders(orders);assert.ok(viewingGuard);assert.ok(viewingData);assert.ok(viewingQuery)
ctx.setViewingId=()=>{};ctx.refetchViewing=()=>{}
run('exports.viewing=()=> <>{'+viewingGuard.getText(orders)+'}{'+viewingData.getText(orders)+'}</>')
ctx.viewingId=213;ctx.viewing={id:213};ctx.viewingError={response:{status:403}};ctx.isViewingLoading=false
const hidden=ctx.exports.viewing(),html=renderToStaticMarkup(hidden)
assert.ok(html.includes('目前沒有權限'));assert.ok(html.includes('重新載入明細'))
assert.equal(React.Children.toArray(hidden.props.children).find(node=>node.type==='div').props['aria-hidden'],true)
ctx.viewingId=null;assert.equal(renderToStaticMarkup(ctx.exports.viewing()),'')
run('exports.viewingOptions='+viewingQuery.getText(orders))
assert.equal(ctx.exports.viewingOptions.retry,false);assert.equal(ctx.exports.viewingOptions.gcTime,0);assert.equal(ctx.exports.viewingOptions.staleTime,0)
assert.ok(mainPanel);assert.ok(mainPanel.attributes.getText(orders).includes('role="dialog"'))
const trap=mainPanel.attributes.properties.find(prop=>prop.name?.text==='onKeyDown').initializer.expression
run('exports.detailTrap='+trap.getText(orders))
const container={querySelectorAll:()=>[first,last]};first.getClientRects=last.getClientRects=()=>[{}]
ctx.orderPanel={current:container};ctx.document.activeElement=first;focus=''
ctx.exports.detailTrap({key:'Tab',shiftKey:true,target:{closest:()=>container},currentTarget:container,preventDefault(){}})
assert.equal(focus,'last');focus=''
ctx.exports.detailTrap({key:'Tab',shiftKey:false,target:{closest:()=>({})},currentTarget:container,preventDefault(){}})
assert.equal(focus,'','Do not steal focus from nested amendment or email dialogs')
const effects=[]
const body={style:{overflow:''},isConnected:true,focus(){focus='body'}}
const visibleModal={getClientRects:()=>[{}],focus(){focus='restored'}}
ctx.document={body,activeElement:body,querySelectorAll:()=>[visibleModal]}
ctx.getComputedStyle=()=>({visibility:'visible'})
ctx.useEffect=callback=>effects.push(callback)
ctx.useRef=()=>({current:{focus(){focus='status'}}})
ctx.OrderDetailStatusDrawer({title:'明細載入失敗',error:Error('QA'),onClose(){}})
const cleanup=effects[0]();focus='';cleanup()
assert.equal(focus,'restored','When the former control disappeared, retry completion must focus the visible detail modal instead of BODY')
assert.equal(body.style.overflow,'')
console.log('PASS actual calendar order lookup and shared status drawer: visible errors, safe cached content, retry/close/Escape, localized messages and fresh access checks')
