const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const {renderToStaticMarkup}=req('react-dom/server')
const compile=source=>ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
const source=fs.readFileSync(path.join(root,'src/admin/pages/cms/CoachEditorPage.tsx'),'utf8')
const coach={id:71,name:'QA真正教練',can_manage:true,img:'',website_slug:'real',website_enabled:true,website_sort_order:0,website_card_bio:'QA後端簡介'}
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const c of React.Children.toArray(node.props?.children)){const hit=find(c,p);if(hit)return hit}return null}
function setup({editing=null,fail=false,error=false,search=''}={}){
  const states=[search,'',editing],calls=[],invalidations=[],messages=[];let i=0,retries=0
  const hooks={...React,useState:initial=>{const index=i++;if(!(index in states))states[index]=initial;return[states[index],v=>states[index]=v]}}
  const ctx=vm.createContext({React,URL,exports:{},require:name=>{
    if(name==='react')return hooks
    if(name==='lucide-react')return new Proxy({},{get:()=>()=>null})
    if(name==='../../components/PromptModal')return{default:function PromptModal(){return null}}
    if(name==='../../context')return{useNotification:()=>({success:v=>messages.push(v),error:v=>messages.push(v)})}
    if(name==='../../api/websiteCoachEditor')return{fetchWebsiteCoachEditor(){},updateWebsiteCoach:async(id,data)=>{calls.push({id,data});if(fail)throw{response:{data:{website_slug:['代號重複']}}};return coach}}
    if(name==='@tanstack/react-query')return{useQuery:()=>({data:[coach],isLoading:false,error:error?new Error('QA'):null,refetch(){retries++}}),useQueryClient:()=>({invalidateQueries:o=>invalidations.push(o.queryKey)}),useMutation:o=>({mutateAsync:async vars=>{try{const result=await o.mutationFn(vars);o.onSuccess(result);return result}catch(e){o.onError(e);throw e}}})}
    throw new Error('Unexpected dependency '+name)
  }})
  vm.runInContext(compile(source),ctx)
  return{ctx,states,calls,messages,invalidations,render:()=>{i=0;return ctx.exports.default()},retries:()=>retries}
}
const values={img:'/qa.jpg',website_slug:'REAL',website_card_bio:'新簡介',website_sort_order:'2',website_enabled:'true'}
;(async()=>{
  const app=setup(),html=renderToStaticMarkup(app.render())
  assert.ok(html.includes('QA真正教練'));assert.ok(!html.includes('Cash 校長'));assert.ok(!html.includes('刪除教練'));assert.ok(!html.includes('新增教練</button>'))
  assert.equal(app.ctx.exports.validateWebsiteCoach(values),undefined)
  coach.img='/vite.svg'
  assert.ok(find(setup().render(),n=>n.type==='img'&&n.props.alt===coach.name).key.endsWith('/vite.svg'))
  coach.img=''
  for(const img of ['//example.com/coach.jpg','/\\example.com/coach.jpg','/photo\n.jpg','https://','https://example.com/'+ 'x'.repeat(200)])assert.ok(app.ctx.exports.validateWebsiteCoach({...values,img}))
  for(const changed of [{website_sort_order:''},{website_sort_order:'1.5'},{website_sort_order:'Infinity'},{website_slug:''},{website_slug:'bad/path'},{img:'javascript:alert(1)'},{website_card_bio:'x'.repeat(161)}])assert.ok(app.ctx.exports.validateWebsiteCoach({...values,...changed}))
  assert.equal(app.ctx.exports.validateWebsiteCoach({...values,website_enabled:'false',website_slug:''}),undefined)
  assert.ok(renderToStaticMarkup(setup({search:'not-found'}).render()).includes('沒有符合條件'))
  const editing=setup({editing:coach}),modal=find(editing.render(),n=>typeof n.type==='function'&&n.type.name==='PromptModal')
  assert.ok(modal.props.open);assert.ok(modal.props.fields.some(f=>f.name==='website_card_bio'&&f.defaultValue==='QA後端簡介'))
  await modal.props.onSubmit(values)
  assert.equal(editing.calls[0].id,71)
  assert.deepEqual(Object.keys(editing.calls[0].data).sort(),['img','website_enabled','website_slug','website_sort_order','website_card_bio','website_profile'].sort())
  assert.equal(editing.calls[0].data.website_slug,'real');assert.equal(editing.states[2],null);assert.equal(editing.invalidations.length,2)
  const rejected=setup({editing:coach,fail:true}),form=find(rejected.render(),n=>typeof n.type==='function'&&n.type.name==='PromptModal')
  await form.props.onSubmit(values);assert.equal(rejected.states[2],coach);assert.ok(rejected.messages.some(m=>m.includes('代號重複')))
  const broken=setup({error:true}),retry=find(broken.render(),n=>n.type==='button'&&n.props.children==='重新載入');retry.props.onClick();assert.equal(broken.retries(),1)
  const profile={sections:[{title:'教學理念',lines:['old'],media:[{src:'/qa.jpg'}],lead:'keep'}],videos:[{src:'https://www.youtube.com/embed/qa'}],reviews:[{name:'QA'}]}
  const updated=app.ctx.exports.websiteCoachValues({...values,'profile_教學理念':'第一段\n第二段'},{...coach,website_profile:profile}).website_profile
  assert.equal(updated.sections[0].lines.length,2);assert.equal(updated.sections[0].media[0].src,'/qa.jpg')
  assert.equal(updated.videos[0].src,profile.videos[0].src);assert.equal(updated.reviews[0].name,'QA')
  assert.equal(app.ctx.exports.profileSectionText({sections:[{title:'教學理念',lines:{}}]},'教學理念'),'')
  let cancelled=0,promptState=0
  const prompt=vm.createContext({React,exports:{},require:name=>{
    if(name==='react')return{useState:value=>[promptState++===1?'QA驗證錯誤':value,()=>{}],useEffect(){},useRef:()=>({current:null})}
    if(name==='lucide-react')return new Proxy({},{get:()=>()=>null})
    throw new Error(name)
  }})
  vm.runInContext(compile(fs.readFileSync(path.join(root,'src/admin/components/PromptModal.tsx'),'utf8')),prompt)
  const dialog=prompt.exports.default({open:true,title:'QA編輯',fields:[{name:'slug',label:'代號'}],onCancel(){cancelled++},onSubmit(){}})
  const formNode=find(dialog,n=>n.type==='form')
  assert.equal(formNode.props.role,'dialog');assert.ok(formNode.props.className.includes('100dvh'))
  assert.ok(find(dialog,n=>n.type==='div'&&n.props.className?.includes('overflow-y-auto')))
  assert.ok(find(dialog,n=>n.props.role==='alert'))
  assert.equal(find(find(dialog,n=>n.type==='div'&&n.props.className?.includes('overflow-y-auto')),n=>n.props.role==='alert'),null)
  assert.equal(find(dialog,n=>n.type==='label').props.htmlFor,find(dialog,n=>n.type==='input').props.id)
  formNode.props.onKeyDown({key:'Escape',stopPropagation(){}});assert.equal(cancelled,1)
  console.log('PASS real coach CMS list, form validation, restricted payload, save refresh/close, retained failed form and error retry')
})().catch(e=>{console.error(e);process.exit(1)})
