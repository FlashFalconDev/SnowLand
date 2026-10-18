const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript'),React=req('react'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/admin/pages/OrdersPage.tsx'),'utf8'),ast=ts.createSourceFile('OrdersPage.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
const drawer=ast.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='OrderDetailDrawer')
assert.ok(drawer)
let payment,feedback,editable,missingCoach,saveButton,retryable,scheduleButton
function walk(node){
 if(ts.isVariableDeclaration(node)&&node.name.getText(ast)==='paymentPill')payment=node.initializer
 if(ts.isJsxExpression(node)&&node.expression?.getText(ast).startsWith('saveMutation.isError &&'))feedback=node.expression
 if(ts.isVariableDeclaration(node)&&node.name.getText(ast)==='canEditCourse')editable=node.initializer
 if(ts.isVariableDeclaration(node)&&node.name.getText(ast)==='canScheduleUnassigned')retryable=node.initializer
 if(ts.isJsxExpression(node)&&node.expression?.getText(ast).startsWith('selectedCoachMissing &&'))missingCoach=node.expression
 if(ts.isJsxElement(node)&&node.openingElement.tagName.getText(ast)==='button'&&node.children.some(child=>ts.isJsxText(child)&&child.text.includes('只儲存')))saveButton=node
 if(ts.isJsxElement(node)&&node.openingElement.tagName.getText(ast)==='button'&&node.children.some(child=>ts.isJsxText(child)&&child.text.includes('儲存並 AI 排課')))scheduleButton=node
 ts.forEachChild(node,walk)
}
walk(drawer)
assert.ok(payment)
const ctx=vm.createContext({React,exports:{},order:{payment_status:'pending'},paymentStatus:'paid',getPaymentPill:status=>({label:status})})
vm.runInContext(ts.transpileModule('exports.payment='+payment.getText(ast),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,ctx)
assert.equal(ctx.exports.payment.label,'pending','Header must show saved payment status, not an uncommitted paid draft')
assert.ok(feedback,'Keep a persistent error in the editor after the toast disappears')
for(const failed of [true,false]){
 ctx.saveMutation={isError:failed,error:{response:{data:{msg:'QA collision'}}}}
 vm.runInContext(ts.transpileModule('exports.render=()=>('+feedback.getText(ast)+')',{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,ctx)
 const html=renderToStaticMarkup(ctx.exports.render())
 if(failed){assert.ok(html.includes('role="alert"'));assert.ok(html.includes('尚未儲存'));assert.ok(html.includes('QA collision'))}
 else assert.equal(html,'')
}
assert.ok(saveButton.openingElement.attributes.getText(ast).includes('min-h-11'),'Save is at least a 44px touch target')
ctx.editing=true
for(const status of ['created','completed','cancelled','deleted']){
 ctx.r={status,shared_course_class_id:null}
 vm.runInContext('exports.editable='+editable.getText(ast),ctx)
 assert.equal(ctx.exports.editable,status==='created')
}
ctx.selectedCoachMissing=true;ctx.selectedCoachId=5;ctx.r={preferred_coach_id:null,preferred_coach:null}
vm.runInContext(ts.transpileModule('exports.missing=()=>('+missingCoach.getText(ast)+')',{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,ctx)
assert.ok(renderToStaticMarkup(ctx.exports.missing()).includes('所選教練已不可排，請重新選擇'),'Do not label an unsaved rejected coach as the currently assigned coach')
assert.ok(retryable);assert.ok(scheduleButton)
for(const status of ['created','manually_assigned','completed','cancelled','deleted','pending_coach_confirmation']){
 ctx.order={reservations:[{status,preferred_coach_id:null,shared_course_class_id:null,bookings:[{id:1}]}]}
 vm.runInContext(ts.transpileModule('exports.retryable='+retryable.getText(ast),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,ctx)
 assert.equal(ctx.exports.retryable,status==='created')
}
const disabled=scheduleButton.openingElement.attributes.properties.find(prop=>prop.name?.text==='disabled').initializer.expression
ctx.saveMutation={isPending:false};ctx.hasOrderChanges=false;ctx.invalidBooking=null;ctx.canScheduleUnassigned=true
vm.runInContext('exports.disabled='+disabled.getText(ast),ctx);assert.equal(ctx.exports.disabled,false,'An unassigned saved course can be scheduled without a fake edit')
ctx.canScheduleUnassigned=false;vm.runInContext('exports.disabled='+disabled.getText(ast),ctx);assert.equal(ctx.exports.disabled,true)
ctx.canScheduleUnassigned=true;ctx.saveMutation.isPending=true;vm.runInContext('exports.disabled='+disabled.getText(ast),ctx);assert.equal(ctx.exports.disabled,true)
for(const text of ['不指定（等待排課）','不會在背景立即重排','人工排定已鎖定教練'])assert.ok(source.includes(text))
console.log('PASS actual order drawer: saved payment badge remains authoritative; rejected edits keep a persistent unsaved error')
