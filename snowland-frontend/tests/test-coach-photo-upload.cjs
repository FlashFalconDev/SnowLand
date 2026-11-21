const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const {renderToStaticMarkup}=req('react-dom/server')
const compile=source=>ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
function find(n,p){if(!n||typeof n!=='object')return null;if(p(n))return n;for(const c of React.Children.toArray(n.props?.children)){const hit=find(c,p);if(hit)return hit}return null}

// 1) ImageUploadField：驗證、上傳、預覽、後備網址、None 顯示
const field=vm.createContext({React,exports:{},require:n=>{if(n==='react')return{...React,useState:v=>{const j=states.i++;if(!(j in states.v))states.v[j]=v;return[states.v[j],x=>{states.v[j]=x}]},useRef:()=>({current:null})};throw new Error(n)}})
const states={i:0,v:{}}
vm.runInContext(compile(fs.readFileSync(path.join(root,'src/admin/components/ImageUploadField.tsx'),'utf8')),field)
const {validateImageFile,cleanImageValue}=field.exports
assert.equal(validateImageFile({type:'image/png',size:10}),undefined)
assert.ok(validateImageFile({type:'image/gif',size:10}))
assert.ok(validateImageFile({type:'application/pdf',size:10}))
assert.ok(validateImageFile({type:'image/png',size:0}))
assert.match(validateImageFile({type:'image/jpeg',size:5*1024*1024+1}),/5 MB/)
assert.match(validateImageFile({type:'image/jpeg',size:3*1024*1024},2*1024*1024),/2 MB/)
for(const bad of [null,undefined,'None','null','  None  ',5])assert.equal(cleanImageValue(bad),'')
assert.equal(cleanImageValue(' /a.jpg '),'/a.jpg')

const render=props=>{states.i=0;return field.exports.default({id:'x',name:'img',value:'',onChange(){},...props})}
let html=renderToStaticMarkup(React.createElement(()=>render({value:'None'})))
assert.ok(!html.includes('None'));assert.ok(html.includes('無預覽'));assert.ok(!html.includes('type="file"'),'未啟用上傳時只留網址後備')
html=renderToStaticMarkup(React.createElement(()=>render({value:'/qa.jpg',upload:async()=>''})))
assert.ok(html.includes('type="file"'));assert.ok(html.includes('src="/qa.jpg"'));assert.ok(html.includes('accept="image/jpeg,image/png,image/webp"'))

;(async()=>{
  const changes=[];let uploaded=[]
  let tree=render({onChange:v=>changes.push(v),upload:async(file,progress)=>{uploaded.push(file);progress(50);return 'https://bucket.example/coach.png'}})
  const input=find(tree,n=>n.type==='input'&&n.props.type==='file')
  await input.props.onChange({target:{files:[{type:'image/gif',size:5,name:'a.gif'}]}})
  assert.equal(uploaded.length,0);assert.equal(changes.length,0)
  tree=render({onChange:v=>changes.push(v)});assert.match(find(tree,n=>n.type==='p'&&n.props.role==='alert').props.children,/JPEG/)
  tree=render({onChange:v=>changes.push(v),upload:async f=>{uploaded.push(f);return 'https://bucket.example/coach.png'}})
  await find(tree,n=>n.type==='input'&&n.props.type==='file').props.onChange({target:{files:[{type:'image/png',size:100,name:'a.png'}]}})
  assert.equal(uploaded.length,1);assert.deepEqual(changes,['https://bucket.example/coach.png'])
  // 上傳失敗：顯示錯誤、不改值
  tree=render({onChange:v=>changes.push(v),upload:async()=>{throw new Error('伺服器拒絕')}})
  await find(tree,n=>n.type==='input'&&n.props.type==='file').props.onChange({target:{files:[{type:'image/png',size:100,name:'a.png'}]}})
  assert.equal(changes.length,1);tree=render({});assert.match(find(tree,n=>n.type==='p'&&n.props.role==='alert').props.children,/伺服器拒絕/)
  // 後備：貼上網址
  tree=render({onChange:v=>changes.push(v)});find(tree,n=>n.type==='input'&&n.props.type==='text').props.onChange({target:{value:'/site/a.jpg'}});assert.equal(changes.at(-1),'/site/a.jpg')

  // 2) PromptModal 對 image 欄位使用 ImageUploadField；表單送出時 FormData 取得 img
  const promptSource=fs.readFileSync(path.join(root,'src/admin/components/PromptModal.tsx'),'utf8')
  assert.ok(promptSource.includes("f.type === 'image'")&&promptSource.includes('ImageUploadField'))

  // 3) API 客戶端以 multipart 欄位 photo 上傳並回傳 URL
  const posts=[]
  class FD{constructor(){this.m=[]}append(k,v){this.m.push([k,v])}}
  const api=vm.createContext({exports:{},FormData:FD,require:n=>{if(n==='./axios')return{default:{get:async()=>({data:{enabled:true,max_bytes:5}}),post:async(url,body,cfg)=>{posts.push({url,body,cfg});cfg.onUploadProgress({loaded:5,total:10});return{data:{url:'https://b/x.png'}}}}};throw new Error(n)}})
  vm.runInContext(compile(fs.readFileSync(path.join(root,'src/admin/api/websiteCoachEditor.ts'),'utf8')),api)
  const percents=[],file={name:'a.png'}
  assert.equal(await api.exports.uploadWebsiteCoachPhoto(7,file,p=>percents.push(p)),'https://b/x.png')
  assert.equal(posts[0].url,'/website-coach-editor/7/upload-photo/');assert.deepEqual(posts[0].body.m,[['photo',file]]);assert.deepEqual(percents,[50])
  assert.equal((await api.exports.fetchPhotoUploadConfig()).enabled,true)
  console.log('PASS coach photo upload: type/size validation, preview, upload success/failure, URL fallback, None hidden, multipart client')
})().catch(e=>{console.error(e);process.exit(1)})
