const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const root = path.resolve(__dirname,'..')
const ts = Module.createRequire(path.join(root,'package.json'))('typescript')
const source = fs.readFileSync(path.join(root,'src/utils/payrollLineText.ts'),'utf8')
const compiled = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText
const result = {exports:{}}
new Function('exports','module',compiled)(result.exports,result)
const {payrollDescription,payrollCalculation} = result.exports
assert.equal(payrollDescription('QA snowboard ski photo'),'QA 單板 雙板 攝影')
assert.equal(payrollCalculation({line_type:'course',quantity:'6.00',unit_amount:'1000.00',total_amount:6000},'TWD'),'6.00 小時 × TWD 1,000 = TWD 6,000')
assert.equal(payrollCalculation({line_type:'referral',quantity:'10.00',unit_amount:'10000.00',total_amount:1000},'TWD'),'10.00% × TWD 10,000 = TWD 1,000')
assert.equal(payrollCalculation({line_type:'adjustment',quantity:'1.00',unit_amount:'-100.00',total_amount:-100},'TWD'),'1.00 項 × TWD -100 = TWD -100')
console.log('PASS 4 payroll document text cases: local names, hourly unit, percentage, negative adjustment')
