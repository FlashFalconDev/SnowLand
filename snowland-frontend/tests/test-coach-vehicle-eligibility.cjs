const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { join } = require('node:path')
const vm = require('node:vm')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const ts = require('typescript')

const source = readFileSync(join(__dirname, '../src/admin/pages/VehiclePage.tsx'), 'utf8')
const code = ts.transpileModule(source, { compilerOptions: {
  jsx: ts.JsxEmit.ReactJSX,
  module: ts.ModuleKind.CommonJS,
  target: ts.ScriptTarget.ES2020,
} }).outputText

function mount(mode = 'coach') {
  const document = Object.assign(new EventTarget(), { visibilityState: 'visible' })
  const window = new EventTarget()
  const requests = []
  const submissions = []
  const confirmations = []
  window.confirm = message => {
    confirmations.push(message)
    return window.confirmResult
  }
  const states = []
  let stateIndex, stateUpdates = 0, cleanup, nextEffect, dependencies
  const exports = {}
  const modules = {
    react: {
      ...React,
      useState(initial) {
        if (stateIndex === undefined) return React.useState(initial)
        const index = stateIndex++
        if (!(index in states)) states[index] = initial
        return [states[index], value => {
          stateUpdates++
          states[index] = typeof value === 'function' ? value(states[index]) : value
        }]
      },
      useEffect(effect, deps) {
        if (dependencies && deps.every((value, index) => Object.is(value, dependencies[index]))) return
        dependencies = deps
        nextEffect = effect
      },
    },
    '../api/axios': { default: {
      get: (path, { params, signal }) => new Promise((resolve, reject) => {
        requests.push({ path, params, signal, reply: data => resolve({ data }), reject })
      }),
      post: async (path, payload) => { submissions.push({ path, ...payload }) },
    } },
    '../consoleNavigation': { vehicleGuidePage: { path: 'help/vehicles' } },
    'react-router-dom': { Link: ({ children }) => React.createElement('a', null, children) },
  }
  class FormData {
    constructor(fields) { this.fields = fields }
    get(name) { return this.fields[name] }
  }
  vm.runInNewContext(code, { AbortController, FormData, document, window, exports, require: id => modules[id] ?? require(id) })

  function render() {
    stateIndex = 0
    const tree = exports.default({ mode })
    stateIndex = undefined
    if (nextEffect) {
      cleanup?.()
      cleanup = nextEffect()
      nextEffect = undefined
    }
    return tree
  }

  render()
  return {
    render, requests, submissions, confirmations,
    confirm: result => { window.confirmResult = result },
    markup: () => renderToStaticMarkup(render()),
    focus: () => window.dispatchEvent(new Event('focus')),
    visibility(state) {
      document.visibilityState = state
      document.dispatchEvent(new Event('visibilitychange'))
    },
    unmount: () => cleanup?.(),
    updates: () => stateUpdates,
  }
}

function findElement(tree, predicate) {
  if (!React.isValidElement(tree)) return
  if (predicate(tree)) return tree
  return React.Children.toArray(tree.props.children).map(child => findElement(child, predicate)).find(Boolean)
}

function findButton(tree, label) {
  return findElement(tree, element => element.type === 'button' && element.props.children === label)
}

const flush = () => new Promise(setImmediate)
const campus = { id: 1, name: '測試校區' }
const desk = (eligible, campuses) => ({ eligible, campuses, trips: [], resorts: [], coaches: [] })
const missingCampus = /此教練沒有啟用中的所屬校區/
const missingPayRule = /請確認此教練有已啟用、且時薪大於 0 的計薪規則/
const oldHint = /需由校區設定有效的教練薪資規則才能提出借車申請。/
const requestForm = /<h2[^>]*>借車申請<\/h2>/
const loadError = /role="alert"[^>]*>用車操作失敗，請重試。/

