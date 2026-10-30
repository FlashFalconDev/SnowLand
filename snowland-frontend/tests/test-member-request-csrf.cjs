const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

// Exercise the actual fetch helper without compiling JSX or sending a network request.
const source = fs.readFileSync(path.join(__dirname, '../src/pages/site/MembershipPage.jsx'), 'utf8')
const start = source.indexOf('async function requestJson(')
const end = source.indexOf('\nfunction EmptyState(', start)
assert.ok(start >= 0 && end > start)
const calls = []
let response = { ok: true, status: 200, json: async () => ({ result: 'ok' }) }
const context = vm.createContext({ schoolBookingApiPath:path=>'/booking/snowland/api'+path, Headers, document: { cookie: 'other=x; csrftoken=QA-only-CSRF' },
  fetch: async (...args) => { calls.push(args); return response } })
vm.runInContext(source.slice(start, end), context)

async function main() {
  await context.requestJson('/local', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
  assert.equal(calls.at(-1)[1].headers.get('X-CSRFToken'), 'QA-only-CSRF')
  assert.equal(calls.at(-1)[1].headers.get('Content-Type'), 'application/json')
  assert.equal(calls.at(-1)[1].credentials, 'include')
  await context.requestJson('/local')
  assert.equal(calls.at(-1)[1].headers.get('X-CSRFToken'), null)
  context.document.cookie = 'other=x'
  await context.requestJson('/local', { method: 'DELETE' })
  assert.equal(calls.at(-1)[1].headers.get('X-CSRFToken'), null)
  response = { ok: false, status: 403, json: async () => ({ detail: 'CSRF Failed: CSRF token missing.' }) }
  await assert.rejects(() => context.requestJson('/local', { method: 'POST' }), error =>
    error.status === 403 && error.message.includes('本次操作未送出'))
  response = { ok: false, status: 400, json: async () => ({ error: '請填寫退款銀行' }) }
  await assert.rejects(() => context.requestJson('/local'), error => error.message === '請填寫退款銀行')
  console.log('PASS member request: CSRF/header preservation, credentials, safe methods, missing token, Chinese errors')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
