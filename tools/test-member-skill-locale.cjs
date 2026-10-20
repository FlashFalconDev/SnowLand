const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const loadLocale=require('./helpers/site-locale-harness.cjs')
const source=fs.readFileSync(path.join(root,'src/pages/site/MembershipPage.jsx'),'utf8')
const component=source.slice(source.indexOf('function PreCourseForm('),source.indexOf('function MissingStudents('))
const model=fs.readFileSync(path.resolve(root,'../snowland/booking/models.py'),'utf8')
const choices=name=>[...model.split(`${name} = [`)[1].split(']')[0].matchAll(/\("([^"]+)", "([^"]+)"\)/g)].map(match=>[match[1],match[2]])
const skillOptions={snowboard_skills:choices('SNOWBOARD_CHOICES'),ski_skills:choices('SKI_CHOICES')}
const find=(node,p)=>{if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,p);if(result)return result}return null}
async function main(){
 for(const language of ['en','ja']){
  const locale=loadLocale(React,language),t=(text,values)=>locale.translateSiteText(language,text,values)
  for(const [,text] of [...skillOptions.snowboard_skills,...skillOptions.ski_skills]) assert.notEqual(t(text),text,`${language}: ${text}`)
  const states=[],calls=[];let cursor=0
  const form={id:42,age_range:'25-35y',insurance_data:{full_name:'QA original name'},snowboard_skills:['雪場S turn'],ski_skills:[],waiver_completed:false,waiver_signature:'',media_consent:''}
  const context=vm.createContext({React,exports:{},useSiteLocale:locale.useSiteLocale,ageOptions:['25-35y'],ageLabel:value=>value,birthDateStatus:()=>({age:null,error:''}),
   useState:initial=>{const index=cursor++;if(!(index in states))states[index]=typeof initial==='function'?initial():initial;return[states[index],value=>states[index]=typeof value==='function'?value(states[index]):value]},
   requestJson:async(url,options)=>{calls.push(JSON.parse(options.body));return{message:'課前資料已儲存'}}})
  vm.runInContext(ts.transpileModule(component,{fileName:'skills.jsx',compilerOptions:{jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText,context)
  const render=()=>{cursor=0;return context.PreCourseForm({form,waiverDocument:{title:'QA legal title original',version:'QA',body:'QA original legal body',source_url:'https://example.test/waiver'},skillOptions,onSaved:async()=>{}})}
  const button=name=>find(render(),node=>node.type==='button'&&node.props.children===t(name))
  assert.ok(renderToStaticMarkup(render()).includes(t('雪場S turn')))
  button('填寫／修改資料').props.onClick()
  const markup=renderToStaticMarkup(render())
  assert.ok(markup.includes(t('室內滑雪機全制動煞車')))
  assert.ok(markup.includes('QA original legal body'),'Never translate the legal document')
  const selected=find(render(),node=>node.type==='label'&&React.Children.toArray(node.props.children).includes(t('雪場S turn')))
  find(selected,node=>node.type==='input').props.onChange()
  const fresh=find(render(),node=>node.type==='label'&&React.Children.toArray(node.props.children).includes(t('無經驗')))
  find(fresh,node=>node.type==='input').props.onChange()
  assert.equal(button('儲存課前資料').props.disabled,false,'An unsigned draft can be saved')
  await button('儲存課前資料').props.onClick()
  assert.ok(renderToStaticMarkup(render()).includes(t('課前資料已儲存')))
  assert.deepEqual(calls[0].snowboard_skills,['無經驗'],'Persist original enum, not translated labels')
  assert.equal(calls[0].waiver_agreed,false)
  assert.equal(calls[0].waiver_signature,'')
  assert.equal(calls[0].insurance_data.full_name,'QA original name')
  // The actual route-loading component uses the same locale, without network mocks.
  const routes=fs.readFileSync(path.join(root,'src/pages/site/SiteRoutes.tsx'),'utf8')
  const loading=routes.slice(routes.indexOf('function PageLoading('),routes.indexOf('function SapporoRedirect('))
  const ctx=vm.createContext({React,useSiteLocale:locale.useSiteLocale})
  vm.runInContext(ts.transpileModule(loading,{fileName:'loading.tsx',compilerOptions:{jsx:ts.JsxEmit.React}}).outputText,ctx)
  assert.ok(renderToStaticMarkup(ctx.PageLoading()).includes(t('載入中…')))
 }
 console.log('PASS actual member skill choices en/ja, stored enums, unsigned draft, original legal/name text, route-loading locale')
}
main().catch(error=>{console.error(error);process.exitCode=1})
