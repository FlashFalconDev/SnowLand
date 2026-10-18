const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const articleContext=vm.createContext({exports:{}})
vm.runInContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/admin/utils/articleContent.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,articleContext)
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
  const ctx=vm.createContext({React,URL,exports:{},window:{location:{pathname:'/snowland/console/reviews/manual'}},require:name=>{
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
    if(name==='../../components/AboutPageEditor')return{default:function AboutPageEditor(){return null}}
    if(name==='../../components/ArticlePageEditor')return{default:function ArticlePageEditor(){return null}}
    if(name==='../../components/GuideArticleFields')return{default:function GuideArticleFields(){return null}}
    if(name==='../../../hooks/useSiteContent')return{GUIDE_CATEGORIES:['裝備與技巧'],guideArticleMode:item=>item.metadata?.article_mode||(item.link_url&&!item.body?'external':'internal')}
    if(name==='../../utils/articleContent')return articleContext.exports
    throw new Error('Unexpected dependency '+name)
  }})
  vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText+'\nexports.Drawer=ContentDrawer;exports.preview=getContentPreviewText;exports.DraftBlock=DraftBlock;',ctx)
  return{block:ctx.exports.DraftBlock,preview:ctx.exports.preview,render:props=>{cursor=0;return ctx.exports.default(props)},drawer:props=>{states.length=0;cursor=0;return ctx.exports.Drawer(props)},drawerAgain:props=>{cursor=0;return ctx.exports.Drawer(props)},refetched:()=>refetched}
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
let articleSaved
const articleDrawer=harness().drawer({groups:[{id:'guides',label:'攻略',locations:[{key:'guides.packing',label:'裝備',type:'page'}]}],group:'guides',item:{id:234,location_key:'guides.packing',content_type:'article',title:'舊標題',tags:[],metadata:{article:{title:'新標題',heroImage:'/new.svg',lead:'新說明',html:'<p>原HTML</p>'}}},galleryItems:[],resortOptions:[],onClose(){},onSubmit:data=>articleSaved=data,isSaving:false})
assert.ok(find(articleDrawer,n=>typeof n.type==='function'&&n.type.name==='ArticlePageEditor'))
assert.ok(!find(articleDrawer,n=>typeof n.type==='function'&&n.type.name==='ContentBlocksEditor'))
find(articleDrawer,n=>n.type==='form').props.onSubmit({preventDefault(){}})
assert.equal(articleSaved.title,'新標題');assert.equal(articleSaved.summary,'新說明');assert.equal(articleSaved.image_url,'/new.svg');assert.equal(articleSaved.metadata.article.html,'<p>原HTML</p>')
let importedSaved
const importedApp=harness(),importedProps={groups:[{id:'guides',label:'攻略',locations:[{key:'guides.articles',label:'精選文章',type:'article'}]}],group:'guides',item:{id:287,location_key:'guides.articles',content_type:'article',title:'卡片標題',tags:[],metadata:{category:'原分類',date:'2026.8.18',article_mode:'internal',article:{title:'原標題',heroImage:'/cover.jpg',html:'<p>完整正文</p>'}}},galleryItems:[],resortOptions:[],articleCategories:['原分類'],onClose(){},onSubmit:data=>importedSaved=data,isSaving:false}
let importedDrawer=importedApp.drawer(importedProps)
const importedEditor=find(importedDrawer,n=>typeof n.type==='function'&&n.type.name==='ArticlePageEditor')
assert.ok(importedEditor,'匯入攻略必須編輯完整原文，不是通用空白區塊')
assert.equal(importedEditor.props.showDate,false,'日期只在文章分類區填一次')
importedEditor.props.onChange({...importedProps.item.metadata,article:{title:'新完整標題',heroImage:'/new-cover.jpg',lead:'新摘要',html:'<p>修改全文</p>'}})
importedDrawer=importedApp.drawerAgain(importedProps)
find(importedDrawer,n=>n.type==='form').props.onSubmit({preventDefault(){}})
assert.equal(importedSaved.title,'新完整標題');assert.equal(importedSaved.image_url,'/new-cover.jpg');assert.equal(importedSaved.summary,'新摘要')
assert.equal(importedSaved.metadata.article.html,'<p>修改全文</p>');assert.equal(importedSaved.metadata.article.date,'2026.8.18');assert.equal(importedSaved.metadata.category,'原分類')
const offerDrawer=harness().drawer({groups:[{id:'news',label:'消息',locations:[{key:'offers.earlybird',label:'早鳥',type:'page'}]}],group:'news',item:{id:10,location_key:'offers.earlybird',content_type:'page',title:'早鳥',tags:[],metadata:{}},galleryItems:[],resortOptions:[],onClose(){},onSubmit(){},isSaving:false})
const offerHtml=renderToStaticMarkup(offerDrawer)
assert.ok(offerHtml.includes('後台列表縮圖（官網圖片請在正文中修改）'))
assert.ok(!offerHtml.includes('點擊後連結'),'原優惠頁不讀取的卡片連結欄位不可誤導使用者')
const badImage=renderToStaticMarkup(harness().block({block:{id:'qa',type:'image',src:'javascript:alert(1)',alt:'QA'},index:0}))
assert.ok(!badImage.includes('<img')&&badImage.includes('圖片網址格式不正確'),'未儲存草稿也不可把危險網址送進圖片預覽')
for(const level of [1,2,3,4])assert.ok(renderToStaticMarkup(harness().block({block:{id:'qa',type:'heading',level,text:'原層級'},index:0})).startsWith(`<h${level}`))
for(const manualThumbnail of ['', '/custom-thumbnail.jpg']){
 let fixed
 const app=harness(),props={groups:[{id:'news',label:'消息',locations:[{key:'offers.earlybird',label:'早鳥',type:'page'}]}],group:'news',item:{id:10,location_key:'offers.earlybird',content_type:'page',title:'早鳥',image_url:manualThumbnail,tags:[],metadata:{blocks:[{id:'img',type:'image',src:'/old.jpg',alt:''}]}},galleryItems:[],resortOptions:[],onClose(){},onSubmit:data=>fixed=data,isSaving:false}
 let tree=app.drawer(props)
 find(tree,n=>typeof n.type==='function'&&n.type.name==='ContentBlocksEditor').props.onChange([{id:'img',type:'image',src:'javascript:alert(1)',alt:''}])
 tree=app.drawerAgain(props)
 find(tree,n=>typeof n.type==='function'&&n.type.name==='ContentBlocksEditor').props.onChange([{id:'img',type:'image',src:'/new.jpg',alt:''}])
 tree=app.drawerAgain(props);find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}})
 assert.equal(fixed.image_url,manualThumbnail||'/new.jpg','修正正文圖片後自動縮圖也要跟著改，另設縮圖則必須保留')
}
const failed=harness({rulesError:true}),tree=failed.render({contentTypes:['review']})
const retry=find(tree,node=>node.type==='button'&&node.props.children==='重新載入')
assert.ok(retry);retry.props.onClick();assert.equal(failed.refetched(),2)
console.log('PASS actual review/gallery workspace and drawer restrictions, custom review sections, CMS compatibility, explicit sync notice and retry')
