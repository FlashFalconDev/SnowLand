const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), Module = require('node:module'), vm = require('node:vm')
const root = path.resolve(__dirname, '../snowland-frontend'), localRequire = Module.createRequire(path.join(root, 'package.json'))
const React = localRequire('react'), ts = localRequire('typescript')
const source = fs.readFileSync(path.join(root, 'src/admin/components/MemberLoyaltyPanel.tsx'), 'utf8')
const compiled = ts.transpileModule(source + '\nexports.LoyaltyForm = LoyaltyForm;', { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020 } }).outputText
const base = { points: 20, previous_points: 0, alumni_verified: false, level: 'new', updated_at: 'QA-version', history: [] }
function find(node, predicate) {
  if (!node || typeof node !== 'object') return null
  if (predicate(node)) return node
  for (const child of React.Children.toArray(node.props?.children)) { const found = find(child, predicate); if (found) return found }
  return null
}
function harness(states, error) {
  let index = 0; const calls = [], cached = [], notices = []
  const context = vm.createContext({ React, exports: {}, require: name => name === 'react' ? { useState: initial => { const i = index++; if (states[i] === undefined) states[i] = initial; return [states[i], value => states[i] = value] } }
    : name === '@tanstack/react-query' ? { useQueryClient: () => ({ setQueryData: (...args) => cached.push(args), invalidateQueries: async () => {} }) }
    : name === '../context' ? { useNotification: () => ({ success: message => notices.push(message) }) }
    : { saveCustomerLoyalty: async (...args) => { calls.push(args); if (error) throw error; return { ...base, points: 120, previous_points: 100, alumni_verified: true } } } })
  vm.runInContext(compiled, context)
  const render = () => { index = 0; return context.exports.LoyaltyForm({ userId: 22, data: base, onReload() {} }) }
  return { calls, cached, notices, render, states, button: () => find(render(), node => node.type === 'button' && node.props.children === '儲存舊生審核'),
    submit: () => find(render(), node => node.type === 'form').props.onSubmit({ preventDefault() {} }) }
}
async function main() {
  for (const values of [[false,'100','QA'],[true,'1.5','QA'],[true,'-1','QA'],[true,'','QA'],[true,'2147483648','QA'],[true,'100',''],[false,'0','QA']]) {
    const ui = harness([...values, false, '', false]); assert.equal(ui.button().props.disabled, true)
    await ui.submit(); assert.equal(ui.calls.length, 0)
  }
  const ui = harness([true,'100','  QA核對  ',false,'',false])
  assert.equal(ui.button().props.disabled, false); await ui.submit()
  assert.equal(ui.calls[0][0], 22)
  assert.equal(JSON.stringify(ui.calls[0][1]), JSON.stringify({ alumni_verified: true, previous_points: 100, reason: 'QA核對', expected_updated_at: 'QA-version' }))
  assert.equal(ui.cached.length, 1); assert.equal(ui.notices.length, 1)
  const stale = harness([true,'100','QA',false,'',false], { response: { status: 409, data: { msg: '資料已更新' } } })
  await stale.submit(); assert.equal(stale.states[5], true); assert.equal(stale.button().props.disabled, true)
  assert.ok(find(stale.render(), node => node.type === 'button' && node.props.children === '重新載入最新審核資料'))
  const busy = harness([true,'100','QA',true,'',false]); await busy.submit(); assert.equal(busy.calls.length, 0)
  console.log('PASS loyalty controls: verification, integer limits, reason, exact total payload, pending guard, success cache/feedback, stale conflict/reload')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
