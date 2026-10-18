const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const frontend = path.resolve(__dirname, '../snowland-frontend')
const ts = Module.createRequire(path.join(frontend, 'package.json'))('typescript')
const source = fs.readFileSync(path.join(frontend, 'src/utils/participantAge.ts'), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const moduleResult = { exports: {} }
new Function('exports', 'module', compiled)(moduleResult.exports, moduleResult)
const check = moduleResult.exports.birthDateStatus
for (const [birth, age] of [['2008-10-17', 17], ['2008-10-16', 18], ['2008-10-15', 18]]) {
  assert.deepEqual(check(birth, '2026-10-16'), { age, error: '' })
}
assert.deepEqual(check('', '2026-10-16'), { age: null, error: '' })
for (const birth of ['2026-10-17', '2026-02-30', 'not-a-date', '20260101']) {
  assert.equal(check(birth, '2026-10-16').age, null)
  assert.ok(check(birth, '2026-10-16').error)
}
assert.ok(check('1990-01-01', '').error)
assert.equal(check('2008-02-29', '2026-03-01').age, 18)
console.log('Participant birth date: 10 boundary/invalid cases passed')
