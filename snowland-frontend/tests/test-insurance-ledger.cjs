const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const ts = require('typescript')
const { renderToStaticMarkup } = require('react-dom/server')

const root = path.resolve(__dirname, '../src/admin')
const read = file => fs.readFileSync(path.join(root, file), 'utf8')
const compile = source => ts.transpileModule(source, {
  fileName: 'ledger.tsx',
  compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText

const entry = {
  id: 11, sequence: 2, kind: 'deduction', amount: '-25.00', balance_after: '75.00',
  actor: 'QA 財務', reference: 'QA 憑證', note: '', member_id: 3, order_id: 6, reverses_id: null, reversed: false,
  created_at: '2025-03-25T12:00:00+08:00',
}
const snapshot = {
  month: '2025-03', opening: '100.00', top_ups: '0.00', deductions: '25.00', reversals: '0.00', closing: '75.00',
  cutoff_sequence: 2, confirmed_at: null, confirmed_by: null,
}

function load({ ledger = {}, campus = 'all', states, month = snapshot } = {}) {
  let mutation
  const calls = []
  const queryOptions = []
  const useQuery = options => {
    queryOptions.push(options)
    return { data: options.queryKey.includes('insurance-reconciliation') ? month : {
      enabled: true, writable: true, currency: 'JPY', balance: '75.00', low_balance: true,
      entries: [entry], page: 1, pages: 3, can_confirm_month: true, ...ledger,
    } }
  }
  const module = { exports: {} }
  let index = 0
  const useState = states ? initial => [states[index++] ?? initial, () => {}] : React.useState
  const context = {
    React, module, exports: module.exports, Date, Intl, window: { localStorage: { getItem: () => campus } },
    require: name => ({
      react: { useState },
      '@tanstack/react-query': {
        useQuery,
        useQueryClient: () => ({ invalidateQueries() {} }),
        useMutation: options => { mutation = options; return { isPending: false, mutate: (...args) => options.mutationFn(...args) } },
      },
      '@/utils/tenant': { currentClientCode: () => 'ledger-qa', campusScopeKey: value => value },
      '../api/insuranceLedger': {
        fetchInsuranceLedger: (...args) => { calls.push(args) }, fetchInsuranceReconciliation() {},
        depositInsuranceFunds: data => { calls.push(data) }, reverseInsuranceEntry() {},
        confirmInsuranceReconciliation: data => { calls.push(data) },
      },
      './useInsuranceRequestKey': { useInsuranceRequestKey: () => ({ forPayload: () => 'qa-uuid', reset() {} }) },
    })[name],
  }
  vm.runInNewContext(compile(read('components/InsuranceLedgerPanel.tsx') + '\nexport { DepositForm, ReconciliationPanel }'), context)
  return { components: module.exports, calls, queryOptions, mutation: () => mutation }
}

const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props))
const active = load()
const activeHtml = render(active.components.default)
assert.match(activeHtml, /目前餘額.*JPY 75\.00/)
assert.match(activeHtml, /低餘額門檻/)
assert.match(activeHtml, /確認儲值/)
assert.match(activeHtml, /帳務月份.*type="month"/)
assert.match(activeHtml, /QA 憑證.*沖正 #2/)
assert.match(activeHtml, /第 1／3 頁/)
active.queryOptions[0].queryFn()
assert.match(active.calls[0][0], /^\d{4}-\d{2}$/)
assert.equal(active.calls[0][1], 1)

const readonly = load({ ledger: { enabled: false, writable: false, low_balance: false, can_confirm_month: false } })
const readonlyHtml = render(readonly.components.default)
assert.match(readonlyHtml, /目前僅供查閱/)
assert.match(readonlyHtml, /帳本明細/)
assert.doesNotMatch(readonlyHtml, /確認儲值|沖正 #|低餘額門檻/)
const campus = load({ campus: '12' })
assert.match(render(campus.components.default), /切換至「全部校區」/)
assert.equal(campus.queryOptions[0].enabled, false)

for (const opening of [true, false]) {
  const { components, calls } = load({ states: ['12.50', ' QA-憑證 ', ' 核對 ', false] })
  const form = components.DepositForm({ opening, currency: 'JPY', onSaved() {} })
  assert.match(renderToStaticMarkup(form), opening ? /確認期初入帳/ : /確認儲值/)
  form.props.onSubmit({ preventDefault() {} })
  assert.equal(calls.length, 1)
  assert.equal(calls[0].kind, opening ? 'opening' : 'top_up')
  assert.equal(calls[0].amount, '12.50')
  assert.equal(calls[0].reference, 'QA-憑證')
  assert.equal(calls[0].idempotency_key, 'qa-uuid')
}

const close = load({ states: [true, '75.00', '已核對'] })
const closingProps = { tenant: 'ledger-qa', month: '2025-03', currency: 'JPY', canConfirm: true, onSaved() {} }
assert.match(render(close.components.ReconciliationPanel, closingProps), /JPY 75\.00.*確認月對帳/)
close.mutation().mutationFn(2)
assert.equal(close.calls[0].statement_balance, '75.00')
assert.equal(close.calls[0].cutoff_sequence, 2)
const confirmed = load({ month: { ...snapshot, confirmed_at: entry.created_at, confirmed_by: 'QA 財務' } })
assert.doesNotMatch(render(confirmed.components.ReconciliationPanel, closingProps), /確認月對帳/)

const permissions = { exports: {} }
vm.runInNewContext(compile(read('permissions.ts')), { exports: permissions.exports })
const canFinance = permissions.exports.hasAdminPermission
const hq = { is_manager: true, role: 'hq_admin', can_view_all_campuses: true }
const grant = { ...hq, permissions: ['insurance_ledger_finance'] }
assert.equal(canFinance(hq, 'insurance_ledger_finance'), false)
assert.equal(canFinance({ ...hq, is_superuser: true }, 'insurance_ledger_finance'), false)
assert.equal(canFinance({ ...grant, role: 'insurance' }, 'insurance_ledger_finance'), false)
assert.equal(canFinance({ ...grant, can_view_all_campuses: false }, 'insurance_ledger_finance'), false)
assert.equal(canFinance(grant, 'insurance_ledger_finance'), true)
assert.match(read('consoleNavigation.ts'), /path: 'insurance\/ledger'.*access: 'insurance_ledger_finance'/)
assert.match(read('AdminRoutes.tsx'), /<RoleGuard page=\{page\}/)
console.log('PASS actual insurance ledger components: deposit payload, scoped ledger and month filter, low balance, read-only and reconciliation controls')
