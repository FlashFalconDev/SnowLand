const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),render=req('react-dom/server').renderToStaticMarkup
const source=ts.createSourceFile('booking.tsx',fs.readFileSync(path.join(root,'src/pages/BookingFlowPage.tsx'),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
const declarations=source.statements.filter(n=>ts.isVariableStatement(n)||ts.isFunctionDeclaration(n)&&['Step1ServiceSelection','Step2SkiConfiguration','Step4Complete'].includes(n.name?.text)).map(n=>n.getText(source)).join('\n')
for(const language of ['en','ja']){
 const locale=require('./helpers/site-locale-harness.cjs')(React,language),selected=[]
 const ctx=vm.createContext({React,useSiteLocale:locale.useSiteLocale,useEffect(){},useNavigate:()=>()=>{},useSiteLink:s=>'/snowland'+s,Check:()=>null})
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
 const complete=render(ctx.Step4Complete({flow:'collecting_class',notice:''}))
 assert.ok(complete.includes(language==='en'?'No payment is needed now':'現在、お支払いは不要です'))
 assert.ok(complete.includes('/snowland/membership/orders'))
}
console.log('PASS real booking components: ja/en service choices and waiting-class completion preserve service IDs, member route and no-payment meaning')
