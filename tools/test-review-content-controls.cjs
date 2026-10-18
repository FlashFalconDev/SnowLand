const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/admin/pages/cms/SiteContentPage.tsx'),'utf8')
const groups=[{id:'homepage',label:'首頁',description:'',locations:[{key:'homepage.reviews',label:'學生評價',hint:'',type:'review'}]},
  {id:'photography',label:'攝影作品',description:'',locations:[{key:'photography.gallery',label:'攝影作品',hint:'',type:'media'}]},
  {id:'custom',label:'自訂評價頁',description:'',locations:[{key:'custom.student-reviews',label:'自訂評價區塊',hint:'',type:'review'}]}]
function harness({rulesError=false}={}){
  const states=[];let cursor=0,refetched=0
  const hooks={...React,useMemo:f=>f(),useEffect(){},useRef:()=>({current:null}),useState:initial=>{
    const i=cursor++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial
    return[states[i],value=>states[i]=typeof value==='function'?value(states[i]):value]
  }}
  const api={fetchSiteContents(){},fetchReviewContentGroups(){},createSiteContent(){},updateSiteContent(){},deleteSiteContent(){}}
  const ctx=vm.createContext({React,exports:{},window:{location:{pathname:'/snowland/console/reviews/manual'}},require:name=>{
    if(name==='react')return hooks
    if(name==='@tanstack/react-query')return{
      useQuery:options=>options.queryKey.includes('review-locations')?{data:groups,isLoading:false,error:rulesError?new Error('QA'):null,refetch(){refetched++}}:{data:[],isLoading:false,error:null,refetch(){refetched++}},
      useMutation:()=>({isPending:false,mutate(){}}),useQueryClient:()=>({invalidateQueries(){}}),
    }
    if(name==='lucide-react')return new Proxy({},{get:()=>()=>null})
    if(name==='../../context')return{useNotification:()=>({success(){},error(){}})}
    if(name==='../../api/siteContent')return api
    if(name==='../../components/ReviewPlacementFields')return{default:function ReviewPlacementFields(){return null}}
    if(name==='../../components/GalleryFields')return{default:function GalleryFields(){return null}}
    if(name==='../../components/PhotographyPageEditor')return{default:function PhotographyPageEditor(){return null}}
    throw new Error('Unexpected dependency '+name)
  }})
  vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText+'\nexports.Drawer=ContentDrawer;exports.preview=getContentPreviewText;',ctx)
  return{preview:ctx.exports.preview,render:props=>{cursor=0;return ctx.exports.default(props)},drawer:props=>{states.length=0;cursor=0;return ctx.exports.Drawer(props)},refetched:()=>refetched}
}
function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of React.Children.toArray(node.props?.children)){const found=find(child,predicate);if(found)return found}return null}
for(const kind of ['review','media']){
  const app=harness(),props={initialGroup:kind==='review'?'homepage':'photography',contentTypes:[kind]}
  const html=renderToStaticMarkup(app.render(props))
  assert.ok(!html.includes('管理頁面'),'Restricted workspace must not offer CMS structure editing')
  assert.ok(!html.includes('首頁主視覺'))
  if(kind==='review'){assert.ok(html.includes('Google 評論自動同步尚未啟用'));assert.ok(html.includes('自訂評價頁'))}
  else assert.ok(!html.includes('自訂評價頁'))
  const tree=app.drawer({groups:groups.filter(g=>g.locations.some(l=>l.type===kind)),contentTypes:[kind],group:props.initialGroup,initialLocation:null,item:null,galleryItems:[],resortOptions:[],onClose(){},onSubmit(){},isSaving:false})
  const select=find(tree,node=>node.type==='select'&&node.props.value===kind)
  assert.ok(select)
  assert.equal(React.Children.toArray(select.props.children).length,1,'Advanced content type must stay restricted too')
  assert.equal(!!find(tree,node=>typeof node.type==='function'&&node.type.name==='ReviewPlacementFields'),kind==='review')
  assert.equal(!!find(tree,node=>typeof node.type==='function'&&node.type.name==='GalleryFields'),kind==='media')
}
assert.ok(renderToStaticMarkup(harness().render({})).includes('管理頁面'),'CMS editor retains original workspace')
assert.equal(harness().preview({location_key:'photography.gallery',metadata:{location:'富良野',section:'森林',shoot_types:['情侶']},tags:['不使用的舊標籤']}),'照片 · 富良野 · 森林 · 情侶')
const photo=harness(),photoDrawer=photo.drawer({groups:[{id:'photography',label:'攝影',locations:[{key:'photography.winter',label:'冬季',type:'page'}]}],group:'photography',initialLocation:'photography.winter',item:null,galleryItems:[],resortOptions:[],onClose(){},onSubmit(){},isSaving:false,saveError:'QA儲存失敗必須持續顯示'})
const photoHtml=renderToStaticMarkup(photoDrawer)
assert.ok(find(photoDrawer,n=>typeof n.type==='function'&&n.type.name==='PhotographyPageEditor'))
assert.ok(photoHtml.includes('依原版型修改欄位'));assert.ok(!photoHtml.includes('封面圖片（可空白'))
assert.ok(!photoHtml.includes('左邊新增正文區塊'));assert.ok(photoHtml.includes('正式官網預覽'))
assert.ok(photoHtml.includes('role="alert"'));assert.ok(photoHtml.includes('QA儲存失敗必須持續顯示'))
const failed=harness({rulesError:true}),tree=failed.render({contentTypes:['review']})
const retry=find(tree,node=>node.type==='button'&&node.props.children==='重新載入')
assert.ok(retry);retry.props.onClick();assert.equal(failed.refetched(),2)
console.log('PASS actual review/gallery workspace and drawer restrictions, custom review sections, CMS compatibility, explicit sync notice and retry')
