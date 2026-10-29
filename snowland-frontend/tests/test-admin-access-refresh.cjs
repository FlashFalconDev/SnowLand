const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
function setup(relative,targetName){
 const text=fs.readFileSync(path.join(root,relative),'utf8'),ast=ts.createSourceFile(relative,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 let effect
 function walk(node,inside=false){const relevant=inside||ts.isFunctionDeclaration(node)&&node.name?.text===targetName;if(relevant&&ts.isCallExpression(node)&&node.expression.getText(ast)==='useEffect'&&node.getText(ast).includes('fetchAdminMe')){effect??=node}ts.forEachChild(node,child=>walk(child,relevant))}
 walk(ast);assert.ok(effect,'Actual access effect must exist')
 const listeners=new Map(),docListeners=new Map(),pending=[],seen=[];let run,deps,disposed
 const ctx=vm.createContext({user:{email:'qa@example.test'},location:{pathname:'/snowland/console/orders'},document:{visibilityState:'visible',addEventListener:(name,fn)=>docListeners.set(name,fn),removeEventListener:(name,fn)=>{if(docListeners.get(name)===fn)docListeners.delete(name)}},window:{addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:(name,fn)=>{if(listeners.get(name)===fn)listeners.delete(name)}},useEffect:(fn,args)=>{run=fn;deps=args},fetchAdminMe:()=>new Promise(resolve=>pending.push(resolve)),setAdminCheck:next=>seen.push(next),setUser:next=>seen.push(next)})
 vm.runInContext(ts.transpileModule(effect.getText(ast),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,ctx)
 disposed=run();return{listeners,docListeners,pending,seen,deps,ctx,dispose:()=>disposed?.()}
}
;(async()=>{
 const React=req('react'),source=fs.readFileSync(path.join(root,'src/admin/layout/AdminLayout.tsx'),'utf8')
 const ast=ts.createSourceFile('AdminLayout.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 const sidebar=ast.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='SidebarItem')
 const ctx=vm.createContext({React,PRIMARY:'#7c3aed',useLocation:()=>({pathname:'/snowland/console/orders'}),useState:()=>[false,()=>{}],NavLink:'a',ChevronDown:'svg'})
 vm.runInContext(ts.transpileModule(sidebar.getText(ast),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,ctx)
 for(const expanded of [false,true]){
   const tree=ctx.SidebarItem({item:{id:'operations',label:'營運管理',icon:'svg',children:[{id:'orders',path:'/snowland/console/orders',label:'訂單管理'}]},collapsed:false,isExpanded:expanded,onToggle(){}})
   const submenu=React.Children.toArray(tree.props.children).find(node=>node.type==='div')
   assert.equal(submenu.props.hidden,!expanded,'Collapsed links must be hidden from keyboard and accessibility navigation')
 }
 const menuAst=[]
 function findMenu(node){if(ts.isJsxOpeningElement(node)&&node.tagName.getText(ast)==='button'&&node.attributes.getText(ast).includes('開啟導覽選單'))menuAst.push(node);ts.forEachChild(node,findMenu)}
 findMenu(ast);assert.equal(menuAst.length,1);assert.match(menuAst[0].getText(ast),/min-h-11 min-w-11/,'Mobile menu needs a labelled 44px touch target')
 for(const [file,name] of [['src/admin/layout/AdminLayout.tsx','AdminLayoutContent'],['src/admin/components/RoleGuard.tsx','RoleGuard']]){
   const app=setup(file,name)
   assert.ok(app.deps.includes('/snowland/console/orders'),'Changing pages must recheck access instead of retaining removed campus metadata')
   assert.equal(typeof app.listeners.get('focus'),'function','Returning to the tab must refresh permissions')
   assert.equal(typeof app.listeners.get('snowland:campuses-updated'),'function')
   app.pending.shift()({user:{id:236,campuses:[{id:74},{id:75}]}});await new Promise(setImmediate)
   app.listeners.get('focus')();assert.equal(app.pending.length,1)
   app.pending.shift()({user:{id:236,campuses:[{id:74}]}});await new Promise(setImmediate)
   const newest=app.seen.at(-1);assert.equal((newest.user||newest).campuses.length,1,'Removed B campus must disappear from rendered access state')
   app.ctx.document.visibilityState='hidden';app.docListeners.get('visibilitychange')();assert.equal(app.pending.length,0)
   app.ctx.document.visibilityState='visible';app.docListeners.get('visibilitychange')();assert.equal(app.pending.length,1)
   app.listeners.get('focus')();assert.equal(app.pending.length,2)
   const old=app.pending.shift(),latest=app.pending.shift();latest({user:null,errorCode:403,errorMsg:'權限已撤銷'});await new Promise(setImmediate)
   const count=app.seen.length;old({user:{id:236,campuses:[{id:74},{id:75}]}});await new Promise(setImmediate)
   assert.equal(app.seen.length,count,'Late old response must not restore revoked access')
   app.listeners.get('focus')();const stale=app.pending.shift();app.dispose();stale({user:{id:236}});await new Promise(setImmediate)
   assert.equal(app.seen.length,count);assert.equal(app.listeners.size,0);assert.equal(app.docListeners.size,0)
 }
 console.log('PASS actual layout/route access effects and navigation: route/focus/visibility refresh, revoked campus removed, latest response only, no update after unmount, listeners cleaned, collapsed links hidden and mobile labelled 44px target')
})().catch(error=>{console.error(error);process.exit(1)})
