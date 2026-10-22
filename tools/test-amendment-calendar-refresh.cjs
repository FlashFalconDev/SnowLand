const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/admin/components/OrderAmendmentDialog.tsx'),'utf8'),ast=ts.createSourceFile('OrderAmendmentDialog.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let confirm
function walk(node){if(ts.isVariableDeclaration(node)&&node.name.getText(ast)==='confirm')confirm=node.initializer;ts.forEachChild(node,walk)}walk(ast);assert.ok(confirm)
const keys=[],ctx=vm.createContext({exports:{},draft:{},quote:{quote_token:'qa'},reviewed:true,reason:'QA改期',busy:{current:false},orderId:1,key:{current:'qa'},reschedule:false,confirmOrderAmendment:async()=>({id:1}),setPending(){},setError(){},setResult(){},setUncertain(){},qc:{invalidateQueries:({queryKey})=>keys.push(queryKey.join('/'))}})
vm.runInContext(ts.transpileModule('exports.confirm='+confirm.getText(ast),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,ctx)
;(async()=>{
 await ctx.exports.confirm();for(const key of ['admin/orders','admin/bookings','admin/group-candidates'])assert.ok(keys.includes(key),`Saving a date change must refresh ${key}, not leave the open calendar stale`)
 keys.length=0;ctx.confirmOrderAmendment=async()=>{throw {response:{status:409}}};ctx.errorMessage=()=> 'QA衝突';ctx.setQuote=()=>{};ctx.setReviewed=()=>{};ctx.crypto={randomUUID:()=> 'qa-retry'}
 await ctx.exports.confirm();assert.equal(keys.length,0,'A rejected date change must not pretend a new schedule was saved')
 console.log('PASS actual amendment confirm: successful save refreshes orders, live calendar and group candidates; rejected saves do not claim a new schedule')
})().catch(error=>{console.error(error);process.exitCode=1})
