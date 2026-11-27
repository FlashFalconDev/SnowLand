const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const source = ts.createSourceFile('BookingFlowPage.tsx', fs.readFileSync(
  path.join(__dirname, '../src/pages/BookingFlowPage.tsx'), 'utf8',
), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

const names = new Set([
  'clearAvailableSlots', 'refreshBlockedSlots', 'PaymentInfoResponseError',
  'fetchSubmittedReservationInfo', 'loadPaymentForCreatedOrder',
])
const declarations = []
function visit(node) {
  if (node.name && names.has(node.name.getText(source))) {
    declarations.push(ts.isVariableDeclaration(node) ? `const ${node.getText(source)}` : node.getText(source))
  }
  ts.forEachChild(node, visit)
}
visit(source)
assert.equal(declarations.length, names.size)

const code = ts.transpileModule(`${declarations.join('\n')}\n({clearAvailableSlots, refreshBlockedSlots, loadPaymentForCreatedOrder})`, {
  compilerOptions: { target: ts.ScriptTarget.ES2022 },
}).outputText

async function main() {
  const slot = { template_id: 10, date: '2027-01-20', start_time: '09:00', end_time: '12:00', message_zh: '上午時段已滿' }
  const otherSlot = { ...slot, date: '2027-01-21', message_zh: '隔日上午時段已滿' }
  const otherTemplateSlot = { ...slot, template_id: 11 }
  const availableSession = { start_time: '09:00:00', end_time: '12:00:00', is_full: false }
  const slotFull = { code: 'slot_full', message: slot.message_zh, conflicts: [slot, otherSlot, otherTemplateSlot] }
  let current = slotFull
  let isChecking = false
  let reloads = 0
  const messages = []
  const toasts = []
  let nextResponse
  const { clearAvailableSlots, refreshBlockedSlots, loadPaymentForCreatedOrder } = vm.runInNewContext(code, {
    slotFull, blockedSlots: slotFull.conflicts, clientCode: 'snowland', URLSearchParams,
    setIsCheckingSlots: value => { isChecking = value },
    setSessionReloadKey: update => { reloads = update(reloads) },
    setSlotFull: update => { current = update(current) },
    fetchCourseSessions: async (templateId, date) => {
      if (date === otherSlot.date) throw new Error('Network Error')
      return [{ ...availableSession, is_full: templateId !== slot.template_id }]
    },
    getBackendURL: () => '',
    fetch: async () => nextResponse(),
    setPaymentInfoError: message => messages.push(message),
    showToast: message => toasts.push(message),
  })

  assert.equal(clearAvailableSlots(slotFull, slot.template_id, slot.date, []), slotFull)
  assert.equal(clearAvailableSlots(slotFull, slot.template_id, slot.date, [{ ...availableSession, is_full: true }]), slotFull)
  assert.equal(clearAvailableSlots(slotFull, slot.template_id, slot.date, [{ ...availableSession, is_full: undefined }]), slotFull)
  assert.equal(clearAvailableSlots({ ...slotFull, conflicts: [slot] }, slot.template_id, slot.date, [availableSession]), null)

  const refresh = refreshBlockedSlots()
  assert.equal(isChecking, true)
  await refresh
  assert.equal(isChecking, false)
  assert.equal(reloads, 1)
  assert.equal(current.conflicts.length, 2)
  assert.equal(current.conflicts[0], otherSlot)
  assert.equal(current.conflicts[1], otherTemplateSlot)

  const fallback = '付款資訊暫時無法取得。'
  const backEndMessage = '這個時段剛剛已經額滿，這筆訂單先不收款。'
  for (const [result, expected] of [
    [() => ({ ok: false, json: async () => ({ code: 'slot_full_at_payment', message: backEndMessage }) }), backEndMessage],
    [() => ({ ok: false, json: async () => ({ error: 'Request failed with status code 500' }) }), fallback],
    [() => ({ ok: false, json: async () => { throw new SyntaxError('Unexpected token') } }), fallback],
    [() => { throw new Error('Network Error') }, fallback],
  ]) {
    nextResponse = result
    await loadPaymentForCreatedOrder([42], {})
    assert.equal(messages.at(-1), expected)
    assert.equal(toasts.at(-1), expected === fallback ? '訂單已建立，但付款資訊暫時無法取得' : expected)
  }
}

main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
