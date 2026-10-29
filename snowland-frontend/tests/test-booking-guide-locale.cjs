const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/site/CourseHowToBookPage.jsx'),'utf8')
const ast=ts.createSourceFile('guide.jsx',source,99,true,ts.ScriptKind.JSX)
const copy=[]
function collect(node){
 if(ts.isPropertyAssignment(node)&&['title','desc'].includes(node.name.getText(ast))&&ts.isStringLiteral(node.initializer))copy.push(node.initializer.text)
 ts.forEachChild(node,collect)
}
collect(ast)
for(const language of ['en','ja']){
 const locale=require('./helpers/site-locale-harness.cjs')(React,language)
 for(const text of copy)assert.notEqual(locale.translateSiteText(language,text),text,`${language}: ${text}`)
 const context=vm.createContext({exports:{},require:name=>{
  if(name==='react')return React
  if(name==='framer-motion')return{motion:{article:({children,initial,whileInView,viewport,transition,...props})=>React.createElement('article',props,children)}}
  if(name.includes('contexts/SiteLocale'))return locale
  if(name.endsWith('/SiteLink'))return({to,children,...props})=>React.createElement('a',{...props,href:'/snowland'+to},children)
  if(name.endsWith('/SiteHeader')||name.endsWith('/SiteFooter'))return()=>null
  throw Error(name)
 }})
 vm.runInContext(ts.transpileModule(source,{fileName:'guide.jsx',compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,context)
 const html=renderToStaticMarkup(React.createElement(context.exports.default))
 assert.equal((html.match(/<article/g)||[]).length,6)
 for(const route of ['booking','cancellation-policy','faq','contact'])assert.ok(html.includes(`href="/snowland/${route}"`),route)
 for(const old of ['NT$300','NT$200','NT$500','70%','14 天','5小時','付款完成後預約即正式成立'])assert.ok(!html.includes(old),'No invented/static operating rules: '+old)
 assert.ok(html.includes(language==='en'?'Do not pay while':'まだお支払いしないでください'))
 assert.ok(html.includes(language==='en'?'Entering details does not mean insurance is active.':'入力のみでは保険加入は完了しません。'))
 assert.ok(html.includes(language==='en'?'Read cancellation and change policy':'キャンセル・変更規則を読む'))
}
console.log('PASS actual booking guide en/ja: six steps, tenant links, configurable payment/discount guidance and no legacy refund/price promises')
