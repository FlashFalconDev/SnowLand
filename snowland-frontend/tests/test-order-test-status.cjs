const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

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

async function main() {
  const { fetchOrdersPaged, fetchCampusManagerOrdersPaged, changeOrderTestStatus, exportOrders } = context.exports
  await fetchOrdersPaged()
  await fetchOrdersPaged({ include_test: true })
  await fetchCampusManagerOrdersPaged({ include_test: true, workflow: 'edit' })
  assert.deepEqual(requests.map(request => request.params.include_test), [undefined, '1', '1'])
  assert.equal(requests[2].params.workflow, 'edit')

  await changeOrderTestStatus(42, true, '本機測試')
  await changeOrderTestStatus(42, false, '恢復計入')
  assert.equal(requests[3].url, '/orders/42/test-status/')
  assert.deepEqual(requests.slice(3).map(({ data }) => [data.is_test, data.reason]), [[true, '本機測試'], [false, '恢復計入']])

  const exportStart = requests.length
  const dates = { date_basis: 'created', sort: 'asc', start: '2026-11-27', end: '2026-11-27' }
  await exportOrders(dates)
  await exportOrders({ ...dates, include_test: '1' })
  const exportRequests = requests.slice(exportStart)
  assert.equal(exportRequests[0].url, '/orders/export/')
  assert.equal(exportRequests[0].responseType, 'blob')
  assert.deepEqual(exportRequests.map(request => request.params.include_test), [undefined, '1'])
}

main().catch(error => { console.error(error); process.exitCode = 1 })
