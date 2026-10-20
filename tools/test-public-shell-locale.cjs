const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module');
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server');
function find(n,p){if(!n||typeof n!=='object')return null;if(p(n))return n;for(const c of React.Children.toArray(n.props?.children)){const hit=find(c,p);if(hit)return hit;}return null;}
function setup(page,language,count=3){
 const state=[],refs=[];let index=0,refIndex=0;
 const posts=Array.from({length:count},(_,i)=>({id:i+1,title:'CMS原貼文'+i,image_url:'/qa.jpg',summary:'CMS原文'+i,link_url:'https://www.instagram.com/p/QA'+i+'/'}));
 const hooks={...React,useState(initial){const key=index++;if(!(key in state))state[key]=page==='NewsPage'&&key===1?posts:page==='NewsPage'&&key===2?[{id:91,title:'CMS原文章',metadata:{category:'裝備與技巧'}}]:initial;return[state[key],next=>state[key]=typeof next==='function'?next(state[key]):next];},useEffect(){},useRef(value){const key=refIndex++;return refs[key]??(refs[key]={current:value});}};
 const locale=require('./helpers/site-locale-harness.cjs')(hooks,language),ctx={exports:{},require(name){
  if(name==='react')return hooks;
  if(name.includes('contexts/SiteLocale'))return locale;
  if(name.includes('websiteCoaches'))return{useWebsiteCoachCards:()=>({coaches:[{id:1,name:'CMS原教練',cardBio:'CMS原簡介',slug:'qa'}],isLoading:false,error:null,retry(){}})};
  if(name.includes('useSiteContent'))return{guideArticleTarget:()=>'/guides/articles/91'};
  if(name.includes('/api/booking'))return{fetchSiteContent:()=>Promise.resolve([])};
  if(name==='react-router-dom')return{Link:p=>React.createElement('a',{href:p.to},p.children)};
  if(name.endsWith('SiteLink'))return p=>React.createElement('a',{...p,href:'/snowland'+p.to},p.children);
  if(/SiteHeader|SiteFooter|CoachLoadNotice/.test(name))return()=>null;
  throw Error(name);
 }};
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/pages/site/'+page+'.jsx'),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,ctx);
 return{refs,t:text=>locale.translateSiteText(language,text),render(){index=0;refIndex=0;return ctx.exports.default();}};
}
for(const language of ['en','ja']){
 const homeSource=ts.createSourceFile('home.jsx',fs.readFileSync(path.join(root,'src/pages/site/HomePage.jsx'),'utf8'),99,true,ts.ScriptKind.JSX);let reviewFactory;
 function walkHome(n){if(ts.isVariableDeclaration(n)&&n.name.getText(homeSource)==='reviews')reviewFactory=n.initializer.arguments[0].getText(homeSource);ts.forEachChild(n,walkHome)}walkHome(homeSource);
 const homeLocale=require('./helpers/site-locale-harness.cjs')(React,language),homeContext={exports:{},cmsReviews:[{title:'',summary:'CMS原評論'},{title:'CMS原姓名',summary:'CMS原評論2'}],t:s=>homeLocale.translateSiteText(language,s)};
 vm.runInNewContext(ts.transpileModule(`exports.reviews=(${reviewFactory})();`,{compilerOptions:{jsx:ts.JsxEmit.React}}).outputText,homeContext);
 assert.equal(homeContext.exports.reviews[0].name,language==='en'?'SnowLand student':'SnowLand受講者');assert.equal(homeContext.exports.reviews[1].name,'CMS原姓名');assert.equal(homeContext.exports.reviews[0].textPrimary,'CMS原評論');
 const coach=setup('CoachTeamPage',language),coachHtml=renderToStaticMarkup(coach.render());assert.ok(coachHtml.includes(coach.t('教練團隊'))&&coachHtml.includes('CMS原教練')&&coachHtml.includes('CMS原簡介'));assert.ok(coachHtml.includes('pt-32 pb-16 md:pt-40 md:pb-24'),'Coach heading must clear the fixed site navigation');
 const news=setup('NewsPage',language);let tree=news.render(),html=renderToStaticMarkup(tree);for(const text of [news.t('最新消息'),news.t('裝備與技巧'),news.t('追蹤我們的 Instagram'),'CMS原文章','CMS原貼文0','CMS原文0'])assert.ok(html.includes(renderToStaticMarkup(React.createElement(React.Fragment,null,text))),text);
 const prev=find(tree,n=>n.type==='button'&&n.props['aria-label']===news.t('上一則貼文')),next=find(tree,n=>n.type==='button'&&n.props['aria-label']===news.t('下一則貼文'));assert.equal(prev.props.disabled,true);assert.equal(next.props.disabled,false);assert.ok(next.props.className.includes('h-11 w-11'));
 let scroll;news.refs[0].current={scrollTo:opts=>scroll=opts};news.refs[1].current=[{offsetLeft:0,clientWidth:100},{offsetLeft:120,clientWidth:100},{offsetLeft:240,clientWidth:100}];next.props.onClick();assert.equal(scroll.left,120);
 find(tree,n=>n.props.onScroll).props.onScroll({currentTarget:{scrollLeft:240,clientWidth:100}});tree=news.render();assert.equal(find(tree,n=>n.type==='button'&&n.props['aria-label']===news.t('下一則貼文')).props.disabled,true);
 const dot=find(tree,n=>n.type==='button'&&n.props['aria-pressed']===true);assert.ok(dot.props.className.includes('h-11 w-11'));dot.props.onClick();assert.equal(scroll.left,240);
 const empty=setup('NewsPage',language,0),emptyTree=empty.render();for(const label of ['上一則貼文','下一則貼文'])assert.equal(find(emptyTree,n=>n.type==='button'&&n.props['aria-label']===empty.t(label)).props.disabled,true);
 const many=setup('NewsPage',language,8),manyTree=many.render();assert.ok(find(manyTree,n=>n.props.className==='mt-4 flex flex-wrap justify-center gap-2 md:hidden'));assert.ok(find(manyTree,n=>n.type==='button'&&n.props['aria-pressed']===true).props.className.includes('shrink-0'));
}
console.log('PASS actual coach/news en/ja: owned labels, original CMS names/content, real carousel scroll callbacks, boundaries/empty disabled, 44px controls');
