const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const compile=code=>ts.transpileModule(code,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
const source=fs.readFileSync(path.join(root,'src/api/websiteCoaches.js'),'utf8')
function harness(failing){
  const states=[];let index=0,effect,failed=failing
  const ctx=vm.createContext({exports:{},URLSearchParams,window:{location:{pathname:'/snowland/'}},localStorage:{getItem:()=>null},fetch:async()=>{if(failed)throw new Error('QA network');return{ok:true,json:async()=>({data:{list:[{id:1,name:'QA後端教練',slug:'qa',image:'/new.jpg'}]}})}},require:name=>{
    if(name==='react')return{useState:initial=>{const i=index++;if(!(i in states))states[i]=initial;return[states[i],value=>states[i]=typeof value==='function'?value(states[i]):value]},useEffect:fn=>effect=fn}
    throw new Error(name)
  }})
  vm.runInContext(compile(source),ctx)
  return{render:()=>{index=0;return ctx.exports.useWebsiteCoachCards()},effect:()=>effect(),states,recover:()=>failed=false}
}
;(async()=>{
  const good=harness(false);assert.equal(good.render().isLoading,true);good.effect();await new Promise(setImmediate)
  assert.equal(good.render().coaches[0].name,'QA後端教練');assert.equal(good.render().error,false)
  const bad=harness(true);bad.render();bad.effect();await new Promise(setImmediate)
  assert.equal(bad.render().error,true);assert.equal(bad.render().coaches.length,0)
  bad.render().retry();assert.equal(bad.states[1],1);bad.recover();bad.render();bad.effect();await new Promise(setImmediate)
  assert.equal(bad.render().coaches[0].image,'/new.jpg')
  const cancelled=harness(false);cancelled.render();const stop=cancelled.effect();stop();await new Promise(setImmediate)
  assert.equal(cancelled.states[0].coaches.length,0,'Late response cannot restore content after unmount')
  const notice=vm.createContext({exports:{},require:name=>{if(name==='react')return React;throw new Error(name)}})
  vm.runInContext(compile(fs.readFileSync(path.join(root,'src/components/site/CoachLoadNotice.jsx'),'utf8')),notice)
  assert.ok(renderToStaticMarkup(React.createElement(notice.exports.default,{isLoading:true})).includes('正在載入'))
  assert.ok(renderToStaticMarkup(React.createElement(notice.exports.default,{count:0})).includes('沒有上架'))
  let retried=0;const error=notice.exports.default({error:true,retry:()=>retried++})
  const button=React.Children.toArray(error.props.children).find(child=>child.type==='button');button.props.onClick();assert.equal(retried,1)
  for(const page of ['HomePage.jsx','CoachTeamPage.jsx']){
    const text=fs.readFileSync(path.join(root,'src/pages/site',page),'utf8')
    assert.ok(text.includes('<CoachLoadNotice'));assert.ok(!text.includes('data/site/coaches'));assert.ok(!text.includes('legacyImageByName'));assert.ok(!text.includes('coachImageByName'))
  }
  console.log('PASS actual coach list hook: canonical API data, failure without static fallback, retry, unmount, and shared loading/error/empty feedback')
})().catch(e=>{console.error(e);process.exit(1)})
