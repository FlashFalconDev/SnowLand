const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')

const source = fs.readFileSync(path.join(__dirname, '../src/admin/staffRoles.ts'), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText
const result = { exports: {} }
new Function('exports', 'module', compiled)(result.exports, result)
const { getSidebarRoleLabel } = result.exports

const cases = [
  [{ is_superuser: true, is_manager: true, role: 'hq_admin' }, '最大管理員'],
  [{ is_manager: true, role: 'assistant' }, '行政小幫手'],
  [{ is_coach: true, role: 'coach' }, '教練'],
  [{ is_manager: true, role: 'campus_manager', is_coach: true }, '校區主管・教練'],
  [{ is_manager: true, role: '' }, '一般後台人員'],
  [{ is_superuser: true, is_coach: true }, '最大管理員・教練'],
  [{ is_manager: true, role: 'legacy' }, '一般後台人員'],
  [{ is_manager: false, role: 'legacy' }, '尚未授權'],
  [{ is_manager: false, role: 'campus_manager', is_coach: true }, '教練'],
  [null, '尚未授權'],
]

for (const [user, expected] of cases) {
  assert.equal(getSidebarRoleLabel(user), expected, JSON.stringify(user))
}
console.log(`PASS ${cases.length} sidebar role label cases`)
