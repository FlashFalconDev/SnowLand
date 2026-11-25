const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { createRequire } = require('node:module')
const vm = require('node:vm')

const frontend = path.resolve(__dirname, '..')
const requireFrontend = createRequire(path.join(frontend, 'package.json'))
const React = requireFrontend('react')
const ts = requireFrontend('typescript')
const { renderToStaticMarkup } = requireFrontend('react-dom/server')
const source = fs.readFileSync(path.join(frontend, 'src/admin/components/LearnerCourseTools.tsx'), 'utf8')
let learners
const imports = {
  react: { ...React, useState: () => [true, () => {}] },
  '@tanstack/react-query': { useQuery: () => ({ isSuccess: true, data: learners }) },
  '@/utils/tenant': { currentClientCode: () => 'qa' },
  '../api/axios': {},
}
const context = vm.createContext({ React, exports: {}, require: name => imports[name] })
const compiled = ts.transpileModule(source, {
  compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText
vm.runInContext(compiled, context)
const { CoachLearnerHistory } = context.exports

const record = { date: '2026-11-01', course_name: '過往課程樣本', technical_assessment: [] }
function render(summary) {
  learners = [{ id: 1, name: '學員樣本', pre_course_summary: summary, records: [record] }]
  return renderToStaticMarkup(React.createElement(CoachLearnerHistory, { reservationId: 1 }))
}

for (const [status, statusLabel] of [['filled', '已填'], ['incomplete', '未完成'], ['empty', '未填']]) {
  const filled = status === 'filled'
  const html = render({
    status,
    status_label: statusLabel,
    empty_label: '此欄尚未作答',
    items: [
      { key: 'custom-recent', label: '租戶的經驗標籤', value: filled ? '沒有經驗' : null, filled },
      { key: 'custom-status', label: '租戶的狀態標籤', value: statusLabel, filled: true },
    ],
  })
  assert.ok(html.includes(`<dd>${statusLabel}</dd>`))
  assert.ok(html.includes(`<dd>${filled ? '沒有經驗' : '此欄尚未作答'}</dd>`))
  const order = ['學員樣本', '租戶的經驗標籤', '租戶的狀態標籤', '過往課程樣本']
  let previous = -1
  for (const text of order) {
    const index = html.indexOf(text)
    assert.ok(index > previous, `Expected learner history to render in server-provided order: ${text}`)
    previous = index
  }
}

assert.ok(!render({ status: 'filled', status_label: '已填', items: [] }).includes('課前自評摘要'))
assert.ok(render(undefined).includes('過往課程樣本'))
console.log('PASS coach pre-course summary: statuses, server field order, hidden fields, and existing history')
