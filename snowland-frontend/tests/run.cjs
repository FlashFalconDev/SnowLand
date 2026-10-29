const {readdirSync} = require('node:fs')
const {join} = require('node:path')
const {spawnSync} = require('node:child_process')

const tests = readdirSync(__dirname).filter(name => /^test-.*\.cjs$/.test(name)).sort()
let failed = 0
for (const test of tests) {
  const result = spawnSync(process.execPath, [join(__dirname, test)], {encoding: 'utf8'})
  if (result.status !== 0) {
    failed++
    process.stderr.write(`FAIL ${test}\n${result.error || ''}${result.stdout || ''}${result.stderr || ''}`)
  } else {
    process.stdout.write(`PASS ${test}\n`)
  }
}
console.log(`${tests.length - failed}/${tests.length} frontend test files passed`)
process.exitCode = failed ? 1 : 0
