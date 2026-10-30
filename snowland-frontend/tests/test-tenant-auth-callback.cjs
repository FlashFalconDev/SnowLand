const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),React=require('react'),ts=require('typescript')
const source=fs.readFileSync(path.resolve(__dirname,'../src/pages/AuthCallbackPage.tsx'),'utf8')
async function check(stored,preLogin){
  const values=new Map([['client_code',stored],['pre_login_url',preLogin]]),calls=[],status=[]
  const window={location:{pathname:'/auth/callback',search:'',href:'original'}}
  const storage={getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}
  const tenant=require('./helpers/tenant-harness.cjs')(window,storage)
  const scope={React,exports:{},window,localStorage:storage,URLSearchParams,console:{error(){}},setTimeout:fn=>fn(),
    fetch:async(url,options)=>{calls.push({url,options});return{ok:true,json:async()=>({code:200,user:{email:'qa@example.test',name:'School A'}})}},
    require:name=>name==='react'?{...React,useState:initial=>[initial,value=>status.push(value)],useEffect:fn=>fn()}:name==='@/utils/tenant'?tenant:require(name)}
  vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText,scope)
  scope.exports.default();await new Promise(setImmediate)
  return{calls,window,values,status}
}
;(async()=>{
  const valid=await check('school-a','/school-a/membership')
  assert.equal(valid.calls[0].url,'/booking/school-a/api/google-login/');assert.equal(valid.calls[0].options.method,'GET')
  assert.equal(valid.window.location.href,'/school-a/membership');assert.ok(valid.status.includes('success'))
  const wrong=await check('school-a','/school-b/console');assert.equal(wrong.window.location.href,'/school-a')
  const missing=await check('','/school-a/');assert.equal(missing.calls.length,0);assert.equal(missing.window.location.href,'/')
  console.log('PASS session callback retains school, rejects cross-school return and never guesses a missing school (mock HTTP)')
})().catch(error=>{console.error(error);process.exit(1)})
