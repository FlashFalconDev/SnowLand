const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm'), Module=require('node:module')
const root=path.resolve(__dirname,'..'), req=Module.createRequire(path.join(root,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const compile=source=>ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText
const data=vm.createContext({exports:{},URL});vm.runInContext(compile(fs.readFileSync(path.join(root,'src/data/site/footerSettings.js'),'utf8')),data)
const settings=data.exports
for(const invalid of ['javascript:alert(1)','//example.test','http://example.test','https://a@evil.test','https://a:b@evil.test','https://example.test:bad','https:\\evil.test','https://example.test/\n','https://example.test/a b',{},null])assert.equal(settings.safeFooterLink(invalid),'')
assert.equal(settings.safeFooterLink('https://example.test/a?b=1&c=2'),'https://example.test/a?b=1&c=2')
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;if(typeof node.type==='function')return find(node.type(node.props),p);for(const child of React.Children.toArray(node.props?.children)){const match=find(child,p);if(match)return match}return null}
const defaults=JSON.parse(fs.readFileSync(path.join(__dirname,'../../snowland/Client/fixtures/site_footer_defaults.json'),'utf8'))
function setup(result={items:[defaults]},scrolled=false,language='zh-Hant'){
 let index=0,open=false,retries=0,topCalls=0
 const motion=new Proxy({},{get:(_,tag)=>p=>{const{initial,animate,exit,transition,...props}=p;return React.createElement(tag,props)}})
 const ctx=vm.createContext({exports:{},window:{scrollTo:()=>topCalls++},require:name=>{if(name.includes('hooks/useClient'))return{useClientInfo:()=>({clientCode:'snowland',clientName:'SnowLand',clientInfo:{}})};
  if(name==='react')return{...React,useEffect(){},useState(){const slot=index++;return slot%2===0?[scrolled,()=>{}]:[open,v=>open=typeof v==='function'?v(open):v]}}
  if(name==='framer-motion')return{motion,AnimatePresence:p=>p.children}
  if(name==='./SiteLink')return p=>React.createElement('a',{href:'/snowland'+p.to},p.children)
  if(name.includes('logo-white'))return'/logo-white.png'
  if(name.includes('assetPaths'))return{homepageAssetBase:'/homepage'}
  if(name.includes('navigationLinks'))return{faqLink:'/faq'}
  if(name.includes('footerSettings'))return settings
  if(name.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(React,language)
  if(name.includes('useSiteContent'))return{useSiteContent:(key,options)=>{assert.equal(key,'site.footer');assert.equal(options.limit,1);return{isLoading:false,error:null,...result,refetch:()=>retries++}}}
  throw Error(name)
 }})
 vm.runInContext(compile(fs.readFileSync(path.join(root,'src/components/site/SiteFooter.jsx'),'utf8')),ctx)
 return{render:()=>{index=0;return ctx.exports.default()},retries:()=>retries,topCalls:()=>topCalls}
}
let app=setup(),html=renderToStaticMarkup(app.render())
assert.ok(html.includes('SNOWLAND合同会社'));assert.ok(html.includes('mailto:land110602@gmail.com'));assert.ok(html.includes('https://www.instagram.com/snowlandcz/'));assert.ok(html.includes('h-11 w-11'))
const custom={metadata:{company_name:'QA新公司',company_name_secondary:'<script>只當文字</script>',email:'qa@example.test',copyright:'QA版權',social_links:{instagram:'https://instagram.com/qa/',line:'https://line.me/qa',whatsapp:''}}}
app=setup({items:[custom]},true);html=renderToStaticMarkup(app.render())
assert.ok(html.includes('QA新公司'));assert.ok(html.includes('&lt;script&gt;只當文字'));assert.ok(!html.includes('land110602'));assert.ok(!html.includes('客服 LINE'))
find(app.render(),n=>n.props?.['aria-label']==='開啟客服連結').props.onClick()
html=renderToStaticMarkup(app.render());assert.ok(html.includes('aria-label="客服 LINE"'));assert.ok(!html.includes('客服 WhatsApp'));assert.ok(!html.includes('snowlandcz'))
find(app.render(),n=>n.props?.['aria-label']==='回到頂部').props.onClick();assert.equal(app.topCalls(),1)
app=setup({items:[]},true);html=renderToStaticMarkup(app.render());assert.ok(!html.includes('land110602'));assert.ok(!html.includes('開啟客服連結'));assert.ok(html.includes('/snowland/privacy-policy'));assert.ok(html.includes('回到頂部'))
html=renderToStaticMarkup(setup({items:[],isLoading:true}).render());assert.ok(html.includes('載入聯絡資訊'));assert.ok(!html.includes('snowlandcz'))
app=setup({items:[],error:Error('QA')});html=renderToStaticMarkup(app.render());assert.ok(html.includes('聯絡資訊暫時無法載入'));find(app.render(),n=>n.type==='button'&&n.props.children==='重新載入聯絡資訊').props.onClick();assert.equal(app.retries(),1)
html=renderToStaticMarkup(setup({items:[{metadata:{social_links:{line:'javascript:alert(1)'},email:'bad\nBcc:x'}}]},true).render());assert.ok(!html.includes('javascript:'));assert.ok(!html.includes('mailto:'));assert.ok(!html.includes('開啟客服連結'))
for(const language of ['en','ja']){
  const translated=renderToStaticMarkup(setup({items:[custom]},true,language).render())
  assert.ok(translated.includes(language==='en'?'Privacy policy':'プライバシーポリシー'))
  assert.ok(translated.includes(language==='en'?'Open support links':'お問い合わせ先を開く'))
  assert.ok(translated.includes('QA新公司')&&translated.includes('https://instagram.com/qa/'),'Do not translate customer company names or social URLs')
}
let form={title:'頁尾',metadata:{...custom.metadata,custom:'保留'}}
const editor=vm.createContext({exports:{},React,require:name=>{if(name.includes('footerSettings'))return settings;throw Error(name)}})
vm.runInContext(compile(fs.readFileSync(path.join(root,'src/admin/components/SiteFooterFields.tsx'),'utf8')),editor)
const render=()=>editor.exports.default({value:form,onChange:patch=>form={...form,...patch}})
find(render(),n=>n.type==='label'&&n.props.children[0]==='公司名稱（第一行）').props.children[1].props.onChange({target:{value:'QA已修改公司'}})
assert.equal(form.metadata.company_name,'QA已修改公司');assert.equal(form.metadata.custom,'保留')
find(render(),n=>n.type==='label'&&n.props.children[0]==='Instagram').props.children[2].props.onChange({target:{value:''}})
assert.equal(form.metadata.social_links.instagram,'');assert.equal(form.metadata.social_links.line,'https://line.me/qa');assert.equal(form.metadata.custom,'保留')
// Saving creates/edits must remount the actual public preview, not show old contact data.
const cmsSource=fs.readFileSync(path.join(root,'src/admin/pages/cms/SiteContentPage.tsx'),'utf8')
const cmsAst=ts.createSourceFile('SiteContentPage.tsx',cmsSource,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
const panel=cmsAst.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='PreviewSidePanel')
const Frame=()=>null,noop=()=>null,preview=vm.createContext({React,exports:{},OfficialSiteFrame:Frame,ExternalLink:noop,Edit:noop,StatusPill:noop,getTypeLabel:()=>'',buildOfficialPreviewUrl:()=>'/snowland/#site-footer'})
vm.runInContext(compile(panel.getText(cmsAst)+'\nexports.render=PreviewSidePanel'),preview)
const panelTree=item=>preview.exports.render({item,groupLabel:'首頁',location:{key:'site.footer',label:'頁尾與社群'},onEdit:noop})
const frameKey=item=>find(panelTree(item),node=>node.type===Frame).key
assert.notEqual(frameKey(null),frameKey({id:1,updated_at:'2026-10-19T03:00:00'}))
assert.notEqual(frameKey({id:1,updated_at:'2026-10-19T03:00:00'}),frameKey({id:1,updated_at:'2026-10-19T03:01:00'}))
const page=cmsAst.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='SiteContentPage')
const declarations=page.body.statements.filter(node=>ts.isVariableStatement(node))
const selected=declarations.filter(node=>node.declarationList.declarations.some(decl=>['structureItem','structureKey','groups'].includes(decl.name.getText(cmsAst))))
let savedDeps,savedGroups
const memo=vm.createContext({exports:{},CMS_STRUCTURE_LOCATION_KEY:'cms.structure',normalizeCmsStructureGroups:metadata=>metadata.groups || [],useMemo:(callback,deps)=>{if(!savedDeps||deps.some((value,index)=>value!==savedDeps[index])){savedDeps=deps;savedGroups=callback()}return savedGroups}})
vm.runInContext(compile('function groupsFor(contents,contentTypes,reviewGroups){'+selected.map(node=>node.getText(cmsAst)).join('\n')+';return groups}\nexports.groupsFor=groupsFor'),memo)
const structure=()=>({content_type:'setting',location_key:'cms.structure',metadata:{groups:[{id:'homepage',locations:[{key:'site.footer',type:'setting'}]}]}})
const firstGroups=memo.exports.groupsFor([structure()],undefined,{})
const nextGroups=memo.exports.groupsFor([structure(),{id:7,title:'更新過的頁尾'}],undefined,{})
assert.equal(firstGroups,nextGroups,'Refetching identical CMS structure after save must not reset active section through a changed groups dependency')
const changed=structure();changed.metadata.groups.push({id:'custom',locations:[]})
assert.notEqual(nextGroups,memo.exports.groupsFor([changed],undefined,{}),'Actual structure edits must still refresh navigation')
console.log('PASS actual footer/editor: dynamic copy, email, 8 socials, hidden/empty/loading/error retry, shared chat links, clear-hides, unsafe href protection, escaped text, 44px controls, metadata preservation')
