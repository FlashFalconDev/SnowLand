const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const ts = require('typescript')

let states = []
let cursor = 0
let previewCalls = []
let commitCalls = []
const fakeFile = { name: 'orders.xlsx', size: 100 }
const issue = (code, level, message, row = 3, first = row, columns = ['指定教練']) => ({
  row_number: row, order_row_number: first, group_key: `EXT-${first}`, level, code, message_zh: message, columns,
})
const pendingCoach = issue('coach_pending', 'warning', '教練欄填了付款方式，已忽略。這堂會先建單、教練待排，請由行政補排。', 5, 3)
const coachConflict = issue('coach_conflict', 'error', '教練已佔用，請換一位教練或留空後重傳。', 6)
const full = issue('full', 'warning', '本堂會超賣，訂單預設跳過。', 7, 7, ['開始時間'])
const underpaid = issue('order_price_gap', 'warning', '待補款 500 元，匯入後請到後台結清。', 3, 3, ['已收款金額'])
const overpaid = issue('order_price_gap', 'warning', '待退款 200 元，匯入後請到後台結清。', 7, 7, ['已收款金額'])
const preview = {
  batch_id: 17, status: 'previewed',
  summary: {
    orders: 3, lessons: 4, amount: 3000, errors: 1, full: 1, closed: 1, skipped_examples: 2,
    committable: 1, warning_orders: 2, blocked_orders: 1, skipped_full: 1, already_imported: 0, full_amount: 1200,
  },
  row_results: [
    issue('closed', 'warning', '本堂已停收'), pendingCoach, coachConflict, full, underpaid, overpaid,
  ],
  order_results: [
    {
      row_number: 3, group_key: 'EXT-3', status: 'ready', amount: 3000, reported_amount: 3000, amount_difference: 0,
      price_gap: { expected_amount: 3500, balance_amount: 500 },
      lesson_amounts: [{ row_number: 3, amount: 1000 }, { row_number: 5, amount: 2000 }],
      member: issue('existing_member', 'ok', '綁定既有會員'),
    },
    { row_number: 6, group_key: 'EXT-6', status: 'error', amount: 1600, reported_amount: 1400, amount_difference: 200 },
    { row_number: 7, group_key: 'EXT-7', status: 'full', amount: 1200, reported_amount: 1200,
      price_gap: { expected_amount: 1000, balance_amount: -200 } },
  ],
}
const result = {
  ...preview, status: 'partial', summary: { ...preview.summary, created: 1, skipped: 0, failed: 1 },
  commit_results: [
    { row_number: 3, group_key: 'EXT-1', status: 'created', order_id: 9, order_number: 'SN-9', overbooked: true, issues: [] },
    { row_number: 4, group_key: 'EXT-2', status: 'failed', issues: [issue('coach_conflict', 'error', '教練已佔用')] },
  ],
}
const fakeApi = {
  async previewOrderImport(file) { previewCalls.push(file); return preview },
  async commitOrderImport(...args) { commitCalls.push(args); return result },
}
const context = vm.createContext({
  React, exports: {}, Intl, URL, setTimeout,
  require(name) {
    if (name === 'react') return {
      useState(initial) {
        const index = cursor++
        if (!(index in states)) states[index] = initial
        return [states[index], value => { states[index] = value }]
      },
    }
    if (name === 'react-router-dom') return { Link: ({ to, ...props }) => React.createElement('a', { href: to, ...props }) }
    if (name === 'lucide-react') return { CheckCircle2: () => null, Download: () => null, Upload: () => null }
    if (name === '@/utils/tenant') return { currentClientCode: () => 'test-school' }
    if (name === '../api/orderImport') return fakeApi
    throw new Error(name)
  },
})
function transpile(file) {
  return ts.transpileModule(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
}
vm.runInContext(transpile('src/admin/pages/OrderImportPage.tsx') + '\nexports.PreviewDetails = PreviewDetails', context)

function nodes(element, predicate) {
  if (Array.isArray(element)) return element.flatMap(node => nodes(node, predicate))
  if (!React.isValidElement(element)) return []
  return [
    ...(predicate(element) ? [element] : []),
    ...nodes(element.props.children, predicate),
  ]
}

function page() {
  cursor = 0
  return context.exports.default()
}

function button(element, phrase) {
  return nodes(element, node => node.type === 'button' && String(node.props.children).includes(phrase))[0]
}

async function verify() {
  let tree = page()
  const instructions = renderToStaticMarkup(nodes(tree, node => node.type === 'section')[0])
  assert.match(instructions, /從最後一列範例的下一列開始填/)
  assert.match(instructions, /同單攝影另填一列，沿用主課單號，堂次備註整格只寫「隨單加購」，排課資料和金額留空/)
  assert.equal(button(tree, '上傳並預覽').props.disabled, true)
  const fileInput = nodes(tree, node => node.type === 'input' && node.props.type === 'file')[0]
  fileInput.props.onChange({ target: { files: [fakeFile] } })
  tree = page()
  assert.equal(button(tree, '上傳並預覽').props.disabled, false)
  nodes(tree, node => node.type === 'form')[0].props.onSubmit({ preventDefault() {} })
  assert.equal(button(page(), '驗證中').props.disabled, true)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(previewCalls, [fakeFile])

  tree = page()
  assert.match(renderToStaticMarkup(tree), /預計處理 1 張，實收 \$3,000/)
  assert.equal(button(tree, '確認匯入已購訂單').props.disabled, true)
  const [confirm, allow] = nodes(tree, node => node.type === 'input' && node.props.type === 'checkbox')
  confirm.props.onChange({ target: { checked: true } })
  assert.equal(button(page(), '確認匯入已購訂單').props.disabled, false)
  allow.props.onChange({ target: { checked: true } })
  assert.match(renderToStaticMarkup(page()), /預計處理 2 張，實收 \$4,200/)
  assert.equal(button(page(), '確認匯入已購訂單').props.disabled, true)
  nodes(page(), node => node.type === 'textarea')[0].props.onChange({ target: { value: ' 紙本已收款 ' } })
  await button(page(), '確認匯入已購訂單').props.onClick()
  assert.deepEqual(commitCalls, [[17, true, '紙本已收款']])
  const finalHtml = renderToStaticMarkup(page())
  assert.match(finalHtml, /成功 1 張，跳過 0 張，失敗 1 張/)
  assert.match(finalHtml, /\/test-school\/console\/orders\/edit\?order_id=9/)
  assert.match(finalHtml, /\/test-school\/membership/)
  assert.match(finalHtml, /已記錄超賣匯入/)

  states = []
  cursor = 0
  const detail = () => { cursor = 0; return context.exports.PreviewDetails({ batch: preview }) }
  const all = renderToStaticMarkup(detail())
  for (const value of [
    '綁定既有會員', '已跳過 2 列範例', '指定教練', '教練已佔用', '本堂已停收', '教練待排',
    '可匯入（請核對）', '請改檔後重傳', '滿堂預設跳過', '處理結果與下一步', '預設可建單', '有警告',
    '本單各堂加總＝$3,000', '本單各堂加總＝$1,200', '首列已收款＝$1,400', '收款核對差額 $200', '第 5 列 $2,000',
    '應收 $3,500 · 實收 $3,000 · 待補款 $500', '應收 $1,000 · 實收 $1,200 · 待退款 $200',
    underpaid.message_zh, overpaid.message_zh,
  ]) {
    assert.ok(all.includes(value), value)
  }
  button(detail(), '滿堂預設跳過').props.onClick()
  assert.match(renderToStaticMarkup(detail()), /本堂會超賣/)
  assert.doesNotMatch(renderToStaticMarkup(detail()), /教練已佔用/)
  button(detail(), '請改檔後重傳').props.onClick()
  assert.match(renderToStaticMarkup(detail()), /教練已佔用/)
  assert.doesNotMatch(renderToStaticMarkup(detail()), /教練待排/)
  button(detail(), '可匯入（請核對）').props.onClick()
  assert.match(renderToStaticMarkup(detail()), /教練待排/)
  assert.doesNotMatch(renderToStaticMarkup(detail()), /教練已佔用/)

  states = []
  page()
  states[0] = fakeFile
  states[1] = { ...preview, summary: { ...preview.summary, committable: 0, amount: 0 } }
  tree = page()
  nodes(tree, node => node.type === 'input' && node.props.type === 'checkbox')[0].props.onChange({ target: { checked: true } })
  assert.equal(button(page(), '確認匯入已購訂單').props.disabled, true)
  assert.match(renderToStaticMarkup(page()), /預計處理 0 張/)
}

verify().catch(error => { console.error(error); process.exitCode = 1 })
