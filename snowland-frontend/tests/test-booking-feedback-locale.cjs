const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),render=req('react-dom/server').renderToStaticMarkup
const source=fs.readFileSync(path.join(root,'src/pages/BookingFlowPage.tsx'),'utf8'),ast=ts.createSourceFile('flow.tsx',source,99,true,ts.ScriptKind.TSX)
const declarations=ast.statements.filter(n=>ts.isVariableStatement(n)||ts.isFunctionDeclaration(n)&&n.name?.text==='Step2SkiConfiguration').map(n=>n.getText(ast)).join('\n')
let overlay
function walk(n){if(ts.isJsxSelfClosingElement(n)&&n.tagName.getText(ast)==='LoadingOverlay')overlay=n.getText(ast);ts.forEachChild(n,walk)}walk(ast);assert.ok(overlay)
const loader=fs.readFileSync(path.join(root,'src/components/ui/LoadingOverlay.tsx'),'utf8')
const memberAst=ts.createSourceFile('member.jsx',fs.readFileSync(path.join(root,'src/pages/site/MembershipPage.jsx'),'utf8'),99,true,ts.ScriptKind.JSX)
let memberNotice
function noticeWalk(n){if(ts.isJsxElement(n)&&n.openingElement.attributes.properties.some(p=>p.name?.getText(memberAst)==='role'&&p.initializer?.text==='status')&&n.getText(memberAst).includes("setNotice('')"))memberNotice=n.getText(memberAst);ts.forEachChild(n,noticeWalk)}noticeWalk(memberAst);assert.ok(memberNotice)
const find=(node,p)=>{if(!node||typeof node!=='object')return null;if(p(node))return node;for(const c of React.Children.toArray(node.props?.children)){const result=find(c,p);if(result)return result}return null}
for(const language of ['en','ja']){
 const locale=require('./helpers/site-locale-harness.cjs')(React,language),t=(s,v)=>locale.translateSiteText(language,s,v),events=[]
 function feedbackKeys(n){if(ts.isCallExpression(n)&&['showToast','setLoadingMessage','setLoadingDetail','startLoading','setCompletionNotice','setPaymentInfoError'].includes(n.expression.getText(ast))){function check(arg){if(ts.isStringLiteral(arg)&&/[\u3400-\u9fff]/.test(arg.text))assert.notEqual(t(arg.text),arg.text,language+' missing dynamic feedback '+arg.text);ts.forEachChild(arg,check)}n.arguments.forEach(check)}ts.forEachChild(n,feedbackKeys)}feedbackKeys(ast)
 const loaderContext=vm.createContext({exports:{},React,require:name=>name==='react'?React:name.includes('SiteLocale')?locale:{Loader2:()=>null}})
 vm.runInContext(ts.transpileModule(loader,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,loaderContext)
 const ctx=vm.createContext({React,exports:{},useSiteLocale:locale.useSiteLocale,useEffect(){},Loader2:()=>null,t,LoadingOverlay:loaderContext.exports.default,
  loadingMessage:'正在建立預約',loadingDetail:t('目前共 {groups} 組預約、{lessons} 堂課。多組排課需要逐一確認教練與時段。',{groups:2,lessons:3}),loadingSteps:['確認課程與價格','建立訂單','整理付款資訊'],loadingStepIndex:1})
 vm.runInContext(ts.transpileModule(declarations+`\nexports.overlay=()=>(${overlay});exports.slotLabel=getPurchasedEquipmentSlotLabel;`,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,ctx)
 let html=render(ctx.exports.overlay())
 for(const raw of ['正在建立預約','確認課程與價格','整理付款資訊','多組預約排課'])assert.ok(!html.includes(raw))
 assert.ok(html.includes(language==='en'?'Creating your booking':'予約を作成中'))
 assert.ok(html.includes('2')&&html.includes('3'))
 ctx.loadingMessage='';assert.equal(render(ctx.exports.overlay()),'')
 const props={field:'timeSlot',courseCategories:[],courseTypes:[],resorts:[],coaches:[],templates:[{id:7,shared_class_enabled:true}],sessions:[{id:1,start_time:'09:00',end_time:'12:00',shared_class:{status:'collecting',registered_students:1,minimum_students:3,remaining_capacity:2}}],state:{selectedCourseTemplate:7,selectedDate:'2026-11-20',selectedTimeSlot:null},actions:{setSelectedTimeSlot:id=>events.push(id)}}
 let tree=ctx.Step2SkiConfiguration(props);html=render(tree)
 assert.ok(html.includes(language==='en'?'Joining 1/3':'募集中 1/3'))
 assert.ok(html.includes('09:00')&&html.includes('12:00'));find(tree,n=>n.type==='button').props.onClick();assert.deepEqual(events,[1])
 props.sessions[0].shared_class.status='ready';html=render(ctx.Step2SkiConfiguration(props));assert.ok(html.includes(language==='en'?'Class formed':'開催確定'))
 props.sessions[0].shared_class=null;html=render(ctx.Step2SkiConfiguration(props));assert.ok(html.includes(language==='en'?'New class':'新規クラス'))
 props.sessions=[];html=render(ctx.Step2SkiConfiguration(props));assert.ok(html.includes(language==='en'?'No time slots':'予約できる時間帯はありません'))
 const slot={day_type:'previous_day',start_time:'15:00',end_time:'15:30'},dates=['2026-11-20','2026-11-21']
 assert.ok(ctx.exports.slotLabel(slot,dates).includes('課程前一日'),'Stored snapshot label remains unchanged without a translator')
 const label=ctx.exports.slotLabel(slot,dates,t);assert.ok(label.includes('2026/11/19')&&label.includes('15:00')&&!label.includes('課程前一日')&&!label.includes('費用只加'))
 assert.ok(ctx.exports.slotLabel({label:'QA custom slot'},[],t).includes('QA custom slot'),'Custom CMS labels stay original')
 for(const message of ['資料載入失敗','頁面驗證已失效，請重新整理後再試；本次操作未送出。','無法確認登出，請重試；確認成功前，請勿將裝置交給他人。','訂單已建立，但付款資訊暫時無法取得','匯款資料已送出，等待客服核對；目前尚未確認付款成功。'])assert.notEqual(t(message),message)
 const privateMessage='QA custom server message <unchanged>';assert.ok(t('預約失敗：{message}',{message:privateMessage}).includes(privateMessage))
 const noticeCtx=vm.createContext({React,exports:{},t,notice:'無法確認登出，請重試；確認成功前，請勿將裝置交給他人。',setNotice:()=>events.push('notice-dismiss')})
 vm.runInContext(ts.transpileModule(`exports.notice=()=>(${memberNotice})`,{compilerOptions:{jsx:ts.JsxEmit.React}}).outputText,noticeCtx)
 assert.ok(render(noticeCtx.exports.notice()).includes(language==='en'?'Sign-out could not be confirmed':'ログアウトを確認できませんでした'))
 find(noticeCtx.exports.notice(),n=>n.type==='button').props.onClick();assert.ok(events.includes('notice-dismiss'))
}
console.log('PASS actual booking loading overlay and shared time-slot branches en/ja; original counts/times/select IDs, safe errors and private server text preserved')
