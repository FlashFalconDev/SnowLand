const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const compile=file=>ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
const ctx=vm.createContext({exports:{},URL,require:name=>name==='react'?React:{}})
vm.runInContext(compile('src/hooks/useSiteContent.js'),ctx)
const articleHtmlCtx=vm.createContext({exports:{}})
vm.runInContext(compile('src/utils/guideArticleHtml.js'),articleHtmlCtx)
const map=ctx.exports.siteContentToArticle
const row={id:501,location_key:'guides.articles',title:'QA新文章',summary:'QA摘要',image_url:'/vite.svg',link_url:'',metadata:{category:'親子滑雪',date:'2026-10-18',article_mode:'internal',blocks:[{type:'paragraph',text:'QA完整內文'}]}}
assert.equal(map(row).url,'/guides/articles/501','新增文章必須能點進完整內頁，不是空白連結')
assert.equal(map({...row,metadata:{...row.metadata,article_mode:'external'},link_url:'https://example.test/original'}).url,'https://example.test/original')
assert.equal(ctx.exports.guideArticleTarget({...row,metadata:{category:'裝備與技巧'},link_url:'https://land110602.com/packing-checklist/'}),'/guides/packing-checklist')
assert.equal(ctx.exports.guideArticleTarget({...row,metadata:{},link_url:'javascript:alert(1)'}),'')
assert.equal(ctx.exports.guideArticleTarget({...row,metadata:{},link_url:'https://land110602.com/%e6%9e%97%e9%96%93%e9%9b%aa%e9%81%93/'}),'/guides/best-hokkaido-tree-runs')
assert.equal(ctx.exports.guideArticleTarget({...row,metadata:{},link_url:'__proto__'}),'')
function render(file,{items=[row],loading=false,error=null,articleId='501',category,query='',language='zh-Hant'}={}){
 let stateIndex=0
 const react=file.includes('NewsPage')?{...React,useState:initial=>[stateIndex++===2?items:initial,()=>{}]}:React
 const context=vm.createContext({exports:{},require:name=>{
  if(name==='react')return react
  if(name.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(React,language)
  if(name==='react-router-dom')return{useParams:()=>({articleId,category}),useNavigate:()=>()=>{},useSearchParams:()=>[new URLSearchParams(query)]}
  if(name.includes('SiteHeader')||name.includes('SiteFooter')||name.includes('HokkaidoMap')||name.includes('ResortGrid'))return()=>null
  if(name.includes('SiteLink'))return{__esModule:true,SiteBasePathContext:React.createContext('/snowland'),default:({to,children,...props})=>React.createElement('a',{...props,href:to},children)}
  if(name.includes('useSiteContent'))return{...ctx.exports,useSiteContent:key=>({items:['guides.articles','guides.article-pages'].includes(key)?items:[],isLoading:loading,error,refetch(){}})}
  if(name.includes('/api/booking'))return{fetchSiteContent:()=>Promise.resolve([])}
  if(name.includes('guideArticleHtml'))return articleHtmlCtx.exports
  throw Error(name)
 }})
 vm.runInContext(compile(file),context)
 return renderToStaticMarkup(React.createElement(context.exports.default))
}
const list=render('src/pages/site/GuidesCollectionPage.jsx')
assert.ok(list.includes('href="/guides/articles/501"'));assert.ok(list.includes('親子滑雪'))
assert.ok(render('src/pages/site/GuidesCollectionPage.jsx',{query:'category='+encodeURIComponent('親子滑雪')}).includes('QA新文章'))
const detail=render('src/pages/site/GuideArticlePage.jsx')
assert.ok(detail.includes('QA完整內文'));assert.ok(detail.includes('QA新文章'));assert.ok(detail.includes('親子滑雪'));assert.ok(detail.includes('返回文章列表'))
const rich=render('src/pages/site/GuideArticlePage.jsx',{items:[{...row,metadata:{...row.metadata,blocks:[],article:{html:'<h2>原標題</h2><p>原完整正文</p><table><tr><td>原表格</td></tr></table><iframe src="https://www.youtube.com/embed/ouVZgVr3HJ4" title="影片" loading="lazy"></iframe><img src="/qa.jpg" loading="lazy">'}}}]})
assert.ok(rich.includes('<table tabindex="0">'));assert.ok(rich.includes('原完整正文'));assert.ok(rich.includes('youtube.com/embed/ouVZgVr3HJ4'));assert.ok(rich.includes('imported-guide'))
assert.ok(rich.includes('表格可左右滑動'))
assert.ok(rich.includes('title="影片" loading="eager"'),'動態正文影片不可因lazy維持空白')
assert.ok(rich.includes('<img src="/qa.jpg" loading="lazy">'),'不影響一般圖片延遲載入')
const covered=render('src/pages/site/GuideArticlePage.jsx',{items:[{...row,metadata:{...row.metadata,article:{html:'<p>原文</p><img src="/vite.svg" alt="正文封面">'}}}]})
assert.equal((covered.match(/src="\/vite.svg"/g)||[]).length,1,'原文已有封面圖時不可再顯示重複首圖')
assert.ok(render('src/pages/site/GuideArticlePage.jsx',{loading:true,items:[]}).includes('文章載入中'))
assert.ok(render('src/pages/site/GuideArticlePage.jsx',{error:Error('qa'),items:[]}).includes('重新載入'))
assert.ok(render('src/pages/site/GuideArticlePage.jsx',{items:[]}).includes('文章不存在或已下架'))
assert.ok(render('src/pages/site/GuideArticlePage.jsx',{items:[{...row,metadata:{...row.metadata,blocks:[{type:'paragraph',text:'<script>unsafe</script>'}]}}]}).includes('&lt;script&gt;'))
assert.doesNotThrow(()=>render('src/pages/site/GuideArticlePage.jsx',{items:[{...row,metadata:{...row.metadata,blocks:[{type:'image',src:'/qa.svg',alt:{}}]}}]}),'舊資料的錯誤圖片說明不可造成空白頁')
for(const language of ['en','ja']){
 const html=render('src/pages/site/GuideArticlePage.jsx',{language,items:[{...row,metadata:{...row.metadata,category:'裝備與技巧',article:{html:'<h2>QA原始章節</h2><p>QA原始內文</p><table><tr><td>QA表格</td></tr></table>'}}}]})
 assert.ok(html.includes(language==='en'?'Article contents':'記事の目次'))
 assert.ok(html.includes(language==='en'?'Back to articles':'記事一覧へ戻る'))
 assert.ok(html.includes(language==='en'?'Scroll tables sideways':'表を左右にスクロール'))
 assert.ok(html.includes('QA原始章節')&&html.includes('QA原始內文')&&html.includes('QA表格'))
 assert.ok(render('src/pages/site/GuideArticlePage.jsx',{language,items:[]}).includes(language==='en'?'unavailable or has been unpublished':'公開が終了しています'))
 for(const [file,slug] of [['PackingChecklistPage.jsx','packing-checklist'],['BestHokkaidoTreeRunsPage.jsx','best-hokkaido-tree-runs']]){
  const markup=render('src/pages/site/'+file,{language,items:[{...row,external_id:slug,metadata:{article:{title:'QA原始文章',date:'2026-10-19',html:'<h2>QA原始章節</h2><p>QA原始內容</p>'}}}]})
  assert.ok(markup.includes(language==='en'?'Collapse contents':'目次を閉じる'))
  assert.ok(markup.includes('min-h-11 min-w-11'),'Legacy TOC toggles need44px touch targets')
  assert.ok(markup.includes('QA原始章節')&&markup.includes('QA原始內容'))
 }
}
assert.ok(render('src/pages/site/NewsPage.jsx').includes('href="/guides/articles/501"'),'新文章在最新消息也要連到同一篇，不能是#')
assert.ok(render('src/pages/site/SkiResortsPage.jsx',{items:[{...row,metadata:{...row.metadata,category:'北海道滑雪場'}}]}).includes('href="/guides/articles/501"'),'雪場延伸閱讀不能漏掉客戶路徑')
console.log('PASS guide articles: internal/external/legacy targets, custom categories, real list/detail, escaped body and loading/error/hidden states')
const fieldCtx=vm.createContext({React,exports:{}})
vm.runInContext(compile('src/admin/components/GuideArticleFields.tsx'),fieldCtx)
let metadata={category:'原分類',date:'2024.10.01',keep:'legacy'},changed
let fields=fieldCtx.exports.default({metadata,mode:'internal',categories:['裝備與技巧','原分類'],onChange:value=>changed=value})
function find(node,test){if(!node||typeof node!=='object')return null;if(test(node))return node;for(const child of React.Children.toArray(node.props?.children)){const found=find(child,test);if(found)return found}return null}
assert.equal(find(fields,n=>n.type==='input'&&n.props.type==='date').props.value,'2024-10-01')
find(fields,n=>n.type==='input'&&n.props.list).props.onChange({target:{value:'新分類'}})
assert.equal(changed.category,'新分類');assert.equal(changed.keep,'legacy');assert.equal(changed.date,'2024.10.01')
find(fields,n=>n.type==='input'&&n.props.type==='date').props.onChange({target:{value:'2026-10-18'}})
assert.equal(changed.date,'2026-10-18');assert.equal(changed.category,'原分類')
find(fields,n=>n.type==='select').props.onChange({target:{value:'external'}})
assert.equal(changed.article_mode,'external');assert.equal(changed.keep,'legacy')
console.log('PASS actual guide editor: custom/existing category, native date conversion/update, mode switch and retained metadata')
