const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/BookingFlowPage.tsx'),'utf8'),ast=ts.createSourceFile('BookingFlowPage.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let guard
function walk(node){if(ts.isIfStatement(node)&&node.expression.getText(ast).includes("staffLinkStatus !== 'valid'"))guard=node;ts.forEachChild(node,walk)}
walk(ast);assert.ok(guard)
for(const status of ['invalid','loading','valid']){
 const locale=require('./helpers/site-locale-harness.cjs')(React)
 const ctx=vm.createContext({React,t:locale.useSiteLocale().t,exports:{},staffLinkToken:'qa-only-token',staffLinkStatus:status,window:{location:{pathname:'/snowland/booking'}},SiteHeader:()=>null,SiteFooter:()=>null})
 vm.runInContext(ts.transpileModule('exports.render=()=>{'+guard.getText(ast)+'}',{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,ctx)
 const html=renderToStaticMarkup(ctx.exports.render())
 if(status==='invalid'){assert.ok(html.includes('代客訂課連結已失效'));assert.ok(html.includes('role="alert"'));assert.ok(html.includes('href="/snowland/booking"'));assert.ok(html.includes('min-h-11'));assert.ok(!html.includes('qa-only-token'));assert.ok(!html.includes('<form'))}
 if(status==='loading'){assert.ok(html.includes('role="status"'));assert.ok(!html.includes('改用一般訂課'))}
 if(status==='valid')assert.equal(html,'')
}
const panelSource=fs.readFileSync(path.join(root,'src/admin/pages/OperationsHubPage.tsx'),'utf8'),panelAst=ts.createSourceFile('OperationsHubPage.tsx',panelSource,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
const panel=panelAst.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='BookingLinksPanel')
for(const status of ['loading','error','retrying']){
 let retries=0
 const ctx=vm.createContext({React,exports:{},useQueryClient:()=>({}),useNotification:()=>({}),useBookingStore:fn=>fn({cart:[],clearCart(){}}),useScopedCampuses:()=>({campuses:[],selectedCampus:''}),useQuery:()=>({data:[],isLoading:status==='loading',isFetching:status==='retrying',error:status!=='loading'?Error('QA'):null,refetch(){retries++}}),useState:initial=>[initial,()=>{}],useEffect(){},useMutation:()=>({isPending:false}),fetchStaffBookingLinks(){},cardClass:'qa-card'})
 vm.runInContext(ts.transpileModule(panel.getText(panelAst),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,ctx)
 const tree=ctx.BookingLinksPanel(),html=renderToStaticMarkup(tree)
 assert.ok(!html.includes('尚未建立連結'),'Loading or errors must not masquerade as an empty link list')
 assert.ok(!html.includes('建立連結</button>'),'Do not create another link while current link state is unavailable')
 if(status==='loading')assert.ok(html.includes('role="status"'))
 if(status==='error'){
   assert.ok(html.includes('role="alert"'));assert.ok(html.includes('不代表沒有建立過連結'))
   const retry=React.Children.toArray(tree.props.children).find(node=>node.type==='button');retry.props.onClick();assert.equal(retries,1)
 }
 if(status==='retrying'){
   const retry=React.Children.toArray(tree.props.children).find(node=>node.type==='button')
   assert.equal(retry.props.disabled,true,'Prevent repeated retry clicks while fetching')
   assert.equal(retry.props['aria-busy'],true)
   assert.ok(html.includes('正在重新載入…'),'Show feedback while retry is in progress')
 }
}
console.log('PASS actual staff-link invalid/loading guard: blocks form, clear explanation, token-free general booking link and 44px action; valid link proceeds normally')
