const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
const text=fs.readFileSync(path.join(root,'src/pages/BookingFlowPage.tsx'),'utf8'),source=ts.createSourceFile('booking.tsx',text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let callback
function visit(node){if(ts.isVariableDeclaration(node)&&node.name.getText(source)==='canGoNext')callback=node.initializer.arguments[0].getText(source);ts.forEachChild(node,visit)}visit(source)
const util={exports:{}};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/utils/cartService.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,util)
const ready={currentStep:3,createdReservationIds:[],submittedReservation:null,discountPreview:{total:100},contactInfo:{name:'QA',phone:'0900000000',messengerType:'LINE',messengerId:'qa'},referralSourceValue:'Instagram',staffLinkInfo:null,acceptedPolicy:true,...util.exports}
const check=cart=>vm.runInNewContext(ts.transpileModule(`(${callback})()`,{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText,{...ready,cart})
for(const [total,price] of [[null,null],[NaN,100],[100,null],[100,Infinity],[undefined,100]])assert.equal(check([{totalPrice:total,courses:[{price}]}]),false,'折扣預覽不能繞過重選日期／價格')
assert.equal(check([{totalPrice:0,courses:[{price:0}]}]),true)
assert.equal(check([{totalPrice:15123,courses:[{price:15123}]}]),true)
console.log('PASS actual booking canGoNext: missing/nonfinite rebook prices blocked even with discount preview; legitimate zero allowed')
