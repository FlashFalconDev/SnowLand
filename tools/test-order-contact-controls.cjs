const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { createRequire } = require('node:module')
const frontend = path.resolve(__dirname, '../snowland-frontend')
const frontendRequire = createRequire(path.join(frontend, 'package.json'))
const ts = frontendRequire('typescript')
const React = frontendRequire('react')
const { renderToStaticMarkup } = frontendRequire('react-dom/server')
const source = fs.readFileSync(path.join(frontend, 'src/admin/pages/OrdersPage.tsx'), 'utf8')
const marker = source.indexOf('訂單聯絡資料')
assert.ok(marker >= 0)
const start = source.lastIndexOf('<section>', marker)
const end = source.indexOf('</section>', marker) + '</section>'.length
assert.ok(start >= 0 && end > marker)
const section = source.slice(start, end)
const wrapped = `const PRIMARY='#8b5cf6'; const User=()=>null; export default function Contact({order}) { return (${section}); }`
const compiled = ts.transpileModule(wrapped, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText
const mod = { exports: {} }
new Function('require', 'module', 'exports', compiled)(frontendRequire, mod, mod.exports)
const render = order => renderToStaticMarkup(React.createElement(mod.exports.default, { order }))
const base = { name: '舊聯絡人', user_name: '訂購會員甲', user_email: 'member@example.test' }
const html = render({ ...base, booking_contact: {
  name: '本單聯絡人乙', email: 'contact@example.test', phone: '0900000000',
  messenger_type: 'LINE', messenger_id: '<script>qa</script>', source_ip: '192.0.2.1',
} })
for (const expected of ['本單聯絡人乙', 'contact@example.test', '0900000000', 'LINE', '訂購會員甲', '聯絡人姓名', '聯絡電話', '訂購會員']) assert.ok(html.includes(expected), expected)
assert.ok(html.includes('&lt;script&gt;qa&lt;/script&gt;'))
assert.ok(!html.includes('<script>'))
assert.ok(!html.includes('192.0.2.1'))
const legacy = render(base)
assert.ok(legacy.includes('舊聯絡人') && legacy.includes('member@example.test'))
assert.ok(!legacy.includes('undefined'))
assert.ok(render({ user_name: '訪客', user_email: '' }).includes('訪客'))
console.log('PASS actual order contact section: per-order snapshot, account identity separate, legacy/guest fallback, escaped messenger and no audit fields')
