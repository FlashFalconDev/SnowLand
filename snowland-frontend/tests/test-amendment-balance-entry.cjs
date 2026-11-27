const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const ts = require('typescript')
const { renderToStaticMarkup } = require('react-dom/server')

const calls = []
const target = {
  focus(options) { calls.push(['focus', options.preventScroll]) },
  scrollIntoView(options) { calls.push(['scroll', options.behavior, options.block]) },
}
let query, queryOptions, reducedMotion
const context = vm.createContext({
  React,
  exports: {},
  window: { matchMedia: () => ({ matches: reducedMotion }) },
  require(name) {
    if (name === 'react') return { ...React, useId: () => 'qa-balance', useRef: () => ({ current: target }), useState: initial => [initial, () => {}] }
    if (name === 'react-router-dom') return { Link: ({ to, children }) => React.createElement('a', { href: to }, children) }
    if (name === '@tanstack/react-query') return { useQuery: options => { queryOptions = options; return query } }
    if (name.includes('settlementPreview')) return require('./helpers/settlement-harness.cjs')
    return { default: () => null }
  },
})
const file = path.join(__dirname, '../src/admin/components/AmendmentBalancesPanel.tsx')
vm.runInContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020 },
}).outputText, context)

const title = '差額回報與核對'
const balance = { amount: 120, statuses: ['topup_due'] }
const reported = { id: 7, version: 2, balance_amount: 120, status: 'topup_reported', events: [] }
const find = (node, match) => {
  if (!React.isValidElement(node)) return undefined
  if (match(node)) return node
  return React.Children.toArray(node.props.children).map(child => find(child, match)).find(Boolean)
}
const getEntry = tree => find(tree, node => node.type === 'button' && node.props.children === title)

function render({ amendmentBalance = balance, status, canReconcile = true, ...props } = {}, queryState = { data: { items: [reported] } }) {
  query = queryState
  const tree = context.exports.default({
    order: { id: 42, amendment_balance: amendmentBalance, cancellation: status ? { status } : undefined },
    canReconcile,
    ...props,
  })
  return { tree, html: renderToStaticMarkup(tree), entry: getEntry(tree) }
}

const ready = render()
assert.ok(ready.entry, '待結差額橫幅須有具名按鈕')
assert.match(ready.html, /訂單修改差額尚未結清/)
const panel = find(ready.tree, node => node.type === 'section' && node.props.id === ready.entry.props['aria-controls'])
assert.ok(panel, '按鈕須控制已掛載的差額區塊')
assert.equal(panel.props.tabIndex, -1)
assert.equal(find(panel, node => node.props.id === panel.props['aria-labelledby']).props.children, title)
assert.match(ready.html, /核對補款/)
ready.entry.props.onClick()
reducedMotion = true
ready.entry.props.onClick()
assert.deepEqual(calls, [['focus', true], ['scroll', 'smooth', 'start'], ['focus', true], ['scroll', 'auto', 'start']])

for (const [queryState, text] of [
  [{ isLoading: true }, /讀取差額核對紀錄/],
  [{ error: { response: { status: 403 } } }, /差額紀錄載入失敗/],
  [{ data: { items: [] } }, /目前沒有可顯示的差額紀錄/],
]) {
  const result = render({}, queryState)
  assert.ok(result.entry)
  assert.match(result.html, text)
  assert.ok(find(result.tree, node => node.props.id === result.entry.props['aria-controls']))
}

const outsideWorkflow = render({ canReconcile: false, paymentsHref: '/qa/console/orders/payments?search=QA-42' })
assert.ok(outsideWorkflow.entry)
assert.equal(queryOptions.enabled, false)
assert.match(outsideWorkflow.html, /href="\/qa\/console\/orders\/payments\?search=QA-42"/)
assert.doesNotMatch(outsideWorkflow.html, /核對補款/)

const noPermission = render({ canReconcile: false })
assert.ok(noPermission.entry)
assert.equal(queryOptions.enabled, false)
assert.match(noPermission.html, /請由具付款權限的人員/)
assert.doesNotMatch(noPermission.html, /<a |核對補款/)

const paused = render({ status: 'requested', refundsHref: '/qa/console/orders/refunds?search=QA-42' })
assert.ok(paused.entry)
assert.match(paused.html, /差額回報暫停核對/)
assert.match(paused.html, /href="\/qa\/console\/orders\/refunds\?search=QA-42"/)
assert.doesNotMatch(paused.html, /核對補款/)

const awaitingReport = render({}, { data: { items: [{ ...reported, status: 'topup_due' }] } })
assert.match(awaitingReport.html, /會員回報補款後/)
assert.doesNotMatch(awaitingReport.html, /<button[^>]*>核對補款/)

const history = render({ amendmentBalance: null })
assert.match(history.html, /差額回報與核對/)
assert.doesNotMatch(history.html, /訂單修改差額尚未結清/)
assert.equal(history.entry, undefined)
assert.equal(render({ amendmentBalance: null }, { data: { items: [] } }).html, '')
