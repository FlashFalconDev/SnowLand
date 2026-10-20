const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),render=req('react-dom/server').renderToStaticMarkup
const source=ts.createSourceFile('booking.tsx',fs.readFileSync(path.join(root,'src/pages/BookingFlowPage.tsx'),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
const declarations=source.statements.filter(n=>ts.isVariableStatement(n)||ts.isFunctionDeclaration(n)&&['Step1ServiceSelection','Step2SkiConfiguration','Step3Confirmation','Step4Complete'].includes(n.name?.text)).map(n=>n.getText(source)).join('\n')
const utils={exports:{}}
for(const file of ['cartService','settlementPreview'])vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/utils/'+file+'.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,utils)
for(const language of ['en','ja']){
 const locale=require('./helpers/site-locale-harness.cjs')(React,language),selected=[]
 const ctx=vm.createContext({React,...utils.exports,useSiteLocale:locale.useSiteLocale,useEffect(){},useNavigate:()=>()=>{},useSiteLink:s=>'/snowland'+s,Check:()=>null,Plus:()=>null,Pencil:()=>null,Trash2:()=>null,MapPin:()=>null,Calendar:()=>null,Users:()=>null,Languages:()=>null,User:()=>null,Package:()=>null,Clock:()=>null,CheckoutPolicyConsent:()=>null,CurrencySelection:()=>null,SettlementSummary:()=>null,settlementAmount:()=> 'JPY ¥ 4,500'})
 vm.runInContext(ts.transpileModule(declarations,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,ctx)
 const tree=ctx.Step1ServiceSelection({selected:'ski',onSelect:value=>selected.push(value)}),html=render(tree)
 assert.ok(html.includes(language==='en'?'Choose a service':'サービスを選択'))
 const visit=node=>{if(!node||typeof node!=='object')return;if(node.type==='button')node.props.onClick();else React.Children.forEach(node.props?.children,visit)}
 visit(tree);assert.deepEqual(selected,['ski','photo'],'Translated labels must keep service IDs')
 const counts=[]
 const people=ctx.Step2SkiConfiguration({field:'people',courseCategories:[],courseTypes:[],resorts:[],coaches:[],templates:[],sessions:[],state:{peopleCount:2,abilityLevelCounts:{}},actions:{setPeopleCount:n=>counts.push(n)}})
 const peopleHtml=render(people)
 assert.ok(peopleHtml.includes(language==='en'?'2 students':'受講者2名'))
 const walkPeople=node=>{if(!node||typeof node!=='object')return;if(node.type==='button')node.props.onClick();else React.Children.forEach(node.props?.children,walkPeople)}
 walkPeople(people);assert.deepEqual(counts,[1,2,3,4,5,6],'Localized student count buttons keep numeric values')
 const abilityChanges=[]
 const ability=ctx.Step2SkiConfiguration({field:'ability',courseCategories:[],courseTypes:[],resorts:[],coaches:[],templates:[],sessions:[],state:{selectedCourseCategoryName:'單板',peopleCount:2,abilityLevelCounts:{level1:1}},actions:{setAbilityLevelCount:(...args)=>abilityChanges.push(args)}})
 const abilityMarkup=render(ability)
 assert.ok(abilityMarkup.includes(language==='en'?'Can side slip on one edge.':'片側のエッジで横滑りができる。'))
 assert.ok(abilityMarkup.includes(language==='en'?'Number of students at Level 1':'レベル1の受講人数'))
 assert.ok(!abilityMarkup.includes('目前依')&&!abilityMarkup.includes('學員人數')&&!abilityMarkup.includes('等級 1'))
 const visitSelect=node=>{if(!node||typeof node!=='object')return;if(node.type==='select')node.props.onChange({target:{value:'2'}});else React.Children.forEach(node.props?.children,visitSelect)}
 visitSelect(ability);assert.deepEqual(abilityChanges[1],['level1',2],'Localized level selector retains enum and numeric count')
 ctx.ChevronLeft=ctx.ChevronRight=()=>null
 const dateProps={field:'date',courseCategories:[],courseTypes:[],resorts:[],coaches:[],templates:[],sessions:[],state:{calendarMonth:new Date(2026,10,1),peopleCount:2},actions:{}}
 const past=render(ctx.Step2SkiConfiguration({...dateProps,dateInfo:{course_start_date:'2000-01-01',course_end_date:'2000-02-01',booking_close_date:'2000-01-01'}}))
 assert.ok(past.includes(language==='en'?'The lesson period ended on 2000-02-01.':'レッスン期間は2000-02-01に終了しました。'))
 assert.ok(past.includes(language==='en'?'Bookings closed on 2000-01-01.':'予約受付は2000-01-01に終了しました。'))
 const future=render(ctx.Step2SkiConfiguration({...dateProps,dateInfo:{course_start_date:'2999-01-01',booking_open_date:'2999-01-01'}}))
 assert.ok(future.includes(language==='en'?'Bookings open on 2999-01-01.':'予約受付は2999-01-01に開始します。'))
 assert.ok(future.includes(language==='en'?'Select one or more lesson dates.':'受講日を1日または複数日選択してください。'))
 const complete=render(ctx.Step4Complete({flow:'collecting_class',notice:''}))
 assert.ok(complete.includes(language==='en'?'No payment is needed now':'現在、お支払いは不要です'))
 assert.ok(complete.includes('/snowland/membership/orders'))
 const props={cart:[{id:'qa-group',serviceType:'ski',courseCategory:'QA課程分類',resortName:'QA雪場',peopleCount:1,coach:'any',language:'zh',equipmentOption:'own_equipment',totalPrice:1000,courses:[{courseTemplateName:'QA課程名稱',date:'2026-12-01',price:1000}]}],contactInfo:{name:'QA私人姓名',email:'qa@example.test',phone:'QA手機',messengerType:'LINE',messengerId:'QA-ID'},messengerOptions:[],referralSourceOptions:[],currencyQuote:{currency:'JPY'},jpyPreview:{totalLabel:'4,500'},referrer:'其他',discountCode:'',setContactInfo(){},onEditGroup:id=>selected.push(id)}
 const before=JSON.stringify(props.cart)
 let checkout=ctx.Step3Confirmation(props),checkoutHtml=render(checkout)
 for(const original of ['QA課程分類','QA雪場','QA課程名稱','QA私人姓名','qa@example.test'])assert.ok(checkoutHtml.includes(original),'Private/CMS content stays unchanged')
 for(const translated of ['預約組 1','第 1 項課程','共 1 組預約','台幣計價基準合計','聯絡人姓名'])assert.ok(!checkoutHtml.includes(translated),'Checkout UI translates '+translated)
 assert.ok(checkoutHtml.includes('JPY ¥ 4,500')&&checkoutHtml.includes('NT$ 1,000'),'Translation does not mix JPY payable and TWD basis')
 const abilityHtml=render(ctx.Step3Confirmation({...props,cart:[{...props.cart[0],abilityLevelCounts:{no_exp:1,level2:1},abilityLevelName:'等級 0 1 人、等級 2 1 人'}]}))
 assert.ok(abilityHtml.includes(language==='en'?'Level 0: 1':'レベル0：1名'))
 assert.ok(!abilityHtml.includes('等級 0 1 人'))
 function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,p);if(result)return result}return null}
 const editButton=find(checkout,n=>n.type==='button'&&React.Children.toArray(n.props.children).includes(language==='en'?'Edit':'変更'))
 assert.ok(editButton,'Translated edit control remains available');editButton.props.onClick();assert.ok(selected.includes('qa-group'))
 assert.equal(JSON.stringify(props.cart),before)
 checkoutHtml=render(ctx.Step3Confirmation({...props,submittedReservation:{total_amount:1000,reservation_group_ids:[42],payment_methods:['bank_transfer'],payment_expires_at:'2026-12-01T01:00:00Z',payment_infos:[{reservation_group_id:42,total_amount:1000,settlement:{currency:'JPY',amount:4500},bank_info:{bank_name:'QA銀行',bank_account_holder:'QA戶名',bank_account_number:'QA-NOT-REAL'}}]},paymentMethod:'bank'}))
 assert.ok(checkoutHtml.includes('QA銀行')&&checkoutHtml.includes('QA-NOT-REAL'))
 assert.ok(checkoutHtml.includes(language==='en'?'Complete the transfer by':'までにお振り込みください'))
 assert.ok(!checkoutHtml.includes('前完成匯款'))
 console.log('PASS actual checkout locale: editable/submitted JPY states, private/CMS/bank preservation, native/TWD totals and payment deadline',language)
}
console.log('PASS real booking components: ja/en service choices and waiting-class completion preserve service IDs, member route and no-payment meaning')
