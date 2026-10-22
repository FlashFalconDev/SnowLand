// Mechanical extraction from this repository's existing JSX, never remote code.
// Default is read-only. --apply saves the original in ignored tmp for parity QA.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),front=path.join(root,'snowland-frontend')
const ts=Module.createRequire(path.join(front,'package.json'))('typescript')
const file=path.join(front,'src/pages/site/LegacyContentPage.jsx'),original=fs.readFileSync(file,'utf8')
if(original.includes('const aboutContent ='))throw Error('About page already parameterized')
const source=ts.createSourceFile(file,original,ts.ScriptTarget.Latest,true,ts.ScriptKind.JSX)
const legacy=JSON.parse(fs.readFileSync(path.join(root,'snowland/Client/fixtures/site_content_defaults.json'),'utf8')).find(row=>row.location_key==='about.snowland').metadata.page
let branch;function locate(node){if(ts.isIfStatement(node)&&node.expression.getText(source)==='isAboutPage')branch=node.thenStatement;ts.forEachChild(node,locate)}locate(source)
if(!branch)throw Error('Missing original about layout')
const fields=[],edits=[]
function cooked(text){const ctx={exports:{},React:{createElement:(_tag,_props,...children)=>children.join('')}};vm.runInNewContext(ts.transpileModule(`exports.value=<span>${text}</span>`,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,ctx);return ctx.exports.value}
function add(node,value,kind,label,jsx,extra={}){const key='about_'+String(fields.length+1).padStart(3,'0');fields.push({key,kind,label,value,...extra});edits.push({start:node.getStart(source),end:node.end,text:jsx?`{c("${key}")}`:`c("${key}")`});return key}
function walk(node){
  if(ts.isVariableDeclaration(node)&&node.name.getText(source)==='aboutIntro')return // unused legacy variable
  if(ts.isCallExpression(node)&&node.expression.getText(source)==='getSectionParagraphs'){
    const heading=node.arguments[1]?.text;if(!heading)throw Error('Unexpected paragraph source')
    const start=legacy.blocks.findIndex(block=>block.type==='heading'&&block.text===heading),paragraphs=[]
    for(let i=start+1;start>=0&&i<legacy.blocks.length;i++){const b=legacy.blocks[i];if(b.type==='heading')break;if(b.type==='paragraph')paragraphs.push(...b.text.replace(/\s+/g,' ').trim().split(/(?<=[。！？])\s*/).filter(Boolean))}
    const key=add(node,paragraphs.join('\n'),'text',heading+'：段落（每行一段）',false,{source_heading:heading})
    edits[edits.length-1].text=`c("${key}").split("\\n").filter(Boolean)`;return
  }
  if(ts.isJsxText(node)){
    const value=cooked(node.getText(source));if(/[A-Za-z0-9\u3400-\u9fff]/.test(value))add(node,value,'text',node.parent.openingElement?.tagName.getText(source)?.match(/^h[1-3]$/)?'標題':'說明文字',true)
  }else if(ts.isStringLiteral(node)){
    const parent=node.parent,value=node.text
    if(ts.isJsxAttribute(parent)&&['src','alt'].includes(parent.name.getText(source)))add(node,value,parent.name.getText(source)==='src'?'image':'text',parent.name.getText(source)==='src'?'圖片網址':'圖片說明',true)
    else if(ts.isPropertyAssignment(parent)&&parent.name.getText(source)==='image')add(node,value,'image','區塊圖片',false)
    else if(ts.isPropertyAssignment(parent)&&['title','englishTitle'].includes(parent.name.getText(source)))add(node,value,'text',parent.name.getText(source)==='title'?'區塊標題':'區塊英文標題',false)
    else if(ts.isArrayLiteralExpression(parent)&&/[\u3400-\u9fff]/.test(value))add(node,value,'text','段落文字',false)
  }
  ts.forEachChild(node,walk)
}walk(branch)
let rewritten=original;for(const edit of edits.sort((a,b)=>b.start-a.start))rewritten=rewritten.slice(0,edit.start)+edit.text+rewritten.slice(edit.end)
rewritten=rewritten.replace('  const isAboutPage = pageKey === "about";','  const isAboutPage = pageKey === "about";\n  const aboutContent = page.layout;\n  const c = (key) => aboutContent?.values?.[key] ?? "";')
const schema={version:1,page_key:'about',title:'滑雪學校介紹',sections:[{id:'original',label:'目前官網原版型',fields}]}
console.log(`about: ${fields.length} editable original values; no layout changes`)
if(process.argv.includes('--apply')){fs.mkdirSync(path.join(root,'tmp'),{recursive:true});fs.writeFileSync(path.join(root,'tmp/about-before-cms.jsx'),original,{flag:'wx'});fs.writeFileSync(file,rewritten);fs.writeFileSync(path.join(root,'snowland/Client/fixtures/about_page_defaults.json'),JSON.stringify(schema,null,2)+'\n',{flag:'wx'})}
