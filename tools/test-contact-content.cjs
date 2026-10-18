const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), Module = require('node:module'), vm = require('node:vm')
const root = path.resolve(__dirname, '../snowland-frontend'), req = Module.createRequire(path.join(root, 'package.json'))
const React = req('react'), ts = req('typescript'), {renderToStaticMarkup} = req('react-dom/server')
const source = fs.readFileSync(path.join(root, 'src/pages/site/ContactPage.jsx'), 'utf8')
function render(item, extra = {}) {
  const ctx = vm.createContext({exports: {}, require(name) {
    if (name === 'react') return React
    if (name.includes('ContactForm')) return () => React.createElement('div', {'data-testid':'contact-form'})
    if (name === 'framer-motion') return {motion: {img: 'img'}, useReducedMotion: () => true, useScroll: () => ({}), useTransform() {}}
    if (name.includes('SiteHeader') || name.includes('SiteFooter')) return () => null
    if (name.includes('assetPaths')) return {homepageAssetBase: '/homepage'}
    if (name.includes('assets/site/')) return '/qa-background.jpg'
    if (name.includes('useSiteContent')) return {useSiteContent: () => ({items: item ? [item] : [], ...extra}), siteContentToPage: row => row}
    throw Error(name)
  }})
  vm.runInContext(ts.transpileModule(source, {compilerOptions: {jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, esModuleInterop: true}}).outputText, ctx)
  return renderToStaticMarkup(React.createElement(ctx.exports.default))
}
const paragraph = text => ({type: 'paragraph', text})
const page = {title: 'QA聯絡設定', blocks: [
  paragraph('QA營業說明：週一至週五回覆'), paragraph('Email：qa-contact@example.test'),
  paragraph('Email：qa-contact@example.test'), paragraph('官方 LINE：https://page.line.me/qa-contact'),
  paragraph('官網：https://example.test/contact'), paragraph('E-mail*'), paragraph('主旨'), paragraph('訊息'),
]}
const html = render(page)
assert.ok(html.includes('QA營業說明：週一至週五回覆'), 'CMS一般說明不可被過濾')
assert.ok(html.includes('href="mailto:qa-contact@example.test"'), 'CMS信箱可直接開啟郵件')
assert.equal((html.match(/mailto:qa-contact@example.test/g) || []).length, 1, '重複匯入的信箱只顯示一次')
assert.ok(html.includes('href="https://page.line.me/qa-contact"'), 'LINE使用CMS連結')
assert.ok(!html.includes('@snowlandcz'), '不得保留寫死的聯絡帳號')
assert.ok(html.includes('href="https://example.test/contact"'))
assert.ok(html.includes('data-testid="contact-form"'), 'CMS聯絡頁保留真正收件表單入口')
assert.ok(!html.includes('已送出'), '未實作收件不得顯示假成功')
assert.ok(render({...page, blocks: [paragraph('e-MAIL: second@example.test')]}).includes('href="mailto:second@example.test"'))
const unsafe = render({...page, blocks: [paragraph('Email：bad@example.test\nBcc: leak@example.test'), paragraph('javascript:alert(1)')]})
assert.ok(!unsafe.includes('href="mailto:')); assert.ok(!unsafe.includes('href="javascript:'))
assert.ok(!render({...page, blocks: [null, {}, paragraph(null), paragraph(123)]}).includes('undefined'))
assert.ok(render(null, {isLoading: true}).includes('聯絡資訊載入中'))
assert.ok(render(null, {error: new Error('QA')}).includes('聯絡資訊暫時無法載入'))
assert.ok(render(null).includes('目前沒有已發布'))
console.log('PASS contact CMS text, dynamic links, email safety, deduplication, wired real form and page loading/error/empty states')
