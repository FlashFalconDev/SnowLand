const assert = require('node:assert/strict');
const {extract} = require('./extract-customer-guide-source.cjs');
const card = {title:'Test article',url:'https://example.test/article',category:'Test',excerpt:'Summary'};
const article = {title:'Test article',heroImage:'/image.jpg',html:'<h2>Title</h2><table><tr><td>Full body</td></tr></table>'};
const bundle = `const cards=${JSON.stringify([card])};const bodies=${JSON.stringify({test:article})};`;
assert.deepEqual(JSON.parse(JSON.stringify(extract(bundle))), [{card,article:{slug:'test',...article}}]);
assert.throws(()=>extract(bundle.replace(JSON.stringify(article.html),'""')), /Missing full article/);
assert.throws(()=>extract(bundle + 'const otherCards='+JSON.stringify([card])+';'), /Ambiguous source/);
assert.throws(()=>extract(bundle.replace(JSON.stringify([card]),JSON.stringify([card,card]))), /Duplicate card/);
assert.equal(extract(bundle.replace(JSON.stringify([card]), JSON.stringify([card,{...card,url:'https://example.test/older-article'}]))).length,2,'Reference can intentionally link two distinct URLs with the same title to the same body');
assert.throws(()=>extract(bundle.replace(JSON.stringify(article.title),'"Different title"')), /Missing full article/);
const hostile = bundle.replace(JSON.stringify([card]), '(()=>{globalThis.executed=true;return []})()');
assert.throws(()=>extract(hostile), /Ambiguous source/);
assert.equal(globalThis.executed, undefined, 'Downloaded runtime code must never execute');
assert.throws(()=>extract(bundle.replace(JSON.stringify(article.html),'`unsafe ${globalThis.executed=true}`')), /Ambiguous source/);
assert.equal(globalThis.executed, undefined);
assert.throws(()=>extract(bundle.replace('"test":','"__proto__":')), /Ambiguous source/);
console.log('PASS literal-only extraction: full markup, missing/duplicate/ambiguous bodies and hostile expressions');

if (process.argv[2]) {
  const fs = require('node:fs');
  const path = require('node:path');
  const snapshot = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const defaults = JSON.parse(fs.readFileSync(path.join(__dirname,'../snowland/Client/fixtures/site_content_defaults.json'),'utf8'));
  const originals = defaults.filter(row=>row.location_key==='guides.articles');
  assert.equal(snapshot.articles.length,75);
  assert.equal(new Set(snapshot.articles.map(row=>row.card.url)).size,75);
  assert.equal(new Set(snapshot.articles.map(row=>row.article.slug)).size,73);
  assert.equal(originals.length,74);
  for (const row of originals) {
    const source = snapshot.articles.find(item=>item.card.url === row.link_url);
    assert.ok(source, `Missing original URL: ${row.link_url}`);
    assert.equal(source.card.title, row.title);
    assert.equal(source.article.title, row.title);
    assert.ok(source.article.html.trim().length > source.card.excerpt.length, 'Full body cannot be replaced by an excerpt');
  }
  const added = snapshot.articles.filter(row=>!originals.some(original=>original.link_url===row.card.url));
  assert.equal(added.length,1);
  assert.equal(added[0].card.url,'https://land110602.com/hokkaido-family-ski-lessons/');
  assert.ok(added[0].article.html.includes('小朋友幾歲適合開始滑雪'));
  assert.ok(added[0].article.html.includes('連續上課3天'));
  console.log('PASS customer snapshot: 75 unique URLs / 73 source bodies, all 74 original cards preserved, one complete family article found');
}
