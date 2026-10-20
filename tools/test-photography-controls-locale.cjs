const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module');
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server');
function all(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of React.Children.toArray(n.props?.children))all(c,p,out);return out;}
function setup(season,language,custom={}){
 let index=0,refIndex=0;const states=[],refs=[],scrolls=[];
 const hooks={...React,useState(value){const i=index++;if(!(i in states))states[i]=value;return[states[i],next=>states[i]=typeof next==='function'?next(states[i]):next];},useEffect(){},useRef(value){const i=refIndex++;return refs[i]??(refs[i]={current:value});}};
 const fixture=require('../snowland/Client/fixtures/photography_page_defaults.json').find(s=>s.season===season),values=Object.fromEntries(fixture.sections.flatMap(s=>s.fields.map(f=>[f.key,f.value])));
 Object.assign(values,custom);const file=`src/pages/site/${season==='summer'?'Summer':'Winter'}PhotographyPage.jsx`,source=fs.readFileSync(path.join(root,file),'utf8').replaceAll('import.meta.env.BASE_URL','"/"')+`;exports.Layout=${season==='summer'?'Summer':'Winter'}PhotographyLayout;`;
 const scope={exports:{},require(name){
  if(name==='react')return hooks;
  if(name.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(hooks,language);
  if(name==='framer-motion')return{motion:new Proxy({},{get:(_,tag)=>tag}),useReducedMotion:()=>true,useScroll:()=>({scrollYProgress:0}),useTransform:()=>0};
  if(name==='react-router-dom')return{Link:p=>React.createElement('a',{href:p.to},p.children)};
  if(name.endsWith('SiteLink'))return p=>React.createElement('a',{href:'/snowland'+p.to},p.children);
  if(name.endsWith('SiteHeader'))return p=>React.createElement('header',{'data-compact':p.forceCompact?'yes':'no'});
  if(/SiteFooter|PhotographyContentGate/.test(name))return()=>null;
  if(name.endsWith('.jpg'))return'qa.jpg';throw Error(name);
 }};
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true}}).outputText,scope);
 return{render(){index=refIndex=0;return scope.exports.Layout({content:{values}});},refs,scrolls,initializeScroll(){refs[0].current={clientWidth:300,scrollTo:v=>scrolls.push(v)};refs[1].current=[0,1,2].map(i=>({offsetLeft:i*300,clientWidth:300}));}};
}
for(const season of ['summer','winter'])for(const language of ['en','ja']){
 const app=setup(season,language),tree=app.render(),html=renderToStaticMarkup(tree),locale=require('./helpers/site-locale-harness.cjs')(React,language);
 assert.ok(html.includes('data-compact="yes"'),'White photography pages must keep navigation readable over scrolled content');
 app.initializeScroll();const next=all(tree,n=>n.type==='button'&&n.props['aria-label']===locale.translateSiteText(language,'下一張照片'))[0];assert.ok(next.props.className.includes('h-11 w-11'));next.props.onClick();assert.equal(app.scrolls[0].left,300);
 const previous=all(app.render(),n=>n.type==='button'&&n.props['aria-label']===locale.translateSiteText(language,'上一張照片'))[0];previous.props.onClick();assert.equal(app.scrolls[1].left,0);
 assert.ok(html.includes(season==='summer'?(language==='en'?'Book summer photography':'夏のロケーション撮影を予約'):(language==='en'?'Book winter photography':'雪上撮影を予約')));
 assert.ok(renderToStaticMarkup(setup(season,language,{[season==='summer'?'summer_021':'winter_010']:'原自訂按鈕'}).render()).includes('原自訂按鈕'));
 assert.ok(html.includes('/snowland/booking?service=photo'),'Keep canonical booking route');
 for(const button of all(tree,n=>n.type==='button'))assert.equal(all(button,n=>n!==button&&n.type==='button').length,0,'Never nest buttons');
 if(season==='summer')for(const key of ['切換旅拍照片','切換旅拍輕婚紗照片','切換旅拍婚紗照片']){
  const label=locale.translateSiteText(language,key),getGroup=()=>all(app.render(),n=>n.type==='div'&&n.props.className==='relative'&&React.Children.toArray(n.props.children).some(c=>c.props?.['aria-label']===label))[0];
  const group=getGroup(),image=all(group,n=>n.type==='button'&&n.props['aria-label']===label)[0];image.props.onClick();
  let dots=all(getGroup(),n=>n.type==='button'&&typeof n.props['aria-pressed']==='boolean');assert.equal(dots[1].props['aria-pressed'],true);
  dots[2].props.onClick({stopPropagation(){}});dots=all(getGroup(),n=>n.type==='button'&&typeof n.props['aria-pressed']==='boolean');assert.equal(dots[2].props['aria-pressed'],true);assert.equal(dots.filter(n=>n.props['aria-pressed']).length,1);assert.ok(dots.every(n=>n.props.className.includes('h-11 w-11')));
 }
}
console.log('PASS actual photography layouts en/ja carousel callbacks, independent44px dots/pressed state, no nested buttons, original CMS copy and tenant booking routes');
