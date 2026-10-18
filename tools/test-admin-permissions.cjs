const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const frontend = path.resolve(__dirname, '../snowland-frontend')
const ts = Module.createRequire(path.join(frontend, 'package.json'))('typescript')
const source = fs.readFileSync(path.join(frontend, 'src/admin/permissions.ts'), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const result = { exports: {} }
new Function('exports', 'module', compiled)(result.exports, result)
const allowed = result.exports.hasAdminPermission
assert.equal(allowed(null, 'notifications'), false)
assert.equal(allowed({ is_manager: false, permissions: ['notifications'] }, 'notifications'), false)
assert.equal(allowed({ is_coach: true, is_manager: false, permissions: [] }, 'notifications'), false)
assert.equal(allowed({ is_manager: true, permissions: ['orders'] }, 'notifications'), false)
assert.equal(allowed({ is_manager: true, permissions: ['orders'] }, 'orders'), true)
assert.equal(allowed({ is_manager: true, permissions: ['notifications'] }, 'notifications'), true)
assert.equal(allowed({ is_superuser: true }, 'notifications'), true)
console.log('PASS 7 admin permission cases: anonymous/member/coach/limited manager/allowed manager/superuser')
