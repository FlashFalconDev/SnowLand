const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module');
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server');
function find(n,p){if(!n||typeof n!=='object')return null;if(p(n))return n;for(const c of React.Children.toArray(n.props?.children)){const x=find(c,p);if(x)return x;}return null;}
function setup(language,overrides={}){let i=0;const states=[];const hooks={...React,useEffect(){},useRef:v=>({current:v}),useState(value){const key=i++;if(!(key in states))states[key]=value;return[states[key],next=>states[key]=typeof next==='function'?next(states[key]):next];}};
 const pricing={season_label:'26-27 QA',currency:'JPY ',columns:['full','half'],column_labels:{full:'全天',half:'半天'},plans:{regular:{period:'QA原日期',rows:[{label:'QA原級距',full:62000,half:41000}]},discount:{period:'QA優惠日期',rows:[{label:'QA原級距',full:58000,half:36000}]}},fee_notes:['QA原費用文字'],promotions:[{title:'QA原優惠',lines:['QA原優惠內容']}],addons:[{title:'QA原加購',rows:[['QA名稱','QA金額']]}]};
 const scope={exports:{},require(name){if(name==='react')return hooks;
 if(name.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(hooks,language);
 if(name.includes('useSiteContent'))return{useCoursePricing(slug){assert.equal(slug,'off-piste-guide');return{pricing,isLoading:false,isStale:false,error:null,...overrides};}};
 if(name==='react-router-dom')return{Link:p=>React.createElement('a',{href:p.to},p.children)};
 if(name.endsWith('SiteLink'))return p=>React.createElement('a',{href:'/snowland'+p.to},p.children);
 if(/SiteFooter|SiteHeader/.test(name))return()=>null;
 if(name.endsWith('resortNavigation'))return[{slug:'qa-resort',nameChinese:'QA原雪場',route:'/course/qa-resort'},{slug:'off-piste-guide',nameChinese:'野雪嚮導',route:'/course/off-piste-guide'}];
 throw Error(name);}};
 const source=fs.readFileSync(path.join(root,'src/pages/site/OffPisteGuidePage.jsx'),'utf8').replaceAll('import.meta.env.BASE_URL','"/"');vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,scope);
 return{render(){i=0;return scope.exports.default();},t:require('./helpers/site-locale-harness.cjs')(React,language).translateSiteText.bind(null,language)};
}
for(const language of ['en','ja']){
 const app=setup(language);let tree=app.render(),html=renderToStaticMarkup(tree);
 assert.ok(html.includes(app.t('野雪嚮導價格')));
 for(const text of ['你已經征服雪道，現在是時候探索真正的粉雪天堂。','星野・富良野・旭岳・十勝岳連峰','中高階','無人探索的自然粉雪地形、山谷、林間、雪場界外','✓ 雪況說明與風險評估','提供 Beacon、Probe、Shovel 租借與現場教學。','BC裝備','雪崩三寶：Beacon發信/收信器、雪鏟、探測棒','防風保暖的衣物','能穩定滑行紅線以上雪道，具備基本粉雪環境控制能力。','在富良野，不只有雪場，更有值得深入探訪的高山粉雪路線。這裡地形變化豐富，雪質乾爽，長距離林間滑行與登頂滑雪挑戰兼備。'])assert.ok(html.includes(app.t(text)),text);
 const areaTitle=find(tree,n=>n.props.children===app.t('星野・富良野・旭岳・十勝岳連峰'));assert.ok(areaTitle.props.className.includes('break-words')&&!areaTitle.props.className.includes('whitespace-nowrap'));
 assert.ok(html.includes('QA原級距')&&html.includes('26-27 QA')&&html.includes('QA原日期'));
 assert.ok(html.includes('JPY 62,000')&&html.includes('JPY 41,000')&&html.includes('/snowland/booking')&&html.includes('QA原雪場'));
 for(const value of ['QA原費用文字','QA原優惠','QA原優惠內容','QA原加購','QA名稱','QA金額'])assert.ok(html.includes(value));
 assert.ok(!html.includes('25-26 SEASON')&&!html.includes('2025/')&&!html.includes('NT$21,000'));
 const toggle=find(tree,n=>n.props?.role==='switch');assert.equal(toggle.props['aria-checked'],true);assert.ok(toggle.props.className.includes('h-11'));toggle.props.onClick();html=renderToStaticMarkup(app.render());assert.ok(html.includes('JPY 58,000')&&html.includes('JPY 36,000'));assert.equal(find(app.render(),n=>n.props?.role==='switch').props['aria-checked'],false);
 const question=app.t('是否提供雪崩安全裝備？'),faq=find(tree,n=>n.type==='button'&&find(n,c=>c.type==='h3'&&c.props.children===question));assert.ok(faq.props.className.includes('min-h-[44px]'));faq.props.onClick();html=renderToStaticMarkup(app.render());assert.ok(html.includes(app.t('可提供雪崩裝備租借，並由嚮導在行程前進行基本使用說明。')));assert.equal(find(app.render(),n=>n.type==='button'&&find(n,c=>c.type==='h3'&&c.props.children===question)).props['aria-expanded'],true);
 find(app.render(),n=>n.type==='button'&&find(n,c=>c.type==='h3'&&c.props.children===question)).props.onClick();assert.ok(!renderToStaticMarkup(app.render()).includes(app.t('可提供雪崩裝備租借，並由嚮導在行程前進行基本使用說明。')));
 for(const key of ['上一張照片','下一張照片'])assert.ok(find(tree,n=>n.type==='button'&&n.props['aria-label']===app.t(key)).props.className.includes('h-11 w-11'));
 for(const flags of [{pricing:null},{pricing:null,isStale:true},{pricing:null,isLoading:true},{pricing:null,error:Error('QA')}]){
  const missing=setup(language,flags),node=missing.render(),markup=renderToStaticMarkup(node);assert.equal(find(node,n=>n.props?.role==='switch'),null);assert.ok(!markup.includes('2025/')&&!markup.includes('NT$21,000'));
  assert.ok(markup.includes(app.t(flags.isLoading?'價目載入中。':flags.error?'價目暫時無法載入，請稍後再試。':'本雪季價目尚未發布。請至')));
 }
}
console.log('PASS actual off-piste en/ja: server pricing/columns/addons/fees/offers, period switch, absent/stale/loading/error failclosed, FAQ/44px/tenant route; no fixed old prices');
// Execute exact CMS preview/option declarations, preserving normal resort routes.
const cmsFile=path.join(root,'src/admin/pages/cms/SiteContentPage.tsx'),cmsSource=fs.readFileSync(cmsFile,'utf8'),cmsAst=ts.createSourceFile(cmsFile,cmsSource,99,true,ts.ScriptKind.TSX),declarations={};
function collect(n){if(ts.isVariableDeclaration(n)&&['buildOfficialPreviewUrl','basePricingResortOptions','pricingResortOptions'].includes(n.name.getText(cmsAst)))declarations[n.name.getText(cmsAst)]=n.parent.parent.getText(cmsAst);ts.forEachChild(n,collect);}collect(cmsAst);
const preview={exports:{},getTenantBasePath:()=>'/snowland',SITE_PREVIEW_ROUTES:{}};vm.runInNewContext(ts.transpileModule(declarations.buildOfficialPreviewUrl+';exports.preview=buildOfficialPreviewUrl;', {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,preview);
assert.equal(preview.exports.preview('course.pricing','off-piste-guide'),'/snowland/course/off-piste-guide?cmsPreview=course.pricing#pricing');
assert.equal(preview.exports.preview('course.pricing','tomamu'),'/snowland/course/tomamu/price?cmsPreview=course.pricing');
for(const existing of ['','custom']){const options={exports:{},resortOptions:[{value:'tomamu',label:'原星野'}],form:{external_id:existing}};vm.runInNewContext(ts.transpileModule(declarations.basePricingResortOptions+';'+declarations.pricingResortOptions+';exports.options=pricingResortOptions;', {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,options);assert.equal(options.exports.options.filter(o=>o.value==='off-piste-guide').length,1);assert.ok(options.exports.options.some(o=>o.value==='tomamu'));if(existing)assert.ok(options.exports.options.some(o=>o.value===existing));}
console.log('PASS actual CMS declarations: selectable off-piste/no duplicate/preserved custom and resort options; preview query before pricing hash');
const hookFile=path.join(root,'src/hooks/useSiteContent.js'),hookSource=fs.readFileSync(hookFile,'utf8'),hookAst=ts.createSourceFile(hookFile,hookSource,99,true,ts.ScriptKind.JS),hook=hookAst.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='useCoursePricing').getText(hookAst);
class FixedDate extends Date{static now(){return Date.parse('2026-10-20T00:00:00Z');}}
for(const [season,stale]of [['25-26 SEASON',true],['26-27 SEASON',false]]){const stored={season_label:season,plans:{regular:{rows:[{label:'QA',full:62000}]}}},ctx={exports:{},Date:FixedDate,useSiteContent:key=>{assert.equal(key,'course.pricing');return{items:[{external_id:'off-piste-guide',metadata:{pricing:stored}}]};}};vm.runInNewContext(ts.transpileModule(hook,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,ctx);const result=ctx.exports.useCoursePricing('off-piste-guide');assert.equal(result.isStale,stale);assert.equal(result.pricing,stale?null:stored);assert.equal(ctx.exports.useCoursePricing('missing').pricing,null);}
console.log('PASS real useCoursePricing hook: old-season excluded, current metadata preserved, never borrow another slug pricing');
