const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const ts = require('typescript')

const file = 'OperationsHubPage.tsx'
const source = fs.readFileSync(path.join(__dirname, '../src/admin/pages', file), 'utf8')
const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
const panel = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'PayrollPanel')
assert.ok(panel)
const { outputText } = ts.transpileModule(panel.getText(ast) + '\nexports.PayrollPanel = PayrollPanel', {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020 },
})

const statement = {
  id: 12, coach: 6, campus: 7, coach_name: 'QA 教練', campus_name: 'QA 校區',
  period_start: '2026-10-01', period_end: '2026-10-31', status: 'draft',
  total_amount: 900, course_pay: 900, specified_fees: 0, referral_commission: 0,
  assistance_pay: 0, supervisor_allowance: 0, lines: [],
}
const noOp = () => {}
const emptyComponent = () => null
function render(statements) {
  let state = 0
  const context = {
    React, exports: {},
    useQueryClient: noOp, useNotification: noOp,
    useScopedCampuses: () => ({ campuses: [], selectedCampus: '' }),
    useQuery: ({ queryKey }) => ({ data: queryKey[1] === 'payroll' ? statements : [] }),
    fetchPayrollCoaches: noOp, fetchPayrollStatements: noOp,
    payrollMonthRange: () => ({ first: '2026-10-01', last: '2026-10-31' }),
    useState: initial => [state++ === 1 ? statement.id : initial, noOp],
    useRef: () => ({ current: null }), useEffect: noOp, useMutation: () => ({}),
    useMemo: get => get(),
    Field: ({ children }) => children, Empty: ({ text }) => text,
    PayrollSettlementPanel: emptyComponent, PayrollReviewActions: emptyComponent,
    PayrollDocumentPanel: emptyComponent, teachingHours: () => 0,
    cardClass: '', inputClass: '', PRIMARY: '#000',
  }
  vm.runInNewContext(outputText, context)
  return renderToStaticMarkup(React.createElement(context.exports.PayrollPanel))
}

const live = render([statement])
assert.match(live, /共 1 張/)
assert.match(live, /aria-label="薪資明細"/)
assert.match(live, /刪除這張草稿薪資單/)
const archived = render([])
assert.match(archived, /共 0 張/)
assert.match(archived, /尚無薪資單/)
assert.doesNotMatch(archived, /QA 教練|薪資明細|刪除這張草稿薪資單/)
console.log('PASS payroll list closes the selected draft when it disappears from the refreshed results')