;(async () => {
  for (const [data, shown, hidden] of [
    [desk(false, undefined), missingCampus, [missingPayRule, requestForm]],
    [desk(false, []), missingCampus, [missingPayRule, requestForm]],
    [desk(false, [campus]), missingPayRule, [missingCampus, requestForm]],
    [desk(true, [campus]), requestForm, [missingCampus, missingPayRule]],
  ]) {
    const app = mount()
    assert.equal(app.requests[0].path, '/coach/vehicles/')
    app.requests[0].reply(data)
    await flush()
    const markup = app.markup()
    assert.match(markup, shown)
    assert.match(markup, /aria-label="用車紀錄"/)
    for (const pattern of [...hidden, oldHint]) assert.doesNotMatch(markup, pattern)
    app.unmount()
  }

  const retry = mount()
  retry.requests[0].reject(new Error('Network error'))
  await flush()
  assert.match(retry.markup(), loadError)
  const button = findButton(retry.render(), '重新載入')
  assert.ok(button, 'First GET failure should offer retry')
  button.props.onClick()
  assert.doesNotMatch(retry.markup(), loadError)
  assert.equal(retry.requests.length, 2)
  assert.equal(retry.requests[1].path, retry.requests[0].path)
  retry.requests[1].reply(desk(true, [campus]))
  await flush()
  assert.match(retry.markup(), requestForm)
  assert.doesNotMatch(retry.markup(), /重新載入/)
  retry.unmount()

  const refresh = mount()
  refresh.requests[0].reply(desk(false, [campus]))
  await flush()
  assert.match(refresh.markup(), missingPayRule)
  refresh.visibility('hidden')
  assert.equal(refresh.requests.length, 1)
  refresh.visibility('visible')
  assert.equal(refresh.requests.length, 2)
  refresh.focus()
  assert.equal(refresh.requests.length, 3)
  assert.equal(refresh.requests[1].signal.aborted, true)
  refresh.requests[2].reply(desk(true, [campus]))
  await flush()
  assert.match(refresh.markup(), requestForm)
  refresh.requests[1].reply(desk(false, []))
  await flush()
  assert.match(refresh.markup(), requestForm, 'An older response cannot replace the current eligibility')
  assert.doesNotMatch(refresh.markup(), missingCampus)

  refresh.focus()
  const pendingRequest = refresh.requests[3]
  refresh.unmount()
  assert.equal(pendingRequest.signal.aborted, true)
  const updates = refresh.updates()
  refresh.focus()
  refresh.visibility('visible')
  assert.equal(refresh.requests.length, 4, 'Unmount should remove both listeners')
  pendingRequest.reply(desk(false, []))
  await flush()
  assert.equal(refresh.updates(), updates, 'Unmounted page must ignore a pending response')

  for (const mode of ['review', 'finance']) {
    const app = mount(mode)
    assert.equal(app.requests[0].path, '/vehicles/')
    app.requests[0].reject(new Error('Network error'))
    await flush()
    assert.match(app.markup(), loadError)
    assert.doesNotMatch(app.markup(), /重新載入/)
    app.focus()
    app.visibility('visible')
    assert.equal(app.requests.length, 1)
    app.unmount()
  }

  const pending = {
    id: 1, campus: campus.id, purpose: 'lesson', status: 'pending', driver: 'QA 課程教練',
    starts_at: '2026-12-01T09:00:00+09:00', ends_at: '2026-12-01T13:00:00+09:00',
    participants: [], expenses: [], charges: [],
    vehicle_options: [
      { vehicle: 4, occupied_outside_scope: false, conflicts: [{
        trip: 2, purpose: 'private', driver: 'QA 私用駕駛', starts_at: '2026-12-01T08:00:00+09:00',
        ends_at: '2026-12-01T12:00:00+09:00', can_revoke: true,
      }] },
      { vehicle: 5, occupied_outside_scope: false, conflicts: [] },
      { vehicle: 6, occupied_outside_scope: true, conflicts: [] },
      { vehicle: 7, occupied_outside_scope: false, conflicts: [{
        trip: 3, purpose: 'private', driver: 'QA 已出車駕駛', starts_at: '2026-12-01T08:00:00+09:00',
        ends_at: '2026-12-01T12:00:00+09:00', can_revoke: false,
      }] },
    ],
  }
  const reviewDesk = {
    ...desk(true, [campus]), demands: [], conflict_mode: 'manual_review', trips: [pending],
    vehicles: [
      { id: 4, name: 'QA 私用車' }, { id: 5, name: 'QA 備用車' },
      { id: 6, name: 'QA 共用車' }, { id: 7, name: 'QA 行駛中' }, { id: 8, name: 'QA 停用車' },
    ],
  }
  const reviewer = mount('review')
  reviewer.requests[0].reply(reviewDesk)
  await flush()
  const occupied = reviewer.markup()
  assert.match(occupied, /目前衝突模式 <code>manual_review<\/code>/)
  assert.match(occupied, /<option value="5">QA 備用車（可用）<\/option>[\s\S]*<option value="4" disabled="">QA 私用車（已占用 · 私用）/)
  assert.match(occupied, /#2 · 私用 · QA 私用駕駛 · .*8:00.*12:00.*日本時間/)
  assert.match(occupied, /QA 共用車（已占用）/)
  assert.match(occupied, /此時段有其他校區的行程/)
  assert.doesNotMatch(occupied, /QA 停用車/)
  assert.equal((occupied.match(/撤銷此私用/g) || []).length, 1)
  assert.match(occupied, /撤銷原因（必填）.*<textarea[^>]*name="note"[^>]*maxLength="500"[^>]*required=""/)

  const card = findElement(reviewer.render(), element => element.props.trip === pending)
  const assignment = findElement(card.type(card.props), element => element.props.vehicles === reviewDesk.vehicles)
  const revoke = findElement(assignment.type(assignment.props), element => element.props.tripId === 2)
  const revokeMarkup = revoke.type(revoke.props)
  const form = findElement(revokeMarkup, element => element.type === 'form')
  const submit = note => form.props.onSubmit({ preventDefault() {}, currentTarget: { note } })
  submit('  ')
  submit('課'.repeat(501))
  assert.deepEqual(reviewer.confirmations, [])
  assert.deepEqual(reviewer.submissions, [])
  reviewer.confirm(false)
  submit('課程改派')
  assert.match(reviewer.confirmations[0], /私用行程 #2/)
  assert.deepEqual(reviewer.submissions, [])
  reviewer.confirm(true)
  submit(' 課程改派  ')
  await flush()
  reviewer.render()
  assert.deepEqual(reviewer.submissions, [{ path: '/vehicles/', action: 'revoke', trip: 2, note: '課程改派' }])
  assert.equal(reviewer.requests.length, 2)
  reviewer.requests[1].reply({
    ...reviewDesk, conflict_mode: 'block', trips: [{
      ...pending, vehicle_options: [{ vehicle: 4, occupied_outside_scope: false, conflicts: [] }],
    }],
  })
  await flush()
  assert.match(reviewer.markup(), /目前衝突模式 <code>block<\/code>/)
  assert.match(reviewer.markup(), /<option value="4">QA 私用車（可用）/)
  assert.doesNotMatch(reviewer.markup(), /撤銷此私用/)
  reviewer.unmount()

  for (const owner of [true, false]) {
    const app = mount()
    app.requests[0].reply({
      ...desk(true, [campus]),
      trips: [{ ...pending, purpose: 'private', status: 'rejected', revoked: true, owner, decision_note: '課程改派' }],
    })
    await flush()
    const markup = app.markup()
    assert.match(markup, /此私用已被主管撤銷/)
    assert.match(markup, /撤銷原因 課程改派/)
    assert.doesNotMatch(markup, /登記出車|目前衝突模式/)
    app.unmount()
  }

  const coach = mount()
  const vehicle_calendar = {
    from: '2026-11-26', to: '2026-12-09',
    vehicles: [
      { id: 4, name: 'QA 本校車', plate: 'CAL-01', occupancy: [
        { starts_at: '2026-12-01T00:00:00Z', ends_at: '2026-12-01T02:00:00Z', resort: 'QA 富良野' },
        { starts_at: '2026-12-02T01:00:00Z', ends_at: '2026-12-02T03:00:00Z',
          purpose: 'private', driver: 'QA 隱藏駕駛', participants: ['QA 隱藏同行'],
          note: 'QA 隱藏備註', decision_note: 'QA 隱藏原因' },
      ] },
      { id: 5, name: 'QA 共用備用車', plate: 'CAL-02', occupancy: [] },
    ],
  }
  const calendarDesk = { ...desk(false, [campus]), vehicle_calendar }
  coach.requests[0].reply(calendarDesk)
  await flush()
  const calendar = coach.markup()
  assert.match(calendar, /<h2[^>]*>車輛行事曆<\/h2>/)
  assert.match(calendar, /2026-11-26 ～ 2026-12-09（日本時間）/)
  assert.match(calendar, /QA 本校車.*CAL-01.*QA 富良野.*9:00.*11:00/)
  assert.match(calendar, /占用時段.*10:00.*12:00/)
  assert.match(calendar, /QA 共用備用車.*這段期間沒有可顯示的占用/)
  assert.match(calendar, missingPayRule)
  assert.doesNotMatch(calendar, /私用|QA 隱藏/)

  const dateForm = findElement(coach.render(), element => element.type === 'form')
  const dates = { from: '2026-12-01', to: '2026-12-01' }
  dateForm.props.onSubmit({ preventDefault() {}, currentTarget: dates })
  coach.render()
  assert.deepEqual({ ...coach.requests[1].params }, dates)
  coach.requests[1].reply({
    ...calendarDesk, vehicle_calendar: { ...dates, vehicles: [] },
  })
  await flush()
  assert.match(coach.markup(), /2026-12-01 ～ 2026-12-01.*所屬校區目前沒有車輛/)
  assert.doesNotMatch(coach.markup(), /QA 本校車|QA 富良野/)

  coach.focus()
  coach.requests[2].reply({
    ...calendarDesk, vehicle_calendar: null,
    trips: [{ ...pending, status: 'rejected', owner: true, note: 'QA 本人紀錄' }],
  })
  await flush()
  const disabled = coach.markup()
  assert.doesNotMatch(disabled, /車輛行事曆|占用時段|QA 本校車|QA 富良野/)
  assert.match(disabled, /查詢用車紀錄.*QA 本人紀錄/)
  coach.unmount()

  console.log('PASS vehicle eligibility, refresh, conflict options, revocation, personal reason and coach calendar')
})().catch(error => { console.error(error); process.exitCode = 1 })
