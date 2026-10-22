// One-time mechanical JSX extraction. Default is read-only; --apply preserves
// original layouts in ignored tmp/ for parity verification before rewriting.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),frontend=path.join(root,'snowland-frontend')
const ts=Module.createRequire(path.join(frontend,'package.json'))('typescript')
const apply=process.argv.includes('--apply'),records=[]
const defaultsPath=path.join(root,'snowland/Client/fixtures/photography_page_defaults.json')
const previous=fs.existsSync(defaultsPath)?JSON.parse(fs.readFileSync(defaultsPath,'utf8')):[]
function cooked(text){
  const js=ts.transpileModule(`exports.value=<span>${text}</span>`,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText
  const context={exports:{},React:{createElement:(_tag,_props,...children)=>children.join('')}}
  vm.runInNewContext(js,context,{timeout:1000});return context.exports.value
}
for(const season of ['winter','summer']){
  const name=season==='winter'?'Winter':'Summer',file=path.join(frontend,`src/pages/site/${name}PhotographyPage.jsx`)
  let original=fs.readFileSync(file,'utf8')
  if(original.includes('PhotographyContentGate')){
    if(!process.argv.includes('--refresh'))throw Error('Already parameterized: '+file)
    original=fs.readFileSync(path.join(root,`tmp/${season}-photography-before-cms.jsx`),'utf8')
  }
  const source=ts.createSourceFile(file,original,ts.ScriptTarget.Latest,true,ts.ScriptKind.JSX)
  const groups=new Map(),replacements=[];let count=0
  const old=previous.find(row=>row.season===season),used=new Set()
  let nextKey=Math.max(0,...(old?.sections||[]).flatMap(s=>s.fields.map(f=>Number(f.key.split('_')[1]))))
  const sections=[]
  function scan(node){if(ts.isJsxElement(node)&&node.openingElement.tagName.getText(source)==='section')sections.push(node);ts.forEachChild(node,scan)}
  scan(source)
  function group(node){
    for(let parent=node.parent;parent;parent=parent.parent){
      if(sections.includes(parent)){
        const index=sections.indexOf(parent),heading=[]
        function title(n){if(ts.isJsxElement(n)&&/^h[1-3]$/.test(n.openingElement.tagName.getText(source)))for(const child of n.children)if(ts.isJsxText(child))heading.push(cooked(child.getText(source)).trim());if(!heading.length)ts.forEachChild(n,title)}
        title(parent)
        return {id:`section-${index+1}`,label:heading.join(' ').slice(0,50)||(index===0?'主視覺輪播':`場景圖片區塊 ${index+1}`),order:index+1}
      }
      if(ts.isVariableDeclaration(parent)){
        const variable=parent.name.getText(source)
        const labels={photos:'主視覺輪播',customTravelPhotos:'客製旅拍照片',lightWeddingPhotos:'輕婚紗照片',weddingPhotos:'婚紗專案照片'}
        if(labels[variable])return{id:`photos-${variable}`,label:labels[variable],order:variable==='photos'?0.5:6.5}
      }
    }
    return{id:'page',label:'頁首與授權說明',order:0}
  }
  function add(node,value,kind,label,jsx){
    const info=group(node);if(!groups.has(info.id))groups.set(info.id,{...info,fields:[]})
    const fields=groups.get(info.id).fields
    const existing=old?.sections.find(s=>s.id===info.id)?.fields.find(f=>!used.has(f.key)&&f.kind===kind&&f.value===value)
    const key=existing?.key||`${season}_${String(++nextKey).padStart(3,'0')}`
    used.add(key);count++
    fields.push({key,kind,label:label==='展示價格'?`${label} ${fields.length+1}`:existing?.label||`${label} ${fields.length+1}`,value})
    replacements.push({start:node.getStart(source),end:node.end,text:jsx?`{c(${JSON.stringify(key)})}`:`c(${JSON.stringify(key)})`})
  }
  function walk(node){
    if(ts.isImportDeclaration(node))return
    if(ts.isJsxText(node)){
      const value=cooked(node.getText(source))
      if(/[A-Za-z0-9\u3400-\u9fff]/.test(value)){
        if(value.trim()==='查看更多常見問題'){
          const link=node.parent.openingElement
          const target=link?.attributes.properties.find(p=>ts.isJsxAttribute(p)&&p.name.getText(source)==='to')?.initializer
          if(target)replacements.push({start:target.getStart(source),end:target.end,text:'"/faq"'})
        }
        const tag=node.parent.openingElement?.tagName.getText(source)||''
        add(node,value,'text',/^h[1-3]$/.test(tag)?'標題':/Link$|^a$/.test(tag)?'按鈕文字':/NT\$/.test(value)?'展示價格／優惠文字':'說明文字',true)
      }
    }else if(ts.isStringLiteral(node)){
      const value=node.text,parent=node.parent
      if(ts.isJsxAttribute(parent)&&['alt','href'].includes(parent.name.getText(source))&&
          (parent.name.getText(source)==='alt'||/^https?:\/\//.test(value)))
        add(node,value,parent.name.getText(source)==='href'?'link':'text',parent.name.getText(source)==='href'?'外部連結':'圖片說明',true)
      else if(/^\/(photography-gallery|legacy)\//.test(value))add(node,value,'image','圖片網址',false)
      else if((/[\u3400-\u9fff]/.test(value)||(ts.isPropertyAssignment(parent)&&['price','title','body','question','heading','description'].includes(parent.name.getText(source))))&&!ts.isJsxAttribute(parent)&&(
        ts.isPropertyAssignment(parent)||ts.isArrayLiteralExpression(parent)))add(node,value,'text',ts.isPropertyAssignment(parent)&&parent.name.getText(source)==='question'?'問題':ts.isPropertyAssignment(parent)&&parent.name.getText(source)==='price'?'展示價格':'項目說明',false)
    }
    ts.forEachChild(node,walk)
  }
  walk(source)
  let rewritten=original
  for(const replacement of replacements.sort((a,b)=>b.start-a.start))rewritten=rewritten.slice(0,replacement.start)+replacement.text+rewritten.slice(replacement.end)
  rewritten=rewritten.replace(`function ${name}PhotographyPage() {`,`function ${name}PhotographyLayout({ content }) {\n  const c = (key) => content.values[key] ?? '';`)
  rewritten=rewritten.replace("import SiteFooter from '../../components/site/SiteFooter';","import SiteFooter from '../../components/site/SiteFooter';\nimport PhotographyContentGate from '../../components/site/PhotographyContentGate';")
  rewritten=rewritten.replace('`${baseUrl}${path.startsWith("/") ? path.slice(1) : path}`','/^https?:\\/\\//i.test(path) ? path : `${baseUrl}${path.startsWith("/") ? path.slice(1) : path}`')
  rewritten=rewritten.replace(/<a\s+href="#(?:booking-flow)?"([\s\S]*?)<\/a>/g,'<SiteLink to="/booking?service=photo"$1</SiteLink>')
  rewritten=rewritten.replaceAll('to="/course/tomamu"','to="/booking?service=ski"')
  rewritten=rewritten.replace(`export default ${name}PhotographyPage;`,`function ${name}PhotographyPage() {\n  return <PhotographyContentGate season="${season}">{content => <${name}PhotographyLayout content={content} />}</PhotographyContentGate>;\n}\n\nexport default ${name}PhotographyPage;`)
  const record={season,title:season==='winter'?'冬季雪地攝影':'夏季旅拍攝影',version:1,sections:[...groups.values()].sort((a,b)=>a.order-b.order).map(({order,...info})=>info)}
  records.push(record)
  console.log(`${season}: ${count} editable values, ${groups.size} groups; layout preserved`)
  if(apply){fs.mkdirSync(path.join(root,'tmp'),{recursive:true});fs.writeFileSync(path.join(root,`tmp/${season}-photography-before-cms.jsx`),original);fs.writeFileSync(file,rewritten)}
}
if(apply)fs.writeFileSync(path.join(root,'snowland/Client/fixtures/photography_page_defaults.json'),JSON.stringify(records,null,2)+'\n')
