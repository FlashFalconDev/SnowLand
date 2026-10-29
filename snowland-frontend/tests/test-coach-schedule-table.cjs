const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), Module = require('node:module'), vm = require('node:vm')
const root = path.resolve(__dirname, '..'), req = Module.createRequire(path.join(root, 'package.json'))
const React = req('react'), { renderToStaticMarkup } = req('react-dom/server'), ts = req('typescript')
const source = fs.readFileSync(path.join(root, 'src/admin/pages/CoachScheduleTable.tsx'), 'utf8')
const ctx = vm.createContext({ React, exports: {}, require: req })
vm.runInContext(ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS } }).outputText, ctx)
const coaches = [{ id: 1, name: '同名' }, { id: 2, name: '同名' }, { id: 3, name: '無課教練' }]
const booking = { id: 20, coach_id: 1, coach_name: '同名', date: '2026-10-21', start_time: '09:00', end_time: '11:00', course_name: '單板四小時', resort: 'QA雪場', number_of_people: 2, is_preferred_coach: true, ability_level: 'level3', group_id: 8 }
let opened = null, selected = null
const props = { coaches, bookings: [booking], leaves: [{ coach_id: 2, coach_name: '同名', start_date: '2026-10-20', end_date: '2026-10-22' }], days: [{ date: new Date(2026, 9, 21), dateStr: '2026-10-21' }], coachFilter: '', isOutsideWindow: () => false, onOpenOrder: value => opened = value, onSelectDate: value => selected = value }
const rows = ctx.exports.getCoachScheduleRows(coaches, [booking, { ...booking, id: 21, coach_id: null, coach_name: '' }], '')
assert.equal(rows.length, 4); assert.equal(rows.filter(row => row.name === '同名').length, 2)
assert.equal(ctx.exports.getCoachScheduleRows(coaches, [], '無課教練').length, 1)
const tree = ctx.exports.default(props), html = renderToStaticMarkup(tree)
for (const text of ['休假（已核准）', '指定', 'Lv3', '— 未排課', '不代表可接課', 'scope="row"', 'scope="col"', 'sticky left-0', 'sticky top-0', 'overflow-auto', 'min-h-11']) assert.ok(html.includes(text), text)
assert.equal((html.match(/單板四小時/g) || []).length, 1, 'Same-name coaches must not duplicate each other’s lessons')
const buttons = []
function collect(node) { if (!node || typeof node !== 'object') return; if (node.type === 'button') buttons.push(node); React.Children.forEach(node.props?.children, collect) }
collect(tree); buttons.find(button => button.props['aria-label']?.includes('查看訂單')).props.onClick(); assert.equal(opened, booking)
buttons.find(button => !button.props['aria-label']).props.onClick(); assert.equal(selected, '2026-10-21')
const hidden = renderToStaticMarkup(ctx.exports.default({ ...props, isOutsideWindow: () => true }))
assert.ok(hidden.includes('超出可查看期間')); assert.ok(!hidden.includes('單板四小時')); assert.ok(!hidden.includes('休假（已核准）')); assert.ok(hidden.includes('disabled=""'))
const filtered = renderToStaticMarkup(ctx.exports.default({ ...props, coachFilter: '無課教練' }))
assert.ok(!filtered.includes('單板四小時')); assert.ok(!filtered.includes('休假（已核准）'))
const empty = renderToStaticMarkup(ctx.exports.default({ ...props, bookings: [], coaches: [], leaves: [] }))
assert.ok(empty.includes('目前範圍沒有教練或排課資料'))
const plain = renderToStaticMarkup(ctx.exports.default({ ...props, bookings: [{ ...booking, is_preferred_coach: false }] }))
assert.ok(plain.includes('一般課程')); assert.ok(plain.includes('bg-violet-100')); assert.ok(html.includes('bg-orange-100'))
console.log('PASS actual coach schedule table: stable IDs, duplicate names, empty roster rows, approved leave, designated color, scoped dates and real callbacks')
