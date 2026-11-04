const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const root = path.resolve(__dirname, '..')
const source = fs.readFileSync(path.join(root, 'src/pages/BookingFlowPage.tsx'), 'utf8')
const tree = ts.createSourceFile('booking.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
let submit
function find(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(tree) === 'submitPayment') submit = node.initializer.getText(tree)
  ts.forEachChild(node, find)
}
find(tree)
assert.ok(submit)

const axiosSource = fs.readFileSync(path.join(root, 'src/api/axios.ts'), 'utf8')
const compiled = ts.transpileModule(axiosSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText

async function run() {
  const requests = []
  let intercept
  const api = {
    interceptors: { request: { use: fn => { intercept = fn } }, response: { use() {} } },
    async post(url, data) {
      requests.push(intercept({ url, data, headers: {}, baseURL: '/booking/api' }))
    },
  }
  const axios = {
    exports: {}, document: { cookie: 'csrftoken=synthetic-test-csrf' },
    require: name => name === 'axios' ? { default: { create: () => api } }
      : { currentClientCode: () => 'snowland' },
  }
  vm.runInNewContext(compiled, axios)
  let step
  const handler = ts.transpileModule(`(${submit})()`, { compilerOptions: { target: ts.ScriptTarget.ES2020 } }).outputText
  await vm.runInNewContext(handler, {
    submittedReservation: {
      reservation_group_ids: [7, 8],
      payment_methods: ['bank_transfer'],
      payment_infos: [{ reservation_group_id: 7, settlement: { currency: 'JPY', amount: 450 } }],
      payment_access_tokens: { 7: 'synthetic-token' },
    },
    paymentMethod: 'bank', senderAccount: '00000',
    bookingApi: axios.exports.default, setCurrentStep: value => { step = value },
    setIsSubmitting() {}, setLoadingMessage() {}, showToast() {},
    setCompletionNotice() {}, setCompletionFlow() {},
  })
  assert.equal(step, 4)
  assert.equal(requests.length, 2)
  for (const request of requests) {
    assert.equal(request.baseURL + request.url, '/booking/snowland/api/process-payment/')
    assert.equal(request.headers['X-CSRFToken'], 'synthetic-test-csrf')
    assert.equal(request.data.sender_account, '00000')
  }
  assert.equal(requests[0].data.expected_amount, 450)
  assert.equal(requests[1].data.currency, 'TWD')
}

run().catch(error => {
  console.error(error)
  process.exitCode = 1
})
