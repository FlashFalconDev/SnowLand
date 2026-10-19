const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const compile=source=>ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
function find(n,p){if(!n||typeof n!=='object')return null;if(p(n))return n;for(const c of React.Children.toArray(n.props?.children)){const hit=find(c,p);if(hit)return hit}return null}
const schema={season:'winter',version:1,sections:[{id:'intro',label:'介紹',fields:[{key:'title',kind:'text',label:'標題',value:'原標題'},{key:'image',kind:'image',label:'照片',value:'/qa.svg'}]}]}
function setup({metadata={legacy:'keep'},loading=false,error=false,search='',matches=[]}={}){
  const changes=[],effects=[];let retried=0,cleared,stateIndex=0
  const ctx=vm.createContext({React,exports:{},require:name=>{
    if(name==='react')return{useState:()=>[stateIndex++===0?search:matches,value=>cleared=value],useEffect:fn=>effects.push(fn)}
    if(name==='@tanstack/react-query')return{useQuery:()=>({data:error?null:schema,isLoading:loading,error:error?Error('QA'):null,refetch(){retried++}})}
    if(name==='../api/siteContent')return{fetchPhotographySchema(){}}
    throw Error(name)
  }})
  vm.runInContext(compile(fs.readFileSync(path.join(root,'src/admin/components/PhotographyPageEditor.tsx'),'utf8')),ctx)
  const tree=ctx.exports.default({season:'winter',metadata,onChange:value=>changes.push(value)})
  return{tree,changes,effects,refetched:()=>retried,cleared:()=>cleared}
}
const initial=setup();initial.effects[0]();assert.equal(initial.changes[0].legacy,'keep');assert.equal(initial.changes[0].photography.values.title,'原標題')
const metadata={legacy:'keep',photography:{version:1,season:'winter',values:{title:'已修改',image:'/qa.svg'}}},saved=setup({metadata})
saved.effects[0]();assert.equal(saved.changes.length,0,'既有內容不可被初始值覆寫')
find(saved.tree,n=>n.type==='textarea').props.onChange({target:{value:'新文字'}})
assert.equal(saved.changes[0].photography.values.title,'新文字');assert.equal(saved.changes[0].photography.values.image,'/qa.svg');assert.equal(saved.changes[0].legacy,'keep')
assert.ok(renderToStaticMarkup(saved.tree).includes('實際訂課收費請到'))
const failure=setup({error:true});find(failure.tree,n=>n.type==='button').props.onClick();assert.equal(failure.refetched(),1)
assert.ok(renderToStaticMarkup(setup({loading:true}).tree).includes('正在載入攝影頁面欄位'))
const missing=setup({search:'找不到的內容'});assert.ok(renderToStaticMarkup(missing.tree).includes('沒有符合的欄位'));find(missing.tree,n=>n.type==='button').props.onClick();assert.equal(missing.cleared(),'')
const wrong=setup({metadata:{photography:{version:2,season:'summer'}}});wrong.effects[0]();assert.equal(wrong.changes.length,0);assert.ok(renderToStaticMarkup(wrong.tree).includes('不會自動覆寫'))
const editingSearch=setup({metadata:{...metadata,photography:{...metadata.photography,values:{...metadata.photography.values,title:'新文字'}}},search:'已修改',matches:['title']})
assert.ok(find(editingSearch.tree,n=>n.type==='textarea'&&n.props.value==='新文字'),'編輯中的搜尋結果不可因文字改變而消失')
function gate(data){
  let reloaded=0
  const ctx=vm.createContext({React,exports:{},window:{location:{reload:()=>reloaded++}},require:name=>{
    if(name==='react')return React
    if(name.includes('useSiteContent'))return{useSiteContent:()=>({items:[],isLoading:false,error:null,...data})}
    if(name==='./SiteHeader'||name==='./SiteFooter')return()=>null
    throw Error(name)
  }})
  vm.runInContext(compile(fs.readFileSync(path.join(root,'src/components/site/PhotographyContentGate.jsx'),'utf8')),ctx)
  return{tree:ctx.exports.default({season:'winter',children:content=>React.createElement('p',null,content.values.title)}),reloaded:()=>reloaded}
}
assert.ok(renderToStaticMarkup(gate({items:[{metadata}]}).tree).includes('已修改'))
assert.ok(renderToStaticMarkup(gate({}).tree).includes('內容更新中'))
assert.ok(renderToStaticMarkup(gate({isLoading:true}).tree).includes('正在載入攝影服務'))
const unavailable=gate({error:Error('QA')});find(unavailable.tree,n=>n.type==='button').props.onClick();assert.equal(unavailable.reloaded(),1)
assert.ok(renderToStaticMarkup(gate({items:[{metadata:{photography:{version:1,season:'winter',values:{title:{bad:true}}}}}]}).tree).includes('內容更新中'))
assert.ok(renderToStaticMarkup(gate({items:[{metadata:{photography:{version:1,season:'winter',values:{}}}}]}).tree).includes('內容更新中'),'空欄位不得顯示空白攝影版型')
console.log('PASS photography editor initialization/preservation/search/price notice/error retry and public gate ready/loading/error/invalid/empty states')
