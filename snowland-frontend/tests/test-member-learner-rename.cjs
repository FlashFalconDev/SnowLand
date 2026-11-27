const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { QueryClient } = require('@tanstack/react-query')
const ts = require('typescript')
const loadSiteLocale = require('./helpers/site-locale-harness.cjs')

const client = 'qa-school'
const account = 'qa@example.test'
const queryKey = ['learner-profiles', client, account]
const cache = new QueryClient()
const editable = { id: 11, name: '可修改的姓名', can_rename: true }
const locked = { id: 12, name: '已連結的姓名', can_rename: false }
const legacy = { id: 13, name: '舊版的姓名' }
cache.setQueryData(queryKey, [editable, locked, legacy])

let locale = loadSiteLocale(React)
let mutations = []
let saved = false
const renamed = { ...editable, name: '修改後姓名' }
const mocks = {
  'react': React,
  '@tanstack/react-query': {
    useQuery: ({ queryKey }) => ({ isSuccess: true, data: cache.getQueryData(queryKey) }),
    useQueryClient: () => cache,
    useMutation: options => {
      mutations.push(options)
      return {}
    },
  },
  '@/api/axios': {},
  '@/utils/tenant': { currentClientCode: () => client },
  '@/contexts/SiteLocale': { useSiteLocale: () => locale.useSiteLocale() },
}

function componentModule(file) {
  const source = fs.readFileSync(path.join(__dirname, '..', file), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    fileName: file, compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS },
  })
  const exports = {}
  vm.runInNewContext(outputText, { React, exports, require: name => {
    assert.ok(name in mocks, `Unexpected dependency: ${name}`)
    return mocks[name]
  } })
  return exports
}

async function run() {
  const selection = componentModule('src/components/booking/LearnerSelection.tsx')
  mocks['../booking/LearnerSelection'] = selection
  const { ManageLearnerProfiles } = componentModule('src/components/site/MemberLearningTools.jsx')
  const renderManager = () => renderToStaticMarkup(React.createElement(ManageLearnerProfiles, { account, onSaved: () => { saved = true } }))
  const html = renderManager()
  const rows = html.match(/<li\b[^>]*>.*?<\/li>/g)
  assert.equal(rows.length, 3)
  assert.match(rows[0], /可修改的姓名.*修改姓名/)
  assert.match(rows[1], /已連結的姓名/)
  assert.match(rows[2], /舊版的姓名/)
  assert.doesNotMatch(rows[1] + rows[2], /修改姓名/)
  assert.match(html, /歷史頁面會顯示新姓名。保險用姓名與已簽署資料不會改變。/)
  assert.match(html, /新增學員檔案/)

  for (const language of ['en', 'ja']) {
    locale = loadSiteLocale(React, language)
    const localizedHtml = renderManager()
    assert.match(localizedHtml, language === 'en' ? /Edit name/ : /名前を変更/)
    assert.match(localizedHtml, language === 'en' ? /Past records.*insurance and signed documents/ : /過去の記録.*保険用の氏名と署名済みの書類/)
    assert.doesNotMatch(localizedHtml, /修改姓名|歷史頁面會顯示新姓名/)
  }

  locale = loadSiteLocale(React)
  // Render a single enabled row so its mutation callbacks are the ones captured.
  cache.setQueryData(queryKey, [editable])
  mutations = []
  renderManager()
  const [renameMutation] = mutations
  const checkout = () => renderToStaticMarkup(React.createElement(selection.CheckoutLearners, {
    cart: [{ id: 'qa-cart', peopleCount: 1, resortName: 'QA 雪場' }], client, account, choices: {}, onChange() {},
  }))
  assert.match(checkout(), /<option value="11">可修改的姓名<\/option>/)
  await renameMutation.onSuccess(renamed)
  assert.match(checkout(), /<option value="11">修改後姓名<\/option>/)
  assert.doesNotMatch(checkout(), /可修改的姓名/)
  assert.ok(saved, 'The member center refreshes its history data after saving')
  assert.equal(cache.getQueryState(queryKey).isInvalidated, true)
  console.log('PASS learner profile list, rename permission, localized explanation, and shared checkout cache')
}

run().catch(error => { console.error(error); process.exitCode = 1 })
