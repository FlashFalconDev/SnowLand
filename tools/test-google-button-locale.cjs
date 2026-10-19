const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/components/auth/GoogleLoginButton.tsx'),'utf8'),ast=ts.createSourceFile('GoogleLoginButton.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
const component=ast.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='GoogleLoginButton')
const effect=component.body.statements.find(node=>ts.isExpressionStatement(node)&&node.getText(ast).startsWith('useEffect('))
const rendered=[],initializations=[]
const env={GOOGLE_CLIENT_ID:'QA-NOT-REAL.apps.googleusercontent.com',googleSdkInitialized:false,activeCredentialHandler:null,
  handleCredentialResponse(){},googleButtonRef:{current:{getBoundingClientRect:()=>({width:350}),replaceChildren(){}}},setError(){},
  ResizeObserver:class{observe(){}disconnect(){}},setTimeout(){throw Error('Loaded SDK should not poll')},clearTimeout(){},
  window:{google:{accounts:{id:{initialize:config=>initializations.push(config),renderButton:(element,config)=>rendered.push(config)}}}}}
const context=vm.createContext({...env,useEffect:fn=>context.cleanup=fn(),locale:'ja'})
const code=ts.transpileModule(effect.getText(ast),{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText
vm.runInContext(code,context)
assert.equal(rendered[0].locale,'ja','Google button must follow the selected site language')
context.cleanup();context.locale='en';vm.runInContext(code,context)
assert.equal(rendered[1].locale,'en');assert.equal(initializations.length,1,'Changing display language must not reinitialize OAuth')
context.cleanup();context.locale='zh-Hant';vm.runInContext(code,context)
assert.equal(rendered[2].locale,'zh_TW')
console.log('PASS real Google render effect follows ja/en/zh-TW without reinitializing OAuth (mock SDK; not real Google sign-in)')
