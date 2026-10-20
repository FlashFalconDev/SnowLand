const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/BookingFlowPage.tsx'),'utf8'),ast=ts.createSourceFile('booking.tsx',source,99,true,ts.ScriptKind.TSX)
let recovery,prepare,coachHint,coachEmpty
function walk(node){if(ts.isJsxElement(node)){const text=node.getText(ast);if(text.startsWith('<div role="alert"')&&text.includes('retryPaymentInfo'))recovery=text;if(text.startsWith('<section className="mx-auto max-w-2xl space-y-4')&&text.includes('staffConsoleUrl'))prepare=text}ts.forEachChild(node,walk)}walk(ast)
assert.ok(recovery&&prepare,'Extract actual product JSX, not a separate implementation')
function coachCopy(node){if(ts.isJsxElement(node)&&node.openingElement.tagName.getText(ast)==='p'){const text=node.getText(ast);if(text.includes('由系統依照時間、等級與雪場'))coachHint=text;if(text.includes('目前沒有符合篩選條件'))coachEmpty=text}ts.forEachChild(node,coachCopy)}coachCopy(ast)
assert.ok(coachHint&&coachEmpty)
const declarations=ast.statements.filter(n=>ts.isVariableStatement(n)||ts.isFunctionDeclaration(n)&&n.name?.text==='Step2SkiConfiguration').map(n=>n.getText(ast)).join('\n')
const find=(node,p)=>{if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,p);if(result)return result}return null}
for(const language of ['en','ja']){
 const locale=require('./helpers/site-locale-harness.cjs')(React,language),t=(text,values)=>locale.translateSiteText(language,text,values),events=[]
 const context=vm.createContext({React,exports:{},useSiteLocale:locale.useSiteLocale,useEffect(){},ChevronLeft:()=>null,ChevronRight:()=>null,t,
  paymentInfoError:'',createdReservationIds:[101,102],isSubmitting:false,membershipUrl:'/snowland/membership/orders',retryPaymentInfo:()=>events.push('retry'),
  cart:[{id:'qa',resortName:'QA雪場',peopleCount:2,totalPrice:9000,courses:[{courseTemplateId:1,courseTemplateName:'QA課程',date:'2026-11-20',timeSlotStart:'09:00',timeSlotEnd:'12:00'}]}],formatCurrency:value=>'NT$ '+value.toLocaleString(),handleEditCartGroup:id=>events.push(id),handleAddCartGroup:()=>events.push('add'),staffConsoleUrl:'/snowland/console/booking-links'})
 vm.runInContext(ts.transpileModule(declarations+`\nexports.recovery=()=>(${recovery});exports.prepare=()=>(${prepare});`,{fileName:'secondary.tsx',compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
 let tree=context.exports.recovery(),html=renderToStaticMarkup(tree)
 assert.ok(html.includes(t('請勿再次送出訂單。'))&&html.includes('101、102'))
 assert.ok(html.includes('/snowland/membership/orders'))
 const retry=find(tree,n=>n.type==='button');assert.equal(retry.props.disabled,false);retry.props.onClick();assert.deepEqual(events,['retry'])
 context.isSubmitting=true;tree=context.exports.recovery();assert.equal(find(tree,n=>n.type==='button').props.disabled,true)
 assert.ok(renderToStaticMarkup(tree).includes(language==='en'?'Loading…':'読み込み中…'),'Busy retry copy is translated')
 html=renderToStaticMarkup(context.exports.prepare());assert.ok(html.includes('QA雪場')&&html.includes('QA課程')&&html.includes('9,000'))
 assert.ok(html.includes(t('回後台建立連結'))&&!html.includes(' 人'))
 find(context.exports.prepare(),n=>n.type==='button'&&n.props.children===t('修改這組課程')).props.onClick();assert.ok(events.includes('qa'))
 const selected=[],months=[],date='2026-11-20'
 const props={field:'date',courseCategories:[],courseTypes:[],resorts:[],coaches:[],templates:[{id:7,shared_class_enabled:true}],sessions:[],state:{selectedCourseTemplate:7,peopleCount:1,calendarMonth:new Date(2026,10,1),selectedCourseDates:[date]},actions:{toggleCourseDate:value=>selected.push(value),setCalendarMonth:value=>months.push(value)},dateInfo:{course_start_date:'2026-11-20',course_end_date:'2027-04-30',shared_class_dates:{[date]:[{status:'collecting',registered_students:1,minimum_students:3,remaining_capacity:2}]}}}
 tree=context.Step2SkiConfiguration(props);html=renderToStaticMarkup(tree)
 assert.ok(html.includes(t('{registered}/{minimum} 湊班',{registered:1,minimum:3})))
 const day=find(tree,n=>n.type==='button'&&n.props['aria-label']?.startsWith(date));assert.equal(day.props['aria-pressed'],true);day.props.onClick();assert.equal(selected[0],date)
 const next=find(tree,n=>n.type==='button'&&n.props['aria-label']===t('月曆下一個月'));next.props.onClick();assert.equal(months[0].getMonth(),11)
 assert.ok(html.includes(t('不可預約')),'Disabled date accessibility text is translated')
 props.field='equipment';props.state.equipmentOption='own_equipment'
 tree=context.Step2SkiConfiguration(props);html=renderToStaticMarkup(tree)
 assert.ok(html.includes(language==='en'?'I will bring my own equipment':'自分の用具を持参します'))
 assert.ok(!html.includes('您已自行安排裝備')&&!html.includes('另計費用，費用只加在第一天課程'))
 const hints=vm.createContext({React,exports:{},t,state:{selectedLanguage:'zh'},canSelectAnyCoach:true,currentTemplateHasCoachRestriction:false,languageRequiresCoach:()=>false})
 vm.runInContext(ts.transpileModule(`exports.hint=()=>(${coachHint});exports.empty=()=>(${coachEmpty});`,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,hints)
 for(const key of ['hint','empty'])assert.ok(!/[\u3400-\u9fff]/.test(language==='en'?renderToStaticMarkup(hints.exports[key]()):''),'English instructor guidance must not fall back to Chinese')
 assert.ok(renderToStaticMarkup(hints.exports.hint()).includes(language==='en'?'schedule':'日時'))
 assert.ok(renderToStaticMarkup(hints.exports.empty()).includes(language==='en'?'No instructors':'条件'))
 for(const [any,restricted,required] of [[false,false,true],[true,true,false]]){
  hints.canSelectAnyCoach=any;hints.currentTemplateHasCoachRestriction=restricted;hints.languageRequiresCoach=()=>required
  for(const key of ['hint','empty']){const copy=renderToStaticMarkup(hints.exports[key]());assert.ok(!copy.includes('由系統')&&!copy.includes('目前沒有')&&!copy.includes('不可選擇'))}
 }
}
console.log('PASS actual booking secondary JSX en/ja: payment reload/busy/no-resubmit, staff cart preservation, shared calendar state/date/month callbacks')
