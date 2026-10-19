const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/admin/pages/CampusesPage.tsx'),'utf8')+'\nexport { PolicyCard }'
const base={id:7,campus:2,campus_name:'QA',unpaid_hold_days:3,provisional_extra_groups:3,leave_advance_days:3,leave_daily_coach_limit:2,leave_max_consecutive_days:2,cancellation_fee_percent:5,cancellation_rules:[{days_before:0,refund_percent:50}],course_reminder_days:[3],settings:{qa:'preserve'}}
function harness({draft=base,canEdit=true,hasOverride=true}={}){
 const states=[structuredClone(draft),false,''],configs=[],calls=[],notices=[];let cursor=0
 const context={React,exports:{},require(name){
  if(name==='react')return{...React,useState(initial){const i=cursor++;if(states[i]===undefined)states[i]=initial;return[states[i],value=>states[i]=typeof value==='function'?value(states[i]):value]},useEffect(){}}
  if(name==='@tanstack/react-query')return{useMutation(config){configs.push(config);return{isPending:false,mutate:()=>calls.push('mutate')}}}
  if(name==='../context')return{useNotification:()=>({success:m=>notices.push(m),error:m=>notices.push(m)})}
  if(name==='../hooks/useAdminDialog')return{useAdminDialog:()=>({current:null})}
  if(name==='../api/campuses')return{updateOperatingPolicy:(id,data)=>{calls.push({type:'update',id,data});return Promise.resolve(data)},createOperatingPolicy:data=>{calls.push({type:'create',data});return Promise.resolve(data)}}
  if(name==='lucide-react')return new Proxy({},{get:()=>()=>null})
  return{}
 }}
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
 function render(){cursor=0;configs.length=0;return context.exports.PolicyCard({campuses:[],policy:base,selectedCampusId:2,hasOverride,canEdit,onSelect(){},onSaved(){calls.push('refresh')}})}
 return{states,configs,calls,notices,render}
}
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,p);if(result)return result}return null}
const save=tree=>find(tree,n=>n.type==='button'&&React.Children.toArray(n.props.children).includes('儲存營運規則'))
async function run(){
 const first=harness();let tree=first.render();const html=renderToStaticMarkup(tree)
 assert.ok(html.includes('連續請假上限'),'school staff must be able to configure the actual consecutive-day rule')
 for(const value of ['',-1,1.5,32768,'invalid']){
  const h=harness({draft:{...base,leave_max_consecutive_days:value}});tree=h.render()
  assert.equal(save(tree).props.disabled,true,`invalid rule ${JSON.stringify(value)} must disable save`)
  assert.ok(renderToStaticMarkup(tree).includes('連續請假上限'))
  assert.throws(()=>h.configs[0].mutationFn(),/請先修正營運規則欄位/)
  assert.equal(h.calls.length,0)
 }
 const valid=harness({draft:{...base,leave_advance_days:'0',leave_max_consecutive_days:'3'}})
 tree=valid.render();assert.equal(save(tree).props.disabled,false)
 await valid.configs[0].mutationFn()
 assert.equal(valid.calls[0].data.leave_advance_days,0);assert.equal(valid.calls[0].data.leave_max_consecutive_days,3)
 assert.equal(valid.calls[0].data.settings.qa,'preserve');assert.equal(valid.calls[0].data.course_reminder_days[0],3)
 const clear=find(tree,n=>n.type==='input'&&n.props['aria-label']==='連續請假上限')
 assert.ok(clear);clear.props.onChange({target:{value:''}});tree=valid.render()
 assert.equal(valid.states[0].leave_max_consecutive_days,'');assert.equal(save(tree).props.disabled,true)
 clear.props.onChange({target:{value:'3'}});tree=valid.render();assert.equal(save(tree).props.disabled,false)
 valid.configs[0].onError({response:{data:{leave_max_consecutive_days:['A valid integer is required.']}}})
 tree=valid.render();assert.ok(renderToStaticMarkup(tree).includes('連續請假上限：請輸入0～32767的整數'))
 assert.ok(find(tree,n=>n.props?.role==='alert'))
 valid.configs[0].onError({response:{status:404,data:{detail:'No OperatingPolicy matches the given query.'}}})
 assert.ok(renderToStaticMarkup(valid.render()).includes('請重新載入頁面後再試'))
 const missingFee=harness({draft:{...base,cancellation_fee_percent:''}});assert.equal(save(missingFee.render()).props.disabled,true)
 const locked=harness({canEdit:false});tree=locked.render();assert.equal(find(tree,n=>n.type==='fieldset').props.disabled,true)
 const fresh=harness({hasOverride:false,draft:{...base,leave_max_consecutive_days:'4'}});fresh.render();await fresh.configs[0].mutationFn()
 assert.equal(fresh.calls[0].type,'create');assert.equal(fresh.calls[0].data.campus,2);assert.equal(fresh.calls[0].data.leave_max_consecutive_days,4)
 console.log('PASS actual policy editor: consecutive-day setting, blank/negative/decimal/range guards, zero allowed, normalized create/update, preserved settings, persistent field errors and read-only role')
}
run().catch(e=>{console.error(e);process.exitCode=1})
