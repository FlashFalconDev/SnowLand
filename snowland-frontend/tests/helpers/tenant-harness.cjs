const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript')
module.exports=function(window,localStorage){
  const scope={exports:{},window,localStorage,URL}
  const source=fs.readFileSync(path.resolve(__dirname,'../../src/utils/tenant.ts'),'utf8')
  vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,scope)
  return scope.exports
}
