const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {join} = require('node:path')
const vm = require('node:vm')
const React = require('react')
const {renderToStaticMarkup} = require('react-dom/server')
const ts = require('typescript')

const source = name => readFileSync(join(__dirname, '../src/admin', name), 'utf8')
const compile = (code, fileName) => ts.transpileModule(code, {fileName, compilerOptions: {
  jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
}}).outputText
const panelSource = source('pages/OperationsHubPage.tsx')
const panel = panelSource.slice(panelSource.indexOf('type EvaluationSearch'), panelSource.indexOf('function CourseFileUploader('))

function harness({ coachView = false, booking = null } = {}) {
  const state = []
  const formState = []
  const queries = []
  const requests = []
  const row = {id: 21, booking: 7, member_name: '甲學員', course_date: '2026-11-26',
    order_date: '2026-11-27', order_number: 'QA-21', self_assessment: {}, media: []}
  const defaults = {date_field: 'ordered', date_from: '2026-10-29', date_to: '2026-11-27'}
  let response = {list: [row, {...row, id: 22, order_date: '2026-11-26'}], page: 1, total: 12, total_pages: 2, date_filters: defaults}
  let stateIndex = 0
  let activeState = state
  let form = {}
  const client = {get: async (path, config) => {
    requests.push({path, params: config?.params})
    return {data: response}
  }}
  const context = vm.createContext({
    exports: {}, require: () => ({default: client}), React, cardClass: '', inputClass: '',
    FormData: class { get(name) { return form[name] } },
    window: {localStorage: {getItem: () => '5'}},
    useState(initial) {
      const index = stateIndex++
      const values = activeState
      if (values.length <= index) values.push(initial)
      return [values[index], value => { values[index] = value }]
    },
    useQuery: options => {
      if (options.queryKey[1] !== 'evaluations') return {}
      queries.push(options)
      return {data: response}
    },
    keepPreviousData: value => value,
    useQueryClient: () => ({}), useNotification: () => ({}), useMutation: () => ({}),
    useSiteLink: path => `/snowland${path}`, currentClientCode: () => 'snowland', campusScopeKey: () => 'scope',
    useSearchParams: () => [new URLSearchParams(booking ? {booking} : {})],
    Link: ({to, children}) => React.createElement('a', {href: to}, children),
    learningProgressFromText: () => ({}), learningProgressToText: () => '',
    CoachCourseAlbum: () => null, EvaluationLearnerLink: () => null,
    Empty: ({text}) => React.createElement('p', null, text), fetchAssessmentRubric: async () => ({}),
  })
  vm.runInContext(compile(source('api/operations.ts'), 'operations.ts'), context)
  Object.assign(context, context.exports)
  vm.runInContext(compile(panel, 'evaluations.tsx'), context)
  return {
    queries, requests, defaults,
    render() { stateIndex = 0; activeState = state; return context.EvaluationsPanel({coachView}) },
    setResponse(value) { response = {...response, ...value} },
    renderForm(node, values) {
      form = values
      stateIndex = 0
      activeState = formState
      return context.EvaluationFilterForm(node.props)
    },
  }
}

function find(node, predicate) {
  if (!React.isValidElement(node)) return
  if (predicate(node)) return node
  return React.Children.toArray(node.props.children).map(child => find(child, predicate)).find(Boolean)
}

async function main() {
  const app = harness()
  let panel = app.render()
  const html = renderToStaticMarkup(panel)
  assert.match(html, /<h3[^>]*>下單日期 2026-11-27<\/h3>/)
  assert.match(html, /<h3[^>]*>下單日期 2026-11-26<\/h3>/)
  assert.match(html, /下單日期 2026-11-27 · 上課日期 2026-11-26/)
  assert.match(html, /value="2026-10-29"/)
  assert.match(html, /evaluations\?booking=7/)
  const findButton = (tree, text) => find(tree, node => node.type === 'button' && node.props.children === text)
  findButton(panel, '下一頁').props.onClick()
  app.setResponse({page: 2})
  panel = app.render()
  await app.queries.at(-1).queryFn()
  assert.equal(app.requests.at(-1).params.page, 2)

  const form = find(panel, node => node.type.name === 'EvaluationFilterForm')
  let formTree = app.renderForm(form, {date_field: 'lesson', search: ' 甲學員 '})
  find(formTree, node => node.type === 'input' && node.props.type === 'date').props.onChange({target: {value: '2026-11-20'}})
  formTree = app.renderForm(form, {date_field: 'lesson', search: ' 甲學員 '})
  formTree.props.onSubmit({preventDefault() {}, currentTarget: {}})
  app.setResponse({page: 1, date_filters: {...app.defaults, date_field: 'lesson', date_from: '2026-11-20'}})
  panel = app.render()
  await app.queries.at(-1).queryFn()
  assert.equal(app.requests.at(-1).path, '/evaluations/')
  assert.equal(JSON.stringify(app.requests.at(-1).params), JSON.stringify({
    date_field: 'lesson', date_from: '2026-11-20', date_to: '2026-11-27', search: '甲學員', page: 1,
  }))
  assert.match(renderToStaticMarkup(panel), /<h3[^>]*>上課日期 2026-11-26<\/h3>/)
  assert.equal(app.queries.at(-1).queryKey[3], '5')

  const booked = harness({booking: '7'})
  const bookingPage = booked.render()
  assert.equal(find(bookingPage, node => node.type.name === 'EvaluationFilterForm'), undefined)
  await booked.queries.at(-1).queryFn()
  assert.equal(JSON.stringify(booked.requests.at(-1).params), '{"booking":"7","page":1}')

  const coach = harness({coachView: true})
  coach.setResponse({date_filters: null, page: undefined})
  assert.match(renderToStaticMarkup(coach.render()), /依上課日期找評量/)
  await coach.queries.at(-1).queryFn()
  assert.equal(coach.requests.at(-1).path, '/coach/evaluations/')
}

main().catch(error => { console.error(error); process.exitCode = 1 })
