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
  ['list hides order number; detail retains it', () => {
    assert.ok(!renderCard(order).includes('QA-only'))
    const detail = renderToStaticMarkup(React.createElement(context.Orders, { data: { orders: [order] } }))
    assert.ok(detail.includes('QA-only'))
  }],
  ['school-assigned coach is not presented as customer-designated', () => {
    const ordinary = renderCard({...order,reservations:[{...active,is_preferred_coach:false}]})
    assert.ok(ordinary.includes('不指定'));assert.ok(!ordinary.includes('QA教練'))
    const designated = renderCard({...order,reservations:[{...active,is_preferred_coach:true}]})
    assert.ok(designated.includes('QA教練'))
    const shared = renderCard({...order,reservations:[{...active,is_shared_class:true,is_preferred_coach:true}]})
    assert.ok(shared.includes('由學校安排'));assert.ok(!shared.includes('QA教練'))
  }],
  ['card days count unique active dates, not sessions or cancelled history', () => {
    const html=renderCard({...order,reservations:[cancelled,{...active,bookings:[
      {id:1,date:'2026-11-06'},{id:2,date:'2026-11-06'},{id:3,date:'2026-11-08'}]},
      {...active,id:7,resort:'第二雪場',bookings:[{id:4,date:'2026-11-08'},{id:5,date:'2026-11-09'}]}]})
    assert.ok(html.includes('天數'));assert.ok(html.includes('3 天'))
    assert.ok(html.includes('2026/11/06'));assert.ok(html.includes('2026/11/09'))
    assert.ok(html.includes('另有 1 項課程'));assert.ok(!html.includes('歷史雪場'))
  }],
  ['expired cancelled history retains its stored price without calling it payable', () => {
    const html=renderCard({...order,payment_status:'expired',total_amount:0,historical_amount:7600,reservations:[cancelled]})
    assert.ok(html.includes('取消前訂單金額'));assert.ok(html.includes('7,600'));assert.ok(!html.includes('前往付款'))
    const free=renderCard({...order,payment_status:'expired',total_amount:5000,historical_amount:0,reservations:[cancelled]})
    assert.ok(free.includes('NT$ 0'));assert.ok(!free.includes('5,000'),'Stored zero must not fall back to a different amount')
  }],
  ['active partial order and approved refund retain their existing amount semantics', () => {
    const mixed=renderCard({...order,total_amount:1000,historical_amount:7600})
    assert.ok(mixed.includes('NT$ 1,000'));assert.ok(!mixed.includes('7,600'));assert.ok(!mixed.includes('取消前訂單金額'))
    const refunded=renderCard({...order,total_amount:0,historical_amount:7600,reservations:[cancelled],cancellation:{status:'approved',original_amount:6800}})
    assert.ok(refunded.includes('原訂單金額'));assert.ok(refunded.includes('6,800'));assert.ok(!refunded.includes('7,600'))
  }],
  ['photo summary uses service setting, not the category name', () => {
    const html = renderCard({...order,reservations:[{...active,service_type:'photo',course_type:'影像方案'}]})
    assert.ok(html.includes('攝影方案') && html.includes('攝影師') && html.includes('預約數量'))
    assert.ok(html.includes('QA教練'),'Photography keeps its actually assigned photographer name')
    assert.ok(!html.includes('>教練</span>') && !html.includes('>人數</span>'))
  }],
  ['detail marks cancelled course instead of presenting it as active', () => {
    const html = renderToStaticMarkup(React.createElement(context.Orders, { data: { orders: [order] } }))
    assert.ok(html.includes('歷史雪場'))
    assert.ok(html.includes('已取消'))
    assert.equal((html.match(/填寫學員與課前資料/g) || []).length, 1)
  }],
  ['inconsistent payment records request review instead of another payment', () => {
    const review={...order,payment_status:'unpaid',payment_hold_status:'payment_records_review'}
    const card=renderCard(review)
    assert.ok(card.includes('付款紀錄待核對'));assert.ok(!card.includes('前往付款'))
    const detail=renderToStaticMarkup(React.createElement(context.Orders,{data:{orders:[review]}}))
    assert.ok(detail.includes('請勿再次付款'));assert.ok(!detail.includes('前往付款'))
  }],
]) {
  try { check(); console.log('PASS', name) }
  catch (error) { failed++; console.error('FAIL', name, error.message) }
}
if (failed) process.exitCode = 1
