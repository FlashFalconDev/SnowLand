const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const vm = require('node:vm')
const root = path.resolve(__dirname, '../snowland-frontend')
const localRequire = Module.createRequire(path.join(root, 'package.json'))
const ts = localRequire('typescript')
const React = localRequire('react')
const { renderToStaticMarkup } = localRequire('react-dom/server')
const source = fs.readFileSync(path.join(root, 'src/pages/site/MembershipPage.jsx'), 'utf8')
const balanceContext = vm.createContext({ exports: {}, require: name => localRequire(name) })
vm.runInContext(ts.transpileModule(fs.readFileSync(path.join(root,
  'src/components/OrderAmendmentBalance.jsx'), 'utf8'), { fileName: 'balance.jsx', compilerOptions: {
  jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
} }).outputText, balanceContext)
const between = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)))
const context = vm.createContext({ React, Intl, Date, Number,
  OrderAmendmentBalance: balanceContext.exports.default,
  requestJson: async () => ({ items: [] }),
  useLocation: () => ({ pathname: '/membership/orders/1' }),
  SiteLink: ({ to, children, ...props }) => React.createElement('a', { href: to, ...props }, children),
  ChevronRight: () => null, SharedClassSummary: () => null, CancellationForm: () => null,
  ClassGroupQRImage: () => null, EmptyState: () => null })
const code = between('const formatDate =', 'const ageOptions =')
  + between('function OrderCard(', 'function CancellationForm(')
  + between('function Orders(', 'function PreCourseForm(')
vm.runInContext(ts.transpileModule(code, { fileName: 'membership.jsx', compilerOptions: {
  jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText, context)
const course = (status, resort, date) => ({ id: resort, status, resort, course_type: 'QA單板', people: 1,
  coach: 'QA教練', bookings: [{ id: date, date, start_time: '09:00', end_time: '11:00' }] })
const cancelled = course('cancelled', '歷史雪場', '2026-10-17')
const active = course('manually_assigned', '有效雪場', '2026-11-06')
const order = { id: 1, order_number: 'QA-only', payment_status: 'paid', total_amount: 10000,
  reservations: [cancelled, active] }
const renderCard = item => renderToStaticMarkup(React.createElement(context.OrderCard, { order: item, showActions: false }))
let failed = 0
for (const [name, check] of [
  ['summary prefers active course over earlier cancelled history', () => {
    const html = renderCard(order)
    assert.ok(html.includes('有效雪場'))
    assert.ok(!html.includes('歷史雪場'))
  }],
  ['fully cancelled order still shows historical course', () => {
    assert.ok(renderCard({ ...order, reservations: [cancelled] }).includes('歷史雪場'))
  }],
  ['photo summary uses service setting, not the category name', () => {
    const html = renderCard({...order,reservations:[{...active,service_type:'photo',course_type:'影像方案'}]})
    assert.ok(html.includes('攝影方案') && html.includes('攝影師') && html.includes('預約數量'))
    assert.ok(!html.includes('>教練</span>') && !html.includes('>人數</span>'))
  }],
  ['detail marks cancelled course instead of presenting it as active', () => {
    const html = renderToStaticMarkup(React.createElement(context.Orders, { data: { orders: [order] } }))
    assert.ok(html.includes('歷史雪場'))
    assert.ok(html.includes('已取消'))
    assert.equal((html.match(/填寫學員與課前資料/g) || []).length, 1)
  }],
]) {
  try { check(); console.log('PASS', name) }
  catch (error) { failed++; console.error('FAIL', name, error.message) }
}
if (failed) process.exitCode = 1
