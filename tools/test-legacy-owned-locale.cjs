const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module');
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server');
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const hit=find(child,p);if(hit)return hit;}return null;}
function setup(language,flags={}){
 const state=[];let index=0;
 const hooks={...React,useState(value){const key=index++;if(!(key in state))state[key]=typeof value==='function'?value():value;return[state[key],next=>state[key]=typeof next==='function'?next(state[key]):next];},useRef:value=>({current:value}),useMemo:fn=>fn(),useEffect(){}};
 const locale=require('./helpers/site-locale-harness.cjs')(hooks,language);
 const scope={exports:{},require(name){
  if(name==='react')return hooks;
  if(name.includes('contexts/SiteLocale'))return locale;
  if(name==='react-router-dom')return{Link:p=>React.createElement('a',{href:p.to},p.children)};
  if(name==='framer-motion')return{motion:new Proxy({},{get:(_,tag)=>({initial,animate,variants,transition,whileInView,viewport,...props})=>React.createElement(tag,props)}),useReducedMotion:()=>true,useScroll:()=>({scrollY:0}),useTransform:()=>0};
  if(name.includes('useSiteContent'))return{useSiteContent:()=>({items:[],isLoading:!!flags.loading,error:flags.error?Error('QA'):null}),siteContentToPage:()=>null,siteContentToArticle:x=>x};
  if(name.endsWith('SiteLink'))return p=>React.createElement('a',{...p,href:'/snowland'+p.to},p.children);
  if(/SiteHeader|SiteFooter/.test(name))return()=>null;
  throw Error(name);
 }};
 const source=fs.readFileSync(path.join(root,'src/pages/site/LegacyContentPage.jsx'),'utf8');
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText+';exports.Layout=LegacyContentLayout;',scope);
 return{t:text=>locale.translateSiteText(language,text),wrapper(key){index=0;return scope.exports.default({pageKey:key});},layout(key='guides-preparation'){index=0;return scope.exports.Layout({pageKey:key,page:{title:'CMS原標題',subtitle:'CMS副標題',blocks:[{type:'heading',level:2,text:'CMS原章節'},{type:'paragraph',text:'CMS原文不改寫'}]},guidesArticles:[]});}};
}
for(const language of ['en','ja']){
 const app=setup(language),tree=app.layout();let html=renderToStaticMarkup(tree);
 for(const text of ['CMS原標題','CMS原章節','CMS原文不改寫',app.t('目錄')])assert.ok(html.includes(text),text);
 const toggle=find(tree,n=>n.type==='button'&&n.props['aria-label']===app.t('收合目錄'));assert.ok(toggle);assert.equal(toggle.props['aria-expanded'],true);assert.ok(toggle.props.className.includes('min-h-[44px]'));
 toggle.props.onClick();const collapsed=app.layout(),open=find(collapsed,n=>n.type==='button'&&n.props['aria-label']===app.t('展開目錄'));assert.equal(open.props['aria-expanded'],false);
 open.props.onClick();assert.equal(find(app.layout(),n=>n.type==='button'&&n.props['aria-label']===app.t('收合目錄')).props['aria-expanded'],true);
 for(const [flags,key]of [[{loading:true},'內容載入中。'],[{error:true},'內容暫時無法載入，請稍後再試。'],[{},'目前沒有已發布的內容。']]){
  const missing=setup(language,flags);assert.ok(renderToStaticMarkup(missing.wrapper('guides-preparation')).includes(missing.t(key)));
 }
 const updating=renderToStaticMarkup(app.wrapper('about'));assert.ok(updating.includes(language==='en'?'content is being updated':'の内容を更新中'));
 assert.ok(updating.includes(language==='en'?'School introduction':'スクール紹介'));
 const deals=renderToStaticMarkup(app.layout('deals'));assert.ok(deals.includes(language==='en'?'Early-bird offers':'早期予約特典'));
 const recruitment=renderToStaticMarkup(app.layout('join-us'));assert.ok(recruitment.includes(language==='en'?'Show photo 2':'写真2枚目を表示'));
}
console.log('PASS actual legacy owned UI en/ja: loading/error/empty/updating, TOC collapse/reopen/44px, original CMS titles and body preserved');
