const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const vm = require('node:vm')
const root = path.resolve(__dirname, '../snowland-frontend')
const localRequire = Module.createRequire(path.join(root, 'package.json'))
const React = localRequire('react')
const ts = localRequire('typescript')
const { renderToStaticMarkup } = localRequire('react-dom/server')
const source = fs.readFileSync(path.join(root, 'src/admin/pages/DashboardPage.tsx'), 'utf8')
const compiled = ts.transpileModule(source, { fileName: 'dashboard.tsx', compilerOptions: {
  jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText
const data = {
  stats: { orders: 1, completed_orders: 1, revenue: 3000, avg_order_value: 3000, members: 0, student_visits: 3, teaching_hours: 3 },
  resort_options: [{ id: 39, display_name: '測試雪場' }], top_items: [], recent_orders: [],
  payment_statuses: [{ status: 'paid', name: '已付款', orders: 1 }],
  marketing_sources: [{name:'上次期間來源',orders:1,revenue:3000}], campus_summary: [{name:'上次期間校區',orders:1,revenue:3000}],
}
function render({ states = ['quarter', 'completed', '', '', '39', false, ''], fetching = false, failExport = false } = {}) {
  let index = 0, query
  const calls = [], links = [], messages = []
  const context = vm.createContext({ React, console, Date, Number, exports: {},
    URL: { createObjectURL: () => 'blob:qa-only', revokeObjectURL: () => {} }, setTimeout: fn => fn(),
    document: { createElement: () => { const link = { click() { links.push({ name: this.download, href: this.href }) } }; return link } },
    require: name => {
      if (name === 'react') return { ...React, useState: initial => {
        const n = index++
        return [n < states.length ? states[n] : initial, value => { if (n === 6) messages.push(value) }]
      } }
      if (name === '@tanstack/react-query') return { keepPreviousData: value => value,
        useQuery: options => { query = options; return { data, isFetching: fetching, error: null } } }
      if (name === 'lucide-react') return new Proxy({}, { get: () => () => null })
      if (name === '../api/dashboard') return {
        fetchDashboard: async (...args) => { calls.push(['fetch', ...args]); return data },
        exportDashboard: async (...args) => { calls.push(['export', ...args]); if (failExport) throw Error('QA network failure'); return {} },
      }
      throw Error('Unexpected dependency: ' + name)
    },
  })
  vm.runInContext(compiled, context)
  const tree = context.exports.default()
  const buttons = []
  function walk(node) {
    if (!React.isValidElement(node)) return
    if (node.type === 'button') buttons.push(node)
    React.Children.forEach(node.props.children, walk)
  }
  walk(tree)
  return { html: renderToStaticMarkup(tree), query, calls, links, messages,
    excel: buttons.find(button => button.props.children === '匯出 Excel'),
    csv: buttons.find(button => button.props.children === '匯出 CSV') }
}
async function main() {
  const ready = render()
  assert.match(ready.html, /已完成學員人次（每堂）/)
  assert.match(ready.html, /非計薪時數/)
  assert.match(ready.html, /付款狀態分布/)
  assert.equal(ready.excel.props.disabled, false)
  await ready.query.queryFn()
  await ready.excel.props.onClick()
  assert.equal(ready.calls[0][2].resort_id, '39')
  assert.equal(ready.calls[1][1], 'quarter')
  assert.equal(ready.calls[1][2].date_basis, 'completed')
  assert.equal(ready.calls[1][2].resort_id, '39')
  assert.equal(ready.calls[1][3], 'xlsx')
  assert.equal(ready.links[0].name, 'SnowLand-completed-quarter.xlsx')
  assert.match(ready.messages.at(-1), /已產生並開始下載/)
  await ready.csv.props.onClick()
  assert.equal(ready.calls.at(-1)[3], 'csv')
  for (const pending of [render({ fetching: true }), render({ states: ['custom','created','2026-10-18','2026-10-17','39',false,''] }),
    render({ states: ['month','created','','','39',true,''] })]) {
    assert.equal(pending.excel.props.disabled, true)
    await pending.excel.props.onClick()
    assert.equal(pending.calls.length, 0)
  }
  const invalid = render({ states: ['custom','created','','','',false,''] })
  assert.equal(invalid.query.enabled, false)
  assert.match(invalid.html, /請選擇開始與結束日期/)
  assert.doesNotMatch(invalid.html, /上次期間來源|上次期間校區/)
  const failed = render({ failExport: true })
  await failed.excel.props.onClick()
  assert.match(failed.messages.at(-1), /匯出失敗/)
  assert.equal(failed.links.length, 0)
  console.log('PASS actual DashboardPage: summary labels, scoped filter payload, CSV/Excel handlers, loading/duplicate/invalid guards and failure feedback')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
