const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

const requests = []
const api = {
  get: async (url, options) => {
    requests.push({ url, ...options })
    return { data: { list: [], total: 0 } }
  },
  post: async (url, data) => {
    requests.push({ url, data })
    return { code: 200 }
  },
}
const context = vm.createContext({ exports: {}, require: () => ({ default: api }) })
const source = fs.readFileSync(path.join(__dirname, '../src/admin/api/orders.ts'), 'utf8')
vm.runInContext(ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, context)

function assertTestStatusErrorsRender() {
  const filename = 'OrdersPage.tsx'
  const page = fs.readFileSync(path.join(__dirname, '../src/admin/pages', filename), 'utf8')
  const ast = ts.createSourceFile(filename, page, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const drawer = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'OrderDetailDrawer')
  assert.ok(drawer)
  function find(node, predicate) {
    return predicate(node) ? node : ts.forEachChild(node, child => find(child, predicate))
  }
  const mutation = find(drawer, node => ts.isVariableDeclaration(node) && node.name.getText(ast) === 'testStatusMutation')
  const feedback = find(drawer, node => ts.isJsxExpression(node) && node.expression?.getText(ast).startsWith('testStatusError &&'))
  const overrideButton = find(drawer, node => ts.isJsxExpression(node) && node.expression?.getText(ast).startsWith('order.can_mark_test && testStatusError?.canOverride'))
  assert.ok(mutation)
  assert.ok(feedback)
  assert.ok(overrideButton)
  const ui = vm.createContext({
    React, exports: {}, useMutation: options => options,
    setTestStatusError: value => { ui.testStatusError = value },
    setTestOverrideOpen: () => {},
  })
  vm.runInContext(ts.transpileModule(`
    const ${mutation.getText(ast)}
    exports.onError = testStatusMutation.onError
    exports.render = () => (${feedback.expression.getText(ast)})
    exports.renderOverride = order => (${overrideButton.expression.getText(ast)})
  `, {
    compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, ui)
  function renderError(data, status = 409) {
    ui.exports.onError({ response: { status, data } })
    return renderToStaticMarkup(ui.exports.render())
  }

  const blocked = {
    detail: '此訂單已有帳務紀錄，無法標記為測試訂單。',
    reasons: [
      { code: 'payment_record', label: '付款紀錄', hint: '到「對帳與差額」核對付款。' },
      { code: 'bank_posted_date', label: '入帳日', hint: '到「核對付款」查看入帳日期。' },
    ],
  }
  const html = renderError(blocked)
  assert.match(html, /role="alert".*此訂單已有帳務紀錄/)
  assert.match(html, /<ul[^>]*><li><strong>付款紀錄<\/strong>：到「對帳與差額」核對付款。<\/li><li><strong>入帳日<\/strong>：到「核對付款」查看入帳日期。<\/li><\/ul>/)

  for (const data of [{ detail: '原有錯誤說明' }, { detail: '原有錯誤說明', reasons: [] }]) {
    const fallback = renderError(data)
    assert.match(fallback, /role="alert".*原有錯誤說明/)
    assert.doesNotMatch(fallback, /<ul/)
  }
  assert.match(renderError({ msg: '預付保費分錄' }, 400), /預付保費分錄/)
  for (const [data, status, canMark, visible] of [
    [{ ...blocked, can_override: true }, 409, true, true],
    [{ ...blocked, can_override: false }, 409, true, false],
    [{ ...blocked, can_override: true }, 409, false, false],
    [{ ...blocked, can_override: true }, 403, true, false],
    [{ ...blocked, can_override: true, reasons: [] }, 409, true, false],
  ]) {
    renderError(data, status)
    const button = renderToStaticMarkup(ui.exports.renderOverride({ can_mark_test: canMark }))
    assert.equal(button.includes('覆寫帳務阻擋'), visible)
  }

  const dialog = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'OrderTestOverrideDialog')
  assert.ok(dialog)
  const form = vm.createContext({ React, exports: {}, useAdminDialog: () => ({ current: null }), useState: () => [form.reason, () => {}] })
  vm.runInContext(ts.transpileModule(`${dialog.getText(ast)}\nexports.render = OrderTestOverrideDialog`, {
    compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, form)
  const submissions = []
  const renderDialog = (reasons, reason, busy = false) => {
    form.reason = reason
    const tree = form.exports.render({ reasons, busy, onConfirm: (...args) => submissions.push(args) })
    tree.props.children.props.onSubmit({ preventDefault() {} })
    return renderToStaticMarkup(tree)
  }
  assert.doesNotMatch(renderDialog(blocked.reasons, '  '), /已入帳的那期需由帳務另外處理/)
  for (const item of [
    { code: 'coach_payroll', label: '教練薪資' },
    { code: 'staff_incentive', label: '行政獎金' },
    { code: 'loyalty', label: '紅利' },
  ]) {
    const confirmation = renderDialog([item], '')
    assert.match(confirmation, /role="dialog"/)
    assert.ok(confirmation.includes(`<li>${item.label}</li>`))
    assert.match(confirmation, /已入帳的那期需由帳務另外處理/)
  }
  renderDialog(blocked.reasons, '將練習單排除', true)
  assert.deepEqual(submissions, [])
  renderDialog(blocked.reasons, '  將練習單排除  ')
  assert.equal(JSON.stringify(submissions), JSON.stringify([['將練習單排除', ['payment_record', 'bank_posted_date']]]))
}

async function main() {
  const { fetchOrdersPaged, fetchCampusManagerOrdersPaged, changeOrderTestStatus, exportOrders } = context.exports
  await fetchOrdersPaged()
  await fetchOrdersPaged({ include_test: true })
  await fetchCampusManagerOrdersPaged({ include_test: true, workflow: 'edit' })
  assert.deepEqual(requests.map(request => request.params.include_test), [undefined, '1', '1'])
  assert.equal(requests[2].params.workflow, 'edit')

  await changeOrderTestStatus(42, true, '本機測試')
  await changeOrderTestStatus(42, false, '恢復計入')
  await changeOrderTestStatus(42, true, '覆寫測試', ['payment_record'])
  assert.equal(requests[3].url, '/orders/42/test-status/')
  assert.equal(JSON.stringify(requests.slice(3).map(({ data }) => data)), JSON.stringify([
    { is_test: true, reason: '本機測試' },
    { is_test: false, reason: '恢復計入' },
    { is_test: true, reason: '覆寫測試', acknowledged_reasons: ['payment_record'] },
  ]))

  const exportStart = requests.length
  const dates = { date_basis: 'created', sort: 'asc', start: '2026-11-27', end: '2026-11-27' }
  await exportOrders(dates)
  await exportOrders({ ...dates, include_test: '1' })
  const exportRequests = requests.slice(exportStart)
  assert.equal(exportRequests[0].url, '/orders/export/')
  assert.equal(exportRequests[0].responseType, 'blob')
  assert.deepEqual(exportRequests.map(request => request.params.include_test), [undefined, '1'])

  assertTestStatusErrorsRender()
}

main().catch(error => { console.error(error); process.exitCode = 1 })
