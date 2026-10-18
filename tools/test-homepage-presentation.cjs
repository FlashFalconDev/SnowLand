const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const defaults=JSON.parse(fs.readFileSync(path.join(__dirname,'../snowland/Client/fixtures/homepage_presentation_defaults.json'),'utf8'))
const compile=source=>ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;if(typeof node.type==='function')return find(node.type(node.props),p);for(const c of React.Children.toArray(node.props?.children)){const result=find(c,p);if(result)return result}return null}
function setup(hero={},intro={},sections={}){
 let expanded=false,retries=0
 const motion=new Proxy({},{get:(_,tag)=>p=>{const {initial,animate,transition,...props}=p;return React.createElement(tag,props)}})
 const ctx=vm.createContext({exports:{},require:name=>{
   if(name==='react')return{...React,useState:()=>[expanded,v=>expanded=typeof v==='function'?v(expanded):v]}
   if(name==='framer-motion')return{motion}
   if(name==='./SiteLink')return p=>React.createElement('a',{href:'/snowland'+p.to,className:p.className},p.children)
   if(name==='./SiteHeader')return p=>React.createElement('header',{'data-dark':String(p.forceDarkText)})
   if(name.includes('About snowland'))return'/qa-original-photo.jpg'
   if(name.includes('useSiteContent'))return{useSiteContent:key=>({items:defaults.filter(row=>row.location_key===key),isLoading:false,error:null,refetch(){retries++},...(key==='homepage.hero'?hero:key==='homepage.intro'?intro:sections[key] || {})})}
   throw Error(name)
 }})
 vm.runInContext(compile(fs.readFileSync(path.join(root,'src/components/site/HomepagePresentation.jsx'),'utf8')),ctx)
 return{render:()=>ctx.exports.default({containerRef:{current:null},y:0,opacity:1}),components:ctx.exports,retries:()=>retries}
}
let app=setup(),html=renderToStaticMarkup(app.render())
assert.ok(html.includes(defaults[0].title));assert.ok(html.includes(defaults[0].summary));assert.ok(html.includes('https://www.youtube.com/embed/m-4vgzqVNqI?'))
assert.ok(html.includes('src="/qa-original-photo.jpg"'));assert.ok(html.includes('/snowland/booking'));assert.ok(html.includes('/snowland/about'))
assert.ok(html.includes('<span class="font-semibold">中文、粵語、英文</span>'));assert.ok(!html.includes('我們將根據您的需求'))
find(app.render(),n=>n.type==='button'&&n.props['aria-expanded']===false).props.onClick();html=renderToStaticMarkup(app.render());assert.ok(html.includes('我們將根據您的需求'));assert.ok(html.includes('aria-expanded="true"'))
find(app.render(),n=>n.type==='button'&&n.props['aria-expanded']===true).props.onClick();assert.ok(!renderToStaticMarkup(app.render()).includes('我們將根據您的需求'))
const custom={...defaults[0],title:'QA全新標題\n第二行',summary:'QA說明',subtitle:'QA English',image_url:'/vite.svg',link_url:'/contact',metadata:{media_type:'image',button_text:'QA聯絡'}}
html=renderToStaticMarkup(setup({items:[custom]}).render());assert.ok(html.includes('QA全新標題'));assert.ok(html.includes('/snowland/contact'));assert.ok(!html.includes('<iframe'));assert.ok(html.includes('src="/vite.svg"'));assert.ok(!html.includes('官方許可滑雪學校'))
html=renderToStaticMarkup(setup({items:[]},{items:[]}).render());assert.ok(!html.includes('官方許可'));assert.ok(!html.includes('<iframe'));assert.ok(html.includes('data-dark="true"'))
html=renderToStaticMarkup(setup({isLoading:true,items:[]},{items:[]}).render());assert.ok(html.includes('正在載入'));assert.ok(!html.includes('官方許可'))
app=setup({error:Error('QA'),items:[]});const retry=find(app.render(),n=>n.type==='button'&&n.props.children[0]==='重新載入');assert.ok(retry);retry.props.onClick();assert.equal(app.retries(),1)
html=renderToStaticMarkup(setup({items:[{...custom,metadata:{media_type:'youtube',youtube_id:'bad"<script>'}}]}).render());assert.ok(!html.includes('<iframe'))
const changedIntro={...defaults[1],image_url:'',link_url:'',metadata:{...defaults[1].metadata,image_asset:'',opening_text:'<script>只當文字</script>',extra_paragraphs:[]}}
html=renderToStaticMarkup(setup({items:[]},{items:[changedIntro]}).render());assert.ok(!html.includes('<img'));assert.ok(html.includes('&lt;script&gt;只當文字'));assert.ok(!html.includes('展開'))
let form={...defaults[1],metadata:{...defaults[1].metadata,custom:'原資料'}}
const context=vm.createContext({React,exports:{}});vm.runInContext(compile(fs.readFileSync(path.join(root,'src/admin/components/HomepagePresentationFields.tsx'),'utf8')),context)
const render=()=>context.exports.default({value:form,onChange:patch=>form={...form,...patch}})
find(render(),n=>n.type==='label'&&n.props.children[0]==='第1段：粗體雪場名稱').props.children[1].props.onChange({target:{value:'QA新雪場'}});assert.equal(form.metadata.resort_names,'QA新雪場');assert.equal(form.metadata.custom,'原資料')
find(render(),n=>n.type==='button'&&n.props.children==='新增展開段落').props.onClick();assert.equal(form.metadata.extra_paragraphs.length,3)
find(render(),n=>n.type==='button'&&Array.isArray(n.props.children)&&n.props.children.join('')==='移除第3段').props.onClick();assert.equal(form.metadata.extra_paragraphs.length,2)
const coach=defaults.find(row=>row.location_key==='homepage.coaches'),contact=defaults.find(row=>row.location_key==='homepage.contact')
assert.ok(coach&&contact,'Both sections must have original source defaults')
html=renderToStaticMarkup(setup().components.HomepageCoachHeading({item:{...coach,title:'QA教練標題',summary:'QA說明',link_url:''}}))
assert.ok(html.includes('QA教練標題'));assert.ok(html.includes('QA說明'));assert.ok(!html.includes('<a'))
html=renderToStaticMarkup(setup().components.HomepageContactBanner());assert.ok(html.includes('/snowland/contact'));assert.ok(html.includes('立即諮詢'));assert.ok(html.includes('off-piste-guide-006.jpg'));assert.ok(!html.includes('md:h-[190px]'),'Long CMS text must not be clipped by a fixed height')
html=renderToStaticMarkup(setup({}, {},{'homepage.contact':{items:[{...contact,title:'QA新標題\n第二行',summary:'<script>只當文字</script>',image_url:'',link_url:'/booking',metadata:{button_text:'QA預約'}}]}}).components.HomepageContactBanner())
assert.ok(html.includes('QA新標題'));assert.ok(html.includes('第二行'));assert.ok(html.includes('/snowland/booking'));assert.ok(html.includes('&lt;script&gt;只當文字'));assert.ok(!html.includes('off-piste-guide-006.jpg'))
assert.equal(renderToStaticMarkup(setup({}, {},{'homepage.contact':{items:[]}}).components.HomepageContactBanner()),'')
app=setup({}, {},{'homepage.contact':{items:[],error:Error('QA')}});const contactRetry=find(app.components.HomepageContactBanner(),n=>n.type==='button');contactRetry.props.onClick();assert.equal(app.retries(),1)
for(const location of ['homepage.coaches','homepage.contact']){
 form={...defaults.find(row=>row.location_key===location),metadata:{custom:'原資料'}}
 const markup=renderToStaticMarkup(render());assert.ok(markup.includes('標題'));assert.ok(!markup.includes('第1段：粗體雪場名稱'))
 find(render(),n=>n.type==='label'&&n.props.children[0]==='說明文字（可空白）').props.children[1].props.onChange({target:{value:'QA可編輯說明'}});assert.equal(form.summary,'QA可編輯說明');assert.equal(form.metadata.custom,'原資料')
 if(location==='homepage.contact')find(render(),n=>n.type==='label'&&n.props.children[0]==='按鈕文字').props.children[1].props.onChange({target:{value:'QA按鈕'}})
 assert.equal(form.metadata.custom,'原資料')
}
const homeSource=fs.readFileSync(path.join(root,'src/pages/site/HomePage.jsx'),'utf8'),homeAst=ts.createSourceFile('HomePage.jsx',homeSource,ts.ScriptTarget.Latest,true,ts.ScriptKind.JSX)
let dots
function findDots(node){if(ts.isJsxElement(node)&&node.openingElement.attributes.getText(homeAst).includes('mt-4 flex')&&node.getText(homeAst).includes('coach-dot-'))dots??=node;ts.forEachChild(node,findDots)}
findDots(homeAst);assert.ok(dots)
const dotCtx=vm.createContext({React,exports:{},coachCards:Array.from({length:12},(_,index)=>({name:'QA'+index})),activeCoachIndex:1,scrollToCoachIndex:index=>dotCtx.clicked=index})
vm.runInContext(compile('exports.render=()=>('+dots.getText(homeAst)+')'),dotCtx)
const dotsTree=dotCtx.exports.render();assert.ok(dotsTree.props.className.includes('flex-wrap'),'Many 44px coach controls must wrap instead of widening the whole phone page')
assert.equal(React.Children.toArray(dotsTree.props.children).length,12)
const secondDot=find(dotsTree,node=>node.type==='button'&&node.props['aria-pressed']===true)
assert.ok(secondDot.props.className.includes('min-h-11 min-w-11'));secondDot.props.onClick();assert.equal(dotCtx.clicked,1)
console.log('PASS actual homepage presentation: original copy/photo/bold/motion classes, dynamic title/media/CTA, expand-collapse, hidden/loading/error retry, escaped text; editor preserves metadata and edits paragraphs')
