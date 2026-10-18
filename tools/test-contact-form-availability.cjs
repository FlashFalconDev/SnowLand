const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/site/ContactPage.jsx'),'utf8')
const compiled=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
function render(page,state={}){
  const context=vm.createContext({exports:{},require:name=>{
    if(name==='react')return React
    if(name==='framer-motion')return{motion:{img:props=>React.createElement('img',props)},useReducedMotion:()=>true,useScroll:()=>({scrollY:0}),useTransform:()=>undefined}
    if(name.includes('/hooks/useSiteContent'))return{useSiteContent:()=>({items:page?[page]:[],isLoading:false,error:null,...state}),siteContentToPage:row=>row}
    if(name.includes('assetPaths'))return{homepageAssetBase:'/assets'}
    if(name.includes('/assets/'))return'/qa-background.jpg'
    if(name.includes('/components/'))return()=>null
    throw new Error(name)
  }})
  vm.runInContext(compiled,context)
  return renderToStaticMarkup(React.createElement(context.exports.default))
}
const loaded=render({title:'QA聯絡我們',blocks:[{type:'paragraph',text:'Email: qa@example.test'}, {type:'paragraph',text:'LINE: https://line.me/qa-configured'}]})
assert.ok(loaded.includes('聯絡表單尚未啟用'))
assert.match(loaded,/<fieldset[^>]*disabled=""/)
assert.match(loaded,/<button[^>]*disabled=""[^>]*>/)
assert.ok(loaded.includes('qa@example.test'))
assert.ok(loaded.includes('https://line.me/qa-configured'))
assert.ok(!source.includes('window.alert("已送出")'))
assert.ok(!loaded.includes('<form'))
assert.ok(render(null,{error:Error('QA')}).includes('聯絡資訊暫時無法載入'))
assert.ok(render(null,{isLoading:true}).includes('聯絡資訊載入中'))
assert.ok(render(null).includes('目前沒有已發布的聯絡資訊'))
console.log('PASS actual contact page: unavailable form clearly labelled and disabled, no false submission, published contacts retained, loading/error/empty states')
