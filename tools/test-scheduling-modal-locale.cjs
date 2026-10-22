const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),render=req('react-dom/server').renderToStaticMarkup
function load(file,locale){const ctx={React,exports:{},require:name=>name==='react'?React:name==='lucide-react'?new Proxy({},{get:()=>()=>null}):locale};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText,ctx);return ctx.exports.default}
function buttons(node,result=[]){if(!node||typeof node!=='object')return result;if(node.type==='button')result.push(node);for(const child of React.Children.toArray(node.props?.children))buttons(child,result);return result}
const booking=ts.createSourceFile('booking.tsx',fs.readFileSync(path.join(root,'src/pages/BookingFlowPage.tsx'),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let advanced
function walk(node){if(ts.isJsxSelfClosingElement(node)&&node.tagName.getText(booking)==='ConfirmModal'&&node.getText(booking).includes("title={t('嘗試進階排課？')}"))advanced=node;ts.forEachChild(node,walk)}walk(booking);assert.ok(advanced)
for(const language of ['en','ja']){
 const locale=require('./helpers/site-locale-harness.cjs')(React,language),Failed=load('components/booking/SchedulingFailedModal.tsx',locale),Confirm=load('components/ui/ConfirmModal.tsx',locale),calls=[]
 const props={isOpen:true,message:'QA私人錯誤內容',conflictDetails:{identifier:'QA課程原始名稱',reason:'QA自訂原因',suggestions:{'2026-12-01':{'09:00-12:00':{available_sessions:1}},'2026-12-02':{'13:00-16:00':{available_sessions:1}}}},isSuggestionBookable:date=>date==='2026-12-01',onClose:()=>calls.push('close'),onWaitForStaff:()=>calls.push('staff'),onChangeDate:()=>calls.push('date'),onTrySuperSchedule:()=>calls.push('advanced'),onSelectSuggestion:(...args)=>calls.push(args)}
 const tree=Failed(props),html=render(tree)
 for(const privateText of ['QA私人錯誤內容','QA課程原始名稱','QA自訂原因'])assert.ok(html.includes(privateText))
 assert.ok(html.includes(language==='en'?'Scheduling unsuccessful':'日程調整ができませんでした'))
 assert.ok(!html.includes('2026-12-02'),'Unbookable suggestions remain hidden')
 assert.ok(html.includes('max-h-[calc(100dvh-2rem)]')&&html.includes('min-h-0 flex-1 overflow-y-auto'))
 for(const button of buttons(tree))button.props.onClick()
 assert.deepEqual(calls,['close',['2026-12-01','09:00-12:00'],'staff','date','advanced'],'Translated controls preserve all original callback arguments')
 const empty=render(Failed({...props,conflictDetails:{},onChangeDate:undefined,onTrySuperSchedule:undefined}))
 assert.ok(empty.includes(language==='en'?'No alternative times are available':'候補の時間帯はありません'))
 assert.ok(!empty.includes(language==='en'?'Choose another date</button>':'別の日付を選ぶ</button>'))
 const actualFailure=render(Failed({...props,message:'訂單已建立但自動排課失敗，請等待課服聯繫或改選其他日期',conflictDetails:{identifier:'於「QA雪場」的「QA單板」',reason:'符合條件的教練都被排除（語言/雪場/課程/能力等級任一項不符）'}}))
 assert.ok(!actualFailure.includes('訂單已建立但自動排課失敗'))
 assert.ok(!actualFailure.includes('符合條件的教練都被排除'))
 assert.ok(!actualFailure.includes('於「QA雪場」的「QA單板」'))
 assert.ok(actualFailure.includes('QA雪場')&&actualFailure.includes('QA單板'),'Keep original resort/course names')
 const transitions=[],ctx={React,t:locale.useSiteLocale().t,ConfirmModal:Confirm,superConfirmOpen:true,setSuperConfirmOpen:value=>transitions.push(value),setSchedulingFailed:fn=>transitions.push(fn({isOpen:false}).isOpen)}
 vm.runInNewContext(ts.transpileModule('function dialog(){return ('+advanced.getText(booking)+')}',{fileName:'dialog.tsx',compilerOptions:{jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText,ctx)
 const confirmProps=ctx.dialog().props,confirmHtml=render(React.createElement(Confirm,confirmProps))
 assert.ok(confirmHtml.includes(language==='en'?'Try flexible scheduling?':'柔軟な日程調整を試しますか'))
 assert.ok(confirmHtml.includes(language==='en'?'different instructor each day':'日によって担当インストラクター'))
 confirmProps.onCancel();assert.deepEqual(transitions,[false,true],'Cancelling returns to failed scheduling without retrying or creating an order')
 console.log('PASS actual scheduling failure/advanced-confirm locale and original callbacks',language)
}
