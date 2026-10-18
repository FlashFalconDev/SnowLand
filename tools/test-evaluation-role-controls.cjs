const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const vm = require('node:vm')
const root = path.resolve(__dirname, '../snowland-frontend')
const localRequire = Module.createRequire(path.join(root, 'package.json'))
const ts = localRequire('typescript')
const React = localRequire('react')
const { renderToStaticMarkup } = localRequire('react-dom/server')
const compile = (source, fileName) => ts.transpileModule(source, { fileName, compilerOptions: {
  jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText
const progress = { exports: {} }
new Function('exports', compile(fs.readFileSync(path.join(root, 'src/utils/learningProgress.ts'), 'utf8'), 'progress.ts'))(progress.exports)
const source = fs.readFileSync(path.join(root, 'src/admin/pages/OperationsHubPage.tsx'), 'utf8')
const card = source.slice(source.indexOf('function EvaluationCard('), source.indexOf('function CourseFileUploader('))
const row = { id: 1, member_name: 'QA', coach_name: 'QA教練', course_date: '2026-10-17', order_number: 'QA-only',
  coach_notes: '原評語', self_assessment: {}, learning_progress: { turn: '持續練習' }, trail_names: ['QA雪道'], media: [] }

function render(canEdit, editing, mediaUrl = '') {
  let index = 0, mutation
  const calls = []
  const context = vm.createContext({ React, Date, Number, URL, ...progress.exports,
    PRIMARY: '#8b5cf6', inputClass: '',
    useQueryClient: () => ({ invalidateQueries() {} }), useNotification: () => ({ success() {}, error() {} }),
    useState: initial => { const n = index++; return [n === 0 ? editing : n === 5 ? mediaUrl : initial, () => {}] },
    useMutation: options => { mutation = options; return { isPending: false, mutate() {} } },
    updateEvaluation: async (...args) => calls.push(args), Save: () => null, Loader2: () => null,
    Field: ({ label, children }) => React.createElement('label', null, label, children),
    CourseFileUploader: () => React.createElement('div', null, '可選檔上傳'),
  })
  vm.runInContext(compile(card, 'evaluation.tsx'), context)
  const html = renderToStaticMarkup(React.createElement(context.EvaluationCard, { row: { ...row, can_edit_assessment: canEdit } }))
  return { html, calls, save: () => mutation.mutationFn() }
}

async function main() {
  assert.match(render(false, false).html, /管理課程附件/)
  const readonly = render(false, true, 'https://example.test/qa.png')
  assert.doesNotMatch(readonly.html, /<textarea|給學員的教練評語|儲存並標示完成/)
  assert.match(readonly.html, /原評語/)
  assert.match(readonly.html, /持續練習/)
  assert.match(readonly.html, /可選檔上傳/)
  assert.match(readonly.html, /加入附件網址/)
  await readonly.save()
  assert.deepEqual(Object.keys(readonly.calls[0][1]), ['new_media'])
  assert.equal(readonly.calls[0][1].new_media.is_public, false)
  const editable = render(true, true)
  assert.match(editable.html, /<textarea/)
  assert.match(editable.html, /儲存並標示完成/)
  await editable.save()
  assert.equal(editable.calls[0][1].coach_notes, '原評語')
  assert.ok(editable.calls[0][1].completed_at)
  console.log('PASS actual EvaluationCard: readonly/editor controls, private upload kept, media-only payload and coach payload')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
