const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const ts = require('typescript')
const { renderToStaticMarkup } = require('react-dom/server')

const source = fs.readFileSync(path.join(__dirname, '../src/admin/pages/OrdersPage.tsx'), 'utf8')
const ast = ts.createSourceFile('OrdersPage.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
const drawer = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'OrderDetailDrawer')
const ctx = vm.createContext({ React, exports: {}, Save: () => null, Zap: () => null, Loader2: () => null, PRIMARY: '#8b5cf6' })

function find(root, predicate) {
  return predicate(root) ? root : ts.forEachChild(root, node => find(node, predicate))
}

function declaration(root, name) {
  return find(root, node => ts.isVariableDeclaration(node) && node.name.getText(ast) === name)
}

function run(code) {
  vm.runInContext(ts.transpileModule(code, {
    compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, ctx)
}

const dateField = find(drawer, node => ts.isConditionalExpression(node) && node.condition.getText(ast) === 'canEnterPostingDate')
const dateError = find(drawer, node => ts.isIfStatement(node) && node.expression.getText(ast).includes('!bankPostedDate'))
const saveButton = find(drawer, node => ts.isJsxElement(node) && node.openingElement.tagName.getText(ast) === 'button'
  && node.children.some(child => ts.isJsxText(child) && child.text.includes('只儲存')))
const scheduleButton = find(drawer, node => ts.isJsxElement(node) && node.openingElement.tagName.getText(ast) === 'button'
  && node.children.some(child => ts.isJsxText(child) && child.text.includes('儲存並 AI 排課')))
const updateCall = find(drawer, node => ts.isCallExpression(node) && node.expression.getText(ast) === 'updateOrder')

run(`exports.taipeiDate = ${declaration(ast, 'taipeiDate').initializer.getText(ast)}`)
assert.equal(ctx.exports.taipeiDate.format(new Date('2026-01-01T16:00:00Z')), '2026-01-02')

function render(mode, draft, { saved = null, status = 'paid', editing = true, previous = 'pending', hasCoachChanges = false } = {}) {
  Object.assign(ctx, {
    order: { payment_status: previous, bank_posted_date: saved, manual_payment_posting_date_mode: mode },
    bankPostedDate: draft, paymentStatus: status, editing, canReconcile: true, sharedPaymentHeld: false,
    todayInTaipei: '2026-01-02', saveMutation: { isPending: false }, setBankPostedDate() {},
    hasBookingChanges: false, hasCoachChanges, invalidBooking: false, canScheduleUnassigned: false,
    requiresJpyReceipt: false, jpyReceiptConfirmed: false, action: 'save', updates: [], bookingUpdates: [],
  })
  run(`{
    ${['postingDateMode', 'canEnterPostingDate', 'postingDateChanged', 'hasPaymentChanges', 'postingDateRequired', 'hasOrderChanges'].map(name =>
      `const ${declaration(drawer, name).getText(ast)}`).join('\n')}
    let postingDateError = ''
    ${dateError.getText(ast)}
    exports.field = (${dateField.getText(ast)})
    exports.save = (${saveButton.getText(ast)})
    exports.schedule = (${scheduleButton.getText(ast)})
    exports.payload = (${updateCall.arguments[1].getText(ast)})
  }`)
  const { field, save, schedule, payload } = ctx.exports
  return { html: renderToStaticMarkup(field), save, schedule, payload }
}

let result = render('optional', '')
assert.match(result.html, /type="date"/)
assert.match(result.html, /max="2026-01-02"/)
assert.match(result.html, /銀行紀錄上的實際入帳日/)
assert.equal(result.save.props.disabled, false)
assert.equal(result.payload.bank_posted_date, undefined)

result = render('required', '')
assert.match(result.html, /role="alert"[^>]*>核對為已付款時，請填寫入帳日期/)
assert.match(result.html, /required=""/)
assert.equal(result.save.props.disabled, true)
assert.equal(render('optional', '2026-01-03').save.props.disabled, true)

result = render('required', '', { previous: 'paid', hasCoachChanges: true })
assert.equal(result.save.props.disabled, false, '舊已付款單只改教練時可儲存')
assert.equal(result.schedule.props.disabled, false)
assert.doesNotMatch(result.html, /role="alert"|required=""/)
assert.equal(result.payload.payment_status, undefined)
assert.equal(result.payload.bank_posted_date, undefined)

result = render('required', '2026-01-02', { previous: 'paid' })
assert.equal(result.save.props.disabled, false)
assert.equal(result.payload.payment_status, 'paid')
assert.equal(result.payload.bank_posted_date, '2026-01-02')

result = render('disabled', '2026-01-02', { saved: '2025-12-31' })
assert.doesNotMatch(result.html, /<input/)
assert.match(result.html, /入帳日期.*2025-12-31/)
assert.equal(result.save.props.disabled, false)
assert.equal(result.payload.bank_posted_date, undefined)
assert.doesNotMatch(render('optional', '', { status: 'pending' }).html, /<input/)
assert.match(render('optional', '', { editing: false, saved: '2025-12-31' }).html, /入帳日期.*2025-12-31/)
console.log('PASS 訂單明細的入帳日期、台北日期限制、必填提示與舊單補登')
