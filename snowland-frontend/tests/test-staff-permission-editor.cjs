const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const ts = require('typescript')
const { renderToStaticMarkup } = require('react-dom/server')

const source = fs.readFileSync(path.join(__dirname, '../src/admin/pages/StaffPermissionsPage.tsx'), 'utf8')
const compiled = ts.transpileModule(source + '\nexport { EditPermissionModal }', {
  compilerOptions: { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText
const positions = [{ id: 0, name: '教練', built_in: true }, { id: 12, name: '校區主管' }, { id: 15, name: '網頁人員' }]
const staff = { id: 91, name: 'QA 員工', is_superuser: false, is_manager: true, has_coach_record: true, position_ids: [0, 12] }

function setup(canManagePlatform, target = staff, platformMode = false) {
  let stateIndex = 0
  let submit
  let payload
  const exports = {}
  const mocks = {
    react: { ...React, useState(value) {
      stateIndex++
      return [stateIndex === 2 ? platformMode : stateIndex === 3 && platformMode ? true : value, () => {}]
    } },
    'react-router-dom': {},
    'lucide-react': new Proxy({}, { get: () => () => null }),
    '../context': { useNotification: () => ({}) },
    '../permissions': {},
    '../consoleNavigation': {},
    '../api/auth': {},
    '../hooks/useAdminDialog': { useAdminDialog() {} },
    '../api/campuses': {},
    '../api/extras': { async updateCustomerPermission(id, data) { payload = data } },
    '@tanstack/react-query': {
      useQuery: ({ queryKey }) => ({ data: queryKey[1] === 'me' ? { user: { is_superuser: canManagePlatform } } : positions }),
      useQueryClient: () => ({}),
      useMutation: options => { submit = options.mutationFn; return {} },
    },
  }
  vm.runInNewContext(compiled, { React, exports, require: name => mocks[name] })
  const tree = exports.EditPermissionModal({ staff: target, onClose() {} })
  return { html: renderToStaticMarkup(tree), submit: async () => { await submit(); return JSON.parse(JSON.stringify(payload)) } }
}

;(async () => {
  const normal = setup(false)
  assert.deepEqual(await normal.submit(), { position_ids: [0, 12] })
  assert.match(normal.html, /教練.*校區主管.*網頁人員/)
  assert.doesNotMatch(normal.html, /最大管理員設定|可查看校區|可使用的側欄分頁/)
  const protectedTarget = setup(false, { ...staff, is_superuser: true })
  assert.match(protectedTarget.html, /disabled=""[^>]*>儲存/)
  const platform = setup(true, staff, true)
  assert.match(platform.html, /最大管理員設定/)
  assert.deepEqual(await platform.submit(), { is_superuser: true })
  console.log('PASS employee editor submits positions only, and maximum administrator uses a separate action')
})().catch(error => { console.error(error); process.exit(1) })
