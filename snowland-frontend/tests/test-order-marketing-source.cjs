const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const ts = require('typescript')
const { renderToStaticMarkup } = require('react-dom/server')

let draft, mutation, pending, error
const saved = []
const invalidations = []
const notices = []
const context = vm.createContext({
  React,
  exports: {},
  require(name) {
    if (name === 'react') return { useId: () => 'qa-source', useState: () => [draft, value => { draft = value }] }
    if (name === '@tanstack/react-query') return {
      useMutation: options => {
        mutation = options
        return { isPending: pending, isError: Boolean(error), error, reset: () => { error = undefined } }
      },
      useQueryClient: () => ({ invalidateQueries: ({ queryKey }) => invalidations.push(queryKey.join('/')) }),
    }
    if (name === 'axios') return { isAxiosError: value => Boolean(value?.response) }
    if (name === '../api/orders') return {
      saveOrderMarketingSource: (id, source) => { saved.push([id, source]); return { msg: '客人來源已儲存' } },
    }
    if (name === '../context') return { useNotification: () => ({ success: msg => notices.push(msg) }) }
    throw new Error(`Unexpected import: ${name}`)
  },
})
const component = path.join(__dirname, '../src/admin/components/OrderMarketingSource.tsx')
vm.runInContext(ts.transpileModule(fs.readFileSync(component, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020 },
}).outputText, context)

function find(node, type) {
  if (!React.isValidElement(node)) return undefined
  if (node.type === type) return node
  return React.Children.toArray(node.props.children).map(child => find(child, type)).find(Boolean)
}

const render = props => context.exports.default({ orderId: 42, source: null, ...props })
const options = ['網站廣告', '活動介紹']

async function test() {
  assert.doesNotMatch(renderToStaticMarkup(render({ source: '網站廣告' })), /<select/)
  assert.match(renderToStaticMarkup(render({ source: '網站廣告' })), /網站廣告/)
  let tree = render({ options })
  assert.equal(find(tree, 'label').props.htmlFor, find(tree, 'select').props.id)
  assert.equal(find(tree, 'button').props.disabled, true)
  assert.match(renderToStaticMarkup(tree), /沿用原始來源/)
  find(tree, 'select').props.onChange({ target: { value: '網站廣告' } })
  tree = render({ options })
  assert.equal(find(tree, 'button').props.disabled, false)
  await mutation.onSuccess(await mutation.mutationFn())
  assert.deepEqual(saved, [[42, '網站廣告']])
  assert.deepEqual(invalidations, ['admin/orders', 'admin/dashboard'])
  assert.deepEqual(notices, ['客人來源已儲存'])

  tree = render({ source: '舊選項', options })
  const select = find(tree, 'select')
  const retired = React.Children.toArray(select.props.children).find(option => option.props.value === '舊選項')
  assert.equal(select.props.value, '舊選項')
  assert.equal(retired.props.disabled, true)
  assert.match(renderToStaticMarkup(tree), /舊選項（已停用）/)
  find(tree, 'select').props.onChange({ target: { value: '' } })
  tree = render({ source: '舊選項', options })
  assert.equal(find(tree, 'button').props.disabled, false)
  await mutation.mutationFn()
  assert.deepEqual(saved[1], [42, null])

  pending = true
  tree = render({ source: '舊選項', options })
  assert.equal(find(tree, 'button').props.disabled, true)
  assert.equal(find(tree, 'select').props.disabled, true)
  assert.match(renderToStaticMarkup(tree), /儲存中…/)
  pending = false
  error = { response: { data: { msg: '請從此租戶的客人來源選項選擇' } } }
  tree = render({ source: '舊選項', options })
  assert.match(renderToStaticMarkup(tree), /role="alert"[^>]*>請從此租戶/)
  assert.equal(find(tree, 'select').props.value, '')
}

test().catch(error => { console.error(error); process.exitCode = 1 })
