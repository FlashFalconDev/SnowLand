const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module');
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server');
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const found=find(child,p);if(found)return found;}return null;}
function setup(name,language,overrides={}){
 const state=[],navigate=[];let index=0;
 const hooks={...React,useState(value){const key=index++;if(!(key in state))state[key]=value;return[state[key],next=>state[key]=typeof next==='function'?next(state[key]):next];},useRef:value=>({current:value}),useEffect(){},useMemo:fn=>fn()};
 const pricing={currency:'NT$',season_label:'QA原季名',columns:['full','half'],column_labels:{full:'全天',half:'半天'},plans:{regular:{period:'原期間',rows:[{label:'原價格級距',full:9000,half:5000}]},discount:{period:'優惠原期間',rows:[{label:'原價格級距',full:8000,half:4000}]}},fee_notes:['原自訂費用說明'],promotions:[],addons:[]};
 const details=[{external_id:'kamui',title:'原雪場',summary:'原介紹',metadata:{resort:{tabs:[{slug:'rental',title:'租借雪具',html:'<p>原CMS租借內容</p>'}],slopes:[],tags:[],description:'原介紹'}}}];
 const source=fs.readFileSync(path.join(root,`src/pages/site/${name}.jsx`),'utf8').replaceAll('import.meta.env.BASE_URL','"/"');
 const scope={exports:{},require(key){
  if(key==='react')return hooks;
  if(key.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(hooks,language);
  if(key==='react-router-dom')return{useParams:()=>({resort:overrides.resort??'kamui',section:'price'}),useNavigate:()=> (...args)=>navigate.push(args),useLocation:()=>({state:overrides.locationState??null}),Link:p=>React.createElement('a',{href:p.to},p.children)};
  if(key==='framer-motion')return{motion:new Proxy({},{get:(_,tag)=>({initial,whileInView,viewport,transition,...props})=>React.createElement(tag,props)})};
  if(key.includes('useSiteBasePath'))return{useSiteLink:to=>'/snowland'+to};
  if(key.includes('useSiteContent'))return{siteContentToResort:item=>item,useSiteContent:kind=>({items:kind==='course.resort-pages'?(overrides.details??details):[{slug:'kamui',nameChinese:'原雪場',nameEnglish:'QA',route:'/course/kamui',slopes:[]}],isLoading:!!overrides.loading,error:overrides.error??null}),useCoursePricing:()=>({pricing:overrides.noPricing?null:pricing,isLoading:!!overrides.pricingLoading,isStale:!!overrides.stale,error:overrides.pricingError??null})};
  if(key.endsWith('SiteLink'))return p=>React.createElement('a',{href:'/snowland'+p.to},p.children);
  if(key.endsWith('SiteHeader'))return p=>React.createElement('header',{'data-dark-text':p.forceDarkText?'yes':'no','data-color-logo':p.forceLogoColor?'yes':'no'});
  if(/SiteFooter|HokkaidoMap/.test(key))return()=>null;
  if(key.endsWith('.png'))return'qa-map.png';
  throw Error(key);
 }};
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true}}).outputText,scope);
 return{render(){index=0;return scope.exports.default();},navigate};
}
for(const name of ['ResortCoursePage','TomamuCoursePage'])for(const language of ['en','ja']){
 const app=setup(name,language),tree=app.render();let html=renderToStaticMarkup(tree);
 assert.ok(html.includes(language==='en'?'Discount period':'割引期間'));
 assert.ok(html.includes(language==='en'?'Regular period':'通常期間'));
 assert.ok(html.includes('NT$9,000')&&html.includes('原價格級距')&&html.includes('原自訂費用說明'));
 assert.ok(html.includes('QA原季名')&&html.includes('原期間'));
 assert.ok(html.includes(require('./helpers/site-locale-harness.cjs')(React,language).translateSiteText(language,'本雪季課程時間請以預約流程可選時段為準。')));
 assert.ok(!html.includes('全天5hr課程')&&!html.includes('半天3h課程')&&!html.includes('08:30~09:00'),'Both resort pricing pages must not display obsolete fixed lesson schedules');
 const toggle=find(tree,n=>n.props?.role==='switch');assert.equal(toggle.props['aria-checked'],true);assert.ok(toggle.props.className.includes('h-11'));
 toggle.props.onClick();html=renderToStaticMarkup(app.render());assert.ok(html.includes('NT$8,000')&&html.includes('優惠原期間'));assert.equal(find(app.render(),n=>n.props?.role==='switch').props['aria-checked'],false);
 for(const [flags,text]of [[{pricingLoading:true},language==='en'?'Loading prices':'料金を読み込み中'],[{stale:true},language==='en'?'not published yet':'まだ公開されていません'],[{noPricing:true},language==='en'?'not published yet':'まだ公開されていません'],[{pricingError:Error('QA')},language==='en'?'could not be loaded':'読み込めませんでした']])assert.ok(renderToStaticMarkup(setup(name,language,flags).render()).includes(text));
 if(name==='ResortCoursePage'){
  assert.ok(html.includes('data-dark-text="yes"')&&html.includes('data-color-logo="yes"'),'Direct white pricing page needs readable header');
  assert.ok(renderToStaticMarkup(setup(name,language,{locationState:{viaTabNav:true}}).render()).includes('data-dark-text="no"'),'Hero navigation retains original transparent-header behavior');
  const rental=find(tree,n=>n.type==='button'&&n.props.children?.[0]===(language==='en'?'Equipment rental':'レンタル用品'));assert.ok(rental);rental.props.onClick();assert.equal(app.navigate[0][0],'/snowland/course/kamui/rental');html=renderToStaticMarkup(app.render());assert.ok(html.includes('原CMS租借內容'));
  assert.ok(renderToStaticMarkup(setup(name,language,{details:[],loading:true}).render()).includes(language==='en'?'Loading resort information':'スキー場情報を読み込み中'));
  for(const cmsHtml of ['', '<p>QA原托兒服務內容</p>']){
   const app2=setup(name,language,{details:[{external_id:'kamui',title:'原雪場',metadata:{resort:{tabs:[{slug:'nursery',title:'雪場托兒',html:cmsHtml}]}}}]});
   const tab=find(app2.render(),n=>n.type==='button'&&n.props.children?.[0]===(language==='en'?'Childcare':'託児サービス'));assert.ok(tab);tab.props.onClick();
   const body=renderToStaticMarkup(app2.render());assert.ok(!body.includes('xxxx')&&!body.includes('方案一'));
   assert.ok(body.includes(cmsHtml?'QA原托兒服務內容':require('./helpers/site-locale-harness.cjs')(React,language).translateSiteText(language,'相關資訊尚未公布，請與 SnowLand 聯繫確認。')));
  }
  const stay=setup(name,language,{details:[{external_id:'kamui',title:'原雪場',metadata:{resort:{tabs:[{slug:'accommodation',title:'住宿',html:''}]}}}]});
  find(stay.render(),n=>n.type==='button'&&n.props.children?.[0]===(language==='en'?'Accommodation':'宿泊')).props.onClick();
  const stayHtml=renderToStaticMarkup(stay.render());assert.ok(stayHtml.includes(language==='en'?'Accommodation in central Asahikawa':'旭川市街の宿泊施設'));
  const slope=setup(name,language,{details:[{external_id:'kamui',title:'原雪場',metadata:{resort:{tabs:[{slug:'ski-slope',title:'雪道介紹',html:''}]}}}]});
  find(slope.render(),n=>n.type==='button'&&n.props.children?.[0]===(language==='en'?'Trail guide':'コース案内')).props.onClick();
  const slopeHtml=renderToStaticMarkup(slope.render());for(const text of ['Kids Garden','Royal Powder','4,000m','15:00','150m'])assert.ok(slopeHtml.includes(text),text);
  assert.ok(slopeHtml.includes(language==='en'?'A slope for children and first-time skiers':'子どもや初心者向けの斜面'));
  assert.ok(!slopeHtml.includes('進階'),'All canonical trail level labels must be translated');
  assert.ok(slopeHtml.includes('min-w-[980px] text-left text-sm'),'Scrollable mobile descriptions must not shrink to 10px');
  assert.ok(slopeHtml.includes(language==='en'?'Runs listed on this page':'このページの掲載コース数'));assert.ok(!slopeHtml.includes('Number of runs</div><div>25'),'Count must come from the rendered list, not the conflicting old constant');
  assert.ok(!slopeHtml.includes('小朋友與初學者專用的斜坡')&&!slopeHtml.includes('第5雙人吊椅'));
  const sapporo=setup(name,language,{resort:'sapporo-kokusai',details:[{external_id:'sapporo-kokusai',title:'原札幌',metadata:{resort:{tabs:[{slug:'accommodation',title:'住宿',html:''}]}}}]});
  find(sapporo.render(),n=>n.type==='button'&&n.props.children?.[0]===(language==='en'?'Accommodation':'宿泊')).props.onClick();
  assert.ok(renderToStaticMarkup(sapporo.render()).includes(language==='en'?'Located in Sapporo':'札幌中心部の繁華街'));
 }
 if(name==='TomamuCoursePage'){
  const locale=require('./helpers/site-locale-harness.cjs')(React,language),t=text=>locale.translateSiteText(language,text)
  assert.ok(html.includes(t('本雪季課程時間請以預約流程可選時段為準。')))
  assert.ok(!html.includes('全天5hr課程')&&!html.includes('半天3h課程')&&!html.includes('08:30~09:00'),'No obsolete fixed timetable alongside backend pricing')
  for(const text of ['特色','親子樂園','初學友善','雪道比例待雪場資料確認後更新。'])assert.ok(html.includes(t(text)),text)
  const nursery=find(app.render(),n=>n.props.to==='/course/tomamu/nursery')
  assert.ok(nursery);nursery.props.onClick();let branch=renderToStaticMarkup(app.render())
  for(const text of ['室內托兒','全日托兒','夜間托兒','營業時間','適合年齡','費用'])assert.ok(branch.includes(t(text)),text)
  for(const text of ['2 小時 6,000 日元；每增加 30 分鐘 1,500 日元。','5 個月至 8 歲（學齡前）。','25,000 日元；延長 30 分鐘 1,500 日元。','2 小時 8,000 日元；每增加 30 分鐘 2,000 日元。','需提前預訂，費用 1,200 日元。','提供網路預約，當日現場不接受報名採完全預約制。'])assert.ok(branch.includes(t(text)),text)
  for(const amount of ['6,000','1,500','25,000','8,000','2,000','1,200'])assert.ok(branch.includes(amount),'Preserve provider amount '+amount)
  const access=find(app.render(),n=>n.props.to==='/course/tomamu/access')
  assert.ok(access);access.props.onClick();branch=renderToStaticMarkup(app.render())
  for(const text of ['交通方式','搭乘國鐵 (JR)','開車前往','乘坐巴士','查看 Google Map'])assert.ok(branch.includes(t(text)),text)
  for(const text of ['2024/03/16 起，停靠 TOMAMU 的列車改為全車指定席。','每班特快列車抵達後皆有免費接駁巴士送往飯店，無需預約。','新千歲機場出發：約 90 分鐘（千歲東 I.C. → TOMAMU I.C.）'])assert.ok(branch.includes(t(text)),text)
  const drivingLinks=find(app.render(),n=>n.props.className==='flex flex-col items-start gap-2 text-sm')
  assert.ok(drivingLinks,'Driving information links remain separated, including English')
  React.Children.toArray(drivingLinks.props.children).forEach(n=>assert.ok(n.props.className.includes('min-h-[44px]')))
  assert.ok(branch.includes('2024/03/16')&&branch.includes('2024/04/01'),'Keep source dates unchanged')
  const accommodation=find(app.render(),n=>n.props.to==='/course/tomamu/accommodation')
  accommodation.props.onClick();branch=renderToStaticMarkup(app.render())
  assert.ok(branch.includes(t('位於度假村中心位置，非常便利的飯店。推薦給想享受機動性度假住宿的人。')))
  assert.ok(branch.includes('100 m²')||branch.includes('100㎡'))
  const lift=find(app.render(),n=>n.props.to==='/course/tomamu/lift');lift.props.onClick();branch=renderToStaticMarkup(app.render())
  for(const text of ['新冬試滑一日券','4小時券','通過閘門初次感應後起算4小時','購入後不可退款，取消及變更。','敬老價格適用於60歲及以上人士，購買纜車票時請出示能確認年齡的身分證明。'])assert.ok(branch.includes(t(text)),text)
  assert.ok(branch.includes(language==='en'?'JPY 7,700':'7,700円'))
  assert.ok(branch.includes(t('以下為 2025–2026 雪季參考資料；最新雪票價格與使用規則請以雪場官方網站為準。')),'Old season data must not be presented as current rates')
  assert.ok(branch.includes(language==='en'?'2025/12/1':'2025年12月1日'),'Do not silently roll old ticket season dates forward')
  assert.ok(!branch.includes(' 日圓')&&!branch.includes('期間內可使用'))
  const rentalTab=find(app.render(),n=>n.props.to==='/course/tomamu/rental');rentalTab.props.onClick();branch=renderToStaticMarkup(app.render())
  for(const text of ['The Tower 1F 租賃區','可使用網路預約，可以記房帳，租借超方便。','高階裝備的尺寸請洽詢工作人員。'])assert.ok(branch.includes(t(text)),text)
  assert.ok(branch.includes('125cm～165cm')&&branch.includes('70cm～140cm'),'Equipment size numbers are unchanged')
 }
}
console.log('PASS resort/Tomamu actual UI en/ja: pricing toggle keeps amounts/data, original tab keys and tenant navigation, missing/loading/stale/error prices, CMS preservation');
