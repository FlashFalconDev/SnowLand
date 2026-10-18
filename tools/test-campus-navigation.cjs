const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const {renderToStaticMarkup}=req('react-dom/server')
const compile=code=>ts.transpileModule(code,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
const layout=fs.readFileSync(path.join(root,'src/admin/layout/AdminLayout.tsx'),'utf8')
const breadcrumb=layout.slice(layout.indexOf('function PageBreadcrumb('),layout.indexOf('function NoManagerPermission('))
let pathname='/snowland/console/coaches/leaves'
const context=vm.createContext({React,useLocation:()=>({pathname})})
vm.runInContext(compile(breadcrumb),context)
const nav=[{id:'settings',label:'基本設定',children:[{id:'coaches',label:'教練管理',path:'/snowland/console/coaches'},{id:'leaves',label:'請假審核',path:'/snowland/console/coaches/leaves'}]}]
const html=renderToStaticMarkup(React.createElement(context.PageBreadcrumb,{navItems:nav}))
assert.ok(html.includes('請假審核'),'Nested leave route must not be labelled as general coach management')
pathname='/snowland/console/coaches/leaves/19'
assert.ok(renderToStaticMarkup(React.createElement(context.PageBreadcrumb,{navItems:nav})).includes('請假審核'))
pathname='/snowland/console/coaches'
assert.ok(renderToStaticMarkup(React.createElement(context.PageBreadcrumb,{navItems:nav})).includes('教練管理'))
pathname='/snowland/console/unknown'
assert.ok(renderToStaticMarkup(React.createElement(context.PageBreadcrumb,{navItems:nav})).includes('管理後台'))

const orders=fs.readFileSync(path.join(root,'src/admin/pages/OrdersPage.tsx'),'utf8')
const campus=orders.slice(orders.indexOf('function CampusManagerOrdersPage('),orders.indexOf('function FullOrdersPage('))
function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,predicate);if(result)return result}return null}
function check(principal){
  const states=[3,'QA-not-found',null];let index=0
  const ctx=vm.createContext({React,PAGE_SIZE:10,useSearchParams:()=>[new URLSearchParams()],useState:()=>{const i=index++;return[states[i],v=>states[i]=v]},useQuery:()=>({data:{list:[],total_pages:1},isLoading:false,error:null}),fetchCampusManagerOrdersPaged(){}})
  vm.runInContext(compile(campus),ctx)
  const render=()=>{index=0;return ctx.CampusManagerOrdersPage({isPrincipal:principal})}
  const clear=find(render(),node=>node.type==='button'&&node.props.children==='清除搜尋')
  assert.ok(clear,'Both roles need an explicit way to clear an unmatched search')
  assert.ok(renderToStaticMarkup(render()).includes('目前可查看範圍內，沒有符合搜尋條件的訂單'))
  clear.props.onClick();assert.equal(states[0],1);assert.equal(states[1],'')
  assert.equal(find(render(),node=>node.type==='button'&&node.props.children==='清除搜尋'),null)
}
check(false);check(true)
console.log('PASS most-specific breadcrumb and both campus roles unmatched-search feedback/clear/reset')
