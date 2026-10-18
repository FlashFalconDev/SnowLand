const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/site/OverseasPhotographyWorksPage.jsx'),'utf8').replace('import.meta.env.BASE_URL','"/"')
function setup(items,states=['All','','',false,false,false,'',null,null],extra={}) {
  let index=0;const hooks={...React,useState:value=>{const key=index++;if(!(key in states))states[key]=value;return [states[key],v=>states[key]=typeof v==='function'?v(states[key]):v]},useEffect(){},useMemo:f=>f(),useRef:()=>({current:null})}
  const ctx=vm.createContext({exports:{},window:{},require:name=>{
    if(name==='react')return hooks
    if(name==='framer-motion')return{motion:{div:'div',span:'span'}}
    if(name.endsWith('SiteLink'))return props=>React.createElement('a',{href:props.to},props.children)
    if(name.includes('/components/'))return()=>null
    if(name.includes('useSiteContent'))return{useSiteContent:()=>({items,isLoading:false,error:null,...extra})}
    throw Error(name)
  }})
  vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText,ctx)
  return{html:()=>{index=0;return renderToStaticMarkup(React.createElement(ctx.exports.default))}}
}
const photos=[{id:1,title:'QA富良野',image_url:'/qa-photo.svg',metadata:{media_type:'photo',location:'富良野',shoot_types:['情侶']}},
  {id:2,title:'QA新照片',image_url:'https://example.test/qa.jpg',metadata:{}}]
assert.ok(setup(photos,['地點','富良野','',true,false,false,'',null,null]).html().includes('/qa-photo.svg'),'非星野地點也要顯示作品')
const all=setup(photos).html();assert.ok(all.includes('https://example.test/qa.jpg'));assert.ok(!all.includes('/https://'))
assert.ok(all.includes('QA新照片'));assert.ok(all.includes('/booking?service=photo'))
const emptyVideo=setup(photos,['影片','','',false,false,false,'',null,null]).html()
assert.ok(emptyVideo.includes('目前沒有已發布的影片'));assert.ok(!emptyVideo.includes('/embed/null'));assert.ok(emptyVideo.includes('/booking?service=photo'))
const invalid=setup([{image_url:'javascript:alert(1)',metadata:{}},{image_url:'/qa.svg',metadata:{shoot_types:{},location:[]}},null]).html()
assert.ok(!invalid.includes('src="javascript:'))
assert.ok(setup([]).html().includes('目前沒有已發布的攝影作品'))
assert.ok(setup([],undefined,{isLoading:true}).html().includes('正在載入攝影作品'))
assert.ok(setup([],undefined,{error:Error('QA')}).html().includes('攝影作品暫時無法載入'))
console.log('PASS gallery dynamic new photos, non-Tomamu location, external paths, empty video, booking CTA, malformed data and states')
