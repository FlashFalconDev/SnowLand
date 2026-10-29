const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),ts=req('typescript')
const compile=file=>ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
const context=vm.createContext({exports:{}});vm.runInContext(compile('src/utils/guideArticleHtml.js'),context)
const prepare=context.exports.prepareGuideArticleHtml
const original='<div id="guide-section-1"></div><h2 class="old">第一節 <strong>粗體</strong></h2><h3 id="old-section">第二節 &amp; 內容</h3><h4 id="old-section">重複ID</h4><h2><img src="/qa.svg"></h2>'
const result=prepare(original)
assert.equal(result.toc.length,3)
assert.equal(result.toc[0].id,'guide-section-2');assert.equal(result.toc[0].label,'第一節 粗體')
assert.equal(result.toc[1].id,'old-section');assert.equal(result.toc[1].label,'第二節 & 內容')
assert.notEqual(result.toc[2].id,'old-section');assert.equal(result.toc[2].level,4)
assert.ok(result.html.includes('<strong>粗體</strong>'));assert.ok(result.html.includes('class="old"'))
const attributes=prepare('<h2 title=\'文字 id="not-an-id"\'>標題</h2><h3 id="snow&amp;ice">雪與冰</h3>')
assert.notEqual(attributes.toc[0].id,'not-an-id','title中的id字樣不是屬性')
assert.equal(attributes.toc[1].id,'snow&ice','目錄錨點必須使用瀏覽器解碼後的ID')
assert.ok(attributes.html.includes('title=\'文字 id="not-an-id"\''))
assert.doesNotThrow(()=>encodeURIComponent(prepare('<h2 id="&#xD800;">安全錨點</h2>').toc[0].id))
console.log('PASS original article TOC: preserved markup and anchors, duplicate IDs, entity labels and quoted attributes')

const requests=[]
const hookContext=vm.createContext({exports:{},URL,require:name=>name==='react'?{useState:initial=>[typeof initial==='function'?initial():initial,()=>{}],useEffect:effect=>effect()}:{fetchSiteContent:params=>{requests.push(params);return Promise.resolve([])}}})
vm.runInContext(compile('src/hooks/useSiteContent.js'),hookContext)
hookContext.exports.useSiteContent('guides.articles')
assert.equal(requests.at(-1).view,'cards')
hookContext.exports.useSiteContent('guides.articles',{contentId:'501',limit:1})
assert.equal(requests.at(-1).content_id,'501');assert.equal(requests.at(-1).view,undefined)
hookContext.exports.useSiteContent('offers.earlybird')
assert.equal(requests.at(-1).view,undefined)
console.log('PASS actual content hook: guide list requests cards, detail requests full, other pages remain unchanged')
