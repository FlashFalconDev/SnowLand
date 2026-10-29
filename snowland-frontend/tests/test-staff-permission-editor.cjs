const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const {renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/admin/pages/StaffPermissionsPage.tsx'),'utf8')+'\nexport { EditPermissionModal };'
const staff={id:91,name:'QA員工',username:'qa-staff',is_superuser:false,is_manager:true,is_coach:false,role:'campus_manager',permissions:['orders'],campus_ids:[11]}
function setup(superuser,target=staff){
  let mutation,submitted
  const context=vm.createContext({React,exports:{},require(name){
    if(name==='react')return {...React,useState:v=>[v,()=>{}]}
    if(name==='react-router-dom')return {}
    if(name==='lucide-react')return new Proxy({},{get:()=>()=>null})
    if(name==='../context')return {useNotification:()=>({success(){},error(){}})}
    if(name==='../permissions')return {ADMIN_PERMISSION_DEFINITIONS:[],groupPermissions:()=>({})}
    if(name==='../api/auth')return {fetchAdminMe(){}}
    if(name==='../api/campuses')return {fetchCampuses(){}}
    if(name==='../api/extras')return {fetchStaff(){},updateCustomerPermission:async(id,body)=>{submitted={id,body};return {code:200}}}
    if(name==='@tanstack/react-query')return {
      useQuery:o=>({data:o.queryKey[1]==='me'?{user:{is_superuser:superuser}}:[{id:11,name:'QA校區',is_active:true}]}),
      useQueryClient:()=>({invalidateQueries(){}}),
      useMutation:o=>{mutation=o;return {isPending:false,mutate(){}}},
    }
    throw new Error(name)
  }})
  vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
  const tree=context.exports.EditPermissionModal({staff:target,onClose(){}})
  return {tree,html:renderToStaticMarkup(tree),submit:async()=>{await mutation.mutationFn();return submitted}}
}
function find(n,p){if(!n||typeof n!=='object')return null;if(p(n))return n;for(const c of React.Children.toArray(n.props?.children)){const r=find(c,p);if(r)return r}return null}
;(async()=>{
  const hq=setup(false),sent=await hq.submit()
  assert.equal('is_superuser' in sent.body,false,'普通總部不可送出受保護的超級管理員欄位')
  assert.equal(sent.body.role,'campus_manager');assert.deepEqual(Array.from(sent.body.campus_ids),[11])
  assert.ok(!hq.html.includes('擁有全部後台權限'))
  const owner=setup(true),ownerSent=await owner.submit()
  assert.equal(ownerSent.body.is_superuser,false);assert.ok(owner.html.includes('擁有全部後台權限'))
  const protectedTarget=setup(false,{...staff,is_superuser:true})
  assert.equal(find(protectedTarget.tree,n=>n.type==='button'&&React.Children.toArray(n.props.children).includes('儲存')).props.disabled,true)
  console.log('PASS staff editor: ordinary HQ omits protected flag, normal scope retained, superuser flag owner-only, protected account save disabled')
})().catch(e=>{console.error(e);process.exit(1)})
