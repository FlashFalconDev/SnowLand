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
const issue = (code, level, message) => ({
  row_number: 3, group_key: 'EXT-1', level, code, message_zh: message, columns: ['指定教練'],
})
const preview = {
  batch_id: 17, status: 'previewed',
  summary: { orders: 1, lessons: 2, amount: 3000, errors: 1, full: 1, closed: 1, skipped_examples: 2, committable: 1 },
  row_results: [
    issue('coach_conflict', 'error', '教練已佔用'), issue('full', 'warning', '本堂會超賣'),
    issue('closed', 'warning', '本堂已停收'), issue('repeated_lesson_amount', 'warning', '請確認各堂分攤'),
  ],
  order_results: [
    { row_number: 3, group_key: 'EXT-1', amount: 3000, member: issue('existing_member', 'ok', '綁定既有會員') },
    { row_number: 4, group_key: 'EXT-2', amount: 1200 },
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
  assert.equal(button(tree, '確認匯入已購訂單').props.disabled, true)
  const [confirm, allow] = nodes(tree, node => node.type === 'input' && node.props.type === 'checkbox')
  confirm.props.onChange({ target: { checked: true } })
  assert.equal(button(page(), '確認匯入已購訂單').props.disabled, false)
  allow.props.onChange({ target: { checked: true } })
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
    '綁定既有會員', '已跳過 2 列範例', '指定教練', '教練已佔用', '本堂已停收', '請核對',
    '本單各堂加總＝$3,000', '本單各堂加總＝$1,200',
  ]) {
    assert.ok(all.includes(value), value)
  }
  button(detail(), '已滿堂').props.onClick()
  assert.match(renderToStaticMarkup(detail()), /本堂會超賣/)
  assert.doesNotMatch(renderToStaticMarkup(detail()), /教練已佔用/)
  button(detail(), '有問題').props.onClick()
  assert.match(renderToStaticMarkup(detail()), /教練已佔用/)
}

verify().catch(error => { console.error(error); process.exitCode = 1 })
