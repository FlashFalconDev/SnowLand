const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/components/booking/CurrencySelection.tsx'),'utf8')
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,p);if(result)return result}return null}
function setup({fail=false,choices=[{code:'TWD',rate:'1.00000000'},{code:'JPY',rate:'4.50000000'}]}={}){
 const states=[],effects=[],pending=[],calls=[],changes=[],ready=[];let stateIndex=0,effectIndex=0
 const props={clientCode:'snowland',value:{currency:'TWD',rate:'1.00000000'},onChange(value){changes.push(value);props.value=value},onReadyChange:value=>ready.push(value)}
 const context=vm.createContext({React,exports:{},AbortController,setTimeout:()=>0,clearTimeout(){},fetch:async(url,options)=>{calls.push({url,options});if(fail)throw Error('QA offline');return{ok:true,json:async()=>({base_currency:'TWD',currencies:choices})}},require(name){
  if(name==='react')return{...React,useId:()=> 'currency-qa',useState(initial){const slot=stateIndex++;if(!(slot in states))states[slot]=typeof initial==='function'?initial():initial;return[states[slot],value=>states[slot]=typeof value==='function'?value(states[slot]):value]},useEffect(callback,deps){const slot=effectIndex++;if(!effects[slot]||deps.some((value,index)=>value!==effects[slot].deps[index])){effects[slot]?.cleanup?.();effects[slot]={deps};pending.push(()=>effects[slot].cleanup=callback())}}}
  throw Error(name)
 }})
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
 const render=()=>{stateIndex=0;effectIndex=0;return context.exports.default(props)}
 return{props,calls,changes,ready,render,async settle(){while(pending.length)pending.shift()();await new Promise(setImmediate);return render()}}
}
;(async()=>{
 const app=setup();let tree=app.render();assert.equal(find(tree,n=>n.type==='select').props.disabled,true)
 tree=await app.settle();assert.equal(app.calls[0].url,'/booking/snowland/api/currency-options/')
 find(tree,n=>n.type==='select').props.onChange({target:{value:'JPY'}})
 assert.equal(app.changes[0].currency,'JPY');assert.equal(app.changes[0].rate,'4.50000000')
 assert.equal(find(app.render(),n=>n.type==='select').props.value,'JPY')
 const stale=setup();stale.props.value={currency:'JPY',rate:'4.00000000'};stale.render();tree=await stale.settle()
 assert.equal(stale.changes.length,0,'A changed rate must not silently replace customer consent')
 assert.equal(stale.ready.at(-1),false)
 const confirm=find(tree,n=>n.type==='button'&&React.Children.toArray(n.props.children).join('').includes('確認使用新匯率'))
 assert.ok(confirm);confirm.props.onClick();stale.render();await stale.settle()
 assert.equal(stale.props.value.rate,'4.50000000');assert.equal(stale.ready.at(-1),true)
 const unavailable=setup({choices:[{code:'TWD',rate:'1.00000000'}]});unavailable.props.value={currency:'JPY',rate:'4.50000000'}
 unavailable.render();tree=await unavailable.settle()
 assert.equal(unavailable.changes.length,0)
 assert.equal(find(tree,n=>n.type==='select').props.value,'JPY')
 assert.ok(find(tree,n=>n.type==='option'&&n.props.value==='JPY'&&n.props.disabled))
 assert.equal(unavailable.ready.at(-1),false)
 const offline=setup({fail:true});offline.props.value={currency:'JPY',rate:'4.50000000'};offline.render();tree=await offline.settle()
 assert.ok(find(tree,n=>n.props.role==='alert'))
 assert.equal(offline.changes.length,0);assert.equal(offline.ready.at(-1),false)
 find(tree,n=>n.type==='select').props.onChange({target:{value:'TWD'}});offline.render();await offline.settle()
 assert.equal(offline.props.value.currency,'TWD');assert.equal(offline.ready.at(-1),true)
 console.log('PASS real currency selector: server choices, loading guard and explicit JPY rate selection')
})().catch(error=>{console.error(error);process.exitCode=1})
