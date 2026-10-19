// Extract only local, repository-owned JSX. Preserve the original for render parity.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),front=path.join(root,'snowland-frontend'),ts=Module.createRequire(path.join(front,'package.json'))('typescript')
const file=path.join(front,'src/pages/site/LegacyContentPage.jsx'),original=fs.readFileSync(file,'utf8')
if(original.includes('const j ='))throw Error('Recruitment already parameterized')
const source=ts.createSourceFile(file,original,ts.ScriptTarget.Latest,true,ts.ScriptKind.JSX)
const old=JSON.parse(fs.readFileSync(path.join(root,'snowland/Client/fixtures/site_content_defaults.json'),'utf8')).find(row=>row.location_key==='about.join-us').metadata.page
const fields=[],edits=[],images=new Map(),targets=[]
function paragraphs(heading){const start=old.blocks.findIndex(b=>b.type==='heading'&&b.text===heading),out=[];for(let i=start+1;start>=0&&i<old.blocks.length;i++){const b=old.blocks[i];if(b.type==='heading')break;if(b.type==='paragraph')out.push(...b.text.replace(/\s+/g,' ').trim().split(/(?<=[。！？])\s*/).filter(Boolean))}return out}
function cooked(text){const ctx={exports:{},React:{createElement:(_tag,_props,...children)=>children.join('')}};vm.runInNewContext(ts.transpileModule(`exports.value=<span>${text}</span>`,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText,ctx);return ctx.exports.value}
function field(value,kind,label,extra={}){if(kind==='image'&&images.has(value))return images.get(value);const key='join_'+String(fields.length+1).padStart(3,'0');fields.push({key,kind,label,value,...extra});if(kind==='image')images.set(value,key);return key}
function replace(node,value,kind,label,jsx,extra={}){const key=field(value,kind,label,extra);edits.push({start:node.getStart(source),end:node.end,text:jsx?`{j("${key}")}`:`j("${key}")`});return key}
function locate(node){
 if(ts.isIfStatement(node)&&node.expression.getText(source)==='isJoinUsPage')targets.push(node.thenStatement)
 if(ts.isVariableDeclaration(node)&&['joinUsBenefits','joinUsResponsibilities','joinUsPriority','joinUsQualities','joinUsSalary','joinUsLanguageNote'].includes(node.name.getText(source)))targets.push(node.initializer)
 if(ts.isVariableDeclaration(node)&&node.name.getText(source)==='joinUsSteps'){
  const rows=[];for(let n=1;n<=7;n++){const heading=`Step ${n}.`,title=field(heading,'text',`流程${n}：步驟標題`),key=field(paragraphs(heading)[0]||'','text',`流程${n}：說明`,{source_heading:heading,source_first:true});rows.push(`{title:j("${title}"),text:j("${key}")}`)}
  edits.push({start:node.initializer.getStart(source),end:node.initializer.end,text:`isJoinUsPage ? [${rows.join(',')}] : []`})
 }
 ts.forEachChild(node,locate)
}locate(source)
function walk(node){
 if(ts.isCallExpression(node)&&node.expression.getText(source)==='getSectionParagraphs'){
  const heading=node.arguments[1]?.text;if(!heading)throw Error('Unexpected original paragraph source')
  let value=paragraphs(heading).join('\n'),target=node,extra={source_heading:heading}
  if(heading==='符合以下條件優先考慮：'){extra.source_contains='具備以上加分語言者優先錄取';value=paragraphs(heading).find(t=>t.includes(extra.source_contains))||'';target=node.parent.parent}
  const key=replace(target,value,'text',heading+'：說明',false,extra)
  if(!extra.source_contains)edits[edits.length-1].text=`j("${key}").split("\\n").filter(Boolean)`
  return
 }
 if(ts.isJsxText(node)){const value=cooked(node.getText(source));if(/[A-Za-z0-9\u3400-\u9fff]/.test(value))replace(node,value,'text',/^h[1-3]$/.test(node.parent.openingElement?.tagName.getText(source))?'標題':'說明文字',true)}
 else if(ts.isStringLiteral(node)){
  const value=node.text,parent=node.parent
  if(ts.isJsxAttribute(parent)&&['src','alt'].includes(parent.name.getText(source)))replace(node,value,parent.name.getText(source)==='src'?'image':'text',parent.name.getText(source)==='src'?'圖片網址':'圖片說明',true)
  else if(ts.isPropertyAssignment(parent)&&['title','englishTitle'].includes(parent.name.getText(source)))replace(node,value,'text',parent.name.getText(source)==='title'?'區塊標題':'區塊英文標題',false)
  else if(ts.isArrayLiteralExpression(parent)&&/[\u3400-\u9fff]/.test(value))replace(node,value,'text','項目文字',false)
 }
 ts.forEachChild(node,walk)
}for(const node of targets)walk(node)
let rewritten=original;for(const edit of edits.sort((a,b)=>b.start-a.start))rewritten=rewritten.slice(0,edit.start)+edit.text+rewritten.slice(edit.end)
rewritten=rewritten.replace('  const aboutContent = page.layout;','  const j = (key) => page.layout?.values?.[key] ?? "";\n  const aboutContent = page.layout;')
const schema={version:1,page_key:'join-us',title:'成為教練',sections:[{id:'original',label:'目前官網原版型',fields}]}
console.log(`${fields.length} recruitment values; original text/layout retained`)
if(process.argv.includes('--apply')){fs.writeFileSync(path.join(root,'tmp/join-before-cms.jsx'),original,{flag:'wx'});fs.writeFileSync(file,rewritten);fs.writeFileSync(path.join(root,'snowland/Client/fixtures/join_page_defaults.json'),JSON.stringify(schema,null,2)+'\n',{flag:'wx'})}
