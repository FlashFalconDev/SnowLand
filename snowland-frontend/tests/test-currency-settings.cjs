const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json'))
const React=req('react'),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/admin/pages/PaymentSettingsPage.tsx'),'utf8')
function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,predicate);if(result)return result}return null}
function labelControl(tree,label,type){const node=find(tree,n=>n.type==='label'&&React.Children.toArray(n.props.children).some(v=>typeof v==='string'&&v.includes(label)));assert.ok(node,label);return find(node,n=>n.type===type)}
function setup({failure=false,authorityError=false,company=true,busy=false}={}){
 const states=[],calls=[];let index=0,retries=0
 const context=vm.createContext({React,exports:{},require(name){
  if(name==='react')return{...React,useEffect(){},useState(initial){const slot=index++;if(!(slot in states))states[slot]=typeof initial==='function'?initial():initial;return[states[slot],value=>states[slot]=typeof value==='function'?value(states[slot]):value]}}
  if(name==='@tanstack/react-query')return{useQuery(options){return options.queryKey.join('/')==='admin/me'?{data:authorityError?undefined:{user:{can_view_all_campuses:company,assigned_campus_ids:[1]}},isSuccess:!authorityError,isError:authorityError,isPending:false,refetch(){retries++}}:{data:undefined,isLoading:false}},useQueryClient:()=>({invalidateQueries(){}}),useMutation(options){return{isPending:busy,async mutate(payload){try{const result=await options.mutationFn(payload);options.onSuccess?.(result)}catch(error){options.onError?.(error)}}}}}
  if(name==='lucide-react')return new Proxy({},{get:()=>()=>null})
  if(name==='../context')return{useNotification:()=>({success(){},error(){}})}
  if(name==='../hooks/useAdminDialog')return{useAdminDialog:()=>({current:null})}
  if(name==='../api/paymentSettings')return{async updatePaymentSettings(payload){calls.push(payload);if(failure)throw{response:{data:{msg:'匯率必須大於0'}}};return payload}}
  if(name.startsWith('../api/'))return new Proxy({},{get:()=>()=>{}})
  throw Error(name)
 }})
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
 return{calls,retries:()=>retries,render(){index=0;return context.exports.default()}}
}
;(async()=>{
 const app=setup();let tree=app.render()
 assert.equal(labelControl(tree,'開放日幣匯款','input').props.checked,false)
 labelControl(tree,'開放日幣匯款','input').props.onChange({target:{checked:true}})
 tree=app.render();labelControl(tree,'1台幣可換多少日幣','input').props.onChange({target:{value:'4.5'}})
 find(app.render(),n=>n.type==='form').props.onSubmit({preventDefault(){}});await new Promise(setImmediate)
 assert.equal(app.calls[0].currency_settings.jpy_enabled,true)
 assert.equal(app.calls[0].currency_settings.jpy_per_twd,'4.5')
 assert.ok(find(app.render(),n=>n.props.role==='status'&&n.props['aria-label']==='付款設定儲存結果'))
 const rejected=setup({failure:true});tree=rejected.render()
 labelControl(tree,'開放日幣匯款','input').props.onChange({target:{checked:true}})
 labelControl(rejected.render(),'1台幣可換多少日幣','input').props.onChange({target:{value:'0'}})
 find(rejected.render(),n=>n.type==='form').props.onSubmit({preventDefault(){}});await new Promise(setImmediate)
 tree=rejected.render()
 assert.equal(find(tree,n=>n.props.role==='alert'&&n.props['aria-label']==='付款設定錯誤').props.children,'匯率必須大於0')
 assert.equal(labelControl(tree,'1台幣可換多少日幣','input').props.value,'0')
 assert.equal(find(tree,n=>n.props.role==='status'&&n.props['aria-label']==='付款設定儲存結果'),null)
 const unknown=setup({authorityError:true});tree=unknown.render()
 assert.equal(find(tree,n=>n.type==='fieldset').props.disabled,true)
 find(tree,n=>n.type==='button'&&n.props.children==='重新確認權限').props.onClick();assert.equal(unknown.retries(),1)
 assert.equal(find(setup({company:false}).render(),n=>n.type==='fieldset').props.disabled,true)
 assert.equal(find(setup({busy:true}).render(),n=>n.type==='fieldset').props.disabled,true)
 console.log('PASS currency settings handlers: explicit rate/enable payload, retained rejected draft and persistent error, success feedback, fail-closed authority with retry, campus readonly and busy guard')
})().catch(error=>{console.error(error);process.exitCode=1})
