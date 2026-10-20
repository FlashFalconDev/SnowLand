const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),render=req('react-dom/server').renderToStaticMarkup
const compile=file=>ts.transpileModule(fs.readFileSync(path.join(root,'src',file),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true}}).outputText
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const found=find(child,p);if(found)return found}return null}
function app(file,language,{rows=[],loading=false,error=false,category,policy}={}){
 const states=[],calls=[];let cursor=0
 const hooks={...React,useContext:()=>'/snowland',useEffect:()=>{},useState:initial=>{const index=cursor++;if(!(index in states))states[index]=initial;return[states[index],value=>states[index]=typeof value==='function'?value(states[index]):value]}}
 const locale=require('./helpers/site-locale-harness.cjs')(React,language)
 const context={exports:{},window:{location:{pathname:'/snowland/privacy-policy'}},require:name=>{
  if(name==='react')return hooks
  if(name.includes('contexts/SiteLocale'))return locale
  if(name==='react-router-dom')return{useParams:()=>({category}),useNavigate:()=>value=>calls.push(value),useSearchParams:()=>[new URLSearchParams()]}
  if(name.includes('SiteHeader')||name.includes('SiteFooter'))return()=>null
  if(name.includes('SiteLink'))return{__esModule:true,default:props=>React.createElement('a',{href:props.to},props.children),SiteBasePathContext:React.createContext('/snowland')}
  if(name==='framer-motion')return{motion:new Proxy({},{get:(_,tag)=>({children})=>React.createElement(tag,null,children)})}
  if(name.includes('useSiteContent'))return{GUIDE_CATEGORIES:['裝備與技巧'],guideArticleTarget:row=>row.link_url,siteContentToPage:row=>row,siteContentToArticle:row=>({...row,category:row.metadata?.category,url:row.link_url}),useSiteContent:key=>({items:key==='guides.index'?[]:rows,isLoading:loading,error,refetch:()=>calls.push('retry')})}
  if(name==='@tanstack/react-query')return{useQuery:()=>({data:policy,isError:error,refetch:()=>calls.push('retry')})}
  if(name.includes('api/booking'))return{fetchCheckoutPolicies(){}}
  throw Error(name)
 }}
 vm.runInNewContext(compile(file),context)
 return{calls,render:()=>{cursor=0;return context.exports.default({contentKey:'privacy'})}}
}
for(const language of ['en','ja']){
 const faq=app('pages/site/FaqPage.jsx',language,{rows:[{title:'QA原始問題',body:'<p>QA原始答案</p>',metadata:{section:'預訂課程時'}}]})
 let view=faq.render(),html=render(view)
 assert.ok(html.includes(language==='en'?'Booking a lesson':'レッスンの予約'))
 assert.ok(html.includes('QA原始問題')&&html.includes('QA原始答案'))
 find(view,node=>node.type==='button'&&node.props['aria-controls']).props.onClick();assert.ok(render(faq.render()).includes('aria-expanded="true"'))
 find(faq.render(),node=>node.type==='button'&&React.Children.toArray(node.props.children).includes(language==='en'?'Before you go':'出発前の準備')).props.onClick()
 assert.equal(faq.calls[0],'/snowland/faq/preparation','Category navigation must preserve the tenant route')
 assert.ok(render(faq.render()).includes(language==='en'?'No questions have been published':'このカテゴリーの質問はまだ'))
 const guides=app('pages/site/GuidesCollectionPage.jsx',language,{rows:[{id:1,title:'QA原始文章',link_url:'/guides/articles/1',metadata:{category:'裝備與技巧'}}]})
 view=guides.render();html=render(view);assert.ok(html.includes('QA原始文章'));assert.ok(html.includes(language==='en'?'Gear &amp; skills':'用具・テクニック'))
 const guideCategory=find(view,node=>node.type==='button'&&render(node).includes(language==='en'?'Gear &amp; skills':'用具・テクニック'));assert.ok(guideCategory,html);guideCategory.props.onClick();assert.equal(guides.calls[0],'/snowland/guides/gear')
 const failed=app('pages/site/GuidesCollectionPage.jsx',language,{error:true});view=failed.render();find(view,node=>node.type==='button'&&node.props.children===(language==='en'?'Reload':'再読み込み')).props.onClick();assert.deepEqual(failed.calls,['retry'])
 const legal=app('pages/site/PolicyPage.jsx',language,{policy:{pages:{privacy:{title:'QA法務原標題',html:'<p>QA法務原文不可自動翻譯</p>'}}}})
 assert.ok(render(legal.render()).includes('QA法務原文不可自動翻譯'))
 const policyError=app('pages/site/PolicyPage.jsx',language,{error:true});view=policyError.render();assert.ok(render(view).includes(language==='en'?'Content could not be loaded':'内容を読み込めませんでした'));find(view,node=>node.type==='button').props.onClick();assert.deepEqual(policyError.calls,['retry'])
 const offers=app('components/site/SpecialOffers.jsx',language,{rows:[{id:1,title:'QA原始優惠',subtitle:'QA原始說明',image_url:'/vite.svg',link_url:'/offers',status:'ended'}]})
 html=render(offers.render());assert.ok(html.includes('QA原始優惠')&&html.includes('QA原始說明'));assert.ok(html.includes(language==='en'?'Ended':'終了'))
 console.log('PASS public locale',language,'FAQ toggle/category, guide canonical route/retry, offers badge/private copy, legal body preserved/error retry')
}
