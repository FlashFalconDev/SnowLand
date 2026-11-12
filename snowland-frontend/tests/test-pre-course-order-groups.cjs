const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { createRequire } = require('node:module')
const vm = require('node:vm')

const root = process.env.SNOWLAND_FRONTEND_TEST_ROOT || path.resolve(__dirname, '..')
const localRequire = createRequire(path.join(root, 'package.json'))
const React = localRequire('react')
const ts = localRequire('typescript')
const { renderToStaticMarkup } = localRequire('react-dom/server')
const source = fs.readFileSync(path.join(root, 'src/pages/site/MembershipPage.jsx'), 'utf8')
const formsSource = source.slice(source.indexOf('function Forms('), source.indexOf('function SatisfactionForm('))
const context = vm.createContext({
  React, URLSearchParams, search: '',
  useSiteLocale: () => ({ t: key => key }),
  useLocation: () => ({ search: context.search }),
  formatDate: date => date,
  ParticipantRoster: () => React.createElement('p', null, '同行邀請'),
  MissingStudents: () => React.createElement('p', null, '建立學員資料'),
  ManageLearnerProfiles: () => null,
  LinkCourseLearner: () => null,
  PreCourseForm: ({ form }) => React.createElement('p', null, form.member_name),
  SiteLink: ({ to, children }) => React.createElement('a', { href: to }, children),
  EmptyState: ({ title }) => React.createElement('p', null, title),
})
vm.runInContext(ts.transpileModule(formsSource, {
  compilerOptions: { jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020 },
}).outputText, context)

const reservation = (id, course_template, dates, extra = {}) => ({
  id, resort: '同一雪場', course_template,
  bookings: dates.map(date => ({ date })), ...extra,
})
const form = (id, order_id, reservation_id, member_name) => ({
  id, order_id, order_number: `QA-${order_id}`, reservation_id, member_name, resort: '同一雪場',
})
const props = {
  orders: [
    { id: 1, order_number: 'QA-1', reservations: [
      reservation(11, '第一堂', ['2026-12-01', '2026-12-01'], { participants: [{ id: 101 }] }),
      reservation(12, '同訂單的第二堂', ['2026-12-02']),
    ] },
    { id: 2, order_number: 'QA-2', reservations: [reservation(21, '另一筆訂單的課', ['2026-12-05'], { missing_students: 1 })] },
  ],
  forms: [form(101, 1, 11, '第一堂學員'), form(102, 1, 12, '只有資料的學員'), form(301, 3, 31, '受邀學員')],
  participantCourses: [{ id: 31, resort: '同一雪場', course_name: '受邀課程', bookings: [{ date: '2026-12-09' }] }],
}
const render = () => renderToStaticMarkup(React.createElement(context.Forms, props))
const html = render()
const firstOrder = html.slice(html.indexOf('訂單 QA-1'), html.indexOf('訂單 QA-2'))
const secondOrder = html.slice(html.indexOf('訂單 QA-2'), html.indexOf('訂單 QA-3'))
const invitedOrder = html.slice(html.indexOf('訂單 QA-3'))
for (const label of ['第一堂學員', '同訂單的第二堂', '2026-12-02', '只有資料的學員', '同行邀請']) {
  assert.ok(firstOrder.includes(label), `Order QA-1 must show ${label} with its course`)
}
assert.equal((firstOrder.match(/2026-12-01/g) || []).length, 1)
assert.ok(secondOrder.includes('另一筆訂單的課') && secondOrder.includes('建立學員資料'))
assert.ok(!secondOrder.includes('第一堂學員') && !secondOrder.includes('同行邀請'))
assert.ok(invitedOrder.includes('受邀課程') && invitedOrder.includes('2026-12-09') && invitedOrder.includes('受邀學員'))
assert.ok(!invitedOrder.includes('同行邀請'))

context.search = '?reservation=12'
const filtered = render()
assert.ok(filtered.includes('QA-1') && filtered.includes('同訂單的第二堂') && filtered.includes('查看全部課程的學員'))
assert.ok(!filtered.includes('QA-2') && !filtered.includes('第一堂學員') && !filtered.includes('受邀學員'))
context.search = '?reservation=999'
assert.ok(render().includes('目前沒有待填寫的課前資料'))
console.log('PASS pre-course order grouping, course dates, bound participant and filtered entry')
