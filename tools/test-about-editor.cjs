const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const schema=JSON.parse(fs.readFileSync(path.join(root,'../snowland/Client/fixtures/about_page_defaults.json'),'utf8'))
const source=fs.readFileSync(path.join(root,'src/admin/components/AboutPageEditor.tsx'),'utf8')
function find(node,p){if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const hit=find(child,p);if(hit)return hit}return null}
function app({metadata={keep:'原設定'},loading=false,error=false,search='',matches=[]}={}){
 const effects=[],changes=[];let i=0,retried=0,cleared
 const ctx=vm.createContext({React,exports:{},require:name=>{
  if(name==='react')return{useState:()=>[i++===0?search:matches,value=>cleared=value],useEffect:fn=>effects.push(fn)}
  if(name==='@tanstack/react-query')return{useQuery:()=>({data:error?null:schema,isLoading:loading,error:error?Error('QA'):null,refetch(){retried++}})}
  if(name==='../api/siteContent')return{fetchAboutSchema(){}}
  throw Error(name)
 }})
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,ctx)
 return{tree:ctx.exports.default({metadata,onChange:value=>changes.push(value)}),effects,changes,defaults:ctx.exports.aboutEditorDefaults,retried:()=>retried,cleared:()=>cleared}
}
const initial=app();initial.effects[0]();const metadata=initial.changes[0]
assert.equal(metadata.keep,'原設定');assert.equal(Object.keys(metadata.layout.values).length,33)
metadata.layout.values.about_004='QA已修改原文'
const saved=app({metadata});saved.effects[0]();assert.equal(saved.changes.length,0)
find(saved.tree,n=>n.type==='textarea'&&n.props.value==='QA已修改原文').props.onChange({target:{value:'QA新原文'}})
assert.equal(saved.changes[0].layout.values.about_004,'QA新原文');assert.equal(saved.changes[0].keep,'原設定')
const filtered=app({metadata:{...metadata,layout:{...metadata.layout,values:{...metadata.layout.values,about_004:'新文字'}}},search:'已修改',matches:['about_004']})
assert.ok(find(filtered.tree,n=>n.type==='textarea'&&n.props.value==='新文字'),'改字後搜尋欄位不可消失')
for(const invalid of [null,[],{version:2,page_key:'about',values:{}},{version:1,page_key:'join-us',values:{}},{version:1,page_key:'about',values:[]},{version:1,page_key:'about',values:{bad:{nested:true}}}]){
 const bad=app({metadata:{layout:invalid}});bad.effects[0]();assert.equal(bad.changes.length,0);assert.ok(renderToStaticMarkup(bad.tree).includes('不會自動覆寫'))
}
const failed=app({error:true});find(failed.tree,n=>n.type==='button').props.onClick();assert.equal(failed.retried(),1)
assert.ok(renderToStaticMarkup(app({loading:true}).tree).includes('正在載入學校介紹'))
const empty=app({search:'找不到'});find(empty.tree,n=>n.type==='button').props.onClick();assert.equal(empty.cleared(),'')
const field=schema.sections.flatMap(s=>s.fields).find(f=>f.source_heading==='學員回饋機制')
assert.equal(initial.defaults(schema,{blocks:[],page:{blocks:[{type:'heading',text:'學員回饋機制'},{type:'paragraph',text:'不可復活'}]}})[field.key],'')
assert.equal(initial.defaults(schema,{blocks:[{type:'heading',text:'學員回饋機制'},{type:'paragraph',text:'管理者改過。下一段！'}]})[field.key],'管理者改過。\n下一段！')
console.log('PASS about actual editor preservation, stable search, original dynamic copy, unsafe metadata refusal and error/empty states')
