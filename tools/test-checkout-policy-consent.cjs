const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/components/booking/CheckoutPolicyConsent.tsx'),'utf8')
const policies={documents:{terms:{title:'服務條款',body:'QA長文件',version:'terms-v1'},privacy:{title:'隱私政策',body:'QA隱私文件',version:'privacy-v1'}}}
const all=node=>!node||typeof node!=='object'?[]:[node,...React.Children.toArray(node.props?.children).flatMap(all)]
function harness(language='zh-Hant'){
 const states=[],refs=[],effects=[],layouts=[],changes=[];let cursor=0,refCursor=0,queue=[],calls=0,closed=0,focused=0
 const hooks={...React,useState(initial){const i=cursor++;if(!(i in states))states[i]=initial;return[states[i],value=>states[i]=typeof value==='function'?value(states[i]):value]},useRef(initial){const i=refCursor++;return refs[i]||(refs[i]={current:initial})},useEffect(fn,deps){effects.push({fn,deps})},useLayoutEffect(fn,deps){layouts.push({fn,deps})}}
 const locale=require('./helpers/site-locale-harness.cjs')(hooks,language)
 const tr=source=>locale.translateSiteText(language,source)
 const ctx=vm.createContext({React,exports:{},require:name=>name==='react'?hooks:name==='../../contexts/SiteLocale'?locale:name==='../../api/booking'?{fetchCheckoutPolicies(){calls++;return new Promise((resolve,reject)=>queue.push({resolve,reject}))}}:req(name)})
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,ctx)
 let prevEffects=[],prevLayouts=[]
 const run=(list,previous)=>list.map((effect,i)=>{if(!previous[i]||effect.deps.some((d,j)=>d!==previous[i].deps[j]))effect.fn();return effect})
 const render=()=>{cursor=0;refCursor=0;effects.length=0;layouts.length=0;const tree=ctx.exports.default({onChange:p=>changes.push(p)});prevEffects=run(effects,prevEffects);prevLayouts=run(layouts,prevLayouts);return tree}
 render();refs[1].current={showModal(){},close(){closed++}};refs[2].current={scrollHeight:2000,clientHeight:500,scrollTop:0}
 return{render,changes,calls:()=>calls,resolve:()=>queue.shift().resolve(policies),reject:()=>queue.shift().reject(Error('QA503')),flush:async()=>{await Promise.resolve();await Promise.resolve();await Promise.resolve()},nodes:()=>all(render()),open(title){all(render()).find(n=>n.type==='button'&&React.Children.toArray(n.props.children).join('')===tr('閱讀：')+title).props.onClick({currentTarget:{focus(){focused++}}});render()},scroll(){all(render()).find(n=>n.props?.['aria-label']===tr('條款正文')).props.onScroll({currentTarget:{scrollHeight:2000,scrollTop:1500,clientHeight:500}})},confirm(){const button=all(render()).find(n=>n.type==='button'&&n.props.children===tr('確認已閱讀'));assert.equal(button.props.disabled,false);button.props.onClick();render()},closed:()=>closed,focused:()=>focused}
}
;(async()=>{
 const app=harness();assert.equal(app.calls(),1);assert.ok(app.nodes().some(n=>n.props?.role==='status'));assert.equal(app.changes.at(-1),null)
 app.resolve();await app.flush();let nodes=app.nodes();assert.equal(nodes.filter(n=>n.type==='input').length,2);assert.ok(nodes.filter(n=>n.type==='input').every(n=>n.props.disabled))
 app.open('服務條款');assert.equal(app.nodes().find(n=>n.type==='button'&&n.props.children==='確認已閱讀').props.disabled,true)
 app.scroll();app.confirm();assert.equal(app.changes.at(-1),null)
 app.open('隱私政策');assert.equal(app.nodes().find(n=>n.type==='button'&&n.props.children==='確認已閱讀').props.disabled,true,'Second document must not inherit previous scroll acknowledgement')
 app.scroll();app.confirm();assert.equal(app.changes.at(-1).terms_version,'terms-v1');assert.equal(app.changes.at(-1).privacy_version,'privacy-v1')
 nodes=app.nodes();nodes.find(n=>n.type==='input').props.onChange();assert.equal(app.changes.at(-1),null,'Withdrawing either consent disables parent submission')
 app.open('服務條款');app.nodes().find(n=>n.type==='dialog').props.onCancel({preventDefault(){}});assert.equal(app.changes.at(-1),null);assert.ok(app.closed()>0&&app.focused()>0)
 nodes=app.nodes();nodes.find(n=>n.type==='button'&&String(n.props.children).startsWith('重新載入最新')).props.onClick();app.render();assert.equal(app.calls(),2);assert.equal(app.changes.at(-1),null)
 app.reject();await app.flush();nodes=app.nodes();assert.ok(nodes.some(n=>n.props?.role==='alert'));assert.equal(nodes.filter(n=>n.type==='input').length,0)
 nodes.find(n=>n.type==='button'&&n.props.children==='重新載入條款').props.onClick();app.render();app.resolve();await app.flush();assert.equal(app.nodes().filter(n=>n.type==='input').length,2)
 const flow=fs.readFileSync(path.join(root,'src/pages/BookingFlowPage.tsx'),'utf8');assert.equal((flow.match(/policy_acceptance: policyAcceptance/g)||[]).length,2)
 assert.match(fs.readFileSync(path.join(root,'src/pages/site/PolicyPage.jsx'),'utf8'),/queryFn: fetchCheckoutPolicies/)
 for(const language of ['en','ja']){
  const translated=harness(language);translated.resolve();await translated.flush()
  const expected=language==='en'?'Confirm I have read this':'確認しました'
  translated.open('服務條款')
  assert.equal(translated.nodes().find(n=>n.type==='button'&&n.props.children===expected).props.disabled,true)
  assert.ok(translated.nodes().some(n=>n.props?.children==='QA長文件'),'Legal document body is never machine translated')
  translated.scroll();translated.confirm();assert.equal(translated.changes.at(-1),null)
  translated.open('隱私政策');translated.scroll();translated.confirm()
  assert.equal(translated.changes.at(-1).terms_version,'terms-v1')
  assert.equal(translated.changes.at(-1).privacy_version,'privacy-v1')
 }
 console.log('PASS actual checkout consent callbacks: independent scroll gates, withdrawal, Escape, version proof, reload reset, 503 retry and both submit paths (component contract, not browser QA)')
})().catch(error=>{console.error(error);process.exitCode=1})
