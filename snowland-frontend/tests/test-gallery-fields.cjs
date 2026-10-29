const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/admin/components/GalleryFields.tsx'),'utf8')
function find(n,p){if(!n||typeof n!=='object')return null;if(p(n))return n;for(const c of React.Children.toArray(n.props?.children)){const hit=find(c,p);if(hit)return hit}return null}
const changes=[],states=['QA新分類',''],metadata={location:'富良野',shoot_types:['親子'],keep:'unchanged'};let i=0
const ctx=vm.createContext({React,exports:{},URL,require:name=>{if(name==='react')return{...React,useState:v=>{const j=i++;return[states[j]??v,x=>states[j]=x]}};throw Error(name)}})
vm.runInContext(ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText,ctx)
const parse=ctx.exports.youtubeId
for(const value of ['dQw4w9WgXcQ','https://youtu.be/dQw4w9WgXcQ?t=3','https://www.youtube.com/watch?v=dQw4w9WgXcQ','https://youtube.com/shorts/dQw4w9WgXcQ'])assert.equal(parse(value),'dQw4w9WgXcQ')
for(const value of ['https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ','javascript:dQw4w9WgXcQ','../bad','https://example.test/watch?v=dQw4w9WgXcQ'])assert.equal(parse(value),'')
const tree=ctx.exports.default({metadata,imageUrl:'/qa.svg',published:true,items:[{metadata:{location:'星野',shoot_types:['情侶']}}],onChange:v=>changes.push(v),onImageChange:v=>changes.push({image:v})})
find(tree,n=>n.type==='button'&&n.props.children==='新增並勾選').props.onClick()
assert.deepEqual(Array.from(changes[0].shoot_types),['親子','QA新分類']);assert.equal(changes[0].keep,'unchanged');assert.equal(states[0],'')
const selected=find(tree,n=>n.type==='input'&&n.props.type==='checkbox'&&n.props.checked)
selected.props.onChange({target:{checked:false}});assert.deepEqual(Array.from(changes[1].shoot_types),[]);assert.equal(changes[1].keep,'unchanged')
const image=find(tree,n=>n.type==='input'&&n.props.value==='/qa.svg');assert.ok(image.props.required);image.props.onChange({target:{value:'/new.svg'}});assert.equal(changes[2].image,'/new.svg')
assert.ok(find(tree,n=>n.type==='option'&&n.props.value==='星野'))
find(tree,n=>n.type==='select').props.onChange({target:{value:'video'}});assert.equal(changes[3].media_type,'video');assert.equal(changes[3].keep,'unchanged')
console.log('PASS gallery editor: existing/new multi-categories, deselect, preserved metadata, photo guard, type switch and safe YouTube parsing')
