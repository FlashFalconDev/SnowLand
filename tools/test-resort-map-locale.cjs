const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),render=req('react-dom/server').renderToStaticMarkup
function all(node,p,out=[]){if(!node||typeof node!=='object')return out;if(p(node))out.push(node);for(const child of React.Children.toArray(node.props?.children))all(child,p,out);return out}
function load(file,language){const states=[];let cursor=0;const ctx={exports:{},require:name=>{
 if(name==='react')return{...React,useMemo:fn=>fn(),useEffect:()=>{},useRef:value=>({current:value}),useState:initial=>{const index=cursor++;if(!(index in states))states[index]=typeof initial==='function'?initial():initial;return[states[index],value=>states[index]=typeof value==='function'?value(states[index]):value]}}
 if(name.includes('contexts/SiteLocale'))return require('./helpers/site-locale-harness.cjs')(React,language)
 if(name==='./SiteLink')return props=>React.createElement('a',{href:'/snowland'+props.to},props.children)
 throw Error(name)
 }};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/components/site',file),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,ctx);return{states,render:props=>{cursor=0;return ctx.exports.default(props)}}}
const knownTags=new Set()
for(const file of ['resortLegacyData.js','skiResorts.ts','resortNavigation.js']){const ast=ts.createSourceFile(file,fs.readFileSync(path.join(root,'src/data/site',file),'utf8'),99,true);function walk(n){if(ts.isPropertyAssignment(n)&&n.name.text==='tags'&&ts.isArrayLiteralExpression(n.initializer))for(const value of n.initializer.elements)if(ts.isStringLiteral(value)&&/[\u3400-\u9fff]/.test(value.text))knownTags.add(value.text);ts.forEachChild(n,walk)}walk(ast)}
const resort={slug:'tomamu',nameChinese:'QA自訂雪場',nameEnglish:'QA Resort',region:'道北',tags:['QA自訂標籤',...knownTags],heroImage:'/vite.svg',route:'/course/tomamu'}
for(const language of ['en','ja']){
 const map=load('HokkaidoMap.jsx',language),props={resorts:[resort]},tree=map.render(props),html=render(tree)
 assert.ok(html.includes(language==='en'?'Zoom in on map':'地図を拡大'))
 assert.ok(html.includes(language==='en'?'Northern Hokkaido':'道北'))
 assert.ok(html.includes('QA自訂雪場')&&html.includes('QA自訂標籤'))
 const locale=require('./helpers/site-locale-harness.cjs')(React,language)
 for(const tag of knownTags){const translated=locale.translateSiteText(language,tag);assert.notEqual(translated,tag,language+' catalog tag '+tag);assert.ok(html.includes(translated))}
 const zoom=all(tree,n=>n.type==='button'&&n.props['aria-label']===(language==='en'?'Zoom in on map':'地図を拡大'))[0]
 zoom.props.onClick();assert.ok(map.states[3]>1,'Translated zoom button must change scale')
 const marker=all(map.render(props),n=>n.type==='button'&&String(n.props['aria-label']).includes('QA自訂雪場'))[0]
 marker.props.onClick();assert.equal(map.states[0],null);marker.props.onClick();assert.equal(map.states[0],'tomamu')
 const card=load('ResortCard.jsx',language),markup=render(card.render({resort}))
 assert.ok(markup.includes(language==='en'?'View resort information':'スキー場の詳細を見る'))
 assert.ok(markup.includes('href="/snowland/course/tomamu"'));assert.ok(markup.includes('QA自訂雪場')&&markup.includes('QA自訂標籤'))
 console.log('PASS resort map/card locale',language,'zoom, marker toggle, canonical target and original custom name/tag')
}
