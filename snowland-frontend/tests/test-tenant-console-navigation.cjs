const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript'),React=req('react'),{renderToStaticMarkup}=req('react-dom/server')
let code='school-a'
const hooks=vm.createContext({exports:{},require:()=>({useParams:()=>({clientCode:code})})})
vm.runInContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/hooks/useSiteBasePath.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,hooks)
const parse=file=>ts.createSourceFile(file,fs.readFileSync(path.join(root,'src/admin/pages',file),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
const schedule=parse('SchedulingPage.tsx'),resorts=parse('ResortsPage.tsx')
let open;const candidates=[],links=[]
function scan(n){if(ts.isVariableDeclaration(n)&&n.name.getText(schedule)==='openBookingOrder')open=n.initializer;if(ts.isJsxAttribute(n)&&n.name.text==='onClick'&&n.initializer?.expression?.getText(schedule).includes('`${ordersUrl}?search='))candidates.push(n.initializer.expression);ts.forEachChild(n,scan)}scan(schedule)
function scanLinks(n){if(ts.isJsxElement(n)&&n.openingElement.tagName.getText(resorts)==='Link'&&n.openingElement.attributes.getText(resorts).includes('to={campusesUrl}'))links.push(n);ts.forEachChild(n,scanLinks)}scanLinks(resorts)
assert.ok(open);assert.equal(candidates.length,2);assert.equal(links.length,3)
for(code of ['school-a','school-b']){
 const calls=[],ordersUrl=hooks.exports.useSiteLink('/console/orders'),campusesUrl=hooks.exports.useSiteLink('/console/campuses')
 const ctx=vm.createContext({React,exports:{},ordersUrl,campusesUrl,adminMe:{user:{}},isCampusOrderViewer:true,navigate:url=>calls.push(url),setSelectedDate(){},setSelectedOrderId:id=>calls.push(id),order:{group_id:7,order_number:'QA #/?'},Link:({to,children,...props})=>React.createElement('a',{href:to,...props},children)})
 const run=s=>vm.runInContext(ts.transpileModule(s,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React}}).outputText,ctx)
 run('exports.open='+open.getText(schedule));ctx.exports.open({date:'2026-11-01',group_id:7,sn:'QA #/?'})
 assert.equal(calls.pop(),ordersUrl+'?search='+encodeURIComponent('QA #/?'))
 for(const click of candidates){run('exports.click='+click.getText(schedule));ctx.exports.click();assert.equal(calls.pop(),ordersUrl+'?search='+encodeURIComponent('QA #/?'))}
 ctx.isCampusOrderViewer=false;ctx.exports.open({date:'2026-11-01',group_id:7});assert.equal(calls.pop(),7,'HQ still opens inline detail')
 for(const link of links){run('exports.link='+link.getText(resorts));assert.ok(renderToStaticMarkup(ctx.exports.link).includes('href="/'+code+'/console/campuses"'))}
}
console.log('PASS real Console navigation callbacks/links: both schools, campus-view order navigation, query escaping and HQ inline details')
