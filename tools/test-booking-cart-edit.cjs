const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const frontend = path.resolve(__dirname, '../snowland-frontend')
const localRequire = Module.createRequire(path.join(frontend, 'package.json'))
const ts = localRequire('typescript')
const values = new Map()
global.localStorage = {
  getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value),
  removeItem: key => values.delete(key),
}
const filename = path.join(frontend, 'src/store/bookingStore.ts')
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText
const loaded = new Module(filename, module)
loaded.filename = filename
loaded.paths = Module._nodeModulePaths(path.dirname(filename))
loaded._compile(compiled, filename)
const store = loaded.exports.useBookingStore
const original = { id: 'original', courses: [{ date: '2026-11-30', price: 100 }], totalPrice: 100 }
const other = { id: 'other', courses: [{ date: '2026-12-01', price: 200 }], totalPrice: 200 }
const updated = { id: 'draft', courses: [{ date: '2026-12-02', price: 300 }], totalPrice: 300 }
store.setState({ cart: [original, other], currentReservationGroup: updated })
assert.deepEqual(store.getState().cart, [original, other], 'draft must not change the cart')
store.getState().finishCurrentGroupAndAddToCart('original')
assert.deepEqual(store.getState().cart, [{ ...updated, id: 'original' }, other], 'replace only after completion')
assert.equal(store.getState().currentReservationGroup, null)
store.setState({ currentReservationGroup: updated })
store.getState().finishCurrentGroupAndAddToCart('missing')
assert.equal(store.getState().cart.length, 2, 'missing edit target must not append a duplicate')
store.setState({ currentReservationGroup: { ...updated, courses: [] } })
store.getState().finishCurrentGroupAndAddToCart('original')
assert.equal(store.getState().cart[0].totalPrice, 300, 'incomplete draft must not overwrite')
store.setState({ currentReservationGroup: { ...updated, id: 'new' } })
store.getState().finishCurrentGroupAndAddToCart()
assert.equal(store.getState().cart.length, 3, 'normal new group still appends')
console.log('PASS: preserve draft, replace exact group, retain other group, reject missing/incomplete edit, append new group')
const reference={reservationId:42,peopleCount:2,learnerCount:2}
store.setState({cart:[{...original,peopleCount:2,rebookSource:reference}],currentReservationGroup:{...updated,peopleCount:2}})
store.getState().finishCurrentGroupAndAddToCart('original')
assert.deepEqual(store.getState().cart[0].rebookSource,reference,'same learner count keeps authorized source reference')
store.setState({currentReservationGroup:{...updated,peopleCount:1}})
store.getState().finishCurrentGroupAndAddToCart('original')
assert.equal(store.getState().cart[0].rebookSource,undefined,'changed count must not guess which learners remain')
assert.equal(store.getState().cart[0].rebookLearnersReset,true)
console.log('PASS: same-count rebook keeps reference; changed count drops reference and shows refill notice')
store.getState().startNewReservationGroup('photo')
assert.equal(store.getState().currentReservationGroup.serviceType, 'photo', '服務類型不可因自訂名稱遺失')
store.getState().addCourseToCurrentGroup({ date: '2026-11-01', price: 15123 })
store.getState().finishCurrentGroupAndAddToCart()
assert.equal(store.getState().cart.at(-1).serviceType, 'photo')
assert.equal(JSON.parse(values.get('booking-storage')).state.cart.at(-1).serviceType, 'photo', '重新載入也須保留攝影類型')
