const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
let loaded=false,hookCalls=[]
const hook=name=>(...args)=>{hookCalls.push(name);if(name==='state')return[typeof args[0]==='function'?args[0]():args[0],()=>{}];if(name==='ref')return{current:args[0]};if(name==='memo')return args[0]();if(name==='scroll')return{scrollY:0};return 0}
const hooks={...React,useState:hook('state'),useRef:hook('ref'),useMemo:hook('memo'),useEffect:hook('effect')}
const ctx=vm.createContext({React:hooks,exports:{},require:name=>{
 if(name==='react')return hooks
 if(name==='react-router-dom')return{Link:()=>null}
 if(name==='framer-motion')return{motion:new Proxy({},{get:()=>()=>null}),useReducedMotion:hook('reduced'),useScroll:hook('scroll'),useTransform:hook('transform')}
 if(name.includes('useSiteContent'))return{useSiteContent:()=>{hookCalls.push('content');return{items:loaded?[{title:'QA行前須知',metadata:{page:{title:'QA行前須知',blocks:[]}}}]:[],isLoading:!loaded,error:null}},siteContentToPage:item=>item?.metadata.page||null,siteContentToArticle:item=>item}
 return{__esModule:true,default:()=>null}
}})
vm.runInContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/pages/site/LegacyContentPage.jsx'),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText,ctx)
hookCalls=[];ctx.exports.default({pageKey:'guides-preparation'});const initial=[...hookCalls]
loaded=true;hookCalls=[];const page=ctx.exports.default({pageKey:'guides-preparation'})
assert.deepEqual(hookCalls,initial,'載入前後不可變更hook順序導致空白頁')
assert.ok(page,'資料載入後必須有頁面')
console.log('PASS actual LegacyContentPage loading→ready keeps stable hooks and renders a keyed layout')
