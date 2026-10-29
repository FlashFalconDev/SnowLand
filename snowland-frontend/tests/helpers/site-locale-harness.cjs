// Execute the real locale modules while substituting React's hook boundary in
// existing lightweight component harnesses. Browser checks cover real effects.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
module.exports=function loadSiteLocale(react,language='zh-Hant'){
  const root=path.resolve(__dirname,'../..'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
  const utilities={exports:{}}
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/utils/siteLocale.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,utilities)
  const hooks={...react,createContext:defaultValue=>({defaultValue}),useContext:context=>({...context.defaultValue,locale:language,t:(source,values)=>utilities.exports.translateSiteText(language,source,values)})}
  const locale={exports:{},require:name=>name==='react'?hooks:name==='react-router-dom'?req(name):utilities.exports}
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/contexts/SiteLocale.jsx'),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,locale)
  return {...locale.exports,...utilities.exports}
}
