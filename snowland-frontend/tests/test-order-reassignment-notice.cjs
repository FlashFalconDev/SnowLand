const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript'),React=req('react'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/admin/pages/OrdersPage.tsx'),'utf8'),ast=ts.createSourceFile('OrdersPage.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let notice
function walk(n){if(ts.isJsxExpression(n)&&n.expression?.getText(ast).startsWith('isSchedulingFailed &&'))notice=n.expression;ts.forEachChild(n,walk)}
walk(ast);assert.ok(notice)
const ctx=vm.createContext({React,exports:{},isSchedulingFailed:true,order:{payment_status:'paid'}})
vm.runInContext(ts.transpileModule('exports.render=()=>('+notice.getText(ast)+')',{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,ctx)
const paid=renderToStaticMarkup(ctx.exports.render())
assert.match(paid,/已付款/);assert.match(paid,/重新指派/);assert.doesNotMatch(paid,/自動取消|重新下單|30 分鐘/)
ctx.order={payment_status:'unpaid'};const unpaid=renderToStaticMarkup(ctx.exports.render())
assert.doesNotMatch(unpaid,/已付款|30 分鐘/);assert.match(unpaid,/排課/)
ctx.isSchedulingFailed=false;assert.equal(renderToStaticMarkup(ctx.exports.render()),'')
console.log('PASS saved paid/unpaid reassignment notices; no hardcoded timeout or duplicate-order advice')
