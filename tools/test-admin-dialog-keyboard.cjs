const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/admin/hooks/useAdminDialog.ts'),'utf8')
function setup({open=true,empty=false}={}){
 const refs=[],effects=[];let cursor=0,closes=0
 const doc={body:{style:{overflow:'auto'}},addEventListener(key,fn){assert.equal(key,'keydown');this.handler=fn},removeEventListener(key,fn){assert.equal(fn,this.handler);this.handler=null}}
 const trigger={isConnected:true,focus(){doc.activeElement=this}},first={focus(){doc.activeElement=this},closest(){return null},getClientRects(){return [1]}},last={...first},hidden={...first,getClientRects(){return []}}
 const panel={querySelectorAll(selector){assert.ok(selector.includes(':disabled'));return empty?[]:[first,hidden,last]},focus(){doc.activeElement=this},contains(node){return [this,first,last,hidden].includes(node)}}
 doc.activeElement=trigger
 const context={document:doc,exports:{},require(name){assert.equal(name,'react');return {useRef(value){const index=cursor++;return refs[index]||(refs[index]={current:value})},useEffect(fn){effects.push(fn)}}}}
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
 const render=(busy=false,close=()=>closes++)=>{cursor=0;return context.exports.useAdminDialog(open,busy,close)}
 const ref=render();ref.current=panel;const cleanup=effects.shift()()
 return {doc,trigger,first,last,hidden,panel,cleanup,render,get closes(){return closes},key(key,shiftKey=false){let prevented=false;doc.handler({key,shiftKey,preventDefault(){prevented=true}});return prevented}}
}
const scene=setup()
assert.equal(scene.doc.activeElement,scene.first);assert.equal(scene.doc.body.style.overflow,'hidden')
assert.equal(scene.key('Tab',true),true);assert.equal(scene.doc.activeElement,scene.last)
assert.equal(scene.key('Tab'),true);assert.equal(scene.doc.activeElement,scene.first)
scene.doc.activeElement=scene.trigger;scene.key('Tab');assert.equal(scene.doc.activeElement,scene.first)
scene.doc.activeElement=scene.panel;scene.key('Tab',true);assert.equal(scene.doc.activeElement,scene.last)
scene.key('Escape');assert.equal(scene.closes,1)
scene.render(true);scene.key('Escape');assert.equal(scene.closes,1,'busy dialogs cannot disappear during a write')
let latest=0;scene.render(false,()=>latest++);scene.key('Escape');assert.equal(latest,1,'event handler uses latest callback without resetting focus')
assert.equal(scene.key('a'),false)
scene.cleanup();assert.equal(scene.doc.activeElement,scene.trigger);assert.equal(scene.doc.body.style.overflow,'auto');assert.equal(scene.doc.handler,null)
const blank=setup({empty:true});assert.equal(blank.doc.activeElement,blank.panel);blank.key('Tab');assert.equal(blank.doc.activeElement,blank.panel);blank.trigger.isConnected=false;blank.cleanup();assert.notEqual(blank.doc.activeElement,blank.trigger)
const closed=setup({open:false});assert.equal(closed.cleanup,undefined);assert.equal(closed.doc.body.style.overflow,'auto')
const page=fs.readFileSync(path.join(root,'src/admin/pages/CampusesPage.tsx'),'utf8')
assert.equal((page.match(/useAdminDialog\(/g)||[]).length,2,'campus editor/delete and policy reset all use keyboard controls')
assert.equal((page.match(/tabIndex=\{-1\} role="dialog"/g)||[]).length,3)
assert.ok(page.includes('{deleteError && <p role="alert"'),'failed deletion must keep a readable error in its dialog')
assert.equal((page.match(/min-h-11 min-w-11 items-center justify-center rounded-lg p-1 text-white\/80/g)||[]).length,2,'both close targets are at least44px')
console.log('PASS actual admin dialog hook: initial/hidden focus, both Tab boundaries, escaped focus, busy Escape, latest callback, cleanup/scroll/trigger; all three campus dialogs wired')
