const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const ts = require('typescript')

const admin = path.resolve(__dirname, '../src/admin')
const source = fs.readFileSync(path.join(admin, 'pages/OrdersPage.tsx'), 'utf8')
const componentSource = fs.readFileSync(path.join(admin, 'components/OrderCoachAvailability.tsx'), 'utf8')
const ast = ts.createSourceFile('OrdersPage.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
const drawer = ast.statements.find((node) => ts.isFunctionDeclaration(node) && node.name?.text === 'OrderDetailDrawer')
assert.ok(drawer)

const bindings = new Map()
let select
let disclosure
function visit(node) {
  if (ts.isVariableDeclaration(node)) bindings.set(node.name.getText(ast), node.getText(ast))
  if (ts.isJsxElement(node) && node.openingElement.tagName.getText(ast) === 'select'
      && node.openingElement.attributes.getText(ast).includes('coachAssignments[r.id]')) select = node.getText(ast)
  if (ts.isJsxExpression(node) && node.expression?.getText(ast).includes('<OrderCoachAvailability reservation={r}')) {
    disclosure = node.expression.getText(ast)
  }
  ts.forEachChild(node, visit)
}
visit(drawer)
assert.ok(select)
assert.ok(disclosure)

const compile = (code) => ts.transpileModule(code, {
  compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS },
}).outputText
const component = vm.createContext({ React, exports: {}, require })
vm.runInContext(compile(componentSource), component)
const context = vm.createContext({ React, exports: {}, OrderCoachAvailability: component.exports.default })
const pickerBindings = ['availableCoaches', 'selectedCoachId', 'selectedCoachMissing'].map((name) => {
  assert.ok(bindings.has(name))
  return `const ${bindings.get(name)}`
})
vm.runInContext(compile(`exports.Picker = ({ r, coachAssignments, canEditCourse, isStudentSpecifiedCoach }) => {
  const idx = 0
  ${pickerBindings.join('\n')}
  return <>${select}{${disclosure}}</>
}`), context)

const reservation = {
  id: 1,
  candidate_status: 'ok',
  preferred_coach_id: 2,
  preferred_coach: '原指派教練例',
  available_coaches: [{ id: 1, name: '可選教練例', requires_confirmation: true }],
  unavailable_coaches: [
    { id: 2, name: '原指派教練例', reason_codes: ['missing_language'] },
    { id: 3, name: '不可選教練例', reason_codes: ['schedule_conflict', 'future_reason'] },
  ],
}
function render(overrides = {}) {
  return renderToStaticMarkup(React.createElement(context.exports.Picker, {
    r: { ...reservation, ...overrides }, coachAssignments: { 1: 2 }, canEditCourse: true, isStudentSpecifiedCoach: false,
  }))
}

const html = render()
assert.match(html, /<details(?![^>]*\bopen(?:\s|=|>))[^>]*><summary[^>]*>查看無法選擇的教練及原因/)
assert.match(html, /<li[^>]*>.*?原指派教練例（目前指派）.*?未開放此語言.*?<\/li>/)
assert.match(html, /<li[^>]*>.*?不可選教練例.*?課程時段重疊、不符合條件.*?<\/li>/)
const dropdown = html.match(/<select[^>]*>.*?<\/select>/)[0]
assert.deepEqual([...dropdown.matchAll(/<option[^>]*value="([^"]*)"/g)].map((option) => option[1]), ['', '2', '1'])
assert.match(dropdown, /<option value="2" disabled="" selected="">原指派教練例/)
assert.match(dropdown, /可選教練例（需確認）/)
assert.doesNotMatch(dropdown, /不可選教練例/)

const empty = render({ available_coaches: [] })
assert.match(empty, /目前沒有符合條件的教練/)
assert.doesNotMatch(empty, /教練名單載入失敗/)
const failed = render({ candidate_status: 'error' })
assert.match(failed, /教練名單載入失敗/)
assert.match(failed, /原指派教練例（目前指派）/)
assert.doesNotMatch(failed, /目前沒有符合條件的教練|目前不在可排清單|<details|<option[^>]*value="1"/)

console.log('PASS order coach picker: closed disclosure, reason labels, current selection, successful empty list and load error')
