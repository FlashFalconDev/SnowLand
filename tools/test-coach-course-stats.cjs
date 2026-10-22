const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const frontend = path.resolve(__dirname, '../snowland-frontend')
const ts = Module.createRequire(path.join(frontend, 'package.json'))('typescript')
const source = fs.readFileSync(path.join(frontend, 'src/utils/coachCourseStats.ts'), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const result = { exports: {} }
new Function('exports', 'module', compiled)(result.exports, result)
const stats = result.exports.calculateCoachCourseStats
const lesson = (bookingId, sharedId = null, changes = {}) => ({
  shared_class_id: sharedId, course_category: '單板 Snowboard', course_type: '一般課程',
  is_preferred_coach: false,
  bookings: [{ id: bookingId, date: '2026-12-21', start_time: '09:00:00', end_time: '13:00:00', ...changes }],
})
assert.deepEqual(stats([lesson(1, 13), lesson(2, 13), lesson(3, 13)], '2026-12'),
  { totalHours: 4, snowboardHours: 4, skiHours: 0, specifiedHours: 0, lessons: 1 })
assert.equal(stats([lesson(1), lesson(2), lesson(3)], '2026-12').totalHours, 12)
assert.equal(stats([lesson(1, 13), lesson(2, 14)], '2026-12').lessons, 2)
assert.equal(stats([lesson(1, 13), lesson(2, 13, { start_time: '13:00', end_time: '17:00' })], '2026-12').totalHours, 8)
assert.equal(stats([lesson(1, 13), lesson(2, 13, { date: '2026-12-22' })], '2026-12').totalHours, 8)
assert.equal(stats([lesson(1, 13, { date: '2026-11-21' })], '2026-12').lessons, 0)
assert.equal(stats([lesson(1), lesson(1)], '2026-12').lessons, 1)
assert.equal(stats([{ ...lesson(1), is_preferred_coach: true, course_category: '雙板 Ski' }], '2026-12').specifiedHours, 4)
assert.equal(stats([{ ...lesson(1), course_category: '雙板 Ski' }], '2026-12').skiHours, 4)
assert.equal(stats([], '2026-12').totalHours, 0)
assert.equal(stats([{ ...lesson(1), course_category: '成人課程', course_type: '單板初級' }], '2026-12').snowboardHours, 4)
assert.equal(stats([{ ...lesson(1), course_category: '兒童課程', course_type: '雙板初級' }], '2026-12').skiHours, 4)
assert.equal(stats([{ ...lesson(1), course_category: '攝影課程', course_type: '一般攝影' }], '2026-12').skiHours, 0)
console.log('Coach course stats: 13 shared/private/month/discipline cases PASS')
