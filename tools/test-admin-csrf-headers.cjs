const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
const code=ts.transpileModule(fs.readFileSync(path.join(root,'src/admin/api/axios.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
function run(cookie){
  let send,options
  const context=vm.createContext({exports:{},document:{cookie},window:{location:{pathname:'/snowland/console/my/pending'}},localStorage:{getItem:()=>null},console,
    require:()=>({default:{create:config=>{options=config;return{interceptors:{request:{use:callback=>send=callback},response:{use(){}}}}}}})})
  vm.runInContext(code,context)
  return{config:send({headers:{}}),options}
}
const valid=run('othercsrf=not-this; csrftoken=QA-local-only-token; other=value')
assert.equal(valid.options.withCredentials,true)
assert.equal(valid.config.headers['X-CSRFToken'],'QA-local-only-token')
assert.equal(valid.config.baseURL,'/api/admin/snowland')
assert.equal(valid.config.headers['X-Campus-ID'],'all')
assert.equal(run('othercsrf=not-this').config.headers['X-CSRFToken'],undefined)
console.log('PASS existing admin transport: same-origin credentials, actual CSRF cookie/header mapping, tenant and campus retained')
