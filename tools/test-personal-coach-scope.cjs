const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/admin/layout/AdminLayout.tsx'),'utf8'),ast=ts.createSourceFile('AdminLayout.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let personal;const selectors=[],notes=[]
function walk(node){
 if(ts.isVariableDeclaration(node)&&node.name.getText(ast)==='isPersonalCoachPage')personal=node
 if(ts.isJsxExpression(node)&&node.expression){const text=node.expression.getText(ast);if(text.includes('aria-label="目前管理校區"'))selectors.push(node.expression);if(text.includes('aria-label="個人教練視角"'))notes.push(node.expression)}
 ts.forEachChild(node,walk)
}
walk(ast);assert.ok(personal,'Personal coach routes must be identified so an unrelated manager campus label cannot mislead users')
const css=fs.readFileSync(path.join(root,'src/index.css'),'utf8')
assert.match(css,/html:has\(\.admin-shell\), body:has\(\.admin-shell\), #root:has\(\.admin-shell\)\s*\{\s*overflow-x:\s*clip;\s*overflow-y:\s*visible;/,'Console ancestors must not trap the sticky header in a false scroll container')
assert.equal(selectors.length,2);assert.equal(notes.length,1)
const compile=code=>ts.transpileModule(code,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
for(const basePath of ['/snowland','/demo'])for(const route of ['my/courses','my/calendar','my/evaluations','my/payroll','my/leaves','orders','scheduling','my-other']){
 const own=route.startsWith('my/'),ctx=vm.createContext({React,exports:{},basePath,location:{pathname:`${basePath}/console/${route}`},adminCheck:{user:{is_manager:true,can_view_all_campuses:false,campuses:[{id:77,name:'A管理校區'}]}},campusScope:'77',changeCampusScope(){}})
 vm.runInContext(compile(`const ${personal.getText(ast)};exports.selectors=()=>[${selectors.map(node=>'('+node.getText(ast)+')').join(',')}];exports.note=()=>(${notes[0].getText(ast)});`),ctx)
 const controls=ctx.exports.selectors().map(item=>renderToStaticMarkup(item)),note=renderToStaticMarkup(ctx.exports.note())
 assert.equal(controls.some(html=>html.includes('目前管理校區')),!own,route)
 assert.equal(note.includes('個人教練視角'),own,route)
 if(own)assert.ok(note.includes('不套用管理校區篩選'))
}
console.log('PASS actual desktop/mobile scope JSX: personal course/calendar/evaluation/payroll/leave routes have clear own-data notice and no misleading manager-campus selector; management and lookalike routes retain selector for both site bases')
