const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const frontend = path.resolve(__dirname, '../snowland-frontend')
const ts = Module.createRequire(path.join(frontend, 'package.json'))('typescript')
const source = fs.readFileSync(path.join(frontend, 'src/utils/payrollDates.ts'), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const moduleResult = { exports: {} }
new Function('exports', 'module', compiled)(moduleResult.exports, moduleResult)
const originalTimezone = process.env.TZ
let count = 0
try {
  for (const zone of ['Asia/Taipei', 'Asia/Tokyo', 'UTC', 'America/Los_Angeles']) {
    process.env.TZ = zone
    for (const [year, month, last] of [[2026, 1, 31], [2026, 2, 28], [2028, 2, 29], [2026, 10, 31], [2026, 12, 31]]) {
      const prefix = `${year}-${String(month).padStart(2, '0')}`
      assert.deepEqual(moduleResult.exports.payrollMonthRange(new Date(year, month - 1, 17)), { first: prefix+'-01', last: prefix+'-'+last })
      count++
    }
  }
} finally {
  if (originalTimezone === undefined) delete process.env.TZ
  else process.env.TZ = originalTimezone
}
console.log(`Payroll local month dates: ${count} timezone/month boundaries passed`)
