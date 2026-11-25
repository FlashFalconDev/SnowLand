const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const {renderToStaticMarkup} = require('react-dom/server')
const ts = require('typescript')

const source = readFileSync(path.join(__dirname, '../src/pages/site/MembershipPage.jsx'), 'utf8')
const components = source.slice(source.indexOf('function PreCourseForm('), source.indexOf('function MissingStudents('))
const context = vm.createContext({
  React, useSiteLocale: require('./helpers/site-locale-harness.cjs')(React).useSiteLocale,
  ageOptions: ['25-35y'], ageLabel: value => value,
  birthDateStatus: () => ({age: 28, error: ''}),
  WaiverSignaturePad: () => React.createElement('button', {type: 'button'}, 'QA 手寫簽名板'),
})
vm.runInContext(ts.transpileModule(components, {
  fileName: 'MembershipPage.jsx', compilerOptions: {jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020},
}).outputText, context)

const submission = {
  id: 42, student_number: 1, age_range: '25-35y', insurance_data: {full_name: 'QA 學員'},
  snowboard_skills: [], ski_skills: [], waiver_completed: false,
}
const waiver = {
  title: 'QA 聲明書', body: 'QA 公開聲明書正文', version: 'QA-W1', questions: [
    {key: 'insurance-question', title: 'QA 投保自訂題目', section: 'insurance', kind: 'text'},
  ],
}
const notice = {title: 'QA 保險說明', body: 'QA 公開保險正文\n第二段', version: 'QA-I1', status: 'active', is_draft: false}

function render(insuranceNotice, waiverDocument = waiver) {
  // Open the form through the same click handler used on the member page.
  const states = []
  let cursor = 0
  context.useState = initial => {
    const index = cursor++
    if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial
    return [states[index], next => { states[index] = typeof next === 'function' ? next(states[index]) : next }]
  }
  const props = {form: submission, insuranceNotice, waiverDocument, skillOptions: {}}
  const closed = context.PreCourseForm(props)
  const edit = React.Children.toArray(closed.props.children).flatMap(child =>
    child.type === React.Fragment ? React.Children.toArray(child.props.children) : [child],
  ).find(child => child.type === 'button')
  edit.props.onClick()
  cursor = 0
  return renderToStaticMarkup(context.PreCourseForm(props))
}

const both = render(notice)
assert.ok(both.includes(notice.title))
assert.ok(both.includes(notice.body))
assert.match(both, /QA 公開聲明書正文/)
assert.ok(both.indexOf('QA 公開保險正文') < both.indexOf('QA 公開聲明書正文'))
assert.match(both, /學員姓名（保險用）/)
assert.match(both, /QA 投保自訂題目/)
assert.match(both, /QA 手寫簽名板/)

for (const unpublished of [undefined, {...notice, status: 'draft'}, {...notice, is_draft: true}]) {
  const html = render(unpublished)
  assert.doesNotMatch(html, /QA 保險說明|QA 公開保險正文/)
  assert.match(html, /QA 公開聲明書正文/)
  assert.match(html, /QA 投保自訂題目/)
}

const onlyNotice = render(notice, {title: '', body: '', version: '', questions: []})
assert.match(onlyNotice, /QA 公開保險正文/)
assert.doesNotMatch(onlyNotice, /QA 公開聲明書正文|QA 手寫簽名板/)
console.log('PASS pre-course form displays each public document independently and preserves insurance fields')
