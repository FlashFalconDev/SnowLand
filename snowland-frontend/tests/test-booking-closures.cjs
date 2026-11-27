const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const ts = require('typescript')
const { renderToStaticMarkup } = require('react-dom/server')

const read = file => fs.readFileSync(path.join(__dirname, '../src', file), 'utf8')
const compile = source => ts.transpileModule(source, {
  compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText

async function testConsole() {
  const state = []
  const requests = []
  const invalidated = []
  let cursor = 0
  let rows = []
  const options = {
    enabled: false,
    can_manage_templates: true,
    resorts: [{ id: 10, name: '測試雪場' }],
    templates: [{
      id: 20, name: '私人半日', resorts: [10], can_close_all_resorts: true,
      sessions: [{ id: 30, start_time: '09:00:00', end_time: '13:00:00' }],
    }],
  }
  const api = {
    fetchBookingClosures() {},
    fetchBookingClosureOptions() {},
    async createBookingClosure(input) {
      requests.push(input)
      rows = [{ id: 40, resort_name: '測試雪場', template_name: '私人半日', ...input }]
      return { msg: '停收規則已新增', warning: '此範圍已被既有停收規則涵蓋，仍已新增。' }
    },
    async deleteBookingClosure(id) {
      requests.push(id)
      rows = []
    },
  }
  const context = vm.createContext({
    React, exports: {}, window: { confirm: () => true },
    require(name) {
      if (name === '../api/bookingClosures') return api
      if (name === 'react') return {
        useState(initial) {
          const index = cursor++
          if (!(index in state)) state[index] = initial
          return [state[index], value => { state[index] = value }]
        },
      }
      if (name === '@tanstack/react-query') return {
        useQuery: ({ queryFn }) => ({ data: queryFn === api.fetchBookingClosures ? rows : options }),
        useQueryClient: () => ({ invalidateQueries: async filters => { invalidated.push(filters) } }),
        useMutation: ({ mutationFn, onSuccess }) => ({
          mutate: async input => onSuccess(await mutationFn(input)),
        }),
      }
      return require(name)
    },
  })
  vm.runInContext(compile(read('admin/pages/BookingClosuresPage.tsx')), context)
  function find(node, predicate) {
    if (!React.isValidElement(node)) return
    if (predicate(node)) return node
    for (const child of React.Children.toArray(node.props.children)) {
      const result = find(child, predicate)
      if (result) return result
    }
  }
  const render = () => {
    cursor = 0
    return context.exports.default()
  }
  const control = label => find(render(), node =>
    node.type === 'label' && React.Children.toArray(node.props.children).includes(label),
  ).props.children.find(React.isValidElement)
  const change = (label, value) => control(label).props.onChange({ target: { value } })

  const initial = renderToStaticMarkup(render())
  assert.match(initial, /已成立的訂單不受影響/)
  assert.match(initial, /此租戶已暫停套用停收規則/)
  assert.match(initial, /目前沒有停收規則/)
  change('停收範圍', 'both')
  change('雪場', '10')
  change('課程模板', '20')
  change('日期', '2027-01-20')
  change('停收時段', 'session')
  change('課程時段', '30')
  change('內部原因（選填）', ' 內部備註 ')
  await find(render(), node => node.type === 'form').props.onSubmit({ preventDefault() {} })
  assert.equal(JSON.stringify(requests[0]), JSON.stringify({
    resort: 10, course_template: 20, date_from: '2027-01-20', date_to: '2027-01-20',
    start_time: '09:00:00', end_time: '13:00:00', reason: '內部備註',
  }))
  const saved = renderToStaticMarkup(render())
  assert.match(saved, /測試雪場／私人半日/)
  assert.match(saved, /09:00–13:00/)
  assert.match(saved, /已被既有停收規則涵蓋/)
  await find(render(), node => node.type === 'button' && node.props.children === '刪除').props.onClick()
  assert.equal(requests[1], 40)
  assert.match(renderToStaticMarkup(render()), /停收規則已刪除/)
  assert.equal(invalidated.length, 2)
}

function testPublicPicker() {
  const source = read('pages/BookingFlowPage.tsx')
  const usable = source.match(/^const isUsableSession = .+$/m)[0]
  const cards = source.match(/\{sessions\.map\(\(s: any\) => \([\s\S]*?<\/button>\s*\)\)\}/)[0]
  const calls = []
  const context = vm.createContext({
    React, exports: {}, t: value => value, state: {},
    actions: { setSelectedTimeSlot: id => calls.push(id) },
    selectedTemplateInfo: { shared_class_enabled: true },
    sessions: [
      { id: 1, start_time: '09:00', end_time: '13:00', is_closed: true },
      { id: 2, start_time: '14:00', end_time: '17:00', is_full: true },
      { id: 3, start_time: '17:00', end_time: '20:00' },
    ],
  })
  vm.runInContext(compile(`${usable}\nexports.cards = <div>${cards}</div>`), context)
  const buttons = context.exports.cards.props.children
  assert.equal(buttons[0].props.disabled, true)
  assert.equal(buttons[1].props.disabled, true)
  assert.equal(buttons[2].props.disabled, false)
  assert.match(renderToStaticMarkup(buttons[0]), /已暫停接單/)
  assert.doesNotMatch(renderToStaticMarkup(buttons[0]), /新班/)
  buttons.forEach(button => button.props.onClick())
  assert.deepEqual(calls, [3])
}

testConsole().then(testPublicPicker).catch(error => {
  console.error(error)
  process.exitCode = 1
})
