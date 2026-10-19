const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),localRequire=Module.createRequire(path.join(root,'package.json')),React=localRequire('react'),ts=localRequire('typescript')
let cart=[];const edits=[]
const serviceModule=new Module(path.join(root,'src/utils/cartService.ts'),module)
serviceModule._compile(ts.transpileModule(fs.readFileSync(path.join(root,'src/utils/cartService.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,serviceModule.id)
const hooks={...React,useState:initial=>[initial,()=>{}]}
const context=vm.createContext({React,exports:{},require:name=>{
  if(name==='react')return hooks
  if(name==='lucide-react')return new Proxy({},{get:()=>()=>null})
  if(name==='@/store/bookingStore')return{useBookingStore:select=>select({cart,removeFromCart(){},removeCourseFromGroup(){}})}
  if(name==='@/utils/cartService')return serviceModule.exports
  return {__esModule:true,default:()=>null}
}})
vm.runInContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/components/booking/CartModal.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText,context)
function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of React.Children.toArray(node.props?.children)){const found=find(child,predicate);if(found)return found}return null}
function render(total,price,extra={}){cart=[{id:'qa-rebook',resortName:'QA雪場',courseCategory:'QA單板',coach:'any',coachName:'不指定',peopleCount:1,abilityLevel:'no_exp',language:'zh',equipmentOption:'own_equipment',totalPrice:total,courses:[{courseTemplateName:'QA半天',date:'2026-11-06',timeSlotStart:'09:00',timeSlotEnd:'12:00',price}],...extra}];return context.exports.default({isOpen:true,onClose(){},onConfirm(){},onEditGroup:id=>edits.push(id)})}
for(const [total,price] of [[null,null],[undefined,100],[NaN,100],[100,null],[100,Infinity]]){
  const tree=render(total,price),button=find(tree,node=>node.type==='button'&&node.props.children==='確認預約')
  assert.equal(button.props.disabled,true)
  assert.match(JSON.stringify(tree),/重新確認價格/)
}
for(const [total,price] of [[0,0],[100,100]])assert.equal(find(render(total,price),node=>node.type==='button'&&node.props.children==='確認預約').props.disabled,false)
const tree=render(null,null),before=JSON.stringify(cart)
find(tree,node=>node.type==='button'&&node.props.children==='修改這組課程').props.onClick()
assert.deepEqual(edits,['qa-rebook']);assert.equal(JSON.stringify(cart),before)
assert.match(JSON.stringify(tree),/不指定/);assert.match(JSON.stringify(tree),/待重新試算/)
assert.match(JSON.stringify(render(null,null,{rebookSource:{reservationId:42,peopleCount:2,learnerCount:2}})),/保險資料與聲明簽名須重新確認/)
assert.match(JSON.stringify(render(100,100,{rebookLearnersReset:true})),/人數已變更，本次不自動沿用學員/)
console.log('PASS actual rebook CartModal: missing/nonfinite prices blocked, legitimate zero allowed, explicit reprice guidance and edit callback without cart mutation')
const photoTree=JSON.stringify(render(15123,15123,{serviceType:'photo',courseCategory:'影像方案',rebookSource:{learnerCount:1}}))
assert.match(photoTree,/攝影師/);assert.match(photoTree,/預約數量/)
assert.ok(!photoTree.includes('滑雪程度'))
for(const label of ['能力','裝備','語言','教練'])assert.ok(!photoTree.includes(`"label":"${label}"`),`攝影購物車不應顯示${label}`)
