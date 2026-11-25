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
      get: (path, { signal }) => new Promise((resolve, reject) => {
        requests.push({ path, signal, reply: data => resolve({ data }), reject })
      }),
    } },
    '../consoleNavigation': { vehicleGuidePage: { path: 'help/vehicles' } },
    'react-router-dom': { Link: ({ children }) => React.createElement('a', null, children) },
  }
  vm.runInNewContext(code, { AbortController, document, window, exports, require: id => modules[id] ?? require(id) })

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
    render, requests,
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

function findButton(tree, label) {
  if (!React.isValidElement(tree)) return
  if (tree.type === 'button' && tree.props.children === label) return tree
  return React.Children.toArray(tree.props.children).map(child => findButton(child, label)).find(Boolean)
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
  const pending = refresh.requests[3]
  refresh.unmount()
  assert.equal(pending.signal.aborted, true)
  const updates = refresh.updates()
  refresh.focus()
  refresh.visibility('visible')
  assert.equal(refresh.requests.length, 4, 'Unmount should remove both listeners')
  pending.reply(desk(false, []))
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

  console.log('PASS coach vehicle eligibility, retry, focus/visibility refresh and request cleanup')
})().catch(error => { console.error(error); process.exitCode = 1 })
